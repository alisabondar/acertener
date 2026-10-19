import { format, parseISO } from "date-fns";
import { useId, useState } from "react";

import { api } from "@/api";
import { fieldErrors, queryKeys, useApiMutation } from "@/api/queries";
import type { components } from "@/api/schema";
import { usePermission } from "@/auth/context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Fields, Panel } from "@/components/Fields";
import { cn } from "@/lib/utils";

import { useChartVitals } from "./chartData";
import { formatBp, isAbnormal } from "./vitalsFormat";
import { WriteError } from "./WriteError";

type Vitals = components["schemas"]["VitalsOut"];
type VitalsCreate = components["schemas"]["VitalsCreate"];

const FIELDS: { key: keyof VitalsCreate; label: string; step?: string }[] = [
  { key: "bp_systolic", label: "Systolic" },
  { key: "bp_diastolic", label: "Diastolic" },
  { key: "heart_rate", label: "Heart rate" },
  { key: "respiratory_rate", label: "Resp. rate" },
  { key: "spo2", label: "SpO₂ (%)" },
  { key: "temperature_c", label: "Temp (°C)", step: "0.1" },
  { key: "weight_kg", label: "Weight (kg)", step: "0.1" },
  { key: "height_cm", label: "Height (cm)", step: "0.1" },
];

export function VitalsTab({ patientId }: { patientId: string }) {
  const canRecord = usePermission("WRITE_NOTES_AND_VITALS");
  const vitals = useChartVitals(patientId, true);
  const [recording, setRecording] = useState(false);

  return (
    <div className="space-y-4">
      {canRecord && !recording && <Button onClick={() => setRecording(true)}>Record vitals</Button>}
      {recording && <RecordVitals patientId={patientId} onDone={() => setRecording(false)} />}
      {vitals.data ? (
        vitals.data.items[0] ? (
          <>
            <LatestVitals latest={vitals.data.items[0]} />
            <VitalsTable items={vitals.data.items} />
          </>
        ) : (
          <p className="text-[14px] text-muted-foreground">No vitals recorded</p>
        )
      ) : (
        <Skeleton className="h-32 w-full rounded-xl" />
      )}
    </div>
  );
}

function RecordVitals({ patientId, onDone }: { patientId: string; onDone: () => void }) {
  const ids = useId();
  const [values, setValues] = useState<Partial<Record<keyof VitalsCreate, string>>>({});
  const save = useApiMutation(
    (body: VitalsCreate) =>
      api.POST("/api/v1/patients/{patient_id}/vitals", {
        params: { path: { patient_id: patientId } },
        body,
      }),
    { invalidate: [queryKeys.patients.chart(patientId)] },
  );
  const errors = fieldErrors(save.error);

  const submit = () => {
    const body = Object.fromEntries(
      Object.entries(values)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, Number(v)]),
    ) as VitalsCreate;
    void save
      .mutateAsync(body)
      .then(onDone)
      .catch(() => {});
  };

  return (
    <form
      aria-label="Record vitals"
      className="space-y-3 rounded-xl border bg-card p-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {FIELDS.map(({ key, label, step }) => {
          const error = errors[key];
          return (
            <div key={key}>
              <label className="space-y-1 text-[13px] text-muted-foreground">
                <span className="block">{label}</span>
                <Input
                  type="number"
                  inputMode="decimal"
                  step={step ?? "1"}
                  value={values[key] ?? ""}
                  aria-invalid={error !== undefined}
                  aria-describedby={error ? `${ids}-${key}` : undefined}
                  onChange={(event) => setValues({ ...values, [key]: event.target.value })}
                  className="bg-card text-foreground tabular-nums"
                />
              </label>
              {error && (
                <p id={`${ids}-${key}`} className="mt-1 text-[12px] text-severe">
                  {error}
                </p>
              )}
            </div>
          );
        })}
      </div>
      <WriteError error={save.error} action="record vitals" />
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          Save vitals
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function VitalsTable({ items }: { items: Vitals[] }) {
  const cell = (v: Vitals, key: keyof Vitals, text: string) => {
    const flagged = isAbnormal(key, v[key] as number | string | null);
    return (
      <TableCell className={cn("tabular-nums", flagged && "font-semibold text-status-inactive")}>
        {text}
        {flagged && <OutOfRange />}
      </TableCell>
    );
  };
  return (
    <div className="rounded-xl border bg-card">
      <Table aria-label="Vitals">
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">Taken</TableHead>
            <TableHead>BP</TableHead>
            <TableHead>HR</TableHead>
            <TableHead>RR</TableHead>
            <TableHead>SpO₂</TableHead>
            <TableHead>Temp</TableHead>
            <TableHead>Weight</TableHead>
            <TableHead>By</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((v) => {
            const bpHigh =
              isAbnormal("bp_systolic", v.bp_systolic) ||
              isAbnormal("bp_diastolic", v.bp_diastolic);
            return (
              <TableRow key={v.id}>
                <TableCell className="pl-4">
                  {format(parseISO(v.taken_at), "MMM d, yyyy h:mm a")}
                </TableCell>
                <TableCell
                  className={cn("tabular-nums", bpHigh && "font-semibold text-status-inactive")}
                >
                  {formatBp(v)}
                  {bpHigh && <OutOfRange />}
                </TableCell>
                {cell(v, "heart_rate", String(v.heart_rate ?? "—"))}
                {cell(v, "respiratory_rate", String(v.respiratory_rate ?? "—"))}
                {cell(v, "spo2", v.spo2 === null ? "—" : `${v.spo2}%`)}
                {cell(v, "temperature_c", v.temperature_c === null ? "—" : `${v.temperature_c}°C`)}
                <TableCell className="tabular-nums">
                  {v.weight_kg === null ? "—" : `${v.weight_kg} kg`}
                </TableCell>
                <TableCell className="text-muted-foreground">{v.recorded_by_name}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

/** Colour alone can't carry meaning, so flagged readings also say so to screen readers. */
function OutOfRange() {
  return <span className="sr-only"> (outside the usual range)</span>;
}

function LatestVitals({ latest }: { latest: Vitals }) {
  const reading = (label: string, value: string, flagged: boolean) => ({
    label,
    value: (
      <span className={cn("tabular-nums", flagged && "text-status-inactive")}>
        {value}
        {flagged && <OutOfRange />}
      </span>
    ),
  });
  return (
    <Panel title="Latest vitals">
      <p className="text-[13px] text-muted-foreground">
        {format(parseISO(latest.taken_at), "MMM d, yyyy h:mm a")} · {latest.recorded_by_name}
      </p>
      <Fields
        items={[
          reading(
            "Blood pressure",
            formatBp(latest),
            isAbnormal("bp_systolic", latest.bp_systolic) ||
              isAbnormal("bp_diastolic", latest.bp_diastolic),
          ),
          reading(
            "Heart rate",
            latest.heart_rate === null ? "—" : `${latest.heart_rate} bpm`,
            isAbnormal("heart_rate", latest.heart_rate),
          ),
          reading(
            "SpO₂",
            latest.spo2 === null ? "—" : `${latest.spo2}%`,
            isAbnormal("spo2", latest.spo2),
          ),
          reading(
            "Temperature",
            latest.temperature_c === null ? "—" : `${latest.temperature_c}°C`,
            isAbnormal("temperature_c", latest.temperature_c),
          ),
        ]}
      />
    </Panel>
  );
}
