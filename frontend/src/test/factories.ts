import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export function makeMe(overrides: Partial<Schemas["MeOut"]> = {}): Schemas["MeOut"] {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    name: "Dr. Wei Chen",
    role: "provider",
    credential: "MD",
    permissions: ["VIEW_DEMOGRAPHICS", "VIEW_CLINICAL"],
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
