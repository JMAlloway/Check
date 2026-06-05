import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { checkApi } from '../services/api';
import type { CheckItemListItem } from '../types';
import { useAutomationStore, type AutoClearTier } from '../stores/automationStore';

const TIER_RANK: Record<string, number> = { low: 0, medium: 1, high: 2, critical: 3 };

const OPEN_STATUSES = ['new', 'in_review', 'escalated', 'pending_approval', 'pending_dual_control'];
const DECIDED_STATUSES = ['approved', 'rejected', 'returned'];

const SAMPLE_SIZE = 500; // backend cap; covers the full open queue + ample decided history

interface AutoClearConfig {
  autoClearMaxTier: AutoClearTier;
  amountCap: number;
}

/**
 * The straight-through eligibility rule. Dual control is a hard guardrail (a
 * genuine two-person control). AI detection flags are advisory and are already
 * reflected in the item's risk tier, so they don't unconditionally block —
 * consistent with how the review screen treats them.
 */
export function autoClears(item: CheckItemListItem, cfg: AutoClearConfig): boolean {
  if (item.requires_dual_control) return false;
  if (TIER_RANK[item.risk_level] > TIER_RANK[cfg.autoClearMaxTier]) return false;
  if (item.amount > cfg.amountCap) return false;
  return true;
}

export interface RoiResult {
  laborSavedPerYear: number;
  hoursFreedPerYear: number;
  ftesFreed: number;
  fraudPreventedPerYear: number;
  totalAnnualValue: number;
}

export function computeRoi(
  stpRate: number,
  cfg: {
    annualVolume: number;
    avgHandleTimeSec: number;
    loadedCostPerMin: number;
    annualFraudPrevented: number;
  }
): RoiResult {
  const autoCleared = cfg.annualVolume * stpRate;
  const laborSavedPerYear = autoCleared * (cfg.avgHandleTimeSec / 60) * cfg.loadedCostPerMin;
  const hoursFreedPerYear = (autoCleared * cfg.avgHandleTimeSec) / 3600;
  const ftesFreed = hoursFreedPerYear / 2080; // 2080 paid hours/yr
  return {
    laborSavedPerYear,
    hoursFreedPerYear,
    ftesFreed,
    fraudPreventedPerYear: cfg.annualFraudPrevented,
    totalAnnualValue: laborSavedPerYear + cfg.annualFraudPrevented,
  };
}

export interface SimulationResult {
  isLoading: boolean;
  // Live queue disposition
  openTotal: number;
  autoClearCount: number;
  reviewCount: number;
  guardrailHeld: number;
  stpRate: number; // 0..1
  // Shadow validation against historical human decisions
  shadowConsidered: number; // items the rule would have auto-cleared
  shadowAgreements: number; // human also approved
  shadowMisses: number; // human returned/rejected (would-be wrong auto-clear)
  shadowMissAmount: number;
  shadowAccuracy: number; // 0..1
  exceptionsCaught: number; // human-rejected/returned that the rule routed to a person
  exceptionsTotal: number;
  // A spot-check sample of items the policy would auto-clear, with what the
  // reviewer actually decided - the basis for ongoing QA / governance.
  qaSample: QaSampleItem[];
}

export interface QaSampleItem {
  id: string;
  externalId: string;
  payee: string;
  amount: number;
  riskLevel: string;
  humanStatus: string; // approved | returned | rejected
  agreed: boolean; // reviewer also approved -> auto-clear would have been correct
}

// QA spot-check sample size. Sized like a real monthly governance sample
// rather than a token handful, so the pass-rate is statistically meaningful.
const QA_SAMPLE_SIZE = 60;

export function useAutomationSimulation(): SimulationResult & { roi: RoiResult } {
  const { autoClearMaxTier, amountCap, annualVolume, avgHandleTimeSec, loadedCostPerMin, annualFraudPrevented } =
    useAutomationStore();

  const openQuery = useQuery({
    queryKey: ['automation-open'],
    queryFn: () => checkApi.getItems({ page_size: SAMPLE_SIZE, status: OPEN_STATUSES }),
    staleTime: 60_000,
  });
  const decidedQuery = useQuery({
    queryKey: ['automation-decided'],
    queryFn: () => checkApi.getItems({ page_size: SAMPLE_SIZE, status: DECIDED_STATUSES }),
    staleTime: 60_000,
  });

  const sim = useMemo<SimulationResult>(() => {
    const open: CheckItemListItem[] = openQuery.data?.items ?? [];
    const decided: CheckItemListItem[] = decidedQuery.data?.items ?? [];
    const cfg = { autoClearMaxTier, amountCap };

    const autoClearCount = open.filter((i) => autoClears(i, cfg)).length;
    const guardrailHeld = open.filter((i) => i.requires_dual_control).length;
    const openTotal = open.length;
    const reviewCount = openTotal - autoClearCount;
    const stpRate = openTotal > 0 ? autoClearCount / openTotal : 0;

    const considered = decided.filter((i) => autoClears(i, cfg));
    const shadowConsidered = considered.length;
    const shadowAgreements = considered.filter((i) => i.status === 'approved').length;
    const missed = considered.filter((i) => i.status === 'rejected' || i.status === 'returned');
    const shadowMisses = missed.length;
    const shadowMissAmount = missed.reduce((s, i) => s + (i.amount || 0), 0);
    const shadowAccuracy = shadowConsidered > 0 ? shadowAgreements / shadowConsidered : 0;

    const trueExceptions = decided.filter((i) => i.status === 'rejected' || i.status === 'returned');
    const exceptionsTotal = trueExceptions.length;
    const exceptionsCaught = trueExceptions.filter((i) => !autoClears(i, cfg)).length;

    // QA spot-check: a stable sample of the auto-clear candidates (every Nth so
    // it spans risk tiers and amounts rather than just the first few).
    const step = Math.max(1, Math.floor(considered.length / QA_SAMPLE_SIZE));
    const qaSample: QaSampleItem[] = considered
      .filter((_, idx) => idx % step === 0)
      .slice(0, QA_SAMPLE_SIZE)
      .map((i) => ({
        id: i.id,
        externalId: i.external_item_id,
        payee: i.payee_name || '—',
        amount: i.amount,
        riskLevel: i.risk_level,
        humanStatus: i.status,
        agreed: i.status === 'approved',
      }));

    return {
      isLoading: openQuery.isLoading || decidedQuery.isLoading,
      openTotal,
      autoClearCount,
      reviewCount,
      guardrailHeld,
      stpRate,
      shadowConsidered,
      shadowAgreements,
      shadowMisses,
      shadowMissAmount,
      shadowAccuracy,
      exceptionsCaught,
      exceptionsTotal,
      qaSample,
    };
  }, [openQuery.data, decidedQuery.data, openQuery.isLoading, decidedQuery.isLoading, autoClearMaxTier, amountCap]);

  const roi = useMemo(
    () => computeRoi(sim.stpRate, { annualVolume, avgHandleTimeSec, loadedCostPerMin, annualFraudPrevented }),
    [sim.stpRate, annualVolume, avgHandleTimeSec, loadedCostPerMin, annualFraudPrevented]
  );

  return { ...sim, roi };
}
