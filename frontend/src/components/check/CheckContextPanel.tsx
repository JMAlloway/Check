import { CheckItem, AccountContext } from '../../types';
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
    <div className={clsx('flex justify-between py-1', highlight && 'bg-yellow-50')}>
      <span className="text-gray-500 text-sm">{label}</span>
      <span className={clsx('font-medium text-sm', highlight ? 'text-yellow-700' : 'text-gray-900')}>
        {value}
      </span>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-sm font-semibold text-gray-700 mb-2 mt-4 first:mt-0">{children}</h4>
  );
}

export default function CheckContextPanel({ item }: CheckContextPanelProps) {
  const ctx = item.account_context;
  const amountRatio = ctx?.amount_vs_avg_ratio;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full overflow-y-auto">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Item Context</h3>

      {/* Check Details */}
      <SectionTitle>Check Details</SectionTitle>
      <div className="space-y-1">
        <ContextRow label="Amount" value={formatCurrency(item.amount)} />
        <ContextRow label="Check #" value={item.check_number || '-'} />
        <ContextRow label="Payee" value={item.payee_name || '-'} />
        <ContextRow label="Memo" value={item.memo || '-'} />
        <ContextRow label="Check Date" value={item.check_date ? new Date(item.check_date).toLocaleDateString() : '-'} />
        <ContextRow label="Presented" value={new Date(item.presented_date).toLocaleString()} />
      </div>

      {/* Account Information */}
      <SectionTitle>Account Information</SectionTitle>
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

      {/* Check Behavior */}
      <SectionTitle>Check Behavior</SectionTitle>
      <div className="space-y-1">
        <ContextRow
          label="Avg Check (30d)"
          value={formatCurrency(ctx?.avg_check_amount_30d)}
        />
        <ContextRow
          label="Avg Check (90d)"
          value={formatCurrency(ctx?.avg_check_amount_90d)}
        />
        <ContextRow
          label="Max Check (90d)"
          value={formatCurrency(ctx?.max_check_amount_90d)}
        />
        <ContextRow
          label="Std Dev (30d)"
          value={formatCurrency(ctx?.check_std_dev_30d)}
        />
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

      {/* Risk History */}
      <SectionTitle>Risk History</SectionTitle>
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

      {/* AI Flags */}
      {item.ai_flags.length > 0 && (
        <>
          <SectionTitle>AI Flags</SectionTitle>
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
                <div className="font-medium">
                  {flag.description}
                </div>
                {flag.explanation && (
                  <div className="text-gray-600 mt-1">{flag.explanation}</div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Workflow Info */}
      <SectionTitle>Workflow</SectionTitle>
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

      {/* Source Info */}
      <SectionTitle>Source</SectionTitle>
      <div className="space-y-1 text-xs text-gray-500">
        <div>Item ID: {item.external_item_id}</div>
        <div>Source: {item.source_system}</div>
        {item.micr_line && <div>MICR: {item.micr_line}</div>}
      </div>
    </div>
  );
}
