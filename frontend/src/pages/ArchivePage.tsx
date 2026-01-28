import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { archiveApi } from '../services/api';
import {
  ArchiveBoxIcon,
  MagnifyingGlassIcon,
  DocumentArrowDownIcon,
  FunnelIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface ArchiveItem {
  id: string;
  external_item_id: string;
  account_number: string;
  amount: number;
  payee_name: string;
  check_number: string;
  status: string;
  risk_level: string;
  created_at: string;
  updated_at: string;
  decision: {
    id: string;
    action: string;
    user_id: string;
    created_at: string;
    notes: string;
  } | null;
}

interface ArchiveItemDetail {
  item: {
    id: string;
    external_item_id: string;
    account_number: string;
    routing_number: string;
    amount: number;
    payee_name: string;
    check_number: string;
    check_date: string;
    memo: string;
    status: string;
    risk_level: string;
    risk_score: number;
    ai_recommendation: string;
    ai_confidence: number;
    account_type: string;
    account_tenure_days: number;
    created_at: string;
    updated_at: string;
  };
  decisions: Array<{
    id: string;
    decision_type: string;
    action: string;
    user_id: string;
    notes: string;
    ai_assisted: boolean;
    is_dual_control_required: boolean;
    dual_control_approver_id: string | null;
    dual_control_approved_at: string | null;
    created_at: string;
  }>;
  audit_trail: Array<{
    id: string;
    action: string;
    user_id: string;
    username: string;
    description: string;
    timestamp: string;
  }>;
}

const STATUS_OPTIONS = ['approved', 'returned', 'rejected', 'exception'];
const RISK_LEVELS = ['low', 'medium', 'high', 'critical'];

const statusColors: Record<string, string> = {
  approved: 'bg-green-100 text-green-800',
  returned: 'bg-orange-100 text-orange-800',
  rejected: 'bg-red-100 text-red-800',
  exception: 'bg-purple-100 text-purple-800',
};

const riskColors: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

export default function ArchivePage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50); // Increased for better grouping
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedItem, setSelectedItem] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [expandedDates, setExpandedDates] = useState<Set<string>>(new Set());

  // Filters
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [riskFilter, setRiskFilter] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [amountMin, setAmountMin] = useState('');
  const [amountMax, setAmountMax] = useState('');

  // Archive search query
  const { data, isLoading } = useQuery({
    queryKey: ['archive', page, pageSize, statusFilter, riskFilter, dateFrom, dateTo, amountMin, amountMax, searchQuery],
    queryFn: () =>
      archiveApi.searchItems({
        page,
        page_size: pageSize,
        status: statusFilter.length > 0 ? statusFilter : undefined,
        risk_level: riskFilter.length > 0 ? riskFilter : undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
        amount_min: amountMin ? parseFloat(amountMin) : undefined,
        amount_max: amountMax ? parseFloat(amountMax) : undefined,
        search_query: searchQuery || undefined,
      }),
  });

  // Archive stats query
  const { data: stats } = useQuery({
    queryKey: ['archive-stats'],
    queryFn: () => archiveApi.getStats(),
  });

  // Item detail query
  const { data: itemDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ['archive-item', selectedItem],
    queryFn: () => (selectedItem ? archiveApi.getItemDetail(selectedItem) : null),
    enabled: !!selectedItem,
  });

  const handleExport = async () => {
    setExporting(true);
    try {
      await archiveApi.exportCsv({
        status: statusFilter.length > 0 ? statusFilter : undefined,
        risk_level: riskFilter.length > 0 ? riskFilter : undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
      });
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export archive data');
    } finally {
      setExporting(false);
    }
  };

  const clearFilters = () => {
    setStatusFilter([]);
    setRiskFilter([]);
    setDateFrom('');
    setDateTo('');
    setAmountMin('');
    setAmountMax('');
    setSearchQuery('');
    setPage(1);
  };

  const hasActiveFilters =
    statusFilter.length > 0 ||
    riskFilter.length > 0 ||
    dateFrom ||
    dateTo ||
    amountMin ||
    amountMax ||
    searchQuery;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDateGroup = (dateStr: string) => {
    if (!dateStr) return 'Unknown Date';
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    }
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getDateKey = (dateStr: string) => {
    if (!dateStr) return 'unknown';
    return new Date(dateStr).toDateString();
  };

  // Group items by date
  const groupedItems = useMemo(() => {
    if (!data?.items) return new Map<string, ArchiveItem[]>();

    const groups = new Map<string, ArchiveItem[]>();
    data.items.forEach((item: ArchiveItem) => {
      const dateKey = getDateKey(item.updated_at);
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(item);
    });

    // Sort groups by date (newest first)
    return new Map(
      Array.from(groups.entries()).sort((a, b) => {
        if (a[0] === 'unknown') return 1;
        if (b[0] === 'unknown') return -1;
        return new Date(b[0]).getTime() - new Date(a[0]).getTime();
      })
    );
  }, [data?.items]);

  const toggleDateGroup = (dateKey: string) => {
    setExpandedDates((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(dateKey)) {
        newSet.delete(dateKey);
      } else {
        newSet.add(dateKey);
      }
      return newSet;
    });
  };

  const expandAllGroups = () => {
    setExpandedDates(new Set(groupedItems.keys()));
  };

  const collapseAllGroups = () => {
    setExpandedDates(new Set());
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ArchiveBoxIcon className="h-8 w-8 text-gray-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Archive</h1>
            <p className="text-sm text-gray-500">
              Search and export historical decisions
            </p>
          </div>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <DocumentArrowDownIcon className="h-5 w-5" />
          <span>{exporting ? 'Exporting...' : 'Export CSV'}</span>
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Total Archived</p>
            <p className="text-2xl font-bold text-gray-900">
              {stats.total_archived?.toLocaleString() || 0}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Last 30 Days</p>
            <p className="text-2xl font-bold text-green-600">
              {stats.by_period?.last_30_days?.toLocaleString() || 0}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Total Amount</p>
            <p className="text-2xl font-bold text-blue-600">
              {formatCurrency(stats.total_amount_processed || 0)}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Date Range</p>
            <p className="text-sm text-gray-700">
              {stats.date_range?.oldest
                ? new Date(stats.date_range.oldest).toLocaleDateString()
                : '-'}{' '}
              to{' '}
              {stats.date_range?.newest
                ? new Date(stats.date_range.newest).toLocaleDateString()
                : '-'}
            </p>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by payee, check number, account..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center space-x-2 px-4 py-2 border rounded-lg ${
              hasActiveFilters
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-300 text-gray-700'
            }`}
          >
            <FunnelIcon className="h-5 w-5" />
            <span>Filters</span>
            {hasActiveFilters && (
              <span className="bg-blue-500 text-white text-xs px-2 py-0.5 rounded-full">
                {statusFilter.length +
                  riskFilter.length +
                  (dateFrom ? 1 : 0) +
                  (dateTo ? 1 : 0) +
                  (amountMin ? 1 : 0) +
                  (amountMax ? 1 : 0)}
              </span>
            )}
          </button>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center space-x-1 px-3 py-2 text-gray-500 hover:text-gray-700"
            >
              <XMarkIcon className="h-4 w-4" />
              <span>Clear</span>
            </button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                multiple
                value={statusFilter}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, (o) => o.value);
                  setStatusFilter(values);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
                size={4}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Risk Level Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Risk Level
              </label>
              <select
                multiple
                value={riskFilter}
                onChange={(e) => {
                  const values = Array.from(e.target.selectedOptions, (o) => o.value);
                  setRiskFilter(values);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
                size={4}
              >
                {RISK_LEVELS.map((r) => (
                  <option key={r} value={r}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Date From */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Date From
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            {/* Date To */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Date To
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            {/* Amount Min */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Amount Min
              </label>
              <input
                type="number"
                placeholder="0.00"
                value={amountMin}
                onChange={(e) => {
                  setAmountMin(e.target.value);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>

            {/* Amount Max */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Amount Max
              </label>
              <input
                type="number"
                placeholder="0.00"
                value={amountMax}
                onChange={(e) => {
                  setAmountMax(e.target.value);
                  setPage(1);
                }}
                className="w-full border border-gray-300 rounded-lg p-2 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results - Grouped by Date */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            Loading...
          </div>
        ) : data?.items?.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            No archived items found
          </div>
        ) : (
          <>
            {/* Expand/Collapse All */}
            <div className="flex justify-end space-x-2">
              <button
                onClick={expandAllGroups}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Expand All
              </button>
              <span className="text-gray-300">|</span>
              <button
                onClick={collapseAllGroups}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Collapse All
              </button>
            </div>

            {/* Date Groups */}
            {Array.from(groupedItems.entries()).map(([dateKey, items]) => {
              const isExpanded = expandedDates.has(dateKey);
              const sampleItem = items[0];
              const totalAmount = items.reduce((sum, item) => sum + (item.amount || 0), 0);
              const statusCounts = items.reduce((acc, item) => {
                acc[item.status] = (acc[item.status] || 0) + 1;
                return acc;
              }, {} as Record<string, number>);

              return (
                <div key={dateKey} className="bg-white rounded-lg shadow overflow-hidden">
                  {/* Date Group Header */}
                  <button
                    onClick={() => toggleDateGroup(dateKey)}
                    className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center space-x-4">
                      {isExpanded ? (
                        <ChevronUpIcon className="h-5 w-5 text-gray-500" />
                      ) : (
                        <ChevronDownIcon className="h-5 w-5 text-gray-500" />
                      )}
                      <div className="text-left">
                        <h3 className="text-sm font-semibold text-gray-900">
                          {formatDateGroup(sampleItem?.updated_at)}
                        </h3>
                        <p className="text-xs text-gray-500">
                          {items.length} item{items.length !== 1 ? 's' : ''} | Total: {formatCurrency(totalAmount)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {Object.entries(statusCounts).map(([status, count]) => (
                        <span
                          key={status}
                          className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
                            statusColors[status] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {count} {status}
                        </span>
                      ))}
                    </div>
                  </button>

                  {/* Date Group Content */}
                  {isExpanded && (
                    <div className="divide-y divide-gray-200">
                      {items.map((item) => (
                        <div
                          key={item.id}
                          onClick={() => setSelectedItem(item.id)}
                          className="px-6 py-4 hover:bg-gray-50 cursor-pointer flex items-center justify-between"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-3">
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                  {item.payee_name || 'Unknown Payee'}
                                </p>
                                <p className="text-xs text-gray-500">
                                  Acct: {item.account_number} | Check #{item.check_number || '-'}
                                </p>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center space-x-4 ml-4">
                            <span className="text-sm font-medium text-gray-900 w-24 text-right">
                              {formatCurrency(item.amount || 0)}
                            </span>
                            <span
                              className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full w-20 justify-center ${
                                statusColors[item.status] || 'bg-gray-100 text-gray-800'
                              }`}
                            >
                              {item.status}
                            </span>
                            <span
                              className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full w-16 justify-center ${
                                riskColors[item.risk_level] || 'bg-gray-100 text-gray-800'
                              }`}
                            >
                              {item.risk_level || '-'}
                            </span>
                            <span className="text-xs text-gray-500 w-12 text-right">
                              {new Date(item.updated_at).toLocaleTimeString('en-US', {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Pagination */}
            {data && (
              <div className="bg-white rounded-lg shadow px-6 py-3 flex items-center justify-between">
                <div className="text-sm text-gray-500">
                  Showing {((page - 1) * pageSize) + 1} to{' '}
                  {Math.min(page * pageSize, data.total)} of {data.total} results
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={!data.has_previous}
                    className="p-2 border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    <ChevronLeftIcon className="h-5 w-5" />
                  </button>
                  <span className="text-sm text-gray-700">
                    Page {page} of {data.total_pages}
                  </span>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!data.has_next}
                    className="p-2 border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    <ChevronRightIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Item Detail Modal */}
      {selectedItem && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="text-lg font-semibold text-gray-900">
                Archived Item Details
              </h2>
              <button
                onClick={() => setSelectedItem(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="overflow-y-auto max-h-[calc(90vh-120px)] p-6">
              {loadingDetail ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : itemDetail ? (
                <div className="space-y-6">
                  {/* Item Info */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Account</p>
                      <p className="text-sm font-medium">{itemDetail.item.account_number}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Amount</p>
                      <p className="text-sm font-medium">
                        {formatCurrency(itemDetail.item.amount || 0)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Check #</p>
                      <p className="text-sm font-medium">{itemDetail.item.check_number || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Payee</p>
                      <p className="text-sm font-medium">{itemDetail.item.payee_name || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Status</p>
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          statusColors[itemDetail.item.status] || 'bg-gray-100'
                        }`}
                      >
                        {itemDetail.item.status}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Risk Level</p>
                      <span
                        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          riskColors[itemDetail.item.risk_level] || 'bg-gray-100'
                        }`}
                      >
                        {itemDetail.item.risk_level || '-'}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">AI Recommendation</p>
                      <p className="text-sm font-medium">{itemDetail.item.ai_recommendation || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Created</p>
                      <p className="text-sm">{formatDate(itemDetail.item.created_at)}</p>
                    </div>
                  </div>

                  {/* Decisions */}
                  <div>
                    <h3 className="text-md font-semibold text-gray-900 mb-3">
                      Decision History
                    </h3>
                    {itemDetail.decisions && itemDetail.decisions.length > 0 ? (
                      <div className="space-y-2">
                        {itemDetail.decisions.map((decision: ArchiveItemDetail['decisions'][number]) => (
                          <div
                            key={decision.id}
                            className="bg-gray-50 rounded-lg p-3 text-sm"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium capitalize">{decision.action}</span>
                              <span className="text-gray-500">
                                {formatDate(decision.created_at)}
                              </span>
                            </div>
                            {decision.notes && (
                              <p className="text-gray-600 mt-1">{decision.notes}</p>
                            )}
                            <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                              <span className="text-gray-400">
                                Type: {decision.decision_type?.replace(/_/g, ' ') || 'Unknown'}
                              </span>
                              {decision.ai_assisted && (
                                <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                                  AI Assisted
                                </span>
                              )}
                              {decision.is_dual_control_required && (
                                <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded">
                                  Dual Control
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="bg-gray-50 rounded-lg p-4 text-center text-gray-500 text-sm">
                        No decision records available
                      </div>
                    )}
                  </div>

                  {/* Audit Trail */}
                  <div>
                    <h3 className="text-md font-semibold text-gray-900 mb-3">
                      Audit Trail
                    </h3>
                    {itemDetail.audit_trail && itemDetail.audit_trail.length > 0 ? (
                      <div className="border rounded-lg divide-y max-h-64 overflow-y-auto">
                        {itemDetail.audit_trail.map((log: ArchiveItemDetail['audit_trail'][number]) => (
                          <div key={log.id} className="p-3 text-sm">
                            <div className="flex items-center justify-between">
                              <span className="font-medium capitalize">
                                {log.action?.replace(/_/g, ' ') || 'Action'}
                              </span>
                              <span className="text-gray-500 text-xs">
                                {formatDate(log.timestamp)}
                              </span>
                            </div>
                            <p className="text-gray-600 text-xs mt-1">{log.description}</p>
                            <p className="text-gray-400 text-xs">By: {log.username || log.user_id}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="border rounded-lg p-4 text-center text-gray-500 text-sm">
                        No audit trail entries available for this item
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  Failed to load item details
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
