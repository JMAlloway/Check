import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  FunnelIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { checkApi, queueApi, resolveImageUrl } from '../services/api';
import { CheckItemListItem, CheckStatus, RiskLevel, PaginatedResponse } from '../types';
import { StatusBadge, RiskBadge, SLABadge } from '../components/common/StatusBadge';
import clsx from 'clsx';

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

// Check if a date is today
function isToday(dateStr: string): boolean {
  const date = new Date(dateStr);
  const today = new Date();
  return date.toDateString() === today.toDateString();
}

// Bucket types
type BucketType = 'pending' | 'sla_breached' | 'dual_control' | 'processed_today';

interface Bucket {
  type: BucketType;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  colorClass: string;
  bgClass: string;
  items: CheckItemListItem[];
}

// Categorize items into buckets
function categorizeItems(items: CheckItemListItem[]): Bucket[] {
  const pending: CheckItemListItem[] = [];
  const slaBreached: CheckItemListItem[] = [];
  const dualControl: CheckItemListItem[] = [];
  const processedToday: CheckItemListItem[] = [];

  items.forEach((item) => {
    const isPending = ['new', 'in_review', 'pending_approval', 'escalated'].includes(item.status);
    const isProcessed = ['approved', 'rejected', 'returned'].includes(item.status);
    const isDualControlPending = item.status === 'pending_dual_control' ||
      (item.requires_dual_control && item.status === 'pending_approval');

    // SLA Breached takes priority
    if (item.sla_breached && isPending) {
      slaBreached.push(item);
    }
    // Dual control pending
    else if (isDualControlPending) {
      dualControl.push(item);
    }
    // Processed today
    else if (isProcessed && isToday(item.presented_date)) {
      processedToday.push(item);
    }
    // Pending items
    else if (isPending) {
      pending.push(item);
    }
    // Default: put in processed today if processed, else pending
    else if (isProcessed) {
      processedToday.push(item);
    }
  });

  return [
    {
      type: 'pending',
      title: 'Pending Review',
      icon: ClockIcon,
      colorClass: 'text-blue-600',
      bgClass: 'bg-blue-50',
      items: pending,
    },
    {
      type: 'sla_breached',
      title: 'SLA Breached',
      icon: ExclamationTriangleIcon,
      colorClass: 'text-red-600',
      bgClass: 'bg-red-50',
      items: slaBreached,
    },
    {
      type: 'dual_control',
      title: 'Dual Control Pending',
      icon: ShieldCheckIcon,
      colorClass: 'text-purple-600',
      bgClass: 'bg-purple-50',
      items: dualControl,
    },
    {
      type: 'processed_today',
      title: 'Processed Today',
      icon: CheckCircleIcon,
      colorClass: 'text-green-600',
      bgClass: 'bg-green-50',
      items: processedToday,
    },
  ];
}

// Collapsible bucket component
function QueueBucket({
  bucket,
  isExpanded,
  onToggle
}: {
  bucket: Bucket;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const Icon = bucket.icon;

  if (bucket.items.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden mb-4">
      {/* Bucket Header */}
      <button
        onClick={onToggle}
        className={clsx(
          'w-full px-4 py-3 flex items-center justify-between',
          bucket.bgClass,
          'hover:opacity-90 transition-opacity'
        )}
      >
        <div className="flex items-center space-x-3">
          <Icon className={clsx('h-5 w-5', bucket.colorClass)} />
          <span className={clsx('font-semibold', bucket.colorClass)}>
            {bucket.title}
          </span>
          <span className={clsx(
            'px-2 py-0.5 text-xs font-medium rounded-full',
            bucket.colorClass,
            'bg-white'
          )}>
            {bucket.items.length}
          </span>
        </div>
        {isExpanded ? (
          <ChevronDownIcon className={clsx('h-5 w-5', bucket.colorClass)} />
        ) : (
          <ChevronRightIcon className={clsx('h-5 w-5', bucket.colorClass)} />
        )}
      </button>

      {/* Bucket Content */}
      {isExpanded && (
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                Image
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Account / Check
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Amount
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Risk
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                SLA
              </th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {bucket.items.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 whitespace-nowrap">
                  {item.thumbnail_url ? (
                    <img
                      src={resolveImageUrl(item.thumbnail_url)}
                      alt="Check thumbnail"
                      className="h-10 w-16 object-cover rounded border border-gray-200"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  ) : (
                    <div className="h-10 w-16 bg-gray-100 rounded border border-gray-200 flex items-center justify-center">
                      <span className="text-xs text-gray-400">No img</span>
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">
                    {item.account_number_masked}
                  </div>
                  <div className="text-sm text-gray-500">
                    Check #{item.check_number || '-'}
                  </div>
                  {item.payee_name && (
                    <div className="text-xs text-gray-400 truncate max-w-[180px]">
                      {item.payee_name}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="text-sm font-semibold text-gray-900">
                    {formatCurrency(item.amount)}
                  </div>
                  {item.requires_dual_control && (
                    <span className="text-xs text-purple-600">Dual Control</span>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <StatusBadge status={item.status} />
                  {item.has_ai_flags && (
                    <span className="ml-1 text-xs text-orange-600">AI</span>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <RiskBadge level={item.risk_level} />
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <SLABadge dueAt={item.sla_due_at} breached={item.sla_breached} />
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-right text-sm">
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
      )}
    </div>
  );
}

export default function QueuePage() {
  const { queueId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  // Track which buckets are expanded (all expanded by default except processed)
  const [expandedBuckets, setExpandedBuckets] = useState<Set<BucketType>>(
    new Set(['pending', 'sla_breached', 'dual_control'])
  );

  // Get filter values from URL
  const statusFilter = searchParams.getAll('status') as CheckStatus[];
  const riskFilter = searchParams.getAll('risk_level') as RiskLevel[];
  const slaBreached = searchParams.get('sla_breached') === 'true';
  const dateFrom = searchParams.get('date_from');
  const dateTo = searchParams.get('date_to');

  // Fetch queue info if queueId provided
  const { data: queue } = useQuery({
    queryKey: ['queue', queueId],
    queryFn: () => queueApi.getQueue(queueId!),
    enabled: !!queueId,
  });

  // Fetch items - get more items to fill buckets
  const { data: itemsData, isLoading, refetch } = useQuery<PaginatedResponse<CheckItemListItem>>({
    queryKey: ['checkItems', page, queueId, statusFilter, riskFilter, slaBreached, dateFrom, dateTo],
    queryFn: () =>
      checkApi.getItems({
        page,
        page_size: 50, // Get more items to fill buckets
        queue_id: queueId,
        status: statusFilter.length > 0 ? statusFilter : undefined,
        risk_level: riskFilter.length > 0 ? riskFilter : undefined,
        sla_breached: slaBreached || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
  });

  // Categorize items into buckets
  const buckets = useMemo(() => {
    if (!itemsData?.items) return [];
    return categorizeItems(itemsData.items);
  }, [itemsData]);

  const toggleBucket = (type: BucketType) => {
    setExpandedBuckets((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

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

  // Calculate total items across buckets
  const totalInBuckets = buckets.reduce((sum, b) => sum + b.items.length, 0);

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
                {[
                  { value: 'new', label: 'New' },
                  { value: 'in_review', label: 'In Review' },
                  { value: 'pending_approval', label: 'Pending Approval' },
                  { value: 'pending_dual_control', label: 'Pending Dual Control' },
                  { value: 'escalated', label: 'Escalated' },
                  { value: 'approved', label: 'Approved' },
                  { value: 'rejected', label: 'Rejected' },
                  { value: 'returned', label: 'Returned' },
                ].map((status) => (
                  <label key={status.value} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={statusFilter.includes(status.value as CheckStatus)}
                      onChange={(e) => updateFilter('status', status.value, e.target.checked)}
                      className="rounded border-gray-300 text-primary-600"
                    />
                    <span className="ml-2 text-sm text-gray-600">
                      {status.label}
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

      {/* Loading State */}
      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
        </div>
      ) : !itemsData || totalInBuckets === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No items found. Try adjusting your filters.
        </div>
      ) : (
        <>
          {/* Bucket Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {buckets.map((bucket) => {
              const Icon = bucket.icon;
              return (
                <div
                  key={bucket.type}
                  className={clsx(
                    'rounded-lg p-3 flex items-center space-x-3',
                    bucket.bgClass
                  )}
                >
                  <Icon className={clsx('h-6 w-6', bucket.colorClass)} />
                  <div>
                    <div className={clsx('text-2xl font-bold', bucket.colorClass)}>
                      {bucket.items.length}
                    </div>
                    <div className="text-xs text-gray-600">{bucket.title}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Collapsible Buckets */}
          {buckets.map((bucket) => (
            <QueueBucket
              key={bucket.type}
              bucket={bucket}
              isExpanded={expandedBuckets.has(bucket.type)}
              onToggle={() => toggleBucket(bucket.type)}
            />
          ))}

          {/* Pagination */}
          {itemsData.total_pages > 1 && (
            <div className="bg-white rounded-lg shadow px-6 py-3 flex items-center justify-between">
              <div className="text-sm text-gray-500">
                Page {page} of {itemsData.total_pages} ({itemsData.total} total items)
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
  );
}
