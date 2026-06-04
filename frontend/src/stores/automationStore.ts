import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AutomationMode = 'off' | 'shadow' | 'active';
export type AutoClearTier = 'low' | 'medium';

/**
 * Client-side configuration for the decision-automation (straight-through
 * processing) demo. Nothing here mutates real data — it drives a live
 * simulation computed from existing queue/archive items so the policy and its
 * value can be explored interactively.
 */
interface AutomationState {
  mode: AutomationMode;
  /** Auto-clear risk tiers up to and including this one. */
  autoClearMaxTier: AutoClearTier;
  /** Auto-clear only when the item amount is at or below this cap. */
  amountCap: number;

  // ROI assumptions (editable, clearly-labeled estimates)
  annualVolume: number;
  avgHandleTimeSec: number;
  loadedCostPerMin: number;
  annualFraudPrevented: number;

  setMode: (mode: AutomationMode) => void;
  setAutoClearMaxTier: (tier: AutoClearTier) => void;
  setAmountCap: (cap: number) => void;
  setAssumption: (
    key: 'annualVolume' | 'avgHandleTimeSec' | 'loadedCostPerMin' | 'annualFraudPrevented',
    value: number
  ) => void;
  reset: () => void;
}

const DEFAULTS = {
  mode: 'shadow' as AutomationMode,
  autoClearMaxTier: 'low' as AutoClearTier,
  amountCap: 2500,
  annualVolume: 1_000_000,
  avgHandleTimeSec: 90,
  loadedCostPerMin: 0.75,
  annualFraudPrevented: 850_000,
};

export const useAutomationStore = create<AutomationState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setMode: (mode) => set({ mode }),
      setAutoClearMaxTier: (autoClearMaxTier) => set({ autoClearMaxTier }),
      setAmountCap: (amountCap) => set({ amountCap: Math.max(0, amountCap) }),
      setAssumption: (key, value) => set({ [key]: Math.max(0, value) } as Partial<AutomationState>),
      reset: () => set(DEFAULTS),
    }),
    { name: 'automation-config' }
  )
);
