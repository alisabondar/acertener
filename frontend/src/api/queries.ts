import { useQuery, type QueryKey, type UseQueryResult } from "@tanstack/react-query";

import type { components, paths } from "./schema";

type PatientListParams = NonNullable<paths["/api/v1/patients"]["get"]["parameters"]["query"]>;
type Scope = components["schemas"]["Scope"];
type SearchTerms = components["schemas"]["SearchTerms"];

/**
 * Query keys, grouped so a whole area can be invalidated at once
 * (e.g. every patient query after a write: queryKeys.patients.all).
 */
export const queryKeys = {
  me: (personaId: string) => ["me", personaId] as const,
  personas: () => ["personas"] as const,
  patients: {
    all: ["patients"] as const,
    list: (params: PatientListParams) => ["patients", "list", params] as const,
    /** Identifying terms live only in this in-memory key and the request body, never the URL. */
    search: (params: PatientListParams, terms: SearchTerms) =>
      ["patients", "search", params, terms] as const,
    counts: (scope: Scope) => ["patients", "counts", scope] as const,
    detail: (id: string) => ["patients", "detail", id] as const,
  },
};

/**
 * TanStack Query over an openapi-fetch call. Errors arrive already typed (ApiProblem or
 * NetworkError) because the client middleware throws them. Pass `signal`
 * to the call so a cancelled or superseded query aborts its request.
 */
export function useApiQuery<T>(
  queryKey: QueryKey,
  call: (signal: AbortSignal) => Promise<{ data?: T }>,
  {
    enabled = true,
    keepPrevious = false,
  }: {
    enabled?: boolean;
    /** While a new key loads, keep returning the previous key's data (isPlaceholderData). */
    keepPrevious?: boolean;
  } = {},
): UseQueryResult<T> {
  return useQuery<T>({
    queryKey,
    enabled,
    placeholderData: (previous) => (keepPrevious ? previous : undefined),
    queryFn: apiQueryFn(call),
  });
}

/** A TanStack query function over an openapi-fetch call; also usable for prefetching. */
export function apiQueryFn<T>(call: (signal: AbortSignal) => Promise<{ data?: T }>) {
  return async ({ signal }: { signal: AbortSignal }): Promise<T> => {
    const { data } = await call(signal);
    if (data === undefined) throw new Error("The API returned no data");
    return data;
  };
}
