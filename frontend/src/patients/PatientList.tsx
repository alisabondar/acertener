import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { api } from "@/api";
import { apiQueryFn, queryKeys, useApiQuery } from "@/api/queries";
import { useCurrentUser } from "@/auth/context";
import { hasCareTeam } from "@/auth/roles";
import { Button } from "@/components/ui/button";

import { EmptyState, ListError } from "./ListStates";
import { patientListQuery } from "./patientListQuery";
import { PatientTable, PatientTableSkeleton } from "./PatientTable";
import { PatientSearchFields } from "./PatientSearchFields";
import { QuickFilters } from "./QuickFilters";
import { ScopeToggle } from "./ScopeToggle";
import { usePatientListParams } from "./usePatientListParams";
import { usePatientSearch } from "./usePatientSearch";

/** How long a prefetched next page counts as fresh, so revisits don't refetch it at once. */
const PREFETCH_FRESH_MS = 30_000;

export function PatientList() {
  const { me } = useCurrentUser();
  const careTeam = hasCareTeam(me.role);
  const [urlParams, setParams] = usePatientListParams({ defaultScope: careTeam ? "my" : "all" });
  // Roles without a care team always see everyone, whatever an old link says.
  const params = useMemo(
    () => (careTeam ? urlParams : { ...urlParams, scope: "all" as const }),
    [careTeam, urlParams],
  );

  // A new search means a new result set, so start it from the first page.
  const search = usePatientSearch({
    onEdit: () => {
      if (params.page !== 1) setParams({ page: 1 });
    },
  });
  const { terms } = search;

  const { queryKey, call } = patientListQuery(params, terms);
  const list = useApiQuery(queryKey, call, { keepPrevious: true });

  // Fetch the next page in the background so "Next" is instant.
  const queryClient = useQueryClient();
  const loaded = list.isSuccess && !list.isPlaceholderData ? list.data : undefined;
  const hasNextPage = loaded !== undefined && loaded.page * loaded.page_size < loaded.total;
  useEffect(() => {
    if (!hasNextPage) return;
    const next = patientListQuery({ ...params, page: params.page + 1 }, terms);
    void queryClient.prefetchQuery({
      queryKey: next.queryKey,
      queryFn: apiQueryFn(next.call),
      staleTime: PREFETCH_FRESH_MS,
    });
  }, [hasNextPage, params, terms, queryClient]);

  const counts = useApiQuery(queryKeys.patients.counts(params.scope), (signal) =>
    api.GET("/api/v1/patients/filter-counts", {
      params: { query: { scope: params.scope } },
      signal,
    }),
  );

  const filtered = params.filter !== null || params.status !== null || params.include_archived;

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-[28px] font-semibold">Patients</h1>
        {careTeam && (
          <ScopeToggle
            value={params.scope}
            onChange={(scope) => setParams({ scope })}
            label="Whose patients"
            myLabel="My patients"
            allLabel="All patients"
          />
        )}
      </div>

      <div className="space-y-3">
        <PatientSearchFields search={search} />
        <QuickFilters params={params} setParams={setParams} counts={counts.data} />
      </div>

      {list.data ? (
        list.data.items.length > 0 ? (
          <>
            <PatientTable
              patients={list.data.items}
              params={params}
              setParams={setParams}
              showCareTeam={careTeam && params.scope === "all"}
              refreshing={list.isPlaceholderData}
            />
            <Pagination
              page={list.data.page}
              pageSize={list.data.page_size}
              total={list.data.total}
              onPage={(page) => setParams({ page })}
            />
          </>
        ) : terms ? (
          <EmptyState
            {...(terms.last_name && !terms.first_name && !terms.dob
              ? {
                  message: `No last names start with “${terms.last_name}”`,
                  detail: "To search by first name, type “last, first”.",
                }
              : { message: "No patients match your search" })}
            action="Clear search"
            onAction={search.clear}
          />
        ) : filtered ? (
          <EmptyState
            message="No patients match these filters"
            action="Clear filters"
            onAction={() => setParams({ filter: null, status: null, include_archived: false })}
          />
        ) : (
          <EmptyState
            message={
              params.scope === "my" ? "No patients on your care team yet" : "No patients yet"
            }
          />
        )
      ) : list.error ? (
        <ListError error={list.error} what="patients" onRetry={() => void list.refetch()} />
      ) : (
        <PatientTableSkeleton />
      )}
    </section>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between text-[13px]">
      <span className="text-muted-foreground tabular-nums">
        {first}–{last} of {total.toLocaleString()}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label="Next page"
          disabled={last >= total}
          onClick={() => onPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
