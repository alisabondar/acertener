import {
  type QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { ApiProblem } from "./errors";

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
  visits: {
    today: (scope: Scope, day: string) => ["visits", "today", scope, day] as const,
  },
  patients: {
    all: ["patients"] as const,
    list: (params: PatientListParams) => ["patients", "list", params] as const,
    /** Identifying terms live only in this in-memory key and the request body, never the URL. */
    search: (params: PatientListParams, terms: SearchTerms) =>
      ["patients", "search", params, terms] as const,
    counts: (scope: Scope) => ["patients", "counts", scope] as const,
    detail: (id: string) => ["patients", "detail", id] as const,
    /** One part of a chart; `chart(id)` alone matches every part, for invalidating after writes. */
    chart: (id: string, part?: "notes" | "vitals" | "allergies" | "conditions" | "access") =>
      part ? (["patients", "chart", id, part] as const) : (["patients", "chart", id] as const),
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
    refetchInterval,
  }: {
    enabled?: boolean;
    /** Re-fetch this often (ms) while the page is open, for data other people change. */
    refetchInterval?: number;
    /** While a new key loads, keep returning the previous key's data (isPlaceholderData). */
    keepPrevious?: boolean;
  } = {},
): UseQueryResult<T> {
  return useQuery<T>({
    queryKey,
    enabled,
    ...(refetchInterval !== undefined && { refetchInterval }),
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

/**
 * A write over an openapi-fetch call. On success it refreshes `invalidate` (and anything
 * under those keys), so screens show the saved state rather than a local guess.
 */
export function useApiMutation<TVars, T = unknown>(
  call: (vars: TVars) => Promise<{ data?: T }>,
  { invalidate }: { invalidate: QueryKey[] },
): UseMutationResult<T | undefined, Error, TVars> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (vars: TVars) => (await call(vars)).data,
    onSuccess: () =>
      Promise.all(invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
}

/** Field errors from a 422 (`errors`, keyed by field name), or none. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiProblem)) return {};
  const errors = error.extras["errors"];
  return errors && typeof errors === "object" ? (errors as Record<string, string>) : {};
}
