import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vite-plus/test";

import { BROOKS, makeDay, makeVisit, type ScheduledVisit } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

/** Answers today's schedule and records each request's scope. */
function dayIs(items: ScheduledVisit[]) {
  const scopes: (string | null)[] = [];
  server.use(
    http.get("/api/v1/visits/today", ({ request }) => {
      scopes.push(new URL(request.url).searchParams.get("scope"));
      return HttpResponse.json(makeDay(items));
    }),
  );
  return scopes;
}

const schedule = () => screen.findByRole("list", { name: "Today's schedule" });

describe("My day", () => {
  it("shows today's visits in time order, with a Now marker between past and upcoming", async () => {
    dayIs([
      makeVisit(-120, {
        status: "completed",
        patient: { ...makeVisit(0).patient, last_name: "Early" },
      }),
      makeVisit(90, { patient: { ...makeVisit(0).patient, last_name: "Later" } }),
    ]);
    renderApp("/");

    const items = within(await schedule()).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining("Early"),
      expect.stringContaining("Now"),
      expect.stringContaining("Later"),
    ]);
    expect(items[0]).toHaveTextContent("Completed");
    expect(items[2]).toHaveTextContent("04/02/1963 (63y)");
  });

  it("summarises the day", async () => {
    dayIs([
      makeVisit(-60, { status: "checked_in" }),
      makeVisit(-30, { status: "no_show" }),
      makeVisit(-90, { status: "completed" }),
      makeVisit(60),
    ]);
    renderApp("/");

    const summary = await screen.findByRole("region", { name: "Today at a glance" });
    await waitFor(() => expect(summary).toHaveTextContent(/Today's visits\s*4/));
    expect(summary).toHaveTextContent(/Checked in\s*1/);
    expect(summary).toHaveTextContent(/Completed\s*1/);
    expect(summary).not.toHaveTextContent(/Still to come/);
    expect(summary).toHaveTextContent(/No-shows\s*1/);
    // The schedule is by provider and the list by care team, so the counts aren't links.
    expect(within(summary).queryByRole("link")).not.toBeInTheDocument();
  });

  it("refreshes the schedule every minute, so other staff's check-ins appear", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      let checkedIn = false;
      server.use(
        http.get("/api/v1/visits/today", () =>
          HttpResponse.json(
            makeDay([makeVisit(30, { status: checkedIn ? "checked_in" : "scheduled" })]),
          ),
        ),
      );
      renderApp("/");
      const list = await schedule();
      expect(list).toHaveTextContent("Scheduled");

      checkedIn = true;
      await vi.advanceTimersByTimeAsync(60_000);

      await waitFor(() => expect(list).toHaveTextContent("Checked in"));
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens a patient's chart from the schedule", async () => {
    const visit = makeVisit(30);
    dayIs([visit]);
    const { router } = renderApp("/");

    // The whole visit card is the link, so there's exactly one per visit.
    const [card] = within(await schedule()).getAllByRole("link");
    expect(within(await schedule()).getAllByRole("link")).toHaveLength(1);
    expect(card).toHaveTextContent(/\d:\d\d [AP]M/);
    await userEvent.click(card!);

    expect(router.state.location.pathname).toBe(`/patients/${visit.patient.id}`);
  });

  it("dates the page by the practice's calendar day, not the browser's", async () => {
    server.use(
      http.get("/api/v1/visits/today", () =>
        HttpResponse.json({ ...makeDay([]), date: "2026-10-19" }),
      ),
    );
    renderApp("/");

    expect(await screen.findByText(/Monday, October 19/)).toBeInTheDocument();
  });

  it("says so when nothing is scheduled", async () => {
    dayIs([]);
    renderApp("/");

    expect(await screen.findByText("No visits scheduled today")).toBeInTheDocument();
  });

  it("shows front desk the whole practice's day, with providers but no clinical reasons", async () => {
    const scopes = dayIs([makeVisit(30, { reason: null, provider_name: "Jordan Rivera" })]);
    renderApp("/", { persona: BROOKS });

    expect(await schedule()).toHaveTextContent("Jordan Rivera");
    expect(scopes).toEqual(["all"]);
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("leaves patient search to the Patients page", async () => {
    dayIs([makeVisit(30)]);
    renderApp("/");

    await schedule();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  });
});
