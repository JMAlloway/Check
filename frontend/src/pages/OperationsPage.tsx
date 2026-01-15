import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ServerIcon,
  CircleStackIcon,
  SignalIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  ArrowTopRightOnSquareIcon,
  BellAlertIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';
import { format, formatDistanceToNow } from 'date-fns';
import { api } from '../services/api';

// =============================================================================
// Types
// =============================================================================

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  latency_ms: number | null;
  details: Record<string, unknown> | null;
  last_checked: string;
}

interface SystemHealth {
  overall_status: string;
  services: ServiceStatus[];
  timestamp: string;
}

interface PerformanceMetrics {
  requests_per_minute: number;
  avg_response_time_ms: number;
  error_rate_percent: number;
  active_users: number;
  pending_checks: number;
  checks_processed_today: number;
  timestamp: string;
}

interface Alert {
  name: string;
  severity: string;
  status: string;
  summary: string;
  description: string | null;
  started_at: string;
  labels: Record<string, string>;
}

interface AlertsSummary {
  total: number;
  critical: number;
  warning: number;
  info: number;
  alerts: Alert[];
  timestamp: string;
}

interface BackupStatus {
  last_backup: string | null;
  backup_size_mb: number | null;
  backup_location: string | null;
  replication_lag_seconds: number | null;
  dr_environment_status: string;
  last_dr_drill: string | null;
  rto_target_hours: number;
  rpo_target_minutes: number;
  timestamp: string;
}

interface QuickLinks {
  grafana: {
    url: string;
    dashboards: { name: string; path: string }[];
  };
  prometheus: {
    url: string;
    useful_queries: { name: string; query: string }[];
  };
  alertmanager: {
    url: string;
  };
  documentation: { name: string; path: string }[];
}

// =============================================================================
// API Functions
// =============================================================================

const operationsApi = {
  getHealth: () => api.get<SystemHealth>('/operations/health').then(r => r.data),
  getMetrics: () => api.get<PerformanceMetrics>('/operations/metrics').then(r => r.data),
  getAlerts: () => api.get<AlertsSummary>('/operations/alerts').then(r => r.data),
  getDRStatus: () => api.get<BackupStatus>('/operations/dr-status').then(r => r.data),
  getQuickLinks: () => api.get<QuickLinks>('/operations/quick-links').then(r => r.data),
};

// =============================================================================
// Components
// =============================================================================

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'healthy':
      return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
    case 'degraded':
      return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />;
    case 'unhealthy':
      return <XCircleIcon className="h-5 w-5 text-red-500" />;
    default:
      return <ClockIcon className="h-5 w-5 text-gray-400" />;
  }
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        status === 'healthy' && 'bg-green-100 text-green-800',
        status === 'degraded' && 'bg-yellow-100 text-yellow-800',
        status === 'unhealthy' && 'bg-red-100 text-red-800',
        status === 'unknown' && 'bg-gray-100 text-gray-800'
      )}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        severity === 'critical' && 'bg-red-100 text-red-800',
        severity === 'warning' && 'bg-yellow-100 text-yellow-800',
        severity === 'info' && 'bg-blue-100 text-blue-800'
      )}
    >
      {severity.toUpperCase()}
    </span>
  );
}

// System Health Panel
function SystemHealthPanel() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['operations-health'],
    queryFn: operationsApi.getHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <ServerIcon className="h-6 w-6 text-gray-400" />
          <h2 className="text-lg font-medium text-gray-900">System Health</h2>
          {data && <StatusBadge status={data.overall_status} />}
        </div>
        <button
          onClick={() => refetch()}
          className="p-1.5 rounded-md hover:bg-gray-100"
          disabled={isFetching}
        >
          <ArrowPathIcon className={clsx('h-5 w-5 text-gray-400', isFetching && 'animate-spin')} />
        </button>
      </div>
      <div className="p-6">
        <div className="space-y-4">
          {data?.services.map((service) => (
            <div
              key={service.name}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div className="flex items-center space-x-3">
                <StatusIcon status={service.status} />
                <div>
                  <p className="font-medium text-gray-900">{service.name}</p>
                  {service.latency_ms !== null && (
                    <p className="text-xs text-gray-500">{service.latency_ms.toFixed(1)}ms latency</p>
                  )}
                </div>
              </div>
              <StatusBadge status={service.status} />
            </div>
          ))}
        </div>
        {data && (
          <p className="text-xs text-gray-400 mt-4 text-right">
            Last updated: {formatDistanceToNow(new Date(data.timestamp), { addSuffix: true })}
          </p>
        )}
      </div>
    </div>
  );
}

// Performance Metrics Panel
function PerformanceMetricsPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['operations-metrics'],
    queryFn: operationsApi.getMetrics,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-20 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const metrics = [
    {
      label: 'Requests/Min',
      value: data?.requests_per_minute.toFixed(1) || '0',
      icon: ChartBarIcon,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Avg Response',
      value: `${data?.avg_response_time_ms.toFixed(0) || 0}ms`,
      icon: ClockIcon,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      label: 'Error Rate',
      value: `${data?.error_rate_percent.toFixed(2) || 0}%`,
      icon: ExclamationTriangleIcon,
      color: data && data.error_rate_percent > 1 ? 'text-red-600' : 'text-gray-600',
      bg: data && data.error_rate_percent > 1 ? 'bg-red-50' : 'bg-gray-50',
    },
    {
      label: 'Active Users',
      value: data?.active_users || 0,
      icon: SignalIcon,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
    {
      label: 'Pending Checks',
      value: data?.pending_checks || 0,
      icon: CircleStackIcon,
      color: 'text-yellow-600',
      bg: 'bg-yellow-50',
    },
    {
      label: 'Processed Today',
      value: data?.checks_processed_today || 0,
      icon: CheckCircleIcon,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
  ];

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center space-x-3">
        <ChartBarIcon className="h-6 w-6 text-gray-400" />
        <h2 className="text-lg font-medium text-gray-900">Performance Metrics</h2>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {metrics.map((metric) => (
            <div key={metric.label} className={clsx('p-4 rounded-lg', metric.bg)}>
              <div className="flex items-center space-x-2 mb-1">
                <metric.icon className={clsx('h-4 w-4', metric.color)} />
                <span className="text-xs font-medium text-gray-500">{metric.label}</span>
              </div>
              <p className={clsx('text-2xl font-semibold', metric.color)}>{metric.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Alerts Panel
function AlertsPanel() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['operations-alerts'],
    queryFn: operationsApi.getAlerts,
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-32 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <div className="flex items-center space-x-3">
          <BellAlertIcon className="h-6 w-6 text-gray-400" />
          <h2 className="text-lg font-medium text-gray-900">Active Alerts</h2>
          {data && data.total > 0 && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
              {data.total}
            </span>
          )}
        </div>
        <button
          onClick={() => refetch()}
          className="p-1.5 rounded-md hover:bg-gray-100"
          disabled={isFetching}
        >
          <ArrowPathIcon className={clsx('h-5 w-5 text-gray-400', isFetching && 'animate-spin')} />
        </button>
      </div>
      <div className="p-6">
        {data?.total === 0 ? (
          <div className="text-center py-8">
            <CheckCircleIcon className="h-12 w-12 text-green-400 mx-auto mb-3" />
            <p className="text-gray-500">No active alerts</p>
          </div>
        ) : (
          <>
            <div className="flex space-x-4 mb-4">
              {data && data.critical > 0 && (
                <span className="text-sm text-red-600 font-medium">
                  {data.critical} Critical
                </span>
              )}
              {data && data.warning > 0 && (
                <span className="text-sm text-yellow-600 font-medium">
                  {data.warning} Warning
                </span>
              )}
              {data && data.info > 0 && (
                <span className="text-sm text-blue-600 font-medium">
                  {data.info} Info
                </span>
              )}
            </div>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {data?.alerts.map((alert, idx) => (
                <div
                  key={idx}
                  className={clsx(
                    'p-3 rounded-lg border-l-4',
                    alert.severity === 'critical' && 'bg-red-50 border-red-500',
                    alert.severity === 'warning' && 'bg-yellow-50 border-yellow-500',
                    alert.severity === 'info' && 'bg-blue-50 border-blue-500'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">{alert.name}</span>
                        <SeverityBadge severity={alert.severity} />
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{alert.summary}</p>
                    </div>
                    <span className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(alert.started_at), { addSuffix: true })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// DR Status Panel
function DRStatusPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['operations-dr-status'],
    queryFn: operationsApi.getDRStatus,
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-32 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center space-x-3">
        <ShieldCheckIcon className="h-6 w-6 text-gray-400" />
        <h2 className="text-lg font-medium text-gray-900">Disaster Recovery Status</h2>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 mb-1">Last Backup</p>
            <p className="text-sm font-semibold text-gray-900">
              {data?.last_backup
                ? format(new Date(data.last_backup), 'MMM d, HH:mm')
                : 'N/A'}
            </p>
            {data?.backup_size_mb && (
              <p className="text-xs text-gray-500">{data.backup_size_mb.toFixed(1)} MB</p>
            )}
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 mb-1">Replication Lag</p>
            <p className="text-sm font-semibold text-gray-900">
              {data?.replication_lag_seconds !== null
                ? `${data.replication_lag_seconds.toFixed(1)}s`
                : 'N/A'}
            </p>
            <p className="text-xs text-gray-500">
              RPO Target: {data?.rpo_target_minutes}min
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 mb-1">DR Environment</p>
            <StatusBadge
              status={data?.dr_environment_status === 'standby' ? 'healthy' : 'unknown'}
            />
            <p className="text-xs text-gray-500 mt-1">
              RTO Target: {data?.rto_target_hours}hr
            </p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-500 mb-1">Last DR Drill</p>
            <p className="text-sm font-semibold text-gray-900">
              {data?.last_dr_drill
                ? formatDistanceToNow(new Date(data.last_dr_drill), { addSuffix: true })
                : 'Never'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Quick Links Panel
function QuickLinksPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['operations-quick-links'],
    queryFn: operationsApi.getQuickLinks,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-32 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center space-x-3">
        <ArrowTopRightOnSquareIcon className="h-6 w-6 text-gray-400" />
        <h2 className="text-lg font-medium text-gray-900">Quick Links</h2>
      </div>
      <div className="p-6 space-y-6">
        {/* Monitoring Tools */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Monitoring Tools</h3>
          <div className="flex flex-wrap gap-2">
            <a
              href={data?.grafana.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-3 py-2 border border-gray-200 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <ChartBarIcon className="h-4 w-4 mr-2 text-orange-500" />
              Grafana
              <ArrowTopRightOnSquareIcon className="h-3 w-3 ml-1.5 text-gray-400" />
            </a>
            <a
              href={data?.prometheus.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-3 py-2 border border-gray-200 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <CircleStackIcon className="h-4 w-4 mr-2 text-red-500" />
              Prometheus
              <ArrowTopRightOnSquareIcon className="h-3 w-3 ml-1.5 text-gray-400" />
            </a>
            <a
              href={data?.alertmanager.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-3 py-2 border border-gray-200 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <BellAlertIcon className="h-4 w-4 mr-2 text-yellow-500" />
              Alertmanager
              <ArrowTopRightOnSquareIcon className="h-3 w-3 ml-1.5 text-gray-400" />
            </a>
          </div>
        </div>

        {/* Grafana Dashboards */}
        {data?.grafana.dashboards && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Dashboards</h3>
            <div className="space-y-2">
              {data.grafana.dashboards.map((dashboard) => (
                <a
                  key={dashboard.path}
                  href={`${data.grafana.url}${dashboard.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-2 rounded-md hover:bg-gray-50"
                >
                  <span className="text-sm text-gray-600">{dashboard.name}</span>
                  <ArrowTopRightOnSquareIcon className="h-4 w-4 text-gray-400" />
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Documentation */}
        {data?.documentation && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Documentation</h3>
            <div className="space-y-2">
              {data.documentation.map((doc) => (
                <div
                  key={doc.path}
                  className="flex items-center space-x-2 p-2 rounded-md bg-gray-50"
                >
                  <DocumentTextIcon className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">{doc.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function OperationsPage() {
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setLastRefresh(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Operations Dashboard</h1>
            <p className="text-sm text-gray-500 mt-1">
              System health, performance metrics, and operational status
            </p>
          </div>
          <div className="text-xs text-gray-400">
            Auto-refresh: {format(lastRefresh, 'HH:mm:ss')}
          </div>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          <SystemHealthPanel />
          <PerformanceMetricsPanel />
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <AlertsPanel />
          <DRStatusPanel />
          <QuickLinksPanel />
        </div>
      </div>
    </div>
  );
}
