import clsx from 'clsx';
import { CheckStatus, RiskLevel } from '../../types';

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
