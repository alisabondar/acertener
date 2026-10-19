import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import { ADMIN, OKAFOR } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const PATIENT = "55555555-5555-4555-8555-000000000001";

function entry(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    occurred_at: "2026-10-19T14:05:00Z",
    actor_id: OKAFOR.id,
    actor_name: "Sam Okafor",
    actor_role: "nurse",
    via_demo_persona: true,
    action: "update",
    entity: "patient",
    entity_id: PATIENT,
    patient_id: PATIENT,
    request_id: "req-1",
    changed_fields: ["city", "phone"],
    ...overrides,
  };
}

/** Answers the audit log with `pages[before_id ?? "first"]`, recording each request's query. */
function auditLog(pages: Record<string, { items: unknown[]; next_before_id: number | null }>) {
  const queries: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/admin/audit-log", ({ request }) => {
      const params = new URL(request.url).searchParams;
      queries.push(params);
      return HttpResponse.json(pages[params.get("before_id") ?? "first"]);
    }),
  );
  return queries;
}

describe("audit log", () => {
  it("shows who did what and when, with field names only and a link to the patient", async () => {
    auditLog({ first: { items: [entry(2)], next_before_id: null } });
    renderApp("/admin/audit", { persona: ADMIN });

    const [, row] = await screen.findAllByRole("row");
    expect(row).toHaveTextContent("Sam Okafor");
    expect(row).toHaveTextContent("Nurse");
    expect(row).toHaveTextContent("Demo");
    expect(row).toHaveTextContent("Updated patient");
    expect(row).toHaveTextContent("city, phone");
    expect(within(row!).getByRole("link", { name: "Open chart" })).toHaveAttribute(
      "href",
      `/patients/${PATIENT}`,
    );
  });

  it("filters by person and loads older entries", async () => {
    const user = userEvent.setup();
    const queries = auditLog({
      first: { items: [entry(9)], next_before_id: 9 },
      "9": { items: [entry(4, { action: "view", changed_fields: [] })], next_before_id: null },
    });
    renderApp("/admin/audit", { persona: ADMIN });
    await screen.findAllByRole("row");

    await user.click(screen.getByRole("button", { name: "Load older" }));
    expect(await screen.findByText("Viewed patient")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load older" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Person"), "Sam Okafor");
    await screen.findAllByRole("row");
    expect(queries.at(-1)?.get("actor_id")).toBe(OKAFOR.id);
  });
});
