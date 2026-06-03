import { useQuery } from '@tanstack/react-query';
import {
  ServerStackIcon,
  ArrowsRightLeftIcon,
  ShieldExclamationIcon,
  LockClosedIcon,
  DocumentCheckIcon,
  ClipboardDocumentListIcon,
  ChartBarSquareIcon,
} from '@heroicons/react/24/outline';
import { api } from '../services/api';

/**
 * Operations Hub
 *
 * Surfaces platform capabilities whose backends are implemented but did not yet
 * have a dedicated screen. Each card pulls live data from its endpoint when
 * available, and otherwise shows a clear "preview" placeholder so every feature
 * is at least demoable and discoverable. As full screens are built, these cards
 * can link out to them.
 */

interface Capability {
  key: string;
  title: string;
  description: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  endpoint?: string;
  // Given the raw endpoint payload, return a short status string to display.
  summarize?: (data: unknown) => string;
}

function countOf(data: unknown): number {
  if (Array.isArray(data)) return data.length;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    for (const k of ['total', 'total_alerts', 'total_archived', 'count']) {
      if (typeof obj[k] === 'number') return obj[k] as number;
    }
    if (Array.isArray(obj.items)) return (obj.items as unknown[]).length;
    if (Array.isArray(obj.incidents)) return (obj.incidents as unknown[]).length;
    if (Array.isArray(obj.batches)) return (obj.batches as unknown[]).length;
  }
  return 0;
}

const CAPABILITIES: Capability[] = [
  {
    key: 'connector-b',
    title: 'Commit Connector (Connector B)',
    description:
      'Outbound batch return/commit of decisions to the core: batch creation, dual-control approval, transmission, acknowledgement and reconciliation.',
    icon: ArrowsRightLeftIcon,
    endpoint: '/connector/dashboard',
    summarize: () => 'Backend ready',
  },
  {
    key: 'connector-c',
    title: 'Item Context Connector (Connector C)',
    description:
      'Inbound SFTP item-context feeds that enrich checks with account tenure, balances and behavior. Configure connectors, map fields and schedule imports.',
    icon: ServerStackIcon,
    endpoint: '/item_context_connectors',
    summarize: (d) => `${countOf(d)} connector(s)`,
  },
  {
    key: 'security',
    title: 'Security Incidents & Breach Notification',
    description:
      'Track security incidents through their lifecycle (draft → confirmed → contained → resolved) with regulatory breach-notification support and timelines.',
    icon: ShieldExclamationIcon,
    endpoint: '/security/incidents',
    summarize: (d) => `${countOf(d)} incident(s)`,
  },
  {
    key: 'evidence',
    title: 'Evidence Chain Verification',
    description:
      'Cryptographic, tamper-evident sealing of every decision. Each decision is hash-chained to the prior one and can be verified on demand from the audit trail.',
    icon: DocumentCheckIcon,
    summarize: () => 'Per-decision verify',
  },
  {
    key: 'audit-activity',
    title: 'Audit Drill-Down',
    description:
      'Who viewed which item and when, plus per-user activity trails — beyond the searchable audit log.',
    icon: ClipboardDocumentListIcon,
    endpoint: '/audit/logs?page_size=1',
    summarize: (d) => `${countOf(d)} audit events`,
  },
  {
    key: 'mfa',
    title: 'Multi-Factor Authentication',
    description:
      'TOTP-based MFA enrollment and verification for privileged users (setup, verify, disable). Pairs with the 6-role RBAC model.',
    icon: LockClosedIcon,
    summarize: () => 'TOTP ready',
  },
  {
    key: 'monitoring',
    title: 'Monitoring Quick Links',
    description:
      'Operational dashboards and runbooks: Grafana, Prometheus and Alertmanager links plus rollback / DR / capacity guides.',
    icon: ChartBarSquareIcon,
    endpoint: '/operations/quick-links',
    summarize: () => 'Configured',
  },
];

function CapabilityCard({ capability }: { capability: Capability }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ops-capability', capability.key],
    queryFn: async () => {
      if (!capability.endpoint) return null;
      const res = await api.get(capability.endpoint);
      return res.data;
    },
    retry: false,
    staleTime: 60_000,
  });

  let status: string;
  let tone: 'live' | 'preview' = 'preview';
  if (!capability.endpoint) {
    status = capability.summarize ? capability.summarize(null) : 'Preview';
  } else if (isLoading) {
    status = 'Loading…';
  } else if (isError) {
    status = 'Preview — UI coming soon';
  } else {
    status = capability.summarize ? capability.summarize(data) : 'Available';
    tone = 'live';
  }

  const Icon = capability.icon;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm flex flex-col">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-primary-50 p-2 text-primary-700">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-gray-900">{capability.title}</h3>
          <span
            className={
              'mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ' +
              (tone === 'live'
                ? 'bg-green-100 text-green-800'
                : 'bg-amber-100 text-amber-800')
            }
          >
            {status}
          </span>
        </div>
      </div>
      <p className="mt-3 text-sm text-gray-600">{capability.description}</p>
    </div>
  );
}

export default function OperationsHubPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Operations Hub</h1>
        <p className="mt-1 text-sm text-gray-600">
          Platform capabilities and integrations. Cards marked{' '}
          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
            live
          </span>{' '}
          are serving real data; those marked{' '}
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            preview
          </span>{' '}
          have a working backend with a dedicated screen on the roadmap.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map((c) => (
          <CapabilityCard key={c.key} capability={c} />
        ))}
      </div>
    </div>
  );
}
