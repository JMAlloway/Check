import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { checkApi, queueApi } from '../services/api';
import { CheckItemListItem, CheckStatus, RiskLevel, PaginatedResponse } from '../types';
import { StatusBadge, RiskBadge, SLABadge } from '../components/common/StatusBadge';
import clsx from 'clsx';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
}

const PAGE_SIZE = 25;

type TabKey = 'pending' | 'sla' | 'dual' | 'processed';

interface TabDef {
  key: TabKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  filters: {
    status?: CheckStatus[];
    sla_breached?: boolean;
  };
}

const TABS: TabDef[] = [
  {
    key: 'pending',
    label: 'Pending Review',
    icon: ClockIcon,
    color: 'text-blue-600',
    filters: { status: ['new', 'in_review', 'pending_approval', 'escalated'] },
  },
  {
    key: 'sla',
    label: 'SLA Breached',
    icon: ExclamationTriangleIcon,
    color: 'text-red-600',
    filters: { status: ['new', 'in_review', 'pending_approval', 'escalated'], sla_breached: true },
  },
  {
    key: 'dual',
    label: 'Dual Control',
    icon: ShieldCheckIcon,
    color: 'text-purple-600',
    filters: { status: ['pending_dual_control'] },
  },
  {
    key: 'processed',
    label: 'Processed',
    icon: CheckCircleIcon,
    color: 'text-green-600',
    filters: { status: ['approved', 'rejected', 'returned'] },
  },
];

const SORTS: { value: string; label: string; sort_by: string; sort_order: string }[] = [
  { value: 'priority_desc', label: 'Priority (high→low)', sort_by: 'priority', sort_order: 'desc' },
  { value: 'sla_due_at_asc', label: 'SLA due (soonest)', sort_by: 'sla_due_at', sort_order: 'asc' },
  { value: 'amount_desc', label: 'Amount (high→low)', sort_by: 'amount', sort_order: 'desc' },
  { value: 'amount_asc', label: 'Amount (low→high)', sort_by: 'amount', sort_order: 'asc' },
  { value: 'presented_date_desc', label: 'Newest first', sort_by: 'presented_date', sort_order: 'desc' },
  { value: 'presented_date_asc', label: 'Oldest first', sort_by: 'presented_date', sort_order: 'asc' },
];

// Lightweight count for a tab (reads `total` from a 1-row page).
function useTabCount(tab: TabDef, queueId?: string, riskFilter?: RiskLevel[]) {
  return useQuery({
    queryKey: ['checkCount', tab.key, queueId, riskFilter],
    queryFn: () =>
      checkApi.getItems({
        page: 1,
        page_size: 1,
        queue_id: queueId,
        status: tab.filters.status,
        sla_breached: tab.filters.sla_breached,
        risk_level: riskFilter && riskFilter.length ? riskFilter : undefined,
      }) as Promise<PaginatedResponse<CheckItemListItem>>,
    select: (d) => d.total,
  });
}

export default function QueuePage() {
  const { queueId } = useParams();
  const [activeTab, setActiveTab] = useState<TabKey>('pending');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(SORTS[0].value);
  const [riskFilter, setRiskFilter] = useState<RiskLevel[]>([]);

  const tab = TABS.find((t) => t.key === activeTab)!;
  const sortDef = SORTS.find((s) => s.value === sort)!;

  const { data: queue } = useQuery({
    queryKey: ['queue', queueId],
    queryFn: () => queueApi.getQueue(queueId!),
    enabled: !!queueId,
  });

  const counts = {
    pending: useTabCount(TABS[0], queueId, riskFilter),
    sla: useTabCount(TABS[1], queueId, riskFilter),
    dual: useTabCount(TABS[2], queueId, riskFilter),
    processed: useTabCount(TABS[3], queueId, riskFilter),
  };

  const { data, isLoading, isFetching, refetch } = useQuery<PaginatedResponse<CheckItemListItem>>({
    queryKey: ['checkItems', queueId, activeTab, page, sort, riskFilter],
    queryFn: () =>
      checkApi.getItems({
        page,
        page_size: PAGE_SIZE,
        queue_id: queueId,
        status: tab.filters.status,
        sla_breached: tab.filters.sla_breached,
        risk_level: riskFilter.length ? riskFilter : undefined,
        sort_by: sortDef.sort_by,
        sort_order: sortDef.sort_order,
      }),
    placeholderData: keepPreviousData,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  const selectTab = (key: TabKey) => {
    setActiveTab(key);
    setPage(1);
  };

  const toggleRisk = (level: RiskLevel) => {
    setRiskFilter((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    );
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{queue ? queue.name : 'Review Queue'}</h1>
          {queue?.description && <p className="text-gray-500">{queue.description}</p>}
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <ArrowPathIcon className={clsx('h-5 w-5 mr-1', isFetching && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Tabs with live counts */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {TABS.map((t) => {
          const Icon = t.icon;
          const c = counts[t.key].data;
          const active = t.key === activeTab;
          return (
            <button
              key={t.key}
              onClick={() => selectTab(t.key)}
              className={clsx(
                'rounded-lg p-3 flex items-center gap-3 border text-left transition-colors',
                active ? 'border-primary-400 bg-primary-50 ring-1 ring-primary-200' : 'border-gray-200 bg-white hover:bg-gray-50'
              )}
            >
              <Icon className={clsx('h-6 w-6', t.color)} />
              <div>
                <div className={clsx('text-2xl font-bold', t.color)}>
                  {c === undefined ? '—' : c}
                </div>
                <div className="text-xs text-gray-600">{t.label}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Toolbar: risk filter chips + sort */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase text-gray-400">Risk</span>
          {(['low', 'medium', 'high', 'critical'] as RiskLevel[]).map((level) => (
            <button
              key={level}
              onClick={() => toggleRisk(level)}
              className={clsx(
                'rounded-full px-2.5 py-0.5 text-xs font-medium border capitalize',
                riskFilter.includes(level)
                  ? 'border-primary-400 bg-primary-50 text-primary-700'
                  : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
              )}
            >
              {level}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          Sort
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          </div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center text-gray-500">No items in {tab.label}.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Account / Check', 'Amount', 'Status', 'Risk', 'SLA', ''].map((h, i) => (
                  <th
                    key={h || i}
                    className={clsx(
                      'px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider',
                      i === 5 ? 'text-right' : 'text-left'
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{item.account_number_masked}</div>
                    <div className="text-sm text-gray-500">Check #{item.check_number || '-'}</div>
                    {item.payee_name && (
                      <div className="text-xs text-gray-400 truncate max-w-[180px]">{item.payee_name}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="text-sm font-semibold text-gray-900">{formatCurrency(item.amount)}</div>
                    {item.requires_dual_control && <span className="text-xs text-purple-600">Dual Control</span>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <StatusBadge status={item.status} />
                    {item.has_ai_flags && <span className="ml-1 text-xs text-orange-600">Flagged</span>}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <RiskBadge level={item.risk_level} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <SLABadge dueAt={item.sla_due_at} breached={item.sla_breached} status={item.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
                    <Link to={`/review/${item.id}`} className="text-primary-600 hover:text-primary-900 font-medium">
                      {['approved', 'rejected', 'returned', 'completed'].includes(item.status) ? 'View' : 'Review'}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination footer */}
        {total > 0 && (
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-sm text-gray-600">
            <span>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-2 py-1 disabled:opacity-40 hover:bg-gray-50"
              >
                <ChevronLeftIcon className="h-4 w-4" /> Prev
              </button>
              <span className="px-1">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => (p < totalPages ? p + 1 : p))}
                disabled={page >= totalPages}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-2 py-1 disabled:opacity-40 hover:bg-gray-50"
              >
                Next <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
