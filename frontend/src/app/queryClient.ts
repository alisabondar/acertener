import { QueryClient } from "@tanstack/react-query";

import { ApiProblem } from "@/api/errors";

/** Results stay in memory only (never persisted): they can contain patient data. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx won't fix itself on retry; network blips and 5xx get one more try.
      retry: (failures, error) =>
        !(error instanceof ApiProblem && error.status < 500) && failures < 1,
      refetchOnWindowFocus: false,
    },
  },
});
