import { MoreHorizontal } from "lucide-react";
import { useId, useState } from "react";

import { api } from "@/api";
import { fieldErrors, queryKeys, useApiMutation } from "@/api/queries";
import type { components } from "@/api/schema";
import { usePermission } from "@/auth/context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import { useChartAllergies, useChartConditions } from "./chartData";
import { Section } from "./Section";
import { WriteError } from "./WriteError";

type RecordStatus = components["schemas"]["StatusChangeIn"]["status"];

const STATUS_LABEL: Record<RecordStatus, string> = {
  active: "Active",
  resolved: "Resolved",
  entered_in_error: "Entered in error",
};

export function AllergiesConditionsTab({ patientId }: { patientId: string }) {
  const [showInactive, setShowInactive] = useState(false);
  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(event) => setShowInactive(event.target.checked)}
        />
        Show resolved and entered in error
      </label>
      <div className="grid gap-4 lg:grid-cols-2">
        <Allergies patientId={patientId} showInactive={showInactive} />
        <Conditions patientId={patientId} showInactive={showInactive} />
      </div>
    </div>
  );
}

function Allergies({ patientId, showInactive }: { patientId: string; showInactive: boolean }) {
  const canEdit = usePermission("EDIT_ALLERGIES");
  const [editing, setEditing] = useState(false);
  const allergies = useChartAllergies(patientId, true);
  const changeStatus = useStatusChange(patientId, "allergies");
  const items = (allergies.data?.items ?? []).filter((a) => showInactive || a.status === "active");

  return (
    <Section
      title="Allergies"
      canEdit={canEdit}
      lockedReason="Requires a clinical role"
      editing={editing}
      onEditingChange={setEditing}
    >
      {editing && <AddAllergy patientId={patientId} />}
      <EntryList
        empty="No allergies recorded"
        items={items.map((a) => ({
          id: a.id,
          status: a.status,
          title: a.substance,
          detail: [a.reaction, a.severity].filter(Boolean).join(" · "),
          severe: a.severity === "severe" && a.status === "active",
        }))}
        actions={editing ? (id, status) => changeStatus.mutate({ id, status }) : undefined}
      />
      <WriteError error={changeStatus.error} action="change allergies" />
    </Section>
  );
}

function Conditions({ patientId, showInactive }: { patientId: string; showInactive: boolean }) {
  const canEdit = usePermission("EDIT_CONDITIONS");
  const [editing, setEditing] = useState(false);
  const conditions = useChartConditions(patientId, true);
  const changeStatus = useStatusChange(patientId, "conditions");
  const items = (conditions.data?.items ?? []).filter((c) => showInactive || c.status === "active");

  return (
    <Section
      title="Conditions"
      canEdit={canEdit}
      lockedReason="Requires a provider role"
      editing={editing}
      onEditingChange={setEditing}
    >
      {editing && <AddCondition patientId={patientId} />}
      <EntryList
        empty="No conditions recorded"
        items={items.map((c) => ({
          id: c.id,
          status: c.status,
          title: c.name,
          detail: c.icd10_code,
          severe: false,
        }))}
        actions={editing ? (id, status) => changeStatus.mutate({ id, status }) : undefined}
      />
      <WriteError error={changeStatus.error} action="change conditions" />
    </Section>
  );
}

function useStatusChange(patientId: string, kind: "allergies" | "conditions") {
  return useApiMutation(
    // The chart refetches after a change, so the response itself isn't needed.
    ({ id, status }: { id: string; status: RecordStatus }): Promise<{ data?: unknown }> =>
      kind === "allergies"
        ? api.POST("/api/v1/allergies/{allergy_id}/status", {
            params: { path: { allergy_id: id } },
            body: { status },
          })
        : api.POST("/api/v1/conditions/{condition_id}/status", {
            params: { path: { condition_id: id } },
            body: { status },
          }),
    { invalidate: [queryKeys.patients.chart(patientId)] },
  );
}

function EntryList({
  items,
  empty,
  actions,
}: {
  items: { id: string; status: RecordStatus; title: string; detail: string; severe: boolean }[];
  empty: string;
  actions: ((id: string, status: RecordStatus) => void) | undefined;
}) {
  if (items.length === 0) return <p className="text-[14px] text-muted-foreground">{empty}</p>;
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-3 py-2">
          <div className={cn(item.status !== "active" && "text-muted-foreground line-through")}>
            <span className={cn("font-medium", item.severe && "text-severe")}>{item.title}</span>
            {item.detail && (
              <span className="text-[13px] text-muted-foreground"> · {item.detail}</span>
            )}
            {item.status !== "active" && (
              <span className="ml-2 text-[12px] no-underline">({STATUS_LABEL[item.status]})</span>
            )}
          </div>
          {actions && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label={`Change ${item.title}`}>
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {item.status !== "active" && (
                  <DropdownMenuItem onSelect={() => actions(item.id, "active")}>
                    Mark active
                  </DropdownMenuItem>
                )}
                {item.status !== "resolved" && (
                  <DropdownMenuItem onSelect={() => actions(item.id, "resolved")}>
                    Mark resolved
                  </DropdownMenuItem>
                )}
                {item.status !== "entered_in_error" && (
                  <DropdownMenuItem onSelect={() => actions(item.id, "entered_in_error")}>
                    Entered in error
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </li>
      ))}
    </ul>
  );
}

function AddAllergy({ patientId }: { patientId: string }) {
  const [substance, setSubstance] = useState("");
  const [reaction, setReaction] = useState("");
  const [severity, setSeverity] = useState<"" | "mild" | "moderate" | "severe">("");
  const add = useApiMutation(
    (body: components["schemas"]["AllergyCreate"]) =>
      api.POST("/api/v1/patients/{patient_id}/allergies", {
        params: { path: { patient_id: patientId } },
        body,
      }),
    { invalidate: [queryKeys.patients.chart(patientId)] },
  );
  const errors = fieldErrors(add.error);
  return (
    <form
      aria-label="Add allergy"
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        void add
          .mutateAsync({ substance, reaction: reaction || null, severity: severity || null })
          .then(() => {
            setSubstance("");
            setReaction("");
            setSeverity("");
          })
          .catch(() => {});
      }}
    >
      <div className="flex flex-wrap gap-2">
        <Field
          label="Substance"
          value={substance}
          onChange={setSubstance}
          error={errors["substance"]}
          required
        />
        <Field
          label="Reaction"
          value={reaction}
          onChange={setReaction}
          error={errors["reaction"]}
        />
        <label className="space-y-1 text-[13px] text-muted-foreground">
          <span className="block">Severity</span>
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value as typeof severity)}
            className="h-8 rounded-lg border bg-card px-2 text-[14px] text-foreground"
          >
            <option value="">Unknown</option>
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
          </select>
        </label>
      </div>
      <WriteError error={add.error} action="add allergies" />
      <Button type="submit" size="sm" disabled={add.isPending || !substance.trim()}>
        Add allergy
      </Button>
    </form>
  );
}

function AddCondition({ patientId }: { patientId: string }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const add = useApiMutation(
    (body: components["schemas"]["ConditionCreate"]) =>
      api.POST("/api/v1/patients/{patient_id}/conditions", {
        params: { path: { patient_id: patientId } },
        body,
      }),
    { invalidate: [queryKeys.patients.chart(patientId)] },
  );
  const errors = fieldErrors(add.error);
  return (
    <form
      aria-label="Add condition"
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        void add
          .mutateAsync({ icd10_code: code, name })
          .then(() => {
            setCode("");
            setName("");
          })
          .catch(() => {});
      }}
    >
      <div className="flex flex-wrap gap-2">
        <Field
          label="ICD-10 code"
          value={code}
          onChange={setCode}
          error={errors["icd10_code"]}
          required
        />
        <Field label="Condition" value={name} onChange={setName} error={errors["name"]} required />
      </div>
      <WriteError error={add.error} action="add conditions" />
      <Button type="submit" size="sm" disabled={add.isPending || !code.trim() || !name.trim()}>
        Add condition
      </Button>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  error,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error: string | undefined;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label className="space-y-1 text-[13px] text-muted-foreground">
        <span className="block">{label}</span>
        <Input
          value={value}
          required={required}
          aria-invalid={error !== undefined}
          aria-describedby={error ? id : undefined}
          onChange={(event) => onChange(event.target.value)}
          className="w-44 bg-card text-foreground"
        />
      </label>
      {error && (
        <p id={id} className="mt-1 text-[12px] text-severe">
          {error}
        </p>
      )}
    </div>
  );
}
