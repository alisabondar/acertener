import { TriangleAlert } from "lucide-react";

import type { components } from "@/api/schema";
import { formatDob } from "@/lib/format";
import { StatusPill } from "@/patients/StatusPill";

import { useChartAllergies } from "./chartData";

type Patient = components["schemas"]["PatientDetail"];

const SEX: Record<string, string> = { female: "F", male: "M", nonbinary: "X", other: "X" };

/** Who this is, at a glance: the two identifiers, status, and any severe allergies. */
export function ChartHeader({
  patient,
  showAllergies,
}: {
  patient: Patient;
  showAllergies: boolean;
}) {
  const allergies = useChartAllergies(patient.id, showAllergies);
  const severe = (allergies.data?.items ?? []).filter(
    (a) => a.status === "active" && a.severity === "severe",
  );
  return (
    <section aria-label="Patient" className="space-y-3 rounded-xl border bg-card px-5 py-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="text-[24px] font-semibold">
          {patient.last_name}, {patient.first_name}
        </h1>
        {patient.status !== "active" && <StatusPill status={patient.status} />}
        {patient.archived && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-[12px] font-medium">
            Archived
          </span>
        )}
      </div>
      <p className="text-[14px] text-muted-foreground tabular-nums">
        {formatDob(patient.dob)} ({patient.age}y)
        {patient.gender && ` · ${SEX[patient.gender] ?? "U"}`} · {patient.mrn}
      </p>
      {severe.length > 0 && (
        <p
          role="alert"
          aria-label="Severe allergies"
          className="flex items-center gap-2 rounded-lg bg-severe/10 px-3 py-2 text-[14px] font-medium text-severe"
        >
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          Severe allergy: {severe.map((a) => a.substance).join(", ")}
        </p>
      )}
    </section>
  );
}
