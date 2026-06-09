/**
 * Dev-only error logging. Keeps the browser console clean in production
 * builds (and demos) while preserving diagnostics during development.
 */
export function logError(message: string, ...details: unknown[]): void {
  if (import.meta.env.DEV) {
    console.error(message, ...details);
  }
}
