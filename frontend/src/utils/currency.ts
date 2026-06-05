// Shared currency formatter so every screen renders amounts identically
// (USD, grouped thousands, two decimals). Prefer this over ad-hoc
// `$${amount.toLocaleString()}` which drops the cents and can diverge between
// screens.
const USD = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

/**
 * Format a numeric amount as USD currency, e.g. 1234.5 -> "$1,234.50".
 * Non-finite values render as "$0.00".
 */
export function formatCurrency(amount: number): string {
  if (!Number.isFinite(amount)) return USD.format(0);
  return USD.format(amount);
}
