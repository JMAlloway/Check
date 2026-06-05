// Safe date formatting helpers. These guard against null/invalid inputs so the
// UI shows a neutral placeholder instead of "Invalid Date".

/**
 * Format a date value as a locale date string (e.g. "1/2/2026"), returning the
 * given fallback for null/undefined/unparseable values.
 */
export function formatDate(value: string | number | Date | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? fallback : d.toLocaleDateString();
}
