import { formatDistanceToNowStrict } from "date-fns";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { memo } from "react";
import { useNavigate } from "react-router";

import type { components } from "@/api/schema";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDob } from "@/lib/format";
import { cn } from "@/lib/utils";

import { StatusPill } from "./StatusPill";
import type { PatientListParams } from "./usePatientListParams";

type Patient = components["schemas"]["PatientListItem"];
type Sort = PatientListParams["sort"];

/** Memoized: typing in the search box re-renders the page, but the rows only change with results. */
export const PatientTable = memo(function PatientTable({
  patients,
  params,
  setParams,
  showCareTeam,
  refreshing,
}: {
  patients: Patient[];
  params: PatientListParams;
  setParams: (changes: Partial<PatientListParams>) => void;
  /** Mark care-team patients, which only adds information when viewing everyone. */
  showCareTeam: boolean;
  refreshing: boolean;
}) {
  const navigate = useNavigate();
  const open = (patient: Patient) => void navigate(`/patients/${patient.id}`);
  const sortBy = (sort: Sort) =>
    setParams(
      params.sort === sort
        ? { order: params.order === "asc" ? "desc" : "asc" }
        : { sort, order: "desc" },
    );

  return (
    <div
      aria-busy={refreshing}
      className={cn("rounded-xl border bg-card transition-opacity", refreshing && "opacity-60")}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">Patient</TableHead>
            <SortableHead
              label="Date of birth"
              sortLabel="age"
              sort="age"
              params={params}
              onSort={sortBy}
            />
            <SortableHead
              label="Last visit"
              sortLabel="last visit"
              sort="last_visit"
              params={params}
              onSort={sortBy}
            />
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {patients.map((patient) => (
            <TableRow
              key={patient.id}
              tabIndex={0}
              onClick={() => open(patient)}
              onKeyDown={(event) => {
                if (event.key === "Enter") open(patient);
              }}
              className="cursor-pointer focus-visible:bg-muted focus-visible:outline-none"
            >
              <TableCell className="py-3 pl-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">
                    {patient.last_name}, {patient.first_name}
                  </span>
                  {showCareTeam && patient.on_my_care_team && (
                    <Tag className="bg-primary text-primary-foreground">My patient</Tag>
                  )}
                  {patient.archived && <Tag>Archived</Tag>}
                </div>
                <div className="text-[12px] text-muted-foreground tabular-nums">{patient.mrn}</div>
              </TableCell>
              <TableCell className="tabular-nums">
                {formatDob(patient.dob)}{" "}
                <span className="text-muted-foreground">({patient.age}y)</span>
              </TableCell>
              <TableCell>
                <LastVisit at={patient.last_visit_at} />
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-2">
                  {patient.status !== "active" && <StatusPill status={patient.status} />}
                  {patient.inactivity_suggested && (
                    <span className="text-[12px] text-muted-foreground">No visit in 3+ years</span>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});

export function PatientTableSkeleton() {
  return (
    <div role="status" aria-label="Loading patients" className="rounded-xl border bg-card p-4">
      <div className="space-y-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="flex items-center gap-6">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-10" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function SortableHead({
  label,
  sortLabel,
  sort,
  params,
  onSort,
}: {
  label: string;
  /** What the server sorts by, for the button's accessible name. */
  sortLabel: string;
  sort: Sort;
  params: PatientListParams;
  onSort: (sort: Sort) => void;
}) {
  const active = params.sort === sort;
  const Icon = !active ? ArrowUpDown : params.order === "asc" ? ArrowUp : ArrowDown;
  return (
    <TableHead aria-sort={active ? (params.order === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        aria-label={`Sort by ${sortLabel}`}
        onClick={() => onSort(sort)}
        className={cn(
          "inline-flex items-center gap-1 rounded-sm hover:text-foreground",
          active ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {label}
        <Icon className="size-3.5" aria-hidden />
      </button>
    </TableHead>
  );
}

function LastVisit({ at }: { at: string | null }) {
  if (!at) return <span className="text-muted-foreground">No visits</span>;
  const date = new Date(at);
  return (
    <time dateTime={at} title={date.toLocaleDateString()}>
      {formatDistanceToNowStrict(date, { addSuffix: true })}
    </time>
  );
}

function Tag({ children, className }: { children: string; className?: string }) {
  return (
    <span
      className={cn(
        "rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
