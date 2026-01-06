import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { FunnelIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { checkApi, queueApi } from '../services/api';
import { CheckItemListItem, CheckStatus, RiskLevel, PaginatedResponse } from '../types';
import { StatusBadge, RiskBadge, SLABadge } from '../components/common/StatusBadge';
import clsx from 'clsx';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export default function QueuePage() {
  const { queueId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  // Get filter values from URL
  const statusFilter = searchParams.getAll('status') as CheckStatus[];
  const riskFilter = searchParams.getAll('risk_level') as RiskLevel[];
  const slaBreached = searchParams.get('sla_breached') === 'true';

  // Fetch queue info if queueId provided
  const { data: queue } = useQuery({
    queryKey: ['queue', queueId],
    queryFn: () => queueApi.getQueue(queueId!),
    enabled: !!queueId,
  });

  // Fetch items
  const { data: itemsData, isLoading, refetch } = useQuery<PaginatedResponse<CheckItemListItem>>({
    queryKey: ['checkItems', page, queueId, statusFilter, riskFilter, slaBreached],
    queryFn: () =>
      checkApi.getItems({
        page,
        page_size: 20,
        queue_id: queueId,
        status: statusFilter.length > 0 ? statusFilter : undefined,
        risk_level: riskFilter.length > 0 ? riskFilter : undefined,
        sla_breached: slaBreached || undefined,
      }),
  });

  const updateFilter = (key: string, value: string, checked: boolean) => {
    const params = new URLSearchParams(searchParams);
    if (checked) {
      params.append(key, value);
    } else {
      const values = params.getAll(key).filter((v) => v !== value);
      params.delete(key);
      values.forEach((v) => params.append(key, v));
    }
    setSearchParams(params);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {queue ? queue.name : 'Review Queue'}
          </h1>
          {queue?.description && (
            <p className="text-gray-500">{queue.description}</p>
          )}
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => refetch()}
            className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <ArrowPathIcon className="h-5 w-5 mr-1" />
            Refresh
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={clsx(
              'flex items-center px-3 py-2 rounded-lg border',
              showFilters
                ? 'bg-primary-50 border-primary-300 text-primary-700'
                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
            )}
          >
            <FunnelIcon className="h-5 w-5 mr-1" />
            Filters
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
              <div className="space-y-2">
                {['new', 'in_review', 'pending_approval', 'escalated'].map((status) => (
                  <label key={status} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={statusFilter.includes(status as CheckStatus)}
                      onChange={(e) => updateFilter('status', status, e.target.checked)}
                      className="rounded border-gray-300 text-primary-600"
                    />
                    <span className="ml-2 text-sm text-gray-600 capitalize">
                      {status.replace('_', ' ')}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Risk Level Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Risk Level</label>
              <div className="space-y-2">
                {['low', 'medium', 'high', 'critical'].map((level) => (
                  <label key={level} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={riskFilter.includes(level as RiskLevel)}
                      onChange={(e) => updateFilter('risk_level', level, e.target.checked)}
                      className="rounded border-gray-300 text-primary-600"
                    />
                    <span className="ml-2 text-sm text-gray-600 capitalize">{level}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Other Filters */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Other</label>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={slaBreached}
                    onChange={(e) => {
                      const params = new URLSearchParams(searchParams);
                      if (e.target.checked) {
                        params.set('sla_breached', 'true');
                      } else {
                        params.delete('sla_breached');
                      }
                      setSearchParams(params);
                      setPage(1);
                    }}
                    className="rounded border-gray-300 text-primary-600"
                  />
                  <span className="ml-2 text-sm text-gray-600">SLA Breached Only</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Items Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          </div>
        ) : !itemsData || itemsData.items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No items found. Try adjusting your filters.
          </div>
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account / Check
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Risk
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Presented
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    SLA
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {itemsData.items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {item.account_number_masked}
                      </div>
                      <div className="text-sm text-gray-500">
                        Check #{item.check_number || '-'}
                      </div>
                      {item.payee_name && (
                        <div className="text-xs text-gray-400 truncate max-w-[200px]">
                          {item.payee_name}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-semibold text-gray-900">
                        {formatCurrency(item.amount)}
                      </div>
                      {item.requires_dual_control && (
                        <span className="text-xs text-purple-600">Dual Control</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={item.status} />
                      {item.has_ai_flags && (
                        <span className="ml-1 text-xs text-orange-600">AI Flags</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <RiskBadge level={item.risk_level} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(item.presented_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <SLABadge dueAt={item.sla_due_at} breached={item.sla_breached} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                      <Link
                        to={`/review/${item.id}`}
                        className="text-primary-600 hover:text-primary-900 font-medium"
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {itemsData.total_pages > 1 && (
              <div className="px-6 py-3 flex items-center justify-between border-t border-gray-200">
                <div className="text-sm text-gray-500">
                  Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, itemsData.total)} of{' '}
                  {itemsData.total} items
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={!itemsData.has_previous}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={!itemsData.has_next}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
