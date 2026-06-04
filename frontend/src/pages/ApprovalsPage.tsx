import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  CheckCircleIcon,
  XCircleIcon,
  ShieldCheckIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { decisionApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { RiskBadge } from '../components/common/StatusBadge';
import { humanizeLabel } from '../utils/labels';
import type { PendingApproval, RiskLevel, DecisionAction } from '../types';

function formatCurrency(amount: string | number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(typeof amount === 'string' ? parseFloat(amount) : amount);
}

const ACTION_LABELS: Record<DecisionAction, string> = {
  approve: 'Approve',
  return: 'Return',
  reject: 'Reject',
  hold: 'Hold',
  escalate: 'Escalate',
  needs_more_info: 'Needs More Info',
};

function RecommendationBadge({ action }: { action: DecisionAction }) {
  const tone =
    action === 'approve'
      ? 'bg-green-100 text-green-800'
      : action === 'reject'
        ? 'bg-red-100 text-red-800'
        : 'bg-amber-100 text-amber-800';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      Recommends: {ACTION_LABELS[action] ?? action}
    </span>
  );
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();
  const canApprove = hasPermission('check_item', 'approve');
  const [actingId, setActingId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['pending-approvals'],
    queryFn: decisionApi.getPendingApprovals,
    enabled: canApprove,
  });

  const decide = useMutation({
    mutationFn: ({ decisionId, approve }: { decisionId: string; approve: boolean }) =>
      decisionApi.approveDualControl({ decision_id: decisionId, approve }),
    onMutate: ({ decisionId }) => setActingId(decisionId),
    onSuccess: (_res, { approve }) => {
      toast.success(approve ? 'Approval recorded' : 'Sent back to review');
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] });
      queryClient.invalidateQueries({ queryKey: ['queues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats'] });
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Action failed. Please try again.';
      toast.error(detail);
    },
    onSettled: () => setActingId(null),
  });

  const approvals = data ?? [];

  if (!canApprove) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <h1 className="text-lg font-semibold text-amber-900">Dual Control Approvals</h1>
        <p className="mt-2 text-sm text-amber-800">
          You do not have the <code>check_item:approve</code> permission required to act on
          dual-control approvals. Sign in as an approver (e.g. supervisor, administrator or
          system admin) to use this screen.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ShieldCheckIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
            Dual Control Approvals
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Second-level review of decisions that require two-person approval. You cannot approve
            your own recommendations.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowPathIcon className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {/* Loading skeletons */}
      {isLoading && (
        <div className="space-y-3" aria-busy="true" aria-label="Loading pending approvals">
          {[0, 1, 2].map((i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-5">
              <div className="h-4 w-1/3 rounded bg-gray-200" />
              <div className="mt-3 h-3 w-1/2 rounded bg-gray-100" />
              <div className="mt-2 h-3 w-1/4 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      )}

      {/* Error + retry */}
      {isError && !isLoading && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">Could not load pending approvals.</p>
          <button
            onClick={() => refetch()}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && approvals.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-10 text-center">
          <CheckCircleIcon className="mx-auto h-10 w-10 text-green-500" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-semibold text-gray-900">All caught up</h3>
          <p className="mt-1 text-sm text-gray-600">
            There are no decisions awaiting dual-control approval right now.
          </p>
        </div>
      )}

      {/* Approval list */}
      {!isLoading && !isError && approvals.length > 0 && (
        <div className="space-y-3">
          {approvals.map((a: PendingApproval) => {
            const isActing = actingId === a.decision_id && decide.isPending;
            return (
              <div
                key={a.decision_id}
                className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/review/${a.check_item_id}`}
                        className="text-sm font-semibold text-primary-700 hover:underline"
                      >
                        Check #{a.check_number ?? '—'}
                      </Link>
                      {a.risk_level && <RiskBadge level={a.risk_level as RiskLevel} />}
                      <RecommendationBadge action={a.recommended_action} />
                    </div>
                    <div className="mt-1 text-lg font-bold text-gray-900">
                      {formatCurrency(a.amount)}
                    </div>
                    <dl className="mt-1 text-sm text-gray-600">
                      <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                        <span>
                          Payee: <span className="text-gray-900">{a.payee_name ?? '—'}</span>
                        </span>
                        <span>
                          Account:{' '}
                          <span className="text-gray-900">{a.account_number_masked ?? '—'}</span>
                        </span>
                        <span>
                          Recommended by:{' '}
                          <span className="text-gray-900">{a.recommended_by_username ?? '—'}</span>
                        </span>
                      </div>
                      {a.dual_control_reason && (
                        <div className="mt-0.5">
                          Reason:{' '}
                          <span className="text-gray-900">{humanizeLabel(a.dual_control_reason)}</span>
                        </div>
                      )}
                    </dl>
                  </div>

                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={() =>
                        decide.mutate({ decisionId: a.decision_id, approve: false })
                      }
                      disabled={isActing}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      <XCircleIcon className="h-4 w-4" aria-hidden="true" />
                      Send back
                    </button>
                    <button
                      onClick={() =>
                        decide.mutate({ decisionId: a.decision_id, approve: true })
                      }
                      disabled={isActing}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                    >
                      <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                      {isActing ? 'Working…' : 'Approve'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
