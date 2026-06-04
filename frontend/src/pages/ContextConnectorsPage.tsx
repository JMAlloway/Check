import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ServerStackIcon,
  ArrowPathIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { contextConnectorApi } from '../services/api';
import BackLink from '../components/common/BackLink';
import type { ContextConnector, ContextImport } from '../types';

const CONNECTOR_STATUS_TONE: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-600',
  error: 'bg-red-100 text-red-800',
  testing: 'bg-blue-100 text-blue-800',
};

const IMPORT_STATUS_TONE: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  partial: 'bg-amber-100 text-amber-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-600',
  pending: 'bg-blue-100 text-blue-800',
  processing: 'bg-blue-100 text-blue-800',
};

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function ImportHistory({ connectorId }: { connectorId: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['context-imports', connectorId],
    queryFn: () => contextConnectorApi.getImports(connectorId),
  });

  if (isLoading) return <p className="px-1 py-2 text-sm text-gray-500">Loading import history…</p>;
  if (isError)
    return (
      <div className="px-1 py-2 text-sm text-red-700">
        Could not load imports.{' '}
        <button onClick={() => refetch()} className="underline">
          Retry
        </button>
      </div>
    );

  const imports = data?.items ?? [];
  if (imports.length === 0)
    return <p className="px-1 py-2 text-sm text-gray-500">No import runs yet.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-gray-500">
            <th className="py-1 pr-4 font-medium">File</th>
            <th className="py-1 pr-4 font-medium">Status</th>
            <th className="py-1 pr-4 font-medium">Records</th>
            <th className="py-1 pr-4 font-medium">Applied</th>
            <th className="py-1 pr-4 font-medium">Invalid</th>
            <th className="py-1 pr-4 font-medium">Started</th>
          </tr>
        </thead>
        <tbody>
          {imports.map((imp: ContextImport) => (
            <tr key={imp.id} className="border-t border-gray-100">
              <td className="py-1.5 pr-4 font-mono text-xs text-gray-800">{imp.file_name}</td>
              <td className="py-1.5 pr-4">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    IMPORT_STATUS_TONE[imp.status] ?? 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {titleCase(imp.status)}
                </span>
              </td>
              <td className="py-1.5 pr-4 text-gray-700">{imp.total_records.toLocaleString()}</td>
              <td className="py-1.5 pr-4 text-gray-700">{imp.applied_records.toLocaleString()}</td>
              <td className={`py-1.5 pr-4 ${imp.invalid_records ? 'text-amber-700' : 'text-gray-500'}`}>
                {imp.invalid_records}
              </td>
              <td className="py-1.5 pr-4 text-gray-500">
                {imp.started_at ? new Date(imp.started_at).toLocaleString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConnectorCard({ connector }: { connector: ContextConnector }) {
  const [open, setOpen] = useState(false);
  const healthy = connector.consecutive_failures === 0;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-900">{connector.name}</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                CONNECTOR_STATUS_TONE[connector.status] ?? 'bg-gray-100 text-gray-600'
              }`}
            >
              {titleCase(connector.status)}
            </span>
            {!connector.is_enabled && (
              <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
                Disabled
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-xs">
              {healthy ? (
                <CheckCircleIcon className="h-4 w-4 text-green-500" aria-hidden="true" />
              ) : (
                <ExclamationTriangleIcon className="h-4 w-4 text-red-500" aria-hidden="true" />
              )}
              <span className={healthy ? 'text-green-700' : 'text-red-700'}>
                {healthy ? 'Healthy' : `${connector.consecutive_failures} consecutive failures`}
              </span>
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">{connector.description}</p>
          <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-0.5 text-xs text-gray-600 sm:grid-cols-2">
            <div>
              Source: <span className="text-gray-900">{titleCase(connector.source_system)}</span>
            </div>
            <div>
              SFTP:{' '}
              <span className="font-mono text-gray-900">
                {connector.sftp_username}@{connector.sftp_host}:{connector.sftp_port}
              </span>
            </div>
            <div>
              Path: <span className="font-mono text-gray-900">{connector.sftp_remote_path}</span>
            </div>
            <div>
              Pattern: <span className="font-mono text-gray-900">{connector.file_pattern}</span> (
              {connector.file_format.toUpperCase()})
            </div>
            <div className="flex items-center gap-1">
              <ClockIcon className="h-3.5 w-3.5" aria-hidden="true" />
              Schedule:{' '}
              <span className="text-gray-900">
                {connector.schedule_enabled ? connector.schedule_cron ?? 'enabled' : 'manual'}
              </span>
            </div>
            <div>
              Last import:{' '}
              <span className="text-gray-900">
                {connector.last_import_at
                  ? `${new Date(connector.last_import_at).toLocaleString()} · ${
                      connector.last_import_records ?? 0
                    } records`
                  : 'never'}
              </span>
            </div>
          </dl>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          {open ? 'Hide import history' : 'Import history'}
        </button>
      </div>

      {open && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <ImportHistory connectorId={connector.id} />
        </div>
      )}
    </div>
  );
}

export default function ContextConnectorsPage() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['context-connectors'],
    queryFn: contextConnectorApi.listConnectors,
  });

  const connectors = data?.items ?? [];

  return (
    <div className="space-y-6">
      <BackLink to="/operations" label="Back to Operations" />
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ServerStackIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
            Account Context Feed
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Inbound SFTP feeds that enrich checks with account tenure, balances and behavior. Review
            connector configuration and import history.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ArrowPathIcon className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {isLoading && (
        <div className="space-y-3" aria-busy="true">
          {[0, 1].map((i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-5">
              <div className="h-4 w-1/3 rounded bg-gray-200" />
              <div className="mt-3 h-3 w-2/3 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      )}

      {isError && !isLoading && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">Could not load connectors.</p>
          <button
            onClick={() => refetch()}
            className="mt-3 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && connectors.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-10 text-center">
          <ServerStackIcon className="mx-auto h-10 w-10 text-gray-400" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-semibold text-gray-900">No connectors configured</h3>
        </div>
      )}

      {!isLoading && !isError && connectors.length > 0 && (
        <div className="space-y-3">
          {connectors.map((c: ContextConnector) => (
            <ConnectorCard key={c.id} connector={c} />
          ))}
        </div>
      )}
    </div>
  );
}
