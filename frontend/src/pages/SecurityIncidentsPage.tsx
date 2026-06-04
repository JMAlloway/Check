import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ShieldExclamationIcon,
  PlusIcon,
  ClockIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { securityApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { useFocusTrap } from '../hooks/useFocusTrap';
import type { SecurityIncident } from '../types';

const SEVERITY_TONE: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-amber-100 text-amber-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

const STATUS_TONE: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  confirmed: 'bg-blue-100 text-blue-800',
  contained: 'bg-amber-100 text-amber-800',
  resolved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-500',
};

const INCIDENT_TYPES = [
  'unauthorized_access',
  'data_breach',
  'account_compromise',
  'insider_threat',
  'malware',
  'phishing',
  'denial_of_service',
  'data_loss',
  'policy_violation',
  'suspicious_activity',
  'audit_failure',
  'other',
];

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// A regulatory notification deadline that has passed on an unresolved incident
// is a compliance breach — surface it in red rather than plain gray.
function DeadlineBadge({ deadline, status }: { deadline: string; status: string }) {
  const overdue = new Date(deadline).getTime() < Date.now() && status !== 'resolved';
  return (
    <span className={overdue ? 'font-semibold text-red-600' : undefined}>
      {overdue ? 'Overdue — deadline ' : 'Deadline '}
      {new Date(deadline).toLocaleString()}
    </span>
  );
}

// Returns the next lifecycle action available for a given status, or null.
function nextAction(status: string): { key: 'confirm' | 'contain' | 'resolve'; label: string } | null {
  if (status === 'draft') return { key: 'confirm', label: 'Confirm' };
  if (status === 'confirmed') return { key: 'contain', label: 'Mark contained' };
  if (status === 'contained') return { key: 'resolve', label: 'Resolve' };
  return null;
}

export default function SecurityIncidentsPage() {
  const queryClient = useQueryClient();
  const isSuperuser = useAuthStore((s) => s.user?.is_superuser ?? false);
  const [showCreate, setShowCreate] = useState(false);
  const [action, setAction] = useState<{ incident: SecurityIncident; key: string } | null>(null);
  const [timelineId, setTimelineId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['security-incidents'],
    queryFn: securityApi.listIncidents,
    enabled: isSuperuser,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['security-incidents'] });

  if (!isSuperuser) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <h1 className="text-lg font-semibold text-amber-900">Security Incidents</h1>
        <p className="mt-2 text-sm text-amber-800">
          Incident management and breach-notification workflows require administrator (superuser)
          privileges. Sign in as <code>system_admin_demo</code> to use this screen.
        </p>
      </div>
    );
  }

  const incidents = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ShieldExclamationIcon className="h-7 w-7 text-primary-600" aria-hidden="true" />
            Security Incidents
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Track incidents through their lifecycle (draft → confirmed → contained → resolved) with
            regulatory breach-notification deadlines.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <ArrowPathIcon className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
          >
            <PlusIcon className="h-4 w-4" aria-hidden="true" />
            Report incident
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-5">
              <div className="h-4 w-1/3 rounded bg-gray-200" />
              <div className="mt-3 h-3 w-2/3 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      )}

      {isError && !isLoading && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">Could not load incidents.</p>
          <button
            onClick={() => refetch()}
            className="mt-3 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && !isError && incidents.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-10 text-center">
          <ShieldExclamationIcon className="mx-auto h-10 w-10 text-gray-400" aria-hidden="true" />
          <h3 className="mt-3 text-sm font-semibold text-gray-900">No active incidents</h3>
          <p className="mt-1 text-sm text-gray-600">Report one to start the workflow.</p>
        </div>
      )}

      {!isLoading && !isError && incidents.length > 0 && (
        <div className="space-y-3">
          {incidents.map((inc) => {
            const na = nextAction(inc.status);
            return (
              <div key={inc.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${SEVERITY_TONE[inc.severity] ?? SEVERITY_TONE.low}`}>
                        {titleCase(inc.severity)}
                      </span>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[inc.status] ?? STATUS_TONE.draft}`}>
                        {titleCase(inc.status)}
                      </span>
                      <span className="text-xs text-gray-500">{titleCase(inc.incident_type)}</span>
                    </div>
                    <h3 className="mt-1.5 text-sm font-semibold text-gray-900">{inc.title}</h3>
                    <p className="mt-1 max-w-2xl text-sm text-gray-600">{inc.description}</p>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
                      <span>Discovered {new Date(inc.discovered_at).toLocaleDateString()}</span>
                      {inc.affected_users_count != null && <span>{inc.affected_users_count} users</span>}
                      {inc.affected_records_count != null && (
                        <span>{inc.affected_records_count.toLocaleString()} records</span>
                      )}
                      {inc.requires_regulator_notification && (
                        <span className="text-red-600">Regulator notification required</span>
                      )}
                      {inc.requires_customer_notification && (
                        <span className="text-orange-600">Customer notification required</span>
                      )}
                      {inc.notification_deadline && (
                        <DeadlineBadge deadline={inc.notification_deadline} status={inc.status} />
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    {na && (
                      <button
                        onClick={() => setAction({ incident: inc, key: na.key })}
                        className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700"
                      >
                        {na.label}
                      </button>
                    )}
                    <button
                      onClick={() => setTimelineId(inc.id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary-700 hover:underline"
                    >
                      <ClockIcon className="h-4 w-4" aria-hidden="true" />
                      Timeline
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showCreate && (
        <CreateIncidentModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            invalidate();
          }}
        />
      )}

      {action && (
        <LifecycleActionModal
          incident={action.incident}
          actionKey={action.key as 'confirm' | 'contain' | 'resolve'}
          onClose={() => setAction(null)}
          onDone={() => {
            setAction(null);
            invalidate();
          }}
        />
      )}

      {timelineId && (
        <TimelineModal incidentId={timelineId} onClose={() => setTimelineId(null)} />
      )}
    </div>
  );
}

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(true, onClose);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        ref={trapRef}
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
      >
        <h2 className="mb-4 text-base font-semibold text-gray-900">{title}</h2>
        {children}
        <div className="mt-4 flex justify-end">
          <button onClick={onClose} className="text-sm font-medium text-gray-500 hover:text-gray-700">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateIncidentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    incident_type: 'suspicious_activity',
    severity: 'medium',
    title: '',
    description: '',
  });

  const create = useMutation({
    mutationFn: () =>
      securityApi.createIncident({
        ...form,
        discovered_at: new Date().toISOString(),
      }),
    onSuccess: () => {
      toast.success('Incident reported');
      onCreated();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Failed to create incident');
    },
  });

  const valid = form.title.trim().length >= 5 && form.description.trim().length >= 10;

  return (
    <ModalShell title="Report security incident" onClose={onClose}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-gray-700">Type</span>
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
              value={form.incident_type}
              onChange={(e) => setForm({ ...form, incident_type: e.target.value })}
            >
              {INCIDENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {titleCase(t)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-700">Severity</span>
            <select
              className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
              value={form.severity}
              onChange={(e) => setForm({ ...form, severity: e.target.value })}
            >
              {['low', 'medium', 'high', 'critical'].map((s) => (
                <option key={s} value={s}>
                  {titleCase(s)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          <span className="text-gray-700">Title</span>
          <input
            className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Short summary (min 5 chars)"
          />
        </label>
        <label className="block text-sm">
          <span className="text-gray-700">Description</span>
          <textarea
            className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
            rows={4}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="What happened (min 10 chars)"
          />
        </label>
        <button
          onClick={() => create.mutate()}
          disabled={!valid || create.isPending}
          className="w-full rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {create.isPending ? 'Reporting…' : 'Report incident'}
        </button>
      </div>
    </ModalShell>
  );
}

function LifecycleActionModal({
  incident,
  actionKey,
  onClose,
  onDone,
}: {
  incident: SecurityIncident;
  actionKey: 'confirm' | 'contain' | 'resolve';
  onClose: () => void;
  onDone: () => void;
}) {
  const [text, setText] = useState('');
  const config = {
    confirm: {
      title: 'Confirm incident',
      label: 'Root cause (optional)',
      required: false,
      run: () => securityApi.confirmIncident(incident.id, text || undefined),
    },
    contain: {
      title: 'Mark incident contained',
      label: 'Containment actions taken (min 10 chars)',
      required: true,
      run: () => securityApi.containIncident(incident.id, text),
    },
    resolve: {
      title: 'Resolve incident',
      label: 'Remediation steps (min 10 chars)',
      required: true,
      run: () => securityApi.resolveIncident(incident.id, text),
    },
  }[actionKey];

  const mut = useMutation({
    mutationFn: config.run,
    onSuccess: () => {
      toast.success('Incident updated');
      onDone();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Action failed');
    },
  });

  const valid = !config.required || text.trim().length >= 10;

  return (
    <ModalShell title={config.title} onClose={onClose}>
      <p className="mb-2 text-sm text-gray-600">{incident.title}</p>
      <label className="block text-sm">
        <span className="text-gray-700">{config.label}</span>
        <textarea
          className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      <button
        onClick={() => mut.mutate()}
        disabled={!valid || mut.isPending}
        className="mt-3 w-full rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
      >
        {mut.isPending ? 'Working…' : config.title}
      </button>
    </ModalShell>
  );
}

function TimelineModal({ incidentId, onClose }: { incidentId: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['incident-timeline', incidentId],
    queryFn: () => securityApi.getTimeline(incidentId),
  });

  return (
    <ModalShell title="Incident timeline" onClose={onClose}>
      {isLoading && <p className="text-sm text-gray-500">Loading timeline…</p>}
      {isError && <p className="text-sm text-red-700">Could not load timeline.</p>}
      {data && (
        <ol className="space-y-3 border-l border-gray-200 pl-4">
          {data.length === 0 && <p className="text-sm text-gray-500">No timeline entries.</p>}
          {data.map((e) => (
            <li key={e.id} className="relative">
              <span className="absolute -left-[1.3rem] top-1 h-2.5 w-2.5 rounded-full bg-primary-500" />
              <p className="text-sm text-gray-900">{e.content}</p>
              <p className="text-xs text-gray-500">{new Date(e.created_at).toLocaleString()}</p>
            </li>
          ))}
        </ol>
      )}
    </ModalShell>
  );
}
