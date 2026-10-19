import { format, parseISO } from "date-fns";
import { Fragment, useState } from "react";
import { Link } from "react-router";

import { api } from "@/api";
import { queryKeys, useApiQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { useCurrentUser } from "@/auth/context";
import { hasCareTeam } from "@/auth/roles";
import { SectionTitle } from "@/components/Fields";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/useNow";
import { formatDob } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EmptyState, ListError } from "@/patients/ListStates";
import { ScopeToggle } from "@/patients/ScopeToggle";

type Visit = components["schemas"]["ScheduledVisitOut"];
type VisitStatus = Visit["status"];
type Scope = components["schemas"]["Scope"];

const SCHEDULE_REFRESH_MS = 60_000;

const STATUS: Record<VisitStatus, { label: string; style: string }> = {
  scheduled: { label: "Scheduled", style: "bg-muted text-muted-foreground" },
  checked_in: { label: "Checked in", style: "bg-primary text-primary-foreground" },
  completed: { label: "Completed", style: "bg-status-active/12 text-status-active" },
  no_show: { label: "No-show", style: "bg-status-inactive/12 text-status-inactive" },
  cancelled: { label: "Cancelled", style: "bg-muted text-muted-foreground line-through" },
};

function greeting(now: Date): string {
  const hour = now.getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

export function MyDay() {
  const { me } = useCurrentUser();
  const careTeam = hasCareTeam(me.role);
  // Care-team roles start with their own schedule; front desk runs the whole practice's day.
  const [scope, setScope] = useState<Scope>(careTeam ? "my" : "all");
  const now = useNow();
  // Keyed by date, so a page left open past midnight moves on to the new day.
  const day = useApiQuery(
    queryKeys.visits.today(scope, format(now, "yyyy-MM-dd")),
    (signal) => api.GET("/api/v1/visits/today", { params: { query: { scope } }, signal }),
    // Other staff check patients in and out; keep the schedule current.
    { refetchInterval: SCHEDULE_REFRESH_MS, keepPrevious: true },
  );

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-semibold">My day</h1>
          <p className="text-[15px] text-muted-foreground">
            {greeting(now)}, {me.name} · {format(now, "EEEE, MMMM d")}
          </p>
        </div>
        {careTeam && (
          <ScopeToggle
            value={scope}
            onChange={setScope}
            label="Whose schedule"
            myLabel="My schedule"
            allLabel="Everyone"
          />
        )}
      </div>

      <AtAGlance visits={day.data?.items} />

      <div className="space-y-3">
        <SectionTitle>Today's schedule</SectionTitle>
        {day.data ? (
          day.data.items.length > 0 ? (
            <Schedule visits={day.data.items} now={now} showProvider={scope === "all"} />
          ) : (
            <EmptyState message="No visits scheduled today" />
          )
        ) : day.error ? (
          <ListError error={day.error} what="today's schedule" onRetry={() => void day.refetch()} />
        ) : (
          <div role="status" aria-label="Loading today's schedule" className="space-y-2">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function AtAGlance({ visits }: { visits: Visit[] | undefined }) {
  const count = (status: VisitStatus) => visits?.filter((v) => v.status === status).length;
  return (
    <section aria-label="Today at a glance" className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Today's visits" value={visits?.length} />
      <Stat label="Checked in" value={count("checked_in")} />
      <Stat label="Completed" value={count("completed")} />
      <Stat label="No-shows" value={count("no_show")} />
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-xl border bg-card px-4 py-3">
      <span className="block text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </span>{" "}
      <span className="block text-[28px] font-semibold text-brand tabular-nums">
        {value ?? "–"}
      </span>
    </div>
  );
}

function Schedule({
  visits,
  now,
  showProvider,
}: {
  visits: Visit[];
  now: Date;
  showProvider: boolean;
}) {
  // The Now line sits before the first visit that hasn't started yet.
  const nextIndex = visits.findIndex((v) => parseISO(v.scheduled_at) > now);
  const nowAt = nextIndex === -1 ? visits.length : nextIndex;
  return (
    <ol aria-label="Today's schedule" className="space-y-2">
      {visits.map((visit, i) => (
        <Fragment key={visit.id}>
          {i === nowAt && <NowLine now={now} />}
          <VisitRow visit={visit} showProvider={showProvider} />
        </Fragment>
      ))}
      {nowAt === visits.length && <NowLine now={now} />}
    </ol>
  );
}

function NowLine({ now }: { now: Date }) {
  return (
    <li className="flex items-center gap-2 text-[12px] font-medium text-severe">
      <span className="tabular-nums">Now · {format(now, "h:mm a")}</span>
      <span className="h-px flex-1 bg-severe/40" aria-hidden />
    </li>
  );
}

function VisitRow({ visit, showProvider }: { visit: Visit; showProvider: boolean }) {
  const { patient } = visit;
  const status = STATUS[visit.status];
  // The whole card opens the chart: a bigger target than a name, and one stop per visit.
  return (
    <li>
      <Link
        to={`/patients/${patient.id}`}
        className="flex items-center gap-4 rounded-xl border bg-card px-4 py-3 transition-colors hover:border-brand/50 hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-ring"
      >
        <time
          dateTime={visit.scheduled_at}
          className="w-20 shrink-0 font-semibold whitespace-nowrap text-brand tabular-nums"
        >
          {format(parseISO(visit.scheduled_at), "h:mm a")}
        </time>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold">
            {patient.last_name}, {patient.first_name}
          </p>
          <p className="text-[12px] text-muted-foreground tabular-nums">
            {formatDob(patient.dob)} ({patient.age}y) · {patient.mrn}
            {showProvider && ` · ${visit.provider_name}`}
          </p>
          {visit.reason && <p className="truncate text-[13px] text-foreground">{visit.reason}</p>}
        </div>
        <span
          className={cn("shrink-0 rounded-full px-2 py-0.5 text-[12px] font-medium", status.style)}
        >
          {status.label}
        </span>
      </Link>
    </li>
  );
}
