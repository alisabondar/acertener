import type { components } from "@/api/schema";

import rolePermissions from "./role-permissions.json";

type Schemas = components["schemas"];
type Permission = Schemas["Permission"];
export type Persona = Schemas["UserOut"];

// Exported from the backend's permission matrix (scripts/export_openapi), so handlers answer
// /auth/me exactly as the API would.
const ROLE_PERMISSIONS = rolePermissions as Record<string, Permission[]>;

export const CHEN: Persona = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Dr. Wei Chen",
  role: "provider",
  credential: "MD",
};
export const RIVERA: Persona = {
  id: "00000000-0000-4000-8000-000000000002",
  name: "Jordan Rivera",
  role: "provider",
  credential: "NP",
};
export const OKAFOR: Persona = {
  id: "00000000-0000-4000-8000-000000000003",
  name: "Sam Okafor",
  role: "nurse",
  credential: "RN",
};
export const BROOKS: Persona = {
  id: "00000000-0000-4000-8000-000000000004",
  name: "Taylor Brooks",
  role: "front_desk",
  credential: null,
};
export const ADMIN: Persona = {
  id: "00000000-0000-4000-8000-000000000005",
  name: "Practice Admin",
  role: "admin",
  credential: null,
};

/** The "View as" choices, in the order the API returns them. */
export const PERSONAS = [CHEN, RIVERA, OKAFOR, BROOKS, ADMIN];

export function makeMe(persona: Persona = CHEN): Schemas["MeOut"] {
  return { ...persona, permissions: ROLE_PERMISSIONS[persona.role] ?? [] };
}

export type PatientListItem = Schemas["PatientListItem"];

let patientSeq = 0;

export function makePatient(overrides: Partial<PatientListItem> = {}): PatientListItem {
  patientSeq += 1;
  return {
    id: `11111111-1111-4111-8111-${String(patientSeq).padStart(12, "0")}`,
    first_name: "Daniel",
    last_name: "Osei",
    mrn: `MRN-${100000 + patientSeq}`,
    dob: "1963-04-02",
    age: 63,
    status: "active",
    last_visit_at: "2026-05-18T14:00:00Z",
    archived: false,
    on_my_care_team: true,
    inactivity_suggested: false,
    active_problems: [],
    ...overrides,
  };
}

export function makePage(
  items: PatientListItem[],
  { total = items.length, page = 1, page_size = 20 } = {},
): Schemas["PatientPage"] {
  return { items, total, page, page_size };
}

export function makeCounts(
  overrides: Partial<Schemas["FilterCountsOut"]> = {},
): Schemas["FilterCountsOut"] {
  return {
    today_visits: 4,
    status: { active: 120, inactive: 30, deceased: 2 },
    archived: 5,
    ...overrides,
  };
}

export type ScheduledVisit = Schemas["ScheduledVisitOut"];

let visitSeq = 0;

/** A visit `minutesFromNow` from the current time (negative for earlier today). */
export function makeVisit(
  minutesFromNow: number,
  overrides: Partial<ScheduledVisit> = {},
): ScheduledVisit {
  visitSeq += 1;
  return {
    id: `22222222-2222-4222-8222-${String(visitSeq).padStart(12, "0")}`,
    scheduled_at: new Date(Date.now() + minutesFromNow * 60_000).toISOString(),
    status: "scheduled",
    provider_name: "Dr. Wei Chen",
    reason: "Follow-up",
    patient: {
      id: `33333333-3333-4333-8333-${String(visitSeq).padStart(12, "0")}`,
      first_name: "Daniel",
      last_name: `Patient${visitSeq}`,
      dob: "1963-04-02",
      age: 63,
      mrn: `MRN-${200000 + visitSeq}`,
    },
    ...overrides,
  };
}

export function makeDay(items: ScheduledVisit[]): Schemas["TodaysVisits"] {
  return { date: new Date().toISOString().slice(0, 10), items };
}

export type PatientDetail = Schemas["PatientDetail"];
export type Note = Schemas["NoteOut"];
export type Allergy = Schemas["AllergyOut"];
export type Condition = Schemas["ConditionOut"];
export type Vitals = Schemas["VitalsOut"];

export function makeDetail(overrides: Partial<PatientDetail> = {}): PatientDetail {
  return {
    id: "44444444-4444-4444-8444-000000000001",
    first_name: "Daniel",
    last_name: "Osei",
    mrn: "MRN-100008",
    dob: "1963-04-02",
    age: 63,
    gender: "male",
    phone: "555-201-3344",
    email: null,
    address_line1: "12 Elm St",
    address_line2: null,
    city: "Springfield",
    state: "IL",
    postal_code: "62701",
    blood_type: "O+",
    status: "active",
    last_visit_at: "2026-05-18T14:00:00Z",
    archived: false,
    archive_reason: null,
    on_my_care_team: true,
    inactivity_suggested: false,
    version: 1,
    ...overrides,
  };
}

const stamp = "2026-10-01T10:00:00Z";

export function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: "55555555-5555-4555-8555-000000000001",
    patient_id: makeDetail().id,
    author_id: CHEN.id,
    author_name: CHEN.name,
    content: "Follow-up for blood pressure.",
    status: "final",
    encounter_at: stamp,
    finalized_at: stamp,
    created_at: stamp,
    updated_at: stamp,
    ...overrides,
  };
}

export function makeAllergy(overrides: Partial<Allergy> = {}): Allergy {
  return {
    id: "66666666-6666-4666-8666-000000000001",
    substance: "Penicillin",
    reaction: "Hives",
    severity: "severe",
    status: "active",
    recorded_by_name: OKAFOR.name,
    created_at: stamp,
    updated_at: stamp,
    ...overrides,
  };
}

export function makeCondition(overrides: Partial<Condition> = {}): Condition {
  return {
    id: "77777777-7777-4777-8777-000000000001",
    icd10_code: "E11.9",
    name: "Type 2 diabetes",
    onset_date: null,
    status: "active",
    recorded_by_name: CHEN.name,
    created_at: stamp,
    updated_at: stamp,
    ...overrides,
  };
}

export function makeVitals(overrides: Partial<Vitals> = {}): Vitals {
  return {
    id: "88888888-8888-4888-8888-000000000001",
    taken_at: stamp,
    recorded_by_name: OKAFOR.name,
    bp_systolic: 142,
    bp_diastolic: 88,
    heart_rate: 76,
    respiratory_rate: null,
    spo2: 98,
    temperature_c: null,
    weight_kg: null,
    height_cm: null,
    ...overrides,
  };
}

export function makeProblem(
  status: number,
  code: string,
  extras: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    type: "about:blank",
    title: "Error",
    status,
    detail: "Something specific went wrong.",
    code,
    request_id: "req-123",
    ...extras,
  };
}
