import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import { queryKeys } from "@/api/queries";
import { ADMIN, BROOKS, CHEN, makeProblem, OKAFOR, type Persona, RIVERA } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

/** The one identity control: shows who you are and opens the "View as" menu. */
const banner = () => screen.findByRole("button", { name: /^(Viewing as|Switching to)/ });

async function navLinks() {
  const nav = await screen.findByRole("navigation", { name: "Main" });
  return within(nav)
    .getAllByRole("link")
    .map((link) => link.textContent);
}

describe("demo identity", () => {
  it("starts as the first persona the API offers", async () => {
    renderApp("/");

    const identity = await banner();
    expect(identity).toHaveTextContent("Viewing as Dr. Wei Chen (Provider, MD)");
    expect(document.body).not.toHaveTextContent(/demo mode/i);
  });

  it("switches persona from the banner and drops everything cached as the previous one", async () => {
    const user = userEvent.setup();
    const { queryClient } = renderApp("/");
    await banner();
    expect(queryClient.getQueryData(queryKeys.me(CHEN.id))).toBeDefined();

    await user.click(await banner());
    await user.click(await screen.findByRole("menuitemradio", { name: /Sam Okafor/ }));

    expect(await banner()).toHaveTextContent("Viewing as Sam Okafor (Nurse, RN)");
    expect(queryClient.getQueryData(queryKeys.me(CHEN.id))).toBeUndefined();
  });

  it("keeps the navigation while switching, showing no page until the new persona loads", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/v1/auth/me", async ({ request }) => {
        if (request.headers.get("X-Persona") === OKAFOR.id) await delay(100);
        return undefined;
      }),
    );
    renderApp("/");
    await banner();

    await user.click(await banner());
    await user.click(await screen.findByRole("menuitemradio", { name: /Sam Okafor/ }));

    expect(await banner()).toHaveTextContent("Switching to Sam Okafor");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "My day" })).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading" })).toHaveTextContent(
      "Loading your day as Sam Okafor",
    );
    await waitFor(async () =>
      expect(await banner()).toHaveTextContent("Viewing as Sam Okafor (Nurse, RN)"),
    );
  });

  it.each([["/api/v1/personas"], ["/api/v1/auth/me"]])(
    "shows the error page, not the app, when %s refuses the demo identity",
    async (path) => {
      server.use(
        http.get(path, () =>
          HttpResponse.json(makeProblem(401, "NOT_AUTHENTICATED"), { status: 401 }),
        ),
      );
      renderApp("/");

      expect(
        await screen.findByRole("heading", { name: "Something went wrong" }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    },
  );
});

it("explains the problem instead of loading forever when no personas are seeded", async () => {
  server.use(http.get("/api/v1/personas", () => HttpResponse.json([])));
  renderApp("/");

  expect(await screen.findByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
});

describe("role-aware navigation", () => {
  it.each<[string, Persona, string[]]>([
    [CHEN.name, CHEN, ["My day", "Patients", "New patient"]],
    [RIVERA.name, RIVERA, ["My day", "Patients", "New patient"]],
    [OKAFOR.name, OKAFOR, ["My day", "Patients", "New patient"]],
    [BROOKS.name, BROOKS, ["My day", "Patients", "New patient"]],
    [ADMIN.name, ADMIN, ["Patients", "Admin"]],
  ])("shows %s only the sections their role can use", async (_name, persona, expected) => {
    renderApp("/patients", { persona });

    expect(await navLinks()).toEqual(expected);
  });

  it("sends admin home to the audit log, since they have no visits", async () => {
    renderApp("/", { persona: ADMIN });

    expect(await screen.findByRole("heading", { level: 1, name: "Audit log" })).toBeInTheDocument();
  });
});

describe("route guards", () => {
  it("tells front desk they can't open the audit log, keeping the navigation", async () => {
    renderApp("/admin/audit", { persona: BROOKS });

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });

  it("lets admin open the audit log", async () => {
    renderApp("/admin/audit", { persona: ADMIN });

    expect(await screen.findByRole("heading", { level: 1, name: "Audit log" })).toBeInTheDocument();
  });

  it("keeps admin out of patient registration", async () => {
    renderApp("/patients/new", { persona: ADMIN });

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
  });
});
