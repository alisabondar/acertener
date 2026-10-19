import type { components } from "@/api/schema";
import { usePermission } from "@/auth/context";
import { cn } from "@/lib/utils";

import { STATUS_LABELS } from "./StatusPill";
import type { PatientListParams } from "./usePatientListParams";

type Counts = components["schemas"]["FilterCountsOut"];
type PatientStatus = components["schemas"]["PatientStatus"];

const STATUSES: PatientStatus[] = ["active", "inactive", "deceased"];

/** Toggle chips with live counts. Each shows only to roles that use it. */
export function QuickFilters({
  params,
  setParams,
  counts,
}: {
  params: PatientListParams;
  setParams: (changes: Partial<PatientListParams>) => void;
  counts: Counts | undefined;
}) {
  const worksVisits = usePermission("SCHEDULE_VISITS");
  const canArchive = usePermission("ARCHIVE_PATIENT");

  return (
    <div role="group" aria-label="Quick filters" className="flex flex-wrap gap-2">
      {worksVisits && (
        <Chip
          label="Today's visits"
          count={counts?.today_visits}
          pressed={params.filter === "today_visits"}
          onToggle={(on) => setParams({ filter: on ? "today_visits" : null })}
        />
      )}
      {STATUSES.map((status) => (
        <Chip
          key={status}
          label={STATUS_LABELS[status]}
          count={counts?.status[status]}
          pressed={params.status === status}
          onToggle={(on) => setParams({ status: on ? status : null })}
        />
      ))}
      {canArchive && (
        <Chip
          label="Show archived"
          count={counts?.archived}
          pressed={params.include_archived}
          onToggle={(on) => setParams({ include_archived: on })}
        />
      )}
    </div>
  );
}

function Chip({
  label,
  count,
  pressed,
  onToggle,
}: {
  label: string;
  count: number | undefined;
  pressed: boolean;
  onToggle: (on: boolean) => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onToggle(!pressed)}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[13px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        pressed
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card hover:bg-muted",
      )}
    >
      {label}{" "}
      <span className={cn("tabular-nums", pressed ? "opacity-80" : "text-muted-foreground")}>
        {count === undefined ? "–" : count.toLocaleString()}
      </span>
    </button>
  );
}
