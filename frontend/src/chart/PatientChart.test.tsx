import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import {
  BROOKS,
  CHEN,
  makeAllergy,
  makeCondition,
  makeDetail,
  makeNote,
  makeProblem,
  makeVitals,
  OKAFOR,
  type Note,
  type Persona,
} from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const patient = makeDetail();
const base = `/api/v1/patients/${patient.id}`;

/** A chart with one of everything, and a record of every write the page sends. */
function chartIs({ notes = [makeNote()] }: { notes?: Note[] } = {}) {
  const writes: { method: string; path: string; body: unknown }[] = [];
  const record = async (request: Request) => {
    const body = request.method === "DELETE" ? null : await request.clone().json();
    writes.push({ method: request.method, path: new URL(request.url).pathname, body });
  };
  server.use(
    http.get(base, () => HttpResponse.json(patient)),
    http.get(`${base}/notes`, () => HttpResponse.json({ items: notes })),
    http.get(`${base}/vitals`, () => HttpResponse.json({ items: [makeVitals()] })),
    http.get(`${base}/allergies`, () =>
      HttpResponse.json({
        items: [makeAllergy(), makeAllergy({ id: "a2", substance: "Latex", severity: "mild" })],
      }),
    ),
    http.get(`${base}/conditions`, () => HttpResponse.json({ items: [makeCondition()] })),
    http.get(`${base}/access-log`, () =>
      HttpResponse.json({
        items: [
          {
            action: "view",
            actor_name: CHEN.name,
            actor_role: "provider",
            changed_fields: [],
            occurred_at: "2026-10-01T10:00:00Z",
            via_demo_persona: true,
          },
        ],
        next_before_id: null,
      }),
    ),
    http.post(`${base}/notes`, async ({ request }) => {
      await record(request);
      return HttpResponse.json(makeNote({ id: "n-new", status: "draft", finalized_at: null }), {
        status: 201,
      });
    }),
    http.patch("/api/v1/notes/:id", async ({ request }) => {
      await record(request);
      return HttpResponse.json(makeNote({ id: "n-new", status: "draft", finalized_at: null }));
    }),
    http.post("/api/v1/notes/:id/finalize", async ({ request }) => {
      writes.push({ method: "POST", path: new URL(request.url).pathname, body: null });
      return HttpResponse.json(makeNote({ id: "n-new" }));
    }),
    http.delete("/api/v1/notes/:id", async ({ request }) => {
      await record(request);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return writes;
}

const open = (persona?: Persona) =>
  renderApp(`/patients/${patient.id}`, persona ? { persona } : {});

describe("patient chart", () => {
  it("identifies the patient and flags severe allergies up front", async () => {
    chartIs();
    open();

    const header = await screen.findByRole("region", { name: "Patient" });
    expect(header).toHaveTextContent("Osei, Daniel");
    expect(header).toHaveTextContent("04/02/1963 (63y)");
    expect(header).toHaveTextContent("MRN-100008");
    expect(header).toHaveTextContent("Blood type O+");
    expect(within(header).getByRole("link", { name: "Edit details" })).toHaveAttribute(
      "href",
      "/patients/44444444-4444-4444-8444-000000000001/edit",
    );
    const alert = await screen.findByRole("alert", { name: "Severe allergies" });
    expect(alert).toHaveTextContent("Penicillin");
    expect(alert).not.toHaveTextContent("Latex");
  });

  it("shows front desk demographics only: no clinical tabs and no allergy banner", async () => {
    chartIs();
    open(BROOKS);

    await screen.findByRole("region", { name: "Patient" });
    const tabs = within(screen.getByRole("tablist")).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Contact"]);
    expect(screen.queryByRole("alert", { name: "Severe allergies" })).not.toBeInTheDocument();
    expect(screen.getByText("Springfield, IL 62701")).toBeInTheDocument();
  });

  it("lets a nurse edit allergies but locks diagnoses with a reason", async () => {
    const user = userEvent.setup();
    chartIs();
    open(OKAFOR);

    await user.click(await screen.findByRole("tab", { name: "Allergies & conditions" }));

    expect(await screen.findByRole("button", { name: "Edit allergies" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit conditions" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Requires a provider role")).toBeInTheDocument();
  });

  it("shows the access history only to roles allowed to see it", async () => {
    const user = userEvent.setup();
    chartIs();
    open();

    await user.click(await screen.findByRole("tab", { name: "Access history" }));

    expect(await screen.findByRole("table", { name: "Access history" })).toHaveTextContent(
      CHEN.name,
    );
  });
});

it("opens on an overview of the AI summary, then problems and allergies; contact has its own tab", async () => {
  const user = userEvent.setup();
  chartIs();
  open();

  const tabs = within(await screen.findByRole("tablist")).getAllByRole("tab");
  expect(tabs.map((t) => t.textContent)).toEqual([
    "Overview",
    "Contact",
    "Notes",
    "Vitals",
    "Allergies & conditions",
    "Access history",
  ]);
  const overview = screen.getByRole("tabpanel");
  const titles = within(overview)
    .getAllByRole("heading", { level: 2 })
    .map((h) => h.textContent);
  expect(titles).toEqual(["AI summary", "Active problems", "Active allergies"]);
  expect(overview).not.toHaveTextContent("Springfield");

  await user.click(screen.getByRole("tab", { name: "Vitals" }));
  expect(await screen.findByRole("region", { name: "Latest vitals" })).toHaveTextContent("142/88");
});

describe("notes", () => {
  it("drafts, saves, and finalizes a note", async () => {
    const user = userEvent.setup();
    const writes = chartIs();
    open();
    await user.click(await screen.findByRole("tab", { name: "Notes" }));

    await user.click(await screen.findByRole("button", { name: "New note" }));
    await user.type(screen.getByRole("textbox", { name: "Note" }), "Seen for BP check.");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Finalize" }));

    await waitFor(() =>
      expect(writes.map((w) => `${w.method} ${w.path}`)).toEqual([
        `POST ${base}/notes`,
        "PATCH /api/v1/notes/n-new",
        "POST /api/v1/notes/n-new/finalize",
      ]),
    );
    expect(writes[0]?.body).toEqual({ content: "Seen for BP check." });
    expect(await screen.findByText("Note finalized")).toBeInTheDocument();
  });

  it("offers delete only on my own drafts, after a confirmation", async () => {
    const user = userEvent.setup();
    const mine = makeNote({ id: "mine", status: "draft", finalized_at: null, content: "My draft" });
    const theirs = makeNote({ id: "theirs", author_id: OKAFOR.id, author_name: OKAFOR.name });
    const writes = chartIs({ notes: [mine, theirs] });
    open();
    await user.click(await screen.findByRole("tab", { name: "Notes" }));

    const list = await screen.findByRole("list", { name: "Notes" });
    expect(within(list).getAllByRole("button", { name: "Delete draft" })).toHaveLength(1);
    await user.click(within(list).getByRole("button", { name: "Delete draft" }));
    const confirm = await screen.findByRole("alertdialog", { name: "Delete this draft?" });
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(writes.map((w) => `${w.method} ${w.path}`)).toEqual(["DELETE /api/v1/notes/mine"]),
    );
  });
});

it("shows the API's field error on the note itself", async () => {
  const user = userEvent.setup();
  chartIs();
  server.use(
    http.post(`${base}/notes`, () =>
      HttpResponse.json(
        makeProblem(422, "VALIDATION_FAILED", {
          errors: { content: "String should have at most 20000 characters" },
        }),
        { status: 422 },
      ),
    ),
  );
  open();
  await user.click(await screen.findByRole("tab", { name: "Notes" }));

  await user.click(await screen.findByRole("button", { name: "New note" }));
  await user.type(screen.getByRole("textbox", { name: "Note" }), "Too long, say.");
  await user.click(screen.getByRole("button", { name: "Save draft" }));

  expect(await screen.findByRole("textbox", { name: "Note" })).toHaveAccessibleDescription(
    "String should have at most 20000 characters",
  );
});

describe("vitals", () => {
  it("shows the API's range errors on the fields that caused them", async () => {
    const user = userEvent.setup();
    chartIs();
    server.use(
      http.post(`${base}/vitals`, () =>
        HttpResponse.json(
          makeProblem(422, "VALIDATION_FAILED", {
            errors: { bp_systolic: "Input should be less than or equal to 260" },
          }),
          { status: 422 },
        ),
      ),
    );
    open(OKAFOR);
    await user.click(await screen.findByRole("tab", { name: "Vitals" }));

    await user.click(await screen.findByRole("button", { name: "Record vitals" }));
    await user.type(screen.getByLabelText("Systolic"), "1200");
    await user.click(screen.getByRole("button", { name: "Save vitals" }));

    expect(await screen.findByLabelText("Systolic")).toHaveAccessibleDescription(
      "Input should be less than or equal to 260",
    );
  });

  it("says plainly when the role isn't allowed to save", async () => {
    const user = userEvent.setup();
    chartIs();
    server.use(
      http.post(`${base}/vitals`, () =>
        HttpResponse.json(makeProblem(403, "PERMISSION_DENIED"), { status: 403 }),
      ),
    );
    open(OKAFOR);
    await user.click(await screen.findByRole("tab", { name: "Vitals" }));

    await user.click(await screen.findByRole("button", { name: "Record vitals" }));
    await user.type(screen.getByLabelText("Heart rate"), "80");
    await user.click(screen.getByRole("button", { name: "Save vitals" }));

    expect(
      await screen.findByText("You don't have permission to record vitals"),
    ).toBeInTheDocument();
  });
});
