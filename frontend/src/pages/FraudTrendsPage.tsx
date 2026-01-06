import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ShieldExclamationIcon,
  BanknotesIcon,
  BuildingLibraryIcon,
} from '@heroicons/react/24/outline';
import { fraudApi } from '../services/api';

interface TrendDataPoint {
  period: string;
  total_events: number;
  total_amount: number;
  avg_amount: number;
  by_type: Record<string, number>;
  by_channel: Record<string, number>;
  by_amount_bucket: Record<string, number>;
  unique_institutions: number;
}

interface NetworkTrendsResponse {
  range: string;
  granularity: string;
  data_points: TrendDataPoint[];
  totals: {
    total_events: number;
    total_amount: number;
    unique_institutions: number;
    top_fraud_types: Array<{ type: string; count: number }>;
    top_channels: Array<{ channel: string; count: number }>;
  };
}

const TIME_RANGES = [
  { value: '3m', label: 'Last 3 Months' },
  { value: '6m', label: 'Last 6 Months' },
  { value: '12m', label: 'Last 12 Months' },
  { value: '24m', label: 'Last 24 Months' },
];

const GRANULARITIES = [
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
  { value: 'quarter', label: 'Quarterly' },
];

function StatCard({
  icon: Icon,
  label,
  value,
  subValue,
  color = 'blue',
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  subValue?: string;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
}) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center space-x-3">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-xl font-semibold text-gray-900">{value}</p>
          {subValue && <p className="text-xs text-gray-500">{subValue}</p>}
        </div>
      </div>
    </div>
  );
}

function formatCurrency(value: number): string {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}K`;
  }
  return `$${value.toFixed(0)}`;
}

function formatFraudType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function SimpleBarChart({ data, label }: { data: Array<{ name: string; value: number }>; label: string }) {
  const maxValue = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-gray-700">{label}</h4>
      <div className="space-y-2">
        {data.slice(0, 6).map((item) => (
          <div key={item.name} className="flex items-center space-x-2">
            <span className="text-xs text-gray-600 w-28 truncate" title={item.name}>
              {formatFraudType(item.name)}
            </span>
            <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded"
                style={{ width: `${(item.value / maxValue) * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-700 w-10 text-right">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendChart({ dataPoints }: { dataPoints: TrendDataPoint[] }) {
  if (!dataPoints.length) return null;

  const maxEvents = Math.max(...dataPoints.map((d) => d.total_events), 1);
  const chartHeight = 200;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Fraud Events Over Time</h3>
      <div className="relative" style={{ height: chartHeight }}>
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-6 w-10 flex flex-col justify-between text-xs text-gray-500">
          <span>{maxEvents}</span>
          <span>{Math.round(maxEvents / 2)}</span>
          <span>0</span>
        </div>

        {/* Chart area */}
        <div className="ml-12 h-full flex items-end space-x-1 pb-6">
          {dataPoints.map((point, idx) => (
            <div key={idx} className="flex-1 flex flex-col items-center">
              <div
                className="w-full max-w-8 bg-primary-500 hover:bg-primary-600 rounded-t transition-colors cursor-pointer group relative"
                style={{ height: `${(point.total_events / maxEvents) * (chartHeight - 30)}px`, minHeight: point.total_events > 0 ? 4 : 0 }}
                title={`${point.period}: ${point.total_events} events`}
              >
                {/* Tooltip */}
                <div className="hidden group-hover:block absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
                  {point.total_events} events
                  <br />
                  {formatCurrency(point.total_amount)}
                </div>
              </div>
              <span className="text-xs text-gray-500 mt-1 truncate w-full text-center" style={{ fontSize: '10px' }}>
                {point.period.slice(0, 7)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function FraudTrendsPage() {
  const [range, setRange] = useState('6m');
  const [granularity, setGranularity] = useState('month');

  const { data: trends, isLoading, error } = useQuery<NetworkTrendsResponse>({
    queryKey: ['networkTrends', range, granularity],
    queryFn: () => fraudApi.getNetworkTrends(range, granularity),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-4 gap-4 mb-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <ShieldExclamationIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-600">Failed to load network trends</p>
        <p className="text-sm text-gray-500 mt-1">Please try again later</p>
      </div>
    );
  }

  const topFraudTypes = trends?.totals?.top_fraud_types?.map((t) => ({
    name: t.type,
    value: t.count,
  })) || [];

  const topChannels = trends?.totals?.top_channels?.map((c) => ({
    name: c.channel,
    value: c.count,
  })) || [];

  // Calculate trend direction
  const dataPoints = trends?.data_points || [];
  const recentHalf = dataPoints.slice(Math.floor(dataPoints.length / 2));
  const olderHalf = dataPoints.slice(0, Math.floor(dataPoints.length / 2));
  const recentTotal = recentHalf.reduce((sum, d) => sum + d.total_events, 0);
  const olderTotal = olderHalf.reduce((sum, d) => sum + d.total_events, 0);
  const trendDirection = olderTotal > 0 ? ((recentTotal - olderTotal) / olderTotal) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Network Fraud Trends</h1>
          <p className="text-gray-600 mt-1">
            Aggregated fraud intelligence across participating institutions
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={range}
            onChange={(e) => setRange(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            {TIME_RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            {GRANULARITIES.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={ShieldExclamationIcon}
          label="Total Fraud Events"
          value={trends?.totals?.total_events?.toLocaleString() || '0'}
          subValue={`${range} period`}
          color="red"
        />
        <StatCard
          icon={BanknotesIcon}
          label="Total Fraud Amount"
          value={formatCurrency(trends?.totals?.total_amount || 0)}
          subValue="Network-wide losses"
          color="yellow"
        />
        <StatCard
          icon={BuildingLibraryIcon}
          label="Institutions Reporting"
          value={trends?.totals?.unique_institutions || 0}
          subValue="Active participants"
          color="blue"
        />
        <StatCard
          icon={trendDirection >= 0 ? ArrowTrendingUpIcon : ArrowTrendingDownIcon}
          label="Trend Direction"
          value={`${trendDirection >= 0 ? '+' : ''}${trendDirection.toFixed(1)}%`}
          subValue="vs. prior period"
          color={trendDirection >= 0 ? 'red' : 'green'}
        />
      </div>

      {/* Trend Chart */}
      <TrendChart dataPoints={dataPoints} />

      {/* Breakdown Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <SimpleBarChart data={topFraudTypes} label="Top Fraud Types" />
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <SimpleBarChart data={topChannels} label="Top Channels" />
        </div>
      </div>

      {/* Privacy Notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <ShieldExclamationIcon className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-blue-900">Privacy-Preserving Analytics</h4>
            <p className="text-sm text-blue-700 mt-1">
              All data shown is aggregated from multiple institutions. Individual transaction details
              and institution identities are never shared. Counts below {3} are suppressed for privacy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
