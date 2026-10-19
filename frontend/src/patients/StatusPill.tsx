import type { components } from "@/api/schema";
import { cn } from "@/lib/utils";

type PatientStatus = components["schemas"]["PatientStatus"];

const STYLES: Record<PatientStatus, string> = {
  active: "bg-status-active/12 text-status-active",
  inactive: "bg-status-inactive/12 text-status-inactive",
  deceased: "bg-status-deceased/12 text-status-deceased",
};

const LABELS: Record<PatientStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  deceased: "Deceased",
};

export function StatusPill({ status }: { status: PatientStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-medium",
        STYLES[status],
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {LABELS[status]}
    </span>
  );
}

export const STATUS_LABELS = LABELS;
