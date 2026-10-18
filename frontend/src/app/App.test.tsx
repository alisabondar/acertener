import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RouteObject } from "react-router";
import { describe, expect, it } from "vite-plus/test";

import { ApiProblem } from "@/api/errors";
import { CurrentUserProvider } from "@/auth/CurrentUserProvider";
import { RouteError } from "@/pages/RouteError";
import { renderApp } from "@/test/render";

import { Shell } from "./Shell";

const nav = () => screen.findByRole("navigation", { name: "Main" });

describe("app shell", () => {
  it("shows the main navigation in the sidebar", async () => {
    renderApp("/");

    expect((await nav()).closest('[data-slot="sidebar"]')).not.toBeNull();
  });

  it("collapses the sidebar to icons and expands it again", async () => {
    const user = userEvent.setup();
    renderApp("/");
    await nav();
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
  ])("routes %s to its page", async (path, heading) => {
    renderApp(path);

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  });

  it.each([
    ["/patients/11111111-1111-4111-8111-111111111111", "Patients"],
    ["/patients/new", "New patient"],
    ["/patients/new/", "New patient"],
    ["/patients/", "Patients"],
  ])("highlights the right section on %s", async (path, section) => {
    renderApp(path);

    const current = within(await nav())
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page")
      .map((link) => link.textContent);
    expect(current).toEqual([section]);
  });

  it("shows a not-found page with a way home", async () => {
    renderApp("/no/such/page");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your home page" })).toHaveAttribute("href", "/");
  });

  it("catches errors in a page and shows the request id, never a stack trace", async () => {
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
        element: (
          <CurrentUserProvider>
            <Shell />
          </CurrentUserProvider>
        ),
        children: [
          { errorElement: <RouteError />, children: [{ path: "broken", element: <Broken /> }] },
        ],
      },
    ];

    renderApp("/broken", { routes });

    expect(
      await screen.findByRole("heading", { name: "Something went wrong" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/at Broken|\.tsx:\d+/);
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });
});
