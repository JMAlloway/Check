// Tokens that should stay fully uppercase when humanizing snake_case labels
// (banking / system acronyms). Keyed by the lowercased token.
const ACRONYMS: Record<string, string> = {
  atm: 'ATM',
  rdc: 'RDC',
  ach: 'ACH',
  sla: 'SLA',
  micr: 'MICR',
  pii: 'PII',
  ip: 'IP',
  id: 'ID',
  api: 'API',
  sftp: 'SFTP',
  csv: 'CSV',
  pdf: 'PDF',
  ai: 'AI',
};

/**
 * Turn a snake_case / lower-case value into a human label, keeping known
 * acronyms (ATM, RDC, ACH, …) fully uppercase. e.g. "atm" -> "ATM",
 * "account_takeover" -> "Account Takeover", "rdc" -> "RDC".
 */
export function humanizeLabel(value: string): string {
  if (!value) return value;
  return value
    .split(/[\s_]+/)
    .map((word) => {
      const lower = word.toLowerCase();
      if (ACRONYMS[lower]) return ACRONYMS[lower];
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}
