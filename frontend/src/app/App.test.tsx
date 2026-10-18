import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router";
import { describe, expect, it } from "vite-plus/test";

import { ApiProblem } from "@/api/errors";

import { RouteError } from "@/pages/RouteError";

import { appRoutes } from "./routes";
import { Shell } from "./Shell";

function renderAt(path: string, routes: RouteObject[] = appRoutes) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("app shell", () => {
  it("shows the main navigation in the sidebar", () => {
    renderAt("/");

    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(nav.closest('[data-slot="sidebar"]')).not.toBeNull();
    for (const name of ["My day", "Patients", "New patient", "Admin"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it("collapses the sidebar to icons and expands it again", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const sidebar = () => document.querySelector('[data-slot="sidebar"][data-state]');
    const toggle = () =>
      within(screen.getByRole("main")).getByRole("button", { name: "Toggle Sidebar" });

    await user.click(toggle());
    expect(sidebar()).toHaveAttribute("data-state", "collapsed");

    await user.click(toggle());
    expect(sidebar()).toHaveAttribute("data-state", "expanded");
  });

  it.each([
    ["/", "My day"],
    ["/patients", "Patients"],
    ["/patients/new", "New patient"],
    ["/patients/11111111-1111-4111-8111-111111111111", "Patient chart"],
    ["/admin/audit", "Audit log"],
  ])("routes %s to its page", (path, heading) => {
    renderAt(path);

    expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it.each([
    ["/patients/11111111-1111-4111-8111-111111111111", "Patients"],
    ["/patients/new", "New patient"],
    ["/patients/new/", "New patient"],
    ["/patients/", "Patients"],
    ["/admin/audit", "Admin"],
  ])("highlights the right section on %s", (path, section) => {
    renderAt(path);

    const current = screen
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page")
      .map((link) => link.textContent);
    expect(current).toEqual([section]);
  });

  it("shows a not-found page with a way home", () => {
    renderAt("/no/such/page");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to My day" })).toHaveAttribute("href", "/");
  });

  it("catches errors in a page and shows the request id, never a stack trace", () => {
    function Broken(): never {
      throw new ApiProblem({
        status: 500,
        code: "INTERNAL_ERROR",
        detail: "Boom",
        requestId: "req-9",
      });
    }
    const routes: RouteObject[] = [
      {
        element: <Shell />,
        children: [
          { errorElement: <RouteError />, children: [{ path: "broken", element: <Broken /> }] },
        ],
      },
    ];

    renderAt("/broken", routes);

    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/at Broken|\.tsx:\d+/);
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });
});
