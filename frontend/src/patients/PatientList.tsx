import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Search, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { api } from "@/api";
import { apiQueryFn, queryKeys, useApiQuery } from "@/api/queries";
import { useCurrentUser } from "@/auth/context";
import { hasCareTeam } from "@/auth/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { EmptyState, ListError } from "./ListStates";
import { patientListQuery } from "./patientListQuery";
import { PatientTable, PatientTableSkeleton } from "./PatientTable";
import { QuickFilters } from "./QuickFilters";
import { dobProblem, parseSearch } from "./searchTerms";
import { usePatientListParams } from "./usePatientListParams";

const SEARCH_DEBOUNCE_MS = 300;
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

  // Search terms identify patients, so they stay in component state: never in the URL.
  const [text, setText] = useState("");
  const [dob, setDob] = useState("");
  const [dobIncomplete, setDobIncomplete] = useState(false);
  const ids = useId();
  const dobNote = dobProblem(dob, dobIncomplete);
  // A DOB with a problem isn't searched; its field explains why.
  const searchableDob = dobNote ? "" : dob;
  const { hint } = parseSearch(text, searchableDob);
  // Typing is debounced; emptying a field applies at once, so a cleared search clears now.
  const debouncedText = useDebouncedValue(text, text ? SEARCH_DEBOUNCE_MS : 0);
  const debouncedDob = useDebouncedValue(searchableDob, searchableDob ? SEARCH_DEBOUNCE_MS : 0);
  const { terms } = useMemo(
    () => parseSearch(debouncedText, debouncedDob),
    [debouncedText, debouncedDob],
  );
  // New search terms mean a new result set, so start it from the first page.
  const editSearch = (update: () => void) => {
    update();
    if (params.page !== 1) setParams({ page: 1 });
  };
  const searchInput = useRef<HTMLInputElement>(null);
  const dobInput = useRef<HTMLInputElement>(null);
  const clearDob = () => {
    setDob("");
    setDobIncomplete(false);
    // A half-typed date is already "" to React, so clear what the browser is showing directly.
    if (dobInput.current) dobInput.current.value = "";
  };
  const clearSearch = () => {
    setText("");
    clearDob();
  };

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
          <Tabs
            value={params.scope}
            onValueChange={(scope) => {
              if (scope === "my" || scope === "all") setParams({ scope });
            }}
          >
            <TabsList>
              <TabsTrigger value="my">My patients</TabsTrigger>
              <TabsTrigger value="all">All patients</TabsTrigger>
            </TabsList>
          </Tabs>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-72 flex-1">
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                type="search"
                aria-label="Search patients"
                aria-describedby={hint ? `${ids}-search` : undefined}
                aria-invalid={hint !== null}
                placeholder="Last name, “last, first”, or MRN"
                value={text}
                onChange={(event) => editSearch(() => setText(event.target.value))}
                autoComplete="off"
                ref={searchInput}
                // One clear control: ours, not the browser's built-in search ×.
                className="bg-card pr-9 pl-9 [&::-webkit-search-cancel-button]:appearance-none"
              />
              {text && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Clear search text"
                  onClick={() => {
                    editSearch(() => setText(""));
                    searchInput.current?.focus();
                  }}
                  className="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground"
                >
                  <X />
                </Button>
              )}
            </div>
            {hint && <FieldNote id={`${ids}-search`} problem={hint} />}
          </div>
          <div>
            <div className="flex items-center gap-1">
              <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
                Date of birth
                <Input
                  ref={dobInput}
                  type="date"
                  aria-describedby={dobNote ? `${ids}-dob` : undefined}
                  aria-invalid={dobNote !== null}
                  value={dob}
                  onChange={(event) => editSearch(() => setDob(event.target.value))}
                  // A half-typed date reads as "" with badInput set; say so rather than ignore it.
                  onInput={(event) => setDobIncomplete(event.currentTarget.validity.badInput)}
                  className="w-40 bg-card"
                />
              </label>
              {(dob || dobIncomplete) && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Clear date of birth"
                  onClick={() => {
                    editSearch(clearDob);
                    dobInput.current?.focus();
                  }}
                >
                  <X />
                </Button>
              )}
            </div>
            {dobNote && <FieldNote id={`${ids}-dob`} problem={dobNote} />}
          </div>
        </div>
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
            onAction={clearSearch}
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

/** A problem with a field's value, shown under it and announced as its description. */
function FieldNote({ id, problem }: { id: string; problem: string }) {
  return (
    <p id={id} className="mt-1.5 flex items-center gap-1.5 text-[12px] text-status-inactive">
      <CircleAlert className="size-3.5 shrink-0" aria-hidden />
      {problem}
    </p>
  );
}
