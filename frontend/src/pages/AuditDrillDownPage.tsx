import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ClipboardDocumentListIcon } from '@heroicons/react/24/outline';
import { auditApi, userApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import type { AuditLogEntry } from '../types';

interface UserOption {
  id: string;
  username: string;
  full_name?: string;
}

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AuditDrillDownPage() {
  const canViewAudit = useAuthStore((s) => s.hasPermission('audit', 'view'));
  const [userId, setUserId] = useState('');

  const { data: usersData } = useQuery({
    queryKey: ['users', 'audit'],
    queryFn: () => userApi.getUsers({ page_size: 100, is_active: true }),
    enabled: canViewAudit,
  });

  const {
    data: activity,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['user-activity', userId],
    queryFn: () => auditApi.getUserActivity(userId, 100),
    enabled: canViewAudit && !!userId,
  });

  if (!canViewAudit) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <h1 className="text-lg font-semibold text-amber-900">Audit Drill-Down</h1>
        <p className="mt-2 text-sm text-amber-800">
          This view requires the <code>audit:view</code> permission.
        </p>
      </div>
    );
  }

  const users: UserOption[] = usersData?.items ?? [];
  const events: AuditLogEntry[] = activity ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <ClipboardDocumentListIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
          Audit Drill-Down
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Per-user activity trails from the immutable audit log. Item-level view trails ("who viewed
          which check") are available from each check's review screen.
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <label className="block max-w-sm text-sm">
          <span className="text-gray-700">User</span>
          <select
            className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          >
            <option value="">Select a user…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.username} ({u.username})
              </option>
            ))}
          </select>
        </label>
      </div>

      {userId && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-100 px-5 py-3">
            <h2 className="text-sm font-semibold text-gray-900">Recent activity</h2>
          </div>

          {isLoading && <div className="p-6 text-sm text-gray-500">Loading activity…</div>}

          {isError && !isLoading && (
            <div className="p-6 text-center">
              <p className="text-sm text-red-800">Could not load activity.</p>
              <button
                onClick={() => refetch()}
                className="mt-2 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
              >
                Retry
              </button>
            </div>
          )}

          {!isLoading && !isError && events.length === 0 && (
            <div className="p-10 text-center text-sm text-gray-500">No recorded activity.</div>
          )}

          {events.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-500">
                    <th className="px-5 py-2 font-medium">When</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Resource</th>
                    <th className="px-3 py-2 font-medium">Detail</th>
                    <th className="px-3 py-2 font-medium">IP</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.id} className="border-t border-gray-100">
                      <td className="whitespace-nowrap px-5 py-2 text-gray-500">
                        {new Date(e.timestamp).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                          {titleCase(e.action)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-700">{titleCase(e.resource_type)}</td>
                      <td className="px-3 py-2 text-gray-600">{e.description ?? '—'}</td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500">
                        {e.ip_address ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
