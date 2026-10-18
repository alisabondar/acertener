import { useQuery, type QueryKey, type UseQueryResult } from "@tanstack/react-query";

import type { components, paths } from "./schema";

type PatientListParams = NonNullable<paths["/api/v1/patients"]["get"]["parameters"]["query"]>;
type Scope = components["schemas"]["Scope"];

/**
 * Query keys, grouped so a whole area can be invalidated at once
 * (e.g. every patient query after a write: queryKeys.patients.all).
 */
export const queryKeys = {
  me: () => ["me"] as const,
  personas: () => ["personas"] as const,
  patients: {
    all: ["patients"] as const,
    list: (params: PatientListParams) => ["patients", "list", params] as const,
    counts: (scope: Scope) => ["patients", "counts", scope] as const,
    detail: (id: string) => ["patients", "detail", id] as const,
  },
};

/**
 * TanStack Query over an openapi-fetch call. Errors arrive already typed (ApiProblem,
 * DemoModeOffError, NetworkError) because the client middleware throws them. Pass `signal`
 * to the call so a cancelled or superseded query aborts its request.
 */
export function useApiQuery<T>(
  queryKey: QueryKey,
  call: (signal: AbortSignal) => Promise<{ data?: T }>,
): UseQueryResult<T> {
  return useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      const { data } = await call(signal);
      if (data === undefined) throw new Error("The API returned no data");
      return data;
    },
  });
}
