import clsx from 'clsx';
import { CheckStatus, RiskLevel, ItemType } from '../../types';

interface ItemTypeBadgeProps {
  itemType: ItemType;
}

const itemTypeConfig: Record<ItemType, { label: string; description: string; className: string }> = {
  on_us: {
    label: 'On Us',
    description: 'Check drawn on our customer',
    className: 'bg-blue-100 text-blue-800 border border-blue-300',
  },
  transit: {
    label: 'Transit',
    description: 'Check deposited by our customer',
    className: 'bg-emerald-100 text-emerald-800 border border-emerald-300',
  },
};

export function ItemTypeBadge({ itemType }: ItemTypeBadgeProps) {
  const config = itemTypeConfig[itemType];
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold',
        config.className
      )}
      title={config.description}
    >
      {config.label}
    </span>
  );
}

interface StatusBadgeProps {
  status: CheckStatus;
}

const statusLabels: Record<CheckStatus, string> = {
  new: 'New',
  in_review: 'In Review',
  escalated: 'Escalated',
  pending_approval: 'Pending Approval',
  pending_dual_control: 'Pending Dual Control',
  approved: 'Approved',
  rejected: 'Rejected',
  returned: 'Returned',
  closed: 'Closed',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        `status-${status}`
      )}
    >
      {statusLabels[status]}
    </span>
  );
}

interface RiskBadgeProps {
  level: RiskLevel;
}

const riskLabels: Record<RiskLevel, string> = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
  critical: 'Critical',
};

export function RiskBadge({ level }: RiskBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        `risk-${level}`
      )}
    >
      {riskLabels[level]}
    </span>
  );
}

interface SLABadgeProps {
  dueAt: string | null | undefined;
  breached: boolean;
}

export function SLABadge({ dueAt, breached }: SLABadgeProps) {
  if (!dueAt) return null;

  const dueDate = new Date(dueAt);
  const now = new Date();
  const hoursRemaining = (dueDate.getTime() - now.getTime()) / (1000 * 60 * 60);

  if (breached) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 sla-warning">
        SLA Breached
      </span>
    );
  }

  if (hoursRemaining < 1) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 sla-warning">
        Due Soon
      </span>
    );
  }

  return null;
}
