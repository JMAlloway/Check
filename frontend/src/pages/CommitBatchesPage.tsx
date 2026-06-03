import { useQuery } from '@tanstack/react-query';
import { ArrowsRightLeftIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { commitConnectorApi } from '../services/api';
import type { CommitBatchSummary, ConnectorDashboard } from '../types';

const BATCH_STATUS_TONE: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800',
  approved: 'bg-blue-100 text-blue-800',
  generating: 'bg-blue-100 text-blue-800',
  generated: 'bg-blue-100 text-blue-800',
  transmitted: 'bg-indigo-100 text-indigo-800',
  acknowledged: 'bg-green-100 text-green-800',
  partially_processed: 'bg-amber-100 text-amber-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-600',
};

const ACK_TONE: Record<string, string> = {
  accepted: 'text-green-700',
  rejected: 'text-red-700',
  partially_processed: 'text-amber-700',
  pending: 'text-gray-500',
};

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function currency(v: string | number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
    typeof v === 'string' ? parseFloat(v) : v
  );
}

function Metric({
  label,
  value,
  tone = 'text-gray-900',
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p>
    </div>
  );
}

export default function CommitBatchesPage() {
  const dashboardQuery = useQuery<ConnectorDashboard>({
    queryKey: ['commit-dashboard'],
    queryFn: commitConnectorApi.getDashboard,
  });
  const batchesQuery = useQuery<CommitBatchSummary[]>({
    queryKey: ['commit-batches'],
    queryFn: () => commitConnectorApi.getBatches(),
  });

  const d = dashboardQuery.data;
  const batches = batchesQuery.data ?? [];
  const isLoading = dashboardQuery.isLoading || batchesQuery.isLoading;
  const isError = dashboardQuery.isError || batchesQuery.isError;

  const refetchAll = () => {
    dashboardQuery.refetch();
    batchesQuery.refetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ArrowsRightLeftIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
            Commit Connector (Connector B)
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Outbound batch commit of decisions to the core: batch creation, dual-control approval,
            transmission, acknowledgement and reconciliation.
          </p>
        </div>
        <button
          onClick={refetchAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowPathIcon
            className={`h-4 w-4 ${dashboardQuery.isFetching || batchesQuery.isFetching ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          Refresh
        </button>
      </div>

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">Could not load connector data.</p>
          <button
            onClick={refetchAll}
            className="mt-3 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* Dashboard metrics */}
      {d && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <Metric
            label="Pending approval"
            value={d.batches_pending_approval}
            tone={d.batches_pending_approval ? 'text-amber-700' : 'text-gray-900'}
          />
          <Metric label="Awaiting acknowledgement" value={d.batches_awaiting_acknowledgement} />
          <Metric
            label="Past ack deadline"
            value={d.batches_past_ack_deadline}
            tone={d.batches_past_ack_deadline ? 'text-red-700' : 'text-gray-900'}
          />
          <Metric
            label="Failed records"
            value={d.records_failed_unresolved}
            tone={d.records_failed_unresolved ? 'text-red-700' : 'text-gray-900'}
          />
          <Metric label="Batches created today" value={d.batches_created_today} />
          <Metric label="Transmitted today" value={d.batches_transmitted_today} />
          <Metric label="Records processed today" value={d.records_processed_today} />
          <Metric label="Committed today" value={currency(d.total_amount_today)} />
        </div>
      )}

      {/* Batch list */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-gray-900">Batches</h2>
        </div>

        {isLoading ? (
          <div className="p-6 text-sm text-gray-500">Loading batches…</div>
        ) : batches.length === 0 ? (
          <div className="p-10 text-center text-sm text-gray-500">No batches yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-500">
                  <th className="px-5 py-2 font-medium">Batch</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Records</th>
                  <th className="px-3 py-2 font-medium">Amount</th>
                  <th className="px-3 py-2 font-medium">Release / Hold / Return / Reject</th>
                  <th className="px-3 py-2 font-medium">Created</th>
                  <th className="px-3 py-2 font-medium">Transmitted</th>
                  <th className="px-3 py-2 font-medium">Ack</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id} className="border-t border-gray-100">
                    <td className="px-5 py-2 font-mono text-xs text-gray-800">{b.batch_number}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          BATCH_STATUS_TONE[b.status] ?? 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {titleCase(b.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-700">{b.total_records}</td>
                    <td className="px-3 py-2 font-medium text-gray-900">{currency(b.total_amount)}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {b.release_count} / {b.hold_count} / {b.return_count} / {b.reject_count}
                      {b.has_high_risk_items && (
                        <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">
                          {b.high_risk_count} high-risk
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(b.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2 text-gray-500">
                      {b.transmitted_at ? new Date(b.transmitted_at).toLocaleString() : '—'}
                    </td>
                    <td className={`px-3 py-2 ${b.ack_status ? ACK_TONE[b.ack_status] : 'text-gray-400'}`}>
                      {b.ack_status ? titleCase(b.ack_status) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
