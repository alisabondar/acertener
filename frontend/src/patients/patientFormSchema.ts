import { z } from "zod";

import type { components } from "@/api/schema";

type PatientDetail = components["schemas"]["PatientDetail"];

// The same rules the API enforces, so most mistakes are caught before a round trip. The server
// stays the authority: its 422s land on the same fields.
const NAME = /^\p{L}+\.?(?:[ '’-]\p{L}+\.?)*$/u;
const MRN_DIGITS = /^\d{4,10}$/;
export const MRN_PREFIX = "MRN-";
const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
const POSTAL_CODE = /^\d{5}(?:-\d{4})?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
export const US_STATES = (
  "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ " +
  "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC AS GU MP PR VI"
).split(" ");
export const BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] as const;
export const SEXES = { female: "Female", male: "Male", nonbinary: "Nonbinary", other: "Other" };
export const STATUSES = { active: "Active", inactive: "Inactive", deceased: "Deceased" };

const NAME_RULE = "Use letters, with spaces, hyphens, apostrophes, or periods between them";

const name = (missing: string) =>
  z
    .string()
    .trim()
    .min(1, missing)
    .refine((v) => NAME.test(v.replace(/\s+/g, " ")), NAME_RULE);

/** Optional text: empty is fine, anything typed must pass `check`. */
const optional = (check: (value: string) => boolean, message: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === "" || check(v), message);

function isPhone(value: string): boolean {
  let digits = value.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) digits = digits.slice(1);
  return digits.length === 10 && !/[^\d\s()+.-]/.test(value);
}

function isDob(value: string): boolean {
  if (!DATE.test(value)) return false;
  const date = new Date(`${value}T00:00:00`);
  return !Number.isNaN(date.getTime()) && date.getFullYear() >= 1900 && date <= new Date();
}

export const patientSchema = z.object({
  first_name: name("Enter a first name"),
  last_name: name("Enter a last name"),
  // Just the number; MRN_PREFIX is added when saving.
  mrn: z
    .string()
    .trim()
    .refine((v) => MRN_DIGITS.test(v), "Enter the MRN's digits"),
  dob: z
    .string()
    .trim()
    .refine(isDob, "Enter a date of birth as YYYY-MM-DD, not in the future or before 1900"),
  // Registration norms: administrative sex and a way to reach the patient are required.
  gender: z.string().min(1, "Choose the patient's sex"),
  phone: z
    .string()
    .trim()
    .min(1, "Enter a phone number to reach the patient")
    .refine(isPhone, "Enter a 10-digit phone number, e.g. 555-867-5309"),
  email: optional((v) => EMAIL.test(v), "Enter an email address like name@example.com"),
  address_line1: optional((v) => /[\p{L}\d]/u.test(v), "Enter a street address"),
  address_line2: z.string().trim(),
  city: optional((v) => NAME.test(v.replace(/\s+/g, " ")), NAME_RULE),
  state: z.string(),
  postal_code: optional(
    (v) => POSTAL_CODE.test(v),
    "Use a 5-digit ZIP code, or ZIP+4 (02139-4307)",
  ),
  blood_type: z.string(),
  status: z.string(),
  allergies: z.array(
    z.object({
      substance: z.string().trim().min(1, "Enter the substance"),
      severity: z.string(),
    }),
  ),
  conditions: z.array(
    z.object({
      icd10_code: z.string().trim().min(1, "Enter the ICD-10 code"),
      name: z.string().trim().min(1, "Enter the condition"),
    }),
  ),
});

export type PatientFormValues = z.infer<typeof patientSchema>;

/** The text fields sent to the API, in form order. */
export const DEMOGRAPHIC_FIELDS = [
  "first_name",
  "last_name",
  "mrn",
  "dob",
  "gender",
  "phone",
  "email",
  "address_line1",
  "address_line2",
  "city",
  "state",
  "postal_code",
  "blood_type",
] as const;

export type DemographicField = (typeof DEMOGRAPHIC_FIELDS)[number];
type Demographics = Record<DemographicField, string>;

export function emptyPatient(): PatientFormValues {
  const blank = Object.fromEntries(DEMOGRAPHIC_FIELDS.map((f) => [f, ""])) as Demographics;
  return { ...blank, status: "active", allergies: [], conditions: [] };
}

export function fromPatient(patient: PatientDetail): PatientFormValues {
  const current = Object.fromEntries(
    DEMOGRAPHIC_FIELDS.map((f) => [f, patient[f] ?? ""]),
  ) as Demographics;
  const mrn = patient.mrn.toUpperCase().startsWith(MRN_PREFIX)
    ? patient.mrn.slice(MRN_PREFIX.length)
    : patient.mrn;
  return { ...current, mrn, status: patient.status, allergies: [], conditions: [] };
}

/** The chosen fields as the API expects them (`T` is the request body): trimmed, empty as null. */
export function toApi<T>(values: PatientFormValues, fields: readonly DemographicField[]): T {
  const body = Object.fromEntries(
    fields.map((f) => {
      const value = values[f].trim();
      if (value === "") return [f, null];
      return [f, f === "mrn" ? `${MRN_PREFIX}${value}` : value];
    }),
  );
  // The values passed `patientSchema`, which holds the same rules as these API types.
  return body as T;
}
