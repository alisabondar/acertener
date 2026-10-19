import { screen, waitFor } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import { BROOKS, makeDetail, makeProblem } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const NEW_ID = "22222222-2222-4222-8222-000000000001";

/** Records each POST to `path` and answers with `respond` (a 201 with a new patient by default). */
function posts(path: string, respond?: (call: number) => Response) {
  const bodies: unknown[] = [];
  server.use(
    http.post(path, async ({ request }) => {
      bodies.push(await request.json());
      return (
        respond?.(bodies.length) ?? HttpResponse.json(makeDetail({ id: NEW_ID }), { status: 201 })
      );
    }),
  );
  return bodies;
}

async function fillRequired(user: UserEvent) {
  await user.type(await screen.findByLabelText("First name"), "Ada");
  await user.type(screen.getByLabelText("Last name"), "O'Neil");
  await user.type(screen.getByLabelText("MRN"), "200001");
  await user.type(screen.getByLabelText("Date of birth"), "1984-02-29");
  await user.selectOptions(screen.getByLabelText("Sex"), "female");
  await user.type(screen.getByLabelText("Phone"), "555-867-5309");
}

describe("new patient", () => {
  it("checks the fields in the browser before sending anything", async () => {
    const user = userEvent.setup();
    const bodies = posts("/api/v1/patients");
    renderApp("/patients/new");

    await user.type(await screen.findByLabelText("Last name"), "x1!!");
    await user.type(screen.getByLabelText("Phone"), "555-0100");
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    expect(await screen.findByLabelText("First name")).toHaveAccessibleDescription(
      "Enter a first name",
    );
    expect(screen.getByLabelText("Last name")).toHaveAccessibleDescription(
      "Use letters, with spaces, hyphens, apostrophes, or periods between them",
    );
    expect(screen.getByLabelText("Phone")).toHaveAccessibleDescription(
      "Enter a 10-digit phone number, e.g. 555-867-5309",
    );
    expect(bodies).toEqual([]);
  });

  it("won't register a patient without the critical details", async () => {
    const user = userEvent.setup();
    const bodies = posts("/api/v1/patients");
    renderApp("/patients/new");

    await user.click(await screen.findByRole("button", { name: "Create patient" }));

    for (const [label, message] of [
      ["Date of birth", "Enter a date of birth as YYYY-MM-DD, not in the future or before 1900"],
      ["Sex", "Choose the patient's sex"],
      ["MRN", "Enter the MRN's 4 to 10 digits"],
      ["Phone", "Enter a phone number to reach the patient"],
    ]) {
      expect(screen.getByLabelText(label!)).toHaveAccessibleDescription(message!);
    }
    expect(bodies).toEqual([]);
  });

  it("takes the MRN as digits only", async () => {
    const user = userEvent.setup();
    renderApp("/patients/new");

    await user.type(await screen.findByLabelText("MRN"), "MRN-12");
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    expect(screen.getByLabelText("MRN")).toHaveAccessibleDescription(
      "Enter the MRN's 4 to 10 digits",
    );
  });

  it("creates the patient with their medical details, then opens the chart", async () => {
    const user = userEvent.setup();
    const created = posts("/api/v1/patients");
    const allergies = posts(`/api/v1/patients/${NEW_ID}/allergies`, () =>
      HttpResponse.json({}, { status: 201 }),
    );
    const { router } = renderApp("/patients/new");

    await fillRequired(user);
    await user.selectOptions(screen.getByLabelText("Blood type"), "O-");
    await user.click(screen.getByRole("button", { name: "Add allergy" }));
    await user.type(screen.getByLabelText("Allergy 1 substance"), "Penicillin");
    await user.selectOptions(screen.getByLabelText("Allergy 1 severity"), "severe");
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/patients/${NEW_ID}`));
    expect(created).toEqual([
      expect.objectContaining({
        first_name: "Ada",
        last_name: "O'Neil",
        mrn: "MRN-200001",
        gender: "female",
        phone: "555-867-5309",
        dob: "1984-02-29",
        blood_type: "O-",
        confirm_not_duplicate: false,
      }),
    ]);
    expect(allergies).toEqual([{ substance: "Penicillin", reaction: null, severity: "severe" }]);
  });

  it("shows the server's validation errors on the fields that caused them", async () => {
    const user = userEvent.setup();
    posts("/api/v1/patients", () =>
      HttpResponse.json(
        makeProblem(422, "VALIDATION_FAILED", { errors: { mrn: "This MRN is already in use" } }),
        { status: 422 },
      ),
    );
    renderApp("/patients/new");

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    expect(await screen.findByLabelText("MRN")).toHaveAccessibleDescription(
      "This MRN is already in use",
    );
  });

  it("warns about a likely duplicate, links to it, and can create anyway", async () => {
    const user = userEvent.setup();
    const existing = "33333333-3333-4333-8333-000000000001";
    const bodies = posts("/api/v1/patients", (call) =>
      call === 1
        ? HttpResponse.json(makeProblem(409, "POSSIBLE_DUPLICATE", { matches: [existing] }), {
            status: 409,
          })
        : HttpResponse.json(makeDetail({ id: NEW_ID }), { status: 201 }),
    );
    const { router } = renderApp("/patients/new");

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    const warning = await screen.findByRole("alert", { name: "Possible duplicate" });
    expect(screen.getByRole("link", { name: "Open the existing chart" })).toHaveAttribute(
      "href",
      `/patients/${existing}`,
    );
    await user.click(screen.getByRole("button", { name: "Create anyway" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/patients/${NEW_ID}`));
    expect(warning).not.toBeInTheDocument();
    expect(bodies).toEqual([
      expect.objectContaining({ confirm_not_duplicate: false }),
      expect.objectContaining({ confirm_not_duplicate: true }),
    ]);
  });

  it("flags an MRN that's already in use and links to that patient", async () => {
    const user = userEvent.setup();
    const holder = "66666666-6666-4666-8666-000000000001";
    posts("/api/v1/patients", () =>
      HttpResponse.json(makeProblem(409, "DUPLICATE_MRN", { matches: [holder] }), { status: 409 }),
    );
    renderApp("/patients/new");

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    expect(await screen.findByLabelText("MRN")).toHaveAccessibleDescription(
      "Something specific went wrong.",
    );
    expect(screen.getByRole("link", { name: "Open the patient with this MRN" })).toHaveAttribute(
      "href",
      `/patients/${holder}`,
    );
  });

  it("says plainly when the server can't be reached, and retries", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("/api/v1/patients", async ({ request }) => {
        bodies.push(await request.json());
        return bodies.length === 1
          ? HttpResponse.error()
          : HttpResponse.json(makeDetail({ id: NEW_ID }), { status: 201 });
      }),
    );
    const { router } = renderApp("/patients/new");

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Create patient" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach the server");
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/patients/${NEW_ID}`));
    expect(bodies).toHaveLength(2);
  });

  it("after a failure partway through, retrying finishes the job without a second patient", async () => {
    const user = userEvent.setup();
    const created = posts("/api/v1/patients");
    let allergyCalls = 0;
    server.use(
      http.post(`/api/v1/patients/${NEW_ID}/allergies`, () => {
        allergyCalls += 1;
        return allergyCalls === 1 ? HttpResponse.error() : HttpResponse.json({}, { status: 201 });
      }),
    );
    const { router } = renderApp("/patients/new");

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Add allergy" }));
    await user.type(screen.getByLabelText("Allergy 1 substance"), "Penicillin");
    await user.click(screen.getByRole("button", { name: "Create patient" }));
    await user.click(await screen.findByRole("button", { name: "Try again" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/patients/${NEW_ID}`));
    expect(created).toHaveLength(1);
    expect(allergyCalls).toBe(2);
  });

  it("leaves clinical fields out for front desk", async () => {
    renderApp("/patients/new", { persona: BROOKS });

    expect(await screen.findByLabelText("First name")).toBeInTheDocument();
    expect(screen.queryByLabelText("Blood type")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add allergy" })).not.toBeInTheDocument();
  });
});

describe("edit patient", () => {
  const id = "11111111-1111-4111-8111-000000000001";

  it("starts from the current record and sends only what changed", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`/api/v1/patients/${id}`, () =>
        HttpResponse.json(makeDetail({ id, city: "Springfield", version: 4 })),
      ),
    );
    const patches: unknown[] = [];
    server.use(
      http.patch(`/api/v1/patients/${id}`, async ({ request }) => {
        patches.push(await request.json());
        return HttpResponse.json(makeDetail({ id, city: "Shelbyville", version: 5 }));
      }),
    );
    const { router } = renderApp(`/patients/${id}/edit`);

    const city = await screen.findByLabelText("City");
    expect(city).toHaveValue("Springfield");
    await user.clear(city);
    await user.type(city, "Shelbyville");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/patients/${id}`));
    expect(patches).toEqual([{ base_version: 4, changes: { city: "Shelbyville" } }]);
  });

  it("explains a conflicting edit and offers the latest version", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`/api/v1/patients/${id}`, () =>
        HttpResponse.json(makeDetail({ id, city: "Springfield", version: 4 })),
      ),
      http.patch(`/api/v1/patients/${id}`, () =>
        HttpResponse.json(
          makeProblem(409, "VERSION_CONFLICT", {
            current: makeDetail({ id, city: "Capital City", version: 5 }),
          }),
          { status: 409 },
        ),
      ),
    );
    renderApp(`/patients/${id}/edit`);

    const city = await screen.findByLabelText("City");
    await user.clear(city);
    await user.type(city, "Shelbyville");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Someone else changed this record while you were editing",
    );
    await user.click(screen.getByRole("button", { name: "Load their version" }));

    expect(screen.getByLabelText("City")).toHaveValue("Capital City");
  });
});
