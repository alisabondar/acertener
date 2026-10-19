import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { useFieldArray, useForm, type Path, type UseFormReturn } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { api } from "@/api";
import { ApiProblem, NetworkError } from "@/api/errors";
import { queryKeys, setServerErrors, useApiQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { usePermission } from "@/auth/context";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { NativeSelect } from "@/components/NativeSelect";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { WriteError } from "@/chart/WriteError";
import { useQueryClient } from "@tanstack/react-query";

import {
  BLOOD_TYPES,
  DEMOGRAPHIC_FIELDS,
  SEXES,
  STATUSES,
  US_STATES,
  emptyPatient,
  fromPatient,
  patientSchema,
  toApi,
  type PatientFormValues,
} from "./patientFormSchema";

type PatientDetail = components["schemas"]["PatientDetail"];
type Severity = "mild" | "moderate" | "severe";
type NewPatientFields = Omit<components["schemas"]["PatientCreate"], "confirm_not_duplicate">;
type Form = UseFormReturn<PatientFormValues>;

export function NewPatient() {
  return (
    <Page title="New patient">
      <PatientForm />
    </Page>
  );
}

export function EditPatient() {
  const { patientId = "" } = useParams();
  const detail = useApiQuery(queryKeys.patients.detail(patientId), (signal) =>
    api.GET("/api/v1/patients/{patient_id}", {
      params: { path: { patient_id: patientId } },
      signal,
    }),
  );
  return (
    <Page title="Edit patient">
      {detail.data ? (
        <PatientForm existing={detail.data} />
      ) : detail.error ? (
        <WriteError error={detail.error} action="view this patient" />
      ) : (
        <Skeleton className="h-96 w-full rounded-xl" />
      )}
    </Page>
  );
}

function Page({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>
      {children}
    </div>
  );
}

/** Why the last save didn't go through, when it isn't a field-level problem. */
type Problem =
  | { kind: "duplicate"; matches: string[] }
  | { kind: "mrn"; matches: string[] }
  | { kind: "network"; retry: () => void }
  | { kind: "conflict"; current: PatientDetail }
  | { kind: "other"; error: Error };

function PatientForm({ existing }: { existing?: PatientDetail }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clinical = usePermission("VIEW_CLINICAL");
  const canAddAllergies = usePermission("EDIT_ALLERGIES");
  const canAddConditions = usePermission("EDIT_CONDITIONS");
  const canChangeStatus = usePermission("CHANGE_PATIENT_STATUS");
  const [version, setVersion] = useState(existing?.version ?? 0);
  const [problem, setProblem] = useState<Problem | null>(null);
  const form = useForm<PatientFormValues>({
    resolver: zodResolver(patientSchema),
    defaultValues: existing ? fromPatient(existing) : emptyPatient(),
  });
  const fields = DEMOGRAPHIC_FIELDS.filter((f) => f !== "blood_type" || clinical);

  const opened = (id: string, message: string) => {
    void queryClient.invalidateQueries({ queryKey: ["patients"] });
    toast.success(message);
    void navigate(`/patients/${id}`);
  };

  const handle = (error: unknown, retry: () => void) => {
    if (error instanceof NetworkError) return setProblem({ kind: "network", retry });
    if (error instanceof ApiProblem && error.code === "POSSIBLE_DUPLICATE") {
      return setProblem({
        kind: "duplicate",
        matches: (error.extras["matches"] as string[]) ?? [],
      });
    }
    if (error instanceof ApiProblem && error.code === "DUPLICATE_MRN") {
      form.setError("mrn", { type: "server", message: error.detail });
      return setProblem({ kind: "mrn", matches: (error.extras["matches"] as string[]) ?? [] });
    }
    if (error instanceof ApiProblem && error.code === "VERSION_CONFLICT") {
      return setProblem({ kind: "conflict", current: error.extras["current"] as PatientDetail });
    }
    if (error instanceof Error && !setServerErrors(error, form.setError)) {
      setProblem({ kind: "other", error });
    }
  };

  // What a create has already saved, so a retry after a failure partway through resumes instead
  // of registering the patient a second time.
  const progress = useRef<{ id: string; allergies: number; conditions: number } | null>(null);

  const create = async (values: PatientFormValues, confirmNotDuplicate = false) => {
    setProblem(null);
    try {
      if (!progress.current) {
        const { data } = await api.POST("/api/v1/patients", {
          body: {
            ...toApi<NewPatientFields>(values, fields),
            confirm_not_duplicate: confirmNotDuplicate,
          },
        });
        if (!data) return;
        progress.current = { id: data.id, allergies: 0, conditions: 0 };
      }
      const done = progress.current;
      const path = { patient_id: done.id };
      const allergies = canAddAllergies ? values.allergies : [];
      for (const a of allergies.slice(done.allergies)) {
        await api.POST("/api/v1/patients/{patient_id}/allergies", {
          params: { path },
          body: {
            substance: a.substance,
            reaction: null,
            severity: a.severity ? (a.severity as Severity) : null,
          },
        });
        done.allergies += 1;
      }
      const conditions = canAddConditions ? values.conditions : [];
      for (const c of conditions.slice(done.conditions)) {
        await api.POST("/api/v1/patients/{patient_id}/conditions", {
          params: { path },
          body: { icd10_code: c.icd10_code, name: c.name },
        });
        done.conditions += 1;
      }
      opened(done.id, "Patient created");
    } catch (error) {
      handle(error, () => void create(values, confirmNotDuplicate));
    }
  };

  const update = async (values: PatientFormValues) => {
    if (!existing) return;
    setProblem(null);
    const dirty = form.formState.dirtyFields;
    const changed = fields.filter((f) => dirty[f]);
    try {
      let current = version;
      if (changed.length > 0) {
        const { data } = await api.PATCH("/api/v1/patients/{patient_id}", {
          params: { path: { patient_id: existing.id } },
          body: {
            base_version: current,
            changes: toApi<components["schemas"]["PatientChanges"]>(values, changed),
          },
        });
        current = data?.version ?? current;
      }
      if (canChangeStatus && dirty.status) {
        await api.POST("/api/v1/patients/{patient_id}/status", {
          params: { path: { patient_id: existing.id } },
          body: {
            base_version: current,
            status: values.status as components["schemas"]["PatientStatus"],
          },
        });
      }
      opened(existing.id, "Changes saved");
    } catch (error) {
      handle(error, () => void update(values));
    }
  };

  return (
    <Form {...form}>
      <form
        noValidate
        aria-label={existing ? "Edit patient" : "New patient"}
        className="space-y-6"
        onSubmit={(event) =>
          void form.handleSubmit((values) => (existing ? update(values) : create(values)))(event)
        }
      >
        <Fieldset legend="Personal information">
          <Text form={form} name="first_name" label="First name" />
          <Text form={form} name="last_name" label="Last name" />
          <Text form={form} name="dob" label="Date of birth" placeholder="YYYY-MM-DD" />
          <Choice form={form} name="gender" label="Sex" options={SEXES} empty="Not recorded" />
          <Text form={form} name="mrn" label="MRN" placeholder="100234" numeric />
        </Fieldset>

        <Fieldset legend="Contact and address">
          <Text form={form} name="phone" label="Phone" placeholder="555-867-5309" />
          <Text form={form} name="email" label="Email" />
          <Text form={form} name="address_line1" label="Address" />
          <Text form={form} name="address_line2" label="Address line 2" />
          <Text form={form} name="city" label="City" />
          <Choice
            form={form}
            name="state"
            label="State"
            options={Object.fromEntries(US_STATES.map((s) => [s, s]))}
            empty="—"
          />
          <Text form={form} name="postal_code" label="ZIP code" />
        </Fieldset>

        {(clinical || (existing && canChangeStatus)) && (
          <Fieldset legend="Medical information">
            {clinical && (
              <Choice
                form={form}
                name="blood_type"
                label="Blood type"
                options={Object.fromEntries(BLOOD_TYPES.map((b) => [b, b]))}
                empty="Unknown"
              />
            )}
            {existing && canChangeStatus && (
              <Choice form={form} name="status" label="Status" options={STATUSES} />
            )}
            {!existing && canAddAllergies && <Allergies form={form} />}
            {!existing && canAddConditions && <Conditions form={form} />}
            {existing && clinical && (
              <p className="col-span-full text-[13px] text-muted-foreground">
                Allergies and conditions are kept up to date on the{" "}
                <Link className="underline" to={`/patients/${existing.id}`}>
                  chart
                </Link>
                .
              </p>
            )}
          </Fieldset>
        )}

        <ProblemNotice
          problem={problem}
          onCreateAnyway={() => void form.handleSubmit((v) => create(v, true))()}
          onLoadLatest={(current) => {
            form.reset(fromPatient(current));
            setVersion(current.version);
            setProblem(null);
          }}
        />

        <div className="flex gap-2">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {existing ? "Save changes" : "Create patient"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => void navigate(existing ? `/patients/${existing.id}` : "/patients")}
          >
            Cancel
          </Button>
        </div>
      </form>
    </Form>
  );
}

function ProblemNotice({
  problem,
  onCreateAnyway,
  onLoadLatest,
}: {
  problem: Problem | null;
  onCreateAnyway: () => void;
  onLoadLatest: (current: PatientDetail) => void;
}) {
  if (!problem) return null;
  if (problem.kind === "other") return <WriteError error={problem.error} action="save patients" />;
  if (problem.kind === "mrn") {
    return problem.matches[0] ? (
      <p className="text-[14px]">
        <Link className="text-brand underline" to={`/patients/${problem.matches[0]}`}>
          Open the patient with this MRN
        </Link>
      </p>
    ) : null;
  }
  const box = "space-y-2 rounded-lg border border-severe/30 bg-severe/5 p-3 text-[14px]";
  if (problem.kind === "network") {
    return (
      <div role="alert" className={box}>
        <p>Couldn't reach the server. Check your connection; nothing was saved.</p>
        <Button type="button" size="sm" variant="outline" onClick={problem.retry}>
          Try again
        </Button>
      </div>
    );
  }
  if (problem.kind === "conflict") {
    return (
      <div role="alert" className={box}>
        <p>
          Someone else changed this record while you were editing. Load their version, then make
          your change again.
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onLoadLatest(problem.current)}
        >
          Load their version
        </Button>
      </div>
    );
  }
  return (
    <div role="alert" aria-label="Possible duplicate" className={box}>
      <p>A patient with this last name and date of birth may already exist.</p>
      <ul className="space-y-1">
        {problem.matches.map((id, i) => (
          <li key={id}>
            <Link className="underline" to={`/patients/${id}`}>
              {problem.matches.length === 1 ? "Open the existing chart" : `Open match ${i + 1}`}
            </Link>
          </li>
        ))}
      </ul>
      <Button type="button" size="sm" variant="outline" onClick={onCreateAnyway}>
        Create anyway
      </Button>
    </div>
  );
}

function Fieldset({ legend, children }: { legend: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded-xl border bg-card p-4">
      <legend className="px-1 text-[13px] font-semibold text-brand">{legend}</legend>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function Text({
  form,
  name,
  label,
  placeholder,
  numeric,
}: {
  form: Form;
  name: Path<PatientFormValues>;
  label: string;
  placeholder?: string;
  /** Brings up the number pad on touch devices. */
  numeric?: boolean;
}) {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input
              {...field}
              value={typeof field.value === "string" ? field.value : ""}
              placeholder={placeholder}
              inputMode={numeric ? "numeric" : undefined}
              className="bg-card text-foreground"
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function Choice({
  form,
  name,
  label,
  options,
  empty,
}: {
  form: Form;
  name: Path<PatientFormValues>;
  label: string;
  options: Record<string, string>;
  empty?: string;
}) {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <NativeSelect {...field} value={typeof field.value === "string" ? field.value : ""}>
              {empty !== undefined && <option value="">{empty}</option>}
              {Object.entries(options).map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </NativeSelect>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function Allergies({ form }: { form: Form }) {
  const list = useFieldArray({ control: form.control, name: "allergies" });
  return (
    <div className="col-span-full space-y-2">
      <p className="text-[13px] font-medium">Allergies</p>
      {list.fields.map((row, i) => (
        <div key={row.id} className="flex flex-wrap items-start gap-2">
          <Row form={form} name={`allergies.${i}.substance`} label={`Allergy ${i + 1} substance`} />
          <FormField
            control={form.control}
            name={`allergies.${i}.severity`}
            render={({ field }) => (
              <NativeSelect {...field} aria-label={`Allergy ${i + 1} severity`}>
                <option value="">Severity unknown</option>
                <option value="mild">Mild</option>
                <option value="moderate">Moderate</option>
                <option value="severe">Severe</option>
              </NativeSelect>
            )}
          />
          <RemoveRow label={`Remove allergy ${i + 1}`} onClick={() => list.remove(i)} />
        </div>
      ))}
      <AddRow label="Add allergy" onClick={() => list.append({ substance: "", severity: "" })} />
    </div>
  );
}

function Conditions({ form }: { form: Form }) {
  const list = useFieldArray({ control: form.control, name: "conditions" });
  return (
    <div className="col-span-full space-y-2">
      <p className="text-[13px] font-medium">Conditions</p>
      {list.fields.map((row, i) => (
        <div key={row.id} className="flex flex-wrap items-start gap-2">
          <Row
            form={form}
            name={`conditions.${i}.icd10_code`}
            label={`Condition ${i + 1} ICD-10 code`}
          />
          <Row form={form} name={`conditions.${i}.name`} label={`Condition ${i + 1} name`} />
          <RemoveRow label={`Remove condition ${i + 1}`} onClick={() => list.remove(i)} />
        </div>
      ))}
      <AddRow label="Add condition" onClick={() => list.append({ icd10_code: "", name: "" })} />
    </div>
  );
}

/** A compact input inside a repeating row, labelled for screen readers by its position. */
function Row({ form, name, label }: { form: Form; name: Path<PatientFormValues>; label: string }) {
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormControl>
            <Input
              {...field}
              value={typeof field.value === "string" ? field.value : ""}
              aria-label={label}
              placeholder={label.replace(/^\w+ \d+ /, "")}
              className="w-48 bg-card"
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function AddRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button type="button" size="sm" variant="outline" onClick={onClick}>
      <Plus className="size-4" aria-hidden />
      {label}
    </Button>
  );
}

function RemoveRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button type="button" size="icon-sm" variant="ghost" aria-label={label} onClick={onClick}>
      <Trash2 className="size-4" aria-hidden />
    </Button>
  );
}
