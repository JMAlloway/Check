import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { maybeAutoStartTour } from '../tour/productTour';
import {
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  UserGroupIcon,
  BuildingLibraryIcon,
  BoltIcon,
  InboxArrowDownIcon,
} from '@heroicons/react/24/outline';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { reportsApi, queueApi } from '../services/api';
import { DashboardStats, Queue } from '../types';
import clsx from 'clsx';

const RISK_HEX: Record<string, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
  unclassified: '#9ca3af',
};

// Get today's date in ISO format for filtering (America/New_York timezone as default for bank)
function getTodayDateRange(): { from: string; to: string } {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const parts = formatter.formatToParts(now);
  const year = parts.find(p => p.type === 'year')?.value;
  const month = parts.find(p => p.type === 'month')?.value;
  const day = parts.find(p => p.type === 'day')?.value;
  const todayStr = `${year}-${month}-${day}`;
  return {
    from: `${todayStr}T00:00:00`,
    to: `${todayStr}T23:59:59`,
  };
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  link,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  link?: string;
}) {
  const content = (
    <div
      className={clsx(
        'bg-white rounded-lg shadow p-6 transition-shadow',
        link && 'cursor-pointer hover:shadow-md hover:ring-1 hover:ring-primary-200'
      )}
    >
      <div className="flex items-center">
        <div className={clsx('p-3 rounded-lg', `bg-${color}-100`)}>
          <Icon className={clsx('h-6 w-6', `text-${color}-600`)} />
        </div>
        <div className="ml-4">
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );

  if (link) {
    return <Link to={link}>{content}</Link>;
  }

  return content;
}

function RiskDistribution({
  data,
  pendingTotal,
  onSegmentClick,
}: {
  data: Record<string, number>;
  pendingTotal?: number;
  onSegmentClick?: (level: string) => void;
}) {
  const categorized = Object.values(data).reduce((a, b) => a + b, 0);
  // Reconcile with the authoritative pending count: any pending items without a
  // risk level show as an "unclassified" slice so the donut total matches the
  // "Pending Items" KPI instead of silently undercounting.
  const unclassified = Math.max(0, (pendingTotal ?? categorized) - categorized);
  const total = categorized + unclassified;

  if (total === 0) {
    return (
      <div className="text-gray-500 text-sm text-center py-4">
        No items in queue
      </div>
    );
  }

  const order = ['low', 'medium', 'high', 'critical', 'unclassified'];
  const counts: Record<string, number> = { ...data, unclassified };
  const pieData = order
    .filter((level) => (counts[level] ?? 0) > 0)
    .map((level) => ({ name: level, value: counts[level] ?? 0 }));

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={88}
              paddingAngle={2}
              onClick={(_, idx) => {
                const name = pieData[idx].name;
                if (name !== 'unclassified') onSegmentClick?.(name);
              }}
            >
              {pieData.map((d) => (
                <Cell
                  key={d.name}
                  fill={RISK_HEX[d.name]}
                  className="cursor-pointer focus:outline-none"
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number, name: string) => [`${value} items`, name]}
              contentStyle={{ textTransform: 'capitalize', fontSize: 12 }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center total */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-gray-900">{total}</span>
          <span className="text-xs text-gray-500">items</span>
        </div>
      </div>

      {/* Clickable legend (the unclassified bucket isn't a filterable risk) */}
      <div className="mt-3 grid w-full grid-cols-2 gap-2 text-sm">
        {order
          .filter((level) => (counts[level] ?? 0) > 0)
          .map((level) => {
            const clickable = level !== 'unclassified';
            return (
              <button
                key={level}
                onClick={clickable ? () => onSegmentClick?.(level) : undefined}
                disabled={!clickable}
                className={clsx(
                  'flex items-center justify-between rounded-md px-2 py-1 text-left',
                  clickable ? 'hover:bg-gray-50' : 'cursor-default'
                )}
              >
                <span className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: RISK_HEX[level] }} />
                  <span className="capitalize text-gray-600">{level}</span>
                </span>
                <span className="font-semibold text-gray-900">{counts[level] ?? 0}</span>
              </button>
            );
          })}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboardStats'],
    queryFn: reportsApi.getDashboard,
  });

  const { data: queues, isLoading: queuesLoading } = useQuery<Queue[]>({
    queryKey: ['queues'],
    queryFn: () => queueApi.getQueues(),
  });

  // Auto-start the guided product tour once per browser (offered again via the
  // "Take a tour" button in the header).
  useEffect(() => {
    maybeAutoStartTour();
  }, []);

  // Build link for "Processed Today" with date filter
  const getProcessedTodayLink = (): string => {
    const { from, to } = getTodayDateRange();
    const params = new URLSearchParams();
    params.append('status', 'approved');
    params.append('status', 'rejected');
    params.append('status', 'returned');
    params.set('date_from', from);
    params.set('date_to', to);
    return `/queue?${params.toString()}`;
  };

  // Handler for risk segment clicks
  const handleRiskSegmentClick = (level: string) => {
    navigate(`/queue?risk_level=${level}`);
  };

  if (statsLoading || queuesLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white rounded-lg shadow p-6 h-24" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Whole-bank daily volume context (demo): frames the review queue as the
          small exception slice of a much larger straight-through-cleared volume. */}
      {stats?.daily_volume && (
        <div
          data-tour="bank-volume"
          className="rounded-lg border border-gray-200 bg-gradient-to-r from-primary-50 to-white p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <BuildingLibraryIcon className="h-5 w-5 text-primary-600" />
              Today across the bank
            </h2>
            <span className="text-xs text-gray-400">Illustrative daily volume</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
                <InboxArrowDownIcon className="h-4 w-4" /> Items presented
              </div>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.daily_volume.presented.toLocaleString()}
              </p>
            </div>
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
                <BoltIcon className="h-4 w-4 text-green-600" /> Cleared straight-through
              </div>
              <p className="mt-1 text-2xl font-bold text-green-700">
                {(stats.daily_volume.straight_through_rate * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500">
                {stats.daily_volume.straight_through_cleared.toLocaleString()} items
              </p>
            </div>
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
                <UserGroupIcon className="h-4 w-4 text-blue-600" /> Routed to review
              </div>
              <p className="mt-1 text-2xl font-bold text-blue-700">
                {stats.daily_volume.routed_to_review.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500">the exception queue below</p>
            </div>
            <div className="flex items-end">
              <Link to="/automation" className="text-xs font-medium text-primary-600 hover:underline">
                See automation opportunity →
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div data-tour="dashboard-kpis" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Pending Items"
          value={stats?.summary.pending_items || 0}
          icon={ClockIcon}
          color="blue"
          link="/queue"
        />
        <StatCard
          title="Processed Today"
          value={stats?.summary.processed_today || 0}
          icon={CheckCircleIcon}
          color="green"
          link={getProcessedTodayLink()}
        />
        <StatCard
          title="SLA Breached"
          value={stats?.summary.sla_breached || 0}
          icon={ExclamationTriangleIcon}
          color="red"
          link="/queue?sla_breached=true"
        />
        <StatCard
          title="Dual Control Pending"
          value={stats?.summary.dual_control_pending || 0}
          icon={UserGroupIcon}
          color="purple"
          link="/queue?status=pending_dual_control"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Distribution */}
        <div data-tour="risk-distribution" className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Risk Distribution</h2>
          <RiskDistribution
            data={stats?.items_by_risk || {}}
            pendingTotal={stats?.summary.pending_items}
            onSegmentClick={handleRiskSegmentClick}
          />
        </div>

        {/* Queue Summary */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Queues</h2>
          <div className="space-y-3">
            {queues?.map((queue) => (
              <Link
                key={queue.id}
                to={`/queue/${queue.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div>
                  <div className="font-medium text-gray-900">{queue.name}</div>
                  <div className="text-sm text-gray-500">{queue.description}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-semibold text-gray-900">
                    {queue.current_item_count}
                  </div>
                  <div className="text-xs text-gray-500">items</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="flex space-x-4">
          <Link
            to="/queue"
            data-tour="start-reviewing"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Start Reviewing
          </Link>
          <Link
            to="/reports"
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            View Reports
          </Link>
        </div>
      </div>
    </div>
  );
}
