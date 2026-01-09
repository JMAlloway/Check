import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';
import { reportsApi, queueApi } from '../services/api';
import { DashboardStats, Queue } from '../types';
import clsx from 'clsx';

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
    <div className={clsx('bg-white rounded-lg shadow p-6', link && 'hover:shadow-md transition-shadow')}>
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

function RiskDistribution({ data, onSegmentClick }: { data: Record<string, number>; onSegmentClick?: (level: string) => void }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  const colors = {
    low: 'bg-green-500',
    medium: 'bg-yellow-500',
    high: 'bg-orange-500',
    critical: 'bg-red-500',
  };
  const hoverColors = {
    low: 'hover:bg-green-600',
    medium: 'hover:bg-yellow-600',
    high: 'hover:bg-orange-600',
    critical: 'hover:bg-red-600',
  };

  if (total === 0) {
    return (
      <div className="text-gray-500 text-sm text-center py-4">
        No items in queue
      </div>
    );
  }

  return (
    <div>
      <div className="flex h-4 rounded-full overflow-hidden">
        {Object.entries(data).map(([level, count]) => {
          const percentage = (count / total) * 100;
          if (percentage === 0) return null;
          return (
            <div
              key={level}
              className={clsx(
                colors[level as keyof typeof colors],
                hoverColors[level as keyof typeof hoverColors],
                'transition-colors cursor-pointer'
              )}
              style={{ width: `${percentage}%` }}
              title={`${level}: ${count} - Click to filter`}
              onClick={() => onSegmentClick?.(level)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSegmentClick?.(level)}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        {Object.entries(data).map(([level, count]) => (
          <div
            key={level}
            className="flex items-center cursor-pointer hover:text-gray-700 transition-colors"
            onClick={() => onSegmentClick?.(level)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSegmentClick?.(level)}
          >
            <div className={clsx('w-2 h-2 rounded-full mr-1', colors[level as keyof typeof colors])} />
            <span className="capitalize">{level}: {count}</span>
          </div>
        ))}
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

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Risk Distribution</h2>
          <RiskDistribution data={stats?.items_by_risk || {}} onSegmentClick={handleRiskSegmentClick} />
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
