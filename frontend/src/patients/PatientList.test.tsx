import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import {
  ADMIN,
  BROOKS,
  makeCounts,
  makePage,
  makePatient,
  makeProblem,
  type PatientListItem,
} from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

/** Answers the list endpoint and records each request's query string. */
function listReturns(respond: (url: URL) => Promise<Response> | Response) {
  const requests: URL[] = [];
  server.use(
    http.get("/api/v1/patients", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      return respond(url);
    }),
  );
  return requests;
}

const rows = () => screen.findAllByRole("row", { name: /MRN-/ });

describe("patient list", () => {
  it("shows a skeleton, then patients with DOB, flags for non-active status, and hints", async () => {
    listReturns(() =>
      HttpResponse.json(
        makePage([
          makePatient({ last_name: "Osei", first_name: "Daniel", mrn: "MRN-100008" }),
          makePatient({
            last_name: "Becker",
            first_name: "Tom",
            status: "inactive",
            inactivity_suggested: true,
          }),
        ]),
      ),
    );
    renderApp("/patients");

    expect(await screen.findByRole("status", { name: "Loading patients" })).toBeInTheDocument();
    const [osei, becker] = await rows();
    expect(osei).toHaveTextContent("Osei, Daniel");
    expect(osei).toHaveTextContent("MRN-100008");
    expect(osei).toHaveTextContent("04/02/1963 (63y)");
    expect(osei).not.toHaveTextContent("Active");
    expect(becker).toHaveTextContent("Inactive");
    expect(becker).toHaveTextContent("No visit in 3+ years");
  });

  it("opens a patient's chart from their row", async () => {
    const user = userEvent.setup();
    const patient = makePatient({ last_name: "Osei" });
    listReturns(() => HttpResponse.json(makePage([patient])));
    const { router } = renderApp("/patients");

    await user.click((await rows())[0]!);

    expect(router.state.location.pathname).toBe(`/patients/${patient.id}`);
  });

  it("explains an empty care team", async () => {
    listReturns(() => HttpResponse.json(makePage([])));
    renderApp("/patients");

    expect(await screen.findByText("No patients on your care team yet")).toBeInTheDocument();
  });

  it("offers a retry when the list fails, and recovers", async () => {
    const user = userEvent.setup();
    let fail = true;
    listReturns(() =>
      fail
        ? HttpResponse.json(makeProblem(500, "INTERNAL_ERROR"), { status: 500 })
        : HttpResponse.json(makePage([makePatient()])),
    );
    renderApp("/patients");

    const retry = await screen.findByRole("button", { name: "Try again" });
    fail = false;
    await user.click(retry);

    expect(await rows()).toHaveLength(1);
  });

  it("says plainly when the role can't see the list", async () => {
    listReturns(() => HttpResponse.json(makeProblem(403, "PERMISSION_DENIED"), { status: 403 }));
    renderApp("/patients");

    expect(
      await screen.findByText("You don't have permission to view this list"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("keeps the current page visible while the next one loads", async () => {
    const user = userEvent.setup();
    const page = (n: number) =>
      Array.from({ length: 20 }, (_, i) => makePatient({ last_name: `Page${n}-${i}` }));
    listReturns(async (url) => {
      const n = Number(url.searchParams.get("page") ?? 1);
      if (n === 2) await delay(150);
      return HttpResponse.json(makePage(page(n), { total: 45, page: n }));
    });
    renderApp("/patients");
    expect(await screen.findByText("1–20 of 45")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(screen.getByText(/Page1-0/)).toBeInTheDocument();
    expect(await screen.findByText(/Page2-0/)).toBeInTheDocument();
    expect(screen.getByText("21–40 of 45")).toBeInTheDocument();
  });

  it("fetches the next page ahead of time, but not past the last page", async () => {
    const requests = listReturns((url) => {
      const n = Number(url.searchParams.get("page") ?? 1);
      return HttpResponse.json(makePage([makePatient()], { total: 45, page: n }));
    });
    renderApp("/patients?page=2");
    await rows();

    await waitFor(() => expect(requests.map((url) => url.searchParams.get("page"))).toContain("3"));
    await delay(100);
    expect(requests.map((url) => url.searchParams.get("page"))).not.toContain("4");
  });

  it("sorts on the server when a column header is clicked", async () => {
    const user = userEvent.setup();
    const requests = listReturns(() => HttpResponse.json(makePage([makePatient()])));
    const { router } = renderApp("/patients");
    await rows();

    await user.click(screen.getByRole("button", { name: "Sort by age" }));

    await waitFor(() => expect(requests.at(-1)?.searchParams.get("sort")).toBe("age"));
    expect(router.state.location.search).toContain("sort=age");
  });
});

describe("quick filters", () => {
  it("shows counts and filters the list by status", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/v1/patients/filter-counts", () =>
        HttpResponse.json(makeCounts({ status: { active: 120, inactive: 30, deceased: 2 } })),
      ),
    );
    const requests = listReturns(() => HttpResponse.json(makePage([makePatient()])));
    const { router } = renderApp("/patients");

    await user.click(await screen.findByRole("button", { name: "Inactive 30" }));

    await waitFor(() => expect(requests.at(-1)?.searchParams.get("status")).toBe("inactive"));
    expect(router.state.location.search).toBe("?status=inactive");
    expect(screen.getByRole("button", { name: "Inactive 30" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it.each<[string, typeof ADMIN, { archived: boolean; today: boolean; myTab: boolean }]>([
    ["Practice Admin", ADMIN, { archived: true, today: false, myTab: false }],
    ["Taylor Brooks", BROOKS, { archived: false, today: true, myTab: false }],
  ])("shows %s only the filters their role uses", async (_name, persona, expected) => {
    renderApp("/patients", { persona });
    await rows();

    const filters = screen.getByRole("group", { name: "Quick filters" });
    expect(!!within(filters).queryByRole("button", { name: /Show archived/ })).toBe(
      expected.archived,
    );
    expect(!!within(filters).queryByRole("button", { name: /Today's visits/ })).toBe(
      expected.today,
    );
    expect(!!screen.queryByRole("tab", { name: "My patients" })).toBe(expected.myTab);
  });
});

describe("search", () => {
  function searchReturns(items: PatientListItem[], wait = 0) {
    const bodies: unknown[] = [];
    const signals: AbortSignal[] = [];
    server.use(
      http.post("/api/v1/patients/search", async ({ request }) => {
        signals.push(request.signal);
        bodies.push(await request.clone().json());
        if (wait) await delay(wait);
        return HttpResponse.json(makePage(items));
      }),
    );
    return { bodies, signals };
  }

  it("waits for 3 letters of the last name, then searches once, keeping terms out of the URL", async () => {
    const user = userEvent.setup();
    const { bodies } = searchReturns([makePatient({ last_name: "Osei" })]);
    const { router } = renderApp("/patients");
    const box = await screen.findByRole("searchbox", { name: "Search patients" });

    await user.type(box, "os");
    expect(box).toHaveAccessibleDescription("Type at least 3 letters of the last name");
    expect(box).toBeInvalid();
    await delay(400);
    expect(bodies).toHaveLength(0);

    await user.type(box, "ei");

    await waitFor(() => expect(bodies).toEqual([{ last_name: "osei" }]));
    expect(router.state.location.search).not.toMatch(/osei/i);
  });

  it("starts a new search from the first page", async () => {
    const user = userEvent.setup();
    const pages: (string | null)[] = [];
    server.use(
      http.post("/api/v1/patients/search", ({ request }) => {
        pages.push(new URL(request.url).searchParams.get("page"));
        return HttpResponse.json(makePage([makePatient()]));
      }),
    );
    renderApp("/patients?page=6");

    await user.type(await screen.findByRole("searchbox", { name: "Search patients" }), "garc");

    await waitFor(() => expect(pages).toEqual(["1"]));
  });

  it("flags a partly typed date of birth instead of silently ignoring it", async () => {
    renderApp("/patients");
    const dob = await screen.findByLabelText("Date of birth");

    // Browsers report a half-typed date (such as a year alone) as empty but "badInput".
    Object.defineProperty(dob, "validity", { value: { badInput: true }, configurable: true });
    fireEvent.input(dob, { target: { value: "" } });

    expect(dob).toHaveAccessibleDescription("Enter the full date of birth (month, day, and year)");
    expect(dob).toBeInvalid();

    await userEvent.click(screen.getByRole("button", { name: "Clear date of birth" }));

    expect(dob).toBeValid();
    expect(dob).not.toHaveAccessibleDescription();
  });

  it("shows no note under the search box until there's a problem", async () => {
    renderApp("/patients");

    expect(
      await screen.findByRole("searchbox", { name: "Search patients" }),
    ).not.toHaveAccessibleDescription();
  });

  it("aborts a search that's overtaken by newer typing", async () => {
    const user = userEvent.setup();
    const { bodies, signals } = searchReturns([makePatient()], 1000);
    renderApp("/patients");
    const box = await screen.findByRole("searchbox", { name: "Search patients" });

    await user.type(box, "osei");
    await waitFor(() => expect(bodies).toHaveLength(1));
    await user.type(box, "n");

    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(signals[0]?.aborted).toBe(true);
  });

  it("explains that one word searches last names, so a first name alone finds nothing", async () => {
    const user = userEvent.setup();
    searchReturns([]);
    renderApp("/patients");

    await user.type(await screen.findByRole("searchbox", { name: "Search patients" }), "daniel");

    expect(await screen.findByText("No last names start with “daniel”")).toBeInTheDocument();
    expect(screen.getByText("To search by first name, type “last, first”.")).toBeInTheDocument();
  });

  it("clears the search from an × in the box, with no other clear button", async () => {
    const user = userEvent.setup();
    renderApp("/patients");
    const box = await screen.findByRole("searchbox", { name: "Search patients" });
    expect(screen.queryByRole("button", { name: "Clear search text" })).not.toBeInTheDocument();

    await user.type(box, "osei");
    await user.click(screen.getByRole("button", { name: "Clear search text" }));

    expect(box).toHaveValue("");
    expect(box).toHaveFocus();
    expect(screen.queryByRole("button", { name: /^Clear$/ })).not.toBeInTheDocument();
  });

  it("explains a search with no matches and clears it", async () => {
    const user = userEvent.setup();
    searchReturns([]);
    renderApp("/patients");
    const box = await screen.findByRole("searchbox", { name: "Search patients" });

    await user.type(box, "zzzz");
    await user.click(await screen.findByRole("button", { name: "Clear search" }));

    expect(box).toHaveValue("");
    // Clearing isn't debounced: the stale "no matches" result goes at once.
    expect(screen.queryByText(/No last names start with/)).not.toBeInTheDocument();
    expect(await rows()).toHaveLength(1);
  });
});
