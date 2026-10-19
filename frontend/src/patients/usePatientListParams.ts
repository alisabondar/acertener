import { useCallback, useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "react-router";
import { z } from "zod";

import type { components, paths } from "@/api/schema";

type Schemas = components["schemas"];
type Scope = Schemas["Scope"];

/** The list's URL state: exactly the non-identifying query params GET /patients accepts. */
export type PatientListParams = Required<
  NonNullable<paths["/api/v1/patients"]["get"]["parameters"]["query"]>
>;

export const DEFAULT_LIST_PARAMS: PatientListParams = {
  scope: "my",
  filter: null,
  status: null,
  include_archived: false,
  sort: "last_visit",
  order: "desc",
  page: 1,
  page_size: 20,
};

/** Every value of a generated enum; the Record type fails to compile if the API adds or drops one. */
function values<T extends string>(all: Record<T, true>): [T, ...T[]] {
  return Object.keys(all) as [T, ...T[]];
}

// Each field falls back on its own, so one bad value doesn't discard the rest of the URL.
function schemaFor(defaults: PatientListParams) {
  return z.object({
    scope: z.enum(values<Scope>({ my: true, all: true })).catch(defaults.scope),
    filter: z
      .enum(values<Schemas["QuickFilter"]>({ today_visits: true }))
      .nullable()
      .catch(null),
    status: z
      .enum(values<Schemas["PatientStatus"]>({ active: true, inactive: true, deceased: true }))
      .nullable()
      .catch(null),
    include_archived: z
      .enum(["true", "false"])
      .transform((value) => value === "true")
      .catch(defaults.include_archived),
    sort: z.enum(values<Schemas["Sort"]>({ last_visit: true, age: true })).catch(defaults.sort),
    order: z.enum(values<Schemas["Order"]>({ asc: true, desc: true })).catch(defaults.order),
    page: z.coerce.number().int().min(1).catch(defaults.page),
    page_size: z.coerce.number().int().min(1).max(100).catch(defaults.page_size),
  });
}

const KEYS = Object.keys(DEFAULT_LIST_PARAMS) as (keyof PatientListParams)[];

/** Only non-default values, in a fixed order, so equal states give equal URLs. */
function toSearch(params: PatientListParams, defaults: PatientListParams): URLSearchParams {
  const search = new URLSearchParams();
  for (const key of KEYS) {
    const value = params[key];
    if (value !== null && value !== defaults[key]) search.set(key, String(value));
  }
  return search;
}

/**
 * The patient list's filters, sort, and page, kept in the URL so views can be shared and
 * bookmarked. Invalid values fall back to defaults and unknown keys are dropped, so nothing
 * else (such as a pasted name) stays in the address bar. Search terms never belong here.
 */
export function usePatientListParams({ defaultScope }: { defaultScope: Scope }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const defaults = useMemo(() => ({ ...DEFAULT_LIST_PARAMS, scope: defaultScope }), [defaultScope]);

  const params = useMemo(
    () => schemaFor(defaults).parse(Object.fromEntries(searchParams)),
    [defaults, searchParams],
  );

  const canonical = toSearch(params, defaults).toString();
  useEffect(() => {
    if (canonical !== searchParams.toString()) setSearchParams(canonical, { replace: true });
  }, [canonical, searchParams, setSearchParams]);

  // React Router hands updaters the last rendered params, not pending ones, so track the
  // latest write here: several changes in one event then build on each other.
  const latest = useRef(searchParams);
  useEffect(() => {
    latest.current = searchParams;
  }, [searchParams]);

  const setParams = useCallback(
    (changes: Partial<PatientListParams>) => {
      const current = schemaFor(defaults).parse(Object.fromEntries(latest.current));
      const onlyPage = Object.keys(changes).every((key) => key === "page");
      const page = onlyPage ? (changes.page ?? current.page) : 1;
      latest.current = toSearch({ ...current, ...changes, page }, defaults);
      setSearchParams(latest.current);
    },
    [defaults, setSearchParams],
  );

  return [params, setParams] as const;
}
