import { useState } from 'react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import { CheckItem } from '../../types';
import { ItemTypeBadge } from '../common/StatusBadge';
import clsx from 'clsx';

interface CheckContextPanelProps {
  item: CheckItem;
}

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

function formatNumber(num: number | undefined): string {
  if (num === undefined) return '-';
  return new Intl.NumberFormat('en-US').format(num);
}

function ContextRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={clsx('flex justify-between gap-3 py-1', highlight && 'bg-yellow-50')}>
      <span className="text-gray-500 text-sm shrink-0">{label}</span>
      <span className={clsx('font-medium text-sm text-right break-words', highlight ? 'text-yellow-700' : 'text-gray-900')}>
        {value}
      </span>
    </div>
  );
}

/**
 * Collapsible section. Sections whose facts are already visible on the check
 * image itself (Check Details) or in the page header (Workflow) default to
 * collapsed; the account-context sections - the data a reviewer can't get
 * from the image - default to open.
 */
function Section({
  title,
  defaultOpen = false,
  badge,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-2 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          {title}
          {badge}
        </span>
        <ChevronDownIcon
          className={clsx('h-4 w-4 text-gray-400 transition-transform', open && 'rotate-180')}
        />
      </button>
      {open && <div className="pb-3">{children}</div>}
    </div>
  );
}

export default function CheckContextPanel({ item }: CheckContextPanelProps) {
  const ctx = item.account_context;
  const amountRatio = ctx?.amount_vs_avg_ratio;
  const riskHistoryFlagged =
    (ctx?.returned_item_count_90d ?? 0) > 0 || (ctx?.exception_count_90d ?? 0) > 2;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full overflow-y-auto">
      <h3 className="text-lg font-semibold text-gray-900 mb-2">Item Context</h3>

      {/* Risk Signals first - the panel's most decision-relevant content */}
      {item.ai_flags.length > 0 && (
        <Section
          title="Risk Signals"
          defaultOpen
          badge={
            <span className="rounded-full bg-yellow-100 px-1.5 py-0.5 text-[10px] font-semibold text-yellow-800">
              {item.ai_flags.length}
            </span>
          }
        >
          <div className="space-y-2">
            {item.ai_flags.map((flag) => (
              <div
                key={flag.code}
                className={clsx(
                  'p-2 rounded text-sm',
                  flag.severity === 'alert' && 'bg-red-50 border border-red-200',
                  flag.severity === 'warning' && 'bg-yellow-50 border border-yellow-200',
                  flag.severity === 'info' && 'bg-blue-50 border border-blue-200'
                )}
              >
                <div className="font-medium">{flag.description}</div>
                {flag.explanation && (
                  <div className="text-gray-600 mt-1">{flag.explanation}</div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Account Information" defaultOpen>
        <div className="space-y-1">
          <ContextRow label="Account" value={item.account_number_masked} />
          <ContextRow
            label="Type"
            value={item.account_type.charAt(0).toUpperCase() + item.account_type.slice(1)}
          />
          <ContextRow
            label="Tenure"
            value={ctx?.account_tenure_days ? `${ctx.account_tenure_days} days` : '-'}
            highlight={ctx?.account_tenure_days !== undefined && ctx.account_tenure_days < 30}
          />
          <ContextRow label="Current Balance" value={formatCurrency(ctx?.current_balance)} />
          <ContextRow label="Avg Balance (30d)" value={formatCurrency(ctx?.average_balance_30d)} />
        </div>
      </Section>

      <Section title="Check Behavior" defaultOpen>
        <div className="space-y-1">
          <ContextRow label="Avg Check (30d)" value={formatCurrency(ctx?.avg_check_amount_30d)} />
          <ContextRow label="Avg Check (90d)" value={formatCurrency(ctx?.avg_check_amount_90d)} />
          <ContextRow label="Max Check (90d)" value={formatCurrency(ctx?.max_check_amount_90d)} />
          <ContextRow label="Std Dev (30d)" value={formatCurrency(ctx?.check_std_dev_30d)} />
          <ContextRow
            label="Frequency (30d)"
            value={ctx?.check_frequency_30d ? `${ctx.check_frequency_30d} checks` : '-'}
          />
          <ContextRow
            label="Amount vs Avg"
            value={amountRatio ? `${amountRatio.toFixed(1)}x` : '-'}
            highlight={amountRatio !== undefined && amountRatio > 3}
          />
        </div>
      </Section>

      <Section
        title="Risk History"
        defaultOpen={riskHistoryFlagged}
        badge={
          riskHistoryFlagged ? (
            <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700">
              !
            </span>
          ) : undefined
        }
      >
        <div className="space-y-1">
          <ContextRow
            label="Returned Items (90d)"
            value={formatNumber(ctx?.returned_item_count_90d)}
            highlight={ctx?.returned_item_count_90d !== undefined && ctx.returned_item_count_90d > 0}
          />
          <ContextRow
            label="Exceptions (90d)"
            value={formatNumber(ctx?.exception_count_90d)}
            highlight={ctx?.exception_count_90d !== undefined && ctx.exception_count_90d > 2}
          />
        </div>
      </Section>

      {/* Collapsed by default: these facts are readable on the check image itself */}
      <Section title="Check Details">
        <div className="space-y-1">
          <div className="flex justify-between py-1">
            <span className="text-gray-500 text-sm">Type</span>
            <ItemTypeBadge itemType={item.item_type} />
          </div>
          <ContextRow label="Amount" value={formatCurrency(item.amount)} />
          <ContextRow label="Check #" value={item.check_number || '-'} />
          <ContextRow label="Payee" value={item.payee_name || '-'} />
          <ContextRow label="Memo" value={item.memo || '-'} />
          <ContextRow
            label="Check Date"
            value={item.check_date ? new Date(item.check_date).toLocaleDateString() : '-'}
          />
          <ContextRow label="Presented" value={new Date(item.presented_date).toLocaleString()} />
        </div>
      </Section>

      {/* Collapsed by default: status/risk/dual-control already shown as header badges */}
      <Section title="Workflow">
        <div className="space-y-1">
          <ContextRow label="Status" value={item.status.replace('_', ' ').toUpperCase()} />
          <ContextRow
            label="Risk Level"
            value={item.risk_level.toUpperCase()}
            highlight={item.risk_level === 'high' || item.risk_level === 'critical'}
          />
          <ContextRow
            label="Dual Control"
            value={item.requires_dual_control ? 'Required' : 'Not Required'}
          />
          {item.sla_due_at && (
            <ContextRow
              label="SLA Due"
              value={new Date(item.sla_due_at).toLocaleString()}
              highlight={item.sla_breached}
            />
          )}
        </div>
      </Section>

      <Section title="Source">
        <div className="space-y-1 text-xs text-gray-500">
          <div>Item ID: {item.external_item_id}</div>
          <div>Source: {item.source_system}</div>
          {item.micr_line && <div>MICR: {item.micr_line}</div>}
        </div>
      </Section>
    </div>
  );
}
