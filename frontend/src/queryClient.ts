import { QueryClient } from '@tanstack/react-query';

// Single shared QueryClient instance. Exported from its own module (rather than
// being created inline in main.tsx) so non-React modules - e.g. the axios
// logout path and the Layout logout handler - can clear cached data on logout.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});
