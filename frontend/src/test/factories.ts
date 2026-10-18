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
