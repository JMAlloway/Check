import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  BoltIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline';
import { checkApi, queueApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { CheckItemListItem, CheckStatus, RiskLevel, PaginatedResponse } from '../types';
import { StatusBadge, RiskBadge, SLABadge } from '../components/common/StatusBadge';
import BackLink from '../components/common/BackLink';
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
    filters: { status: ['new', 'in_review', 'escalated'] },
  },
  {
    key: 'sla',
    label: 'SLA Breached',
    icon: ExclamationTriangleIcon,
    color: 'text-red-600',
    filters: { status: ['new', 'in_review', 'escalated'], sla_breached: true },
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

const EMPTY_STATE_COPY: Record<TabKey, { title: string; hint: string }> = {
  pending: {
    title: 'The queue is clear.',
    hint: 'All presented items have been triaged. New items will appear here as they arrive, or adjust the filters above.',
  },
  sla: {
    title: 'No SLA breaches.',
    hint: 'Every pending item is within its review window.',
  },
  dual: {
    title: 'Nothing awaiting dual control.',
    hint: 'Items appear here when a recommendation needs a second approver.',
  },
  processed: {
    title: 'No processed items match the current filters.',
    hint: 'Try widening the date range or clearing the risk filters above.',
  },
};

const SORTS: { value: string; label: string; sort_by: string; sort_order: string }[] = [
  { value: 'priority_desc', label: 'Priority (high→low)', sort_by: 'priority', sort_order: 'desc' },
  { value: 'sla_due_at_asc', label: 'SLA due (soonest)', sort_by: 'sla_due_at', sort_order: 'asc' },
  { value: 'amount_desc', label: 'Amount (high→low)', sort_by: 'amount', sort_order: 'desc' },
  { value: 'amount_asc', label: 'Amount (low→high)', sort_by: 'amount', sort_order: 'asc' },
  { value: 'presented_date_desc', label: 'Newest first', sort_by: 'presented_date', sort_order: 'desc' },
  { value: 'presented_date_asc', label: 'Oldest first', sort_by: 'presented_date', sort_order: 'asc' },
];

interface DateRange {
  date_from?: string;
  date_to?: string;
}

// Map dashboard deep-link query params (status / sla_breached / date) to the
// tab whose filters best match, so the landing view matches the clicked KPI
// card rather than always defaulting to "Pending Review".
function initialTabFromParams(params: URLSearchParams): TabKey {
  const statuses = params
    .getAll('status')
    .flatMap((v) => v.split(','))
    .map((s) => s.trim().toLowerCase());
  if (params.get('sla_breached') === 'true') return 'sla';
  if (statuses.includes('pending_dual_control')) return 'dual';
  if (statuses.some((s) => ['approved', 'rejected', 'returned'].includes(s))) return 'processed';
  return 'pending';
}

// Lightweight count for a tab (reads `total` from a 1-row page).
function useTabCount(tab: TabDef, queueId?: string, riskFilter?: RiskLevel[], dates?: DateRange) {
  return useQuery({
    queryKey: ['checkCount', tab.key, queueId, riskFilter, dates],
    queryFn: () =>
      checkApi.getItems({
        page: 1,
        page_size: 1,
        queue_id: queueId,
        status: tab.filters.status,
        sla_breached: tab.filters.sla_breached,
        risk_level: riskFilter && riskFilter.length ? riskFilter : undefined,
        date_from: dates?.date_from,
        date_to: dates?.date_to,
      }) as Promise<PaginatedResponse<CheckItemListItem>>,
    select: (d) => d.total,
  });
}

export default function QueuePage() {
  const { queueId } = useParams();
  const [searchParams] = useSearchParams();
  // Land on the tab matching the dashboard KPI card that was clicked.
  const [activeTab, setActiveTab] = useState<TabKey>(() => initialTabFromParams(searchParams));
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(SORTS[0].value);
  // Seed the date range from the URL so the "Processed Today" deep link
  // (/queue?status=...&date_from=...&date_to=...) lands pre-filtered to today.
  const [dateRange] = useState<DateRange>(() => ({
    date_from: searchParams.get('date_from') || undefined,
    date_to: searchParams.get('date_to') || undefined,
  }));
  // Seed the risk filter from the URL so deep links like the dashboard's
  // "Risk Distribution" segments (/queue?risk_level=low) actually filter.
  const [riskFilter, setRiskFilter] = useState<RiskLevel[]>(() => {
    const valid: RiskLevel[] = ['low', 'medium', 'high', 'critical'];
    return searchParams
      .getAll('risk_level')
      .flatMap((v) => v.split(','))
      .map((v) => v.trim().toLowerCase())
      .filter((v): v is RiskLevel => valid.includes(v as RiskLevel));
  });

  const tab = TABS.find((t) => t.key === activeTab)!;
  const sortDef = SORTS.find((s) => s.value === sort)!;

  const { data: queue } = useQuery({
    queryKey: ['queue', queueId],
    queryFn: () => queueApi.getQueue(queueId!),
    enabled: !!queueId,
  });

  const counts = {
    pending: useTabCount(TABS[0], queueId, riskFilter, dateRange),
    sla: useTabCount(TABS[1], queueId, riskFilter, dateRange),
    dual: useTabCount(TABS[2], queueId, riskFilter, dateRange),
    processed: useTabCount(TABS[3], queueId, riskFilter, dateRange),
  };

  const { data, isLoading, isFetching, refetch } = useQuery<PaginatedResponse<CheckItemListItem>>({
    queryKey: ['checkItems', queueId, activeTab, page, sort, riskFilter, dateRange],
    queryFn: () =>
      checkApi.getItems({
        page,
        page_size: PAGE_SIZE,
        queue_id: queueId,
        status: tab.filters.status,
        sla_breached: tab.filters.sla_breached,
        risk_level: riskFilter.length ? riskFilter : undefined,
        date_from: dateRange.date_from,
        date_to: dateRange.date_to,
        sort_by: sortDef.sort_by,
        sort_order: sortDef.sort_order,
      }),
    placeholderData: keepPreviousData,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  // Claim-based worklist: who is actively working which item.
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canReview = useAuthStore((s) => s.hasPermission('check_item', 'review'));
  const { data: locksData } = useQuery({
    queryKey: ['worklist-locks'],
    queryFn: checkApi.getWorklistLocks,
    refetchInterval: 15000,
  });
  const lockByItem = new Map((locksData?.locks ?? []).map((l) => [l.item_id, l]));
  const [pulling, setPulling] = useState(false);
  const [pullMsg, setPullMsg] = useState<string | null>(null);

  const handlePullNext = async () => {
    setPulling(true);
    setPullMsg(null);
    try {
      const item = await checkApi.pullNextItem();
      navigate(`/review/${item.id}`);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPullMsg(detail ?? 'No items are available to pull right now.');
    } finally {
      setPulling(false);
    }
  };

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
      {/* When viewing a single queue (e.g. opened from a dashboard tile),
          offer a way back to the full queue list. */}
      {queueId && <BackLink to="/queue" label="Back to all queues" />}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{queue ? queue.name : 'Review Queue'}</h1>
          {queue?.description && <p className="text-gray-500">{queue.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {canReview && (
            <div className="flex flex-col items-end">
              <button
                onClick={handlePullNext}
                disabled={pulling}
                className="flex items-center px-3 py-2 font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Claim the highest-priority unassigned item and start reviewing it"
              >
                <BoltIcon className="h-5 w-5 mr-1" />
                {pulling ? 'Pulling…' : 'Pull next item'}
              </button>
              {pullMsg && <span className="mt-1 text-xs text-amber-600">{pullMsg}</span>}
            </div>
          )}
          <button
            onClick={() => refetch()}
            className="flex items-center px-3 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <ArrowPathIcon className={clsx('h-5 w-5 mr-1', isFetching && 'animate-spin')} />
            Refresh
          </button>
        </div>
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
          <div className="p-10 text-center text-gray-500">
            <p className="font-medium text-gray-700">{EMPTY_STATE_COPY[activeTab].title}</p>
            <p className="mt-1 text-sm">{EMPTY_STATE_COPY[activeTab].hint}</p>
          </div>
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
              {items.map((item) => {
                const lock = lockByItem.get(item.id);
                const lockedByOther = lock && lock.user_id !== currentUser?.id;
                return (
                <tr
                  key={item.id}
                  onClick={() => {
                    if (!lockedByOther) navigate(`/review/${item.id}`);
                  }}
                  className={clsx(
                    'hover:bg-gray-50',
                    lockedByOther ? 'opacity-70 cursor-not-allowed' : 'cursor-pointer'
                  )}
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{item.account_number_masked}</div>
                    <div className="text-sm text-gray-500">Check #{item.check_number || '-'}</div>
                    {item.payee_name && (
                      <div className="text-xs text-gray-400 truncate max-w-[180px]">{item.payee_name}</div>
                    )}
                    {lock && (
                      <div
                        className={clsx(
                          'mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                          lockedByOther ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'
                        )}
                      >
                        <LockClosedIcon className="h-3 w-3" />
                        {lockedByOther ? `In use by ${lock.username}` : 'You have this'}
                      </div>
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
                    {lockedByOther ? (
                      <span className="text-gray-400" title={`In use by ${lock?.username}`}>In use</span>
                    ) : (
                      <Link to={`/review/${item.id}`} className="text-primary-600 hover:text-primary-900 font-medium">
                        {['approved', 'rejected', 'returned', 'completed'].includes(item.status) ? 'View' : 'Review'}
                      </Link>
                    )}
                  </td>
                </tr>
                );
              })}
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
