import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vite-plus/test";

import { makeDetail, makeProblem } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const patient = makeDetail();
const url = `/api/v1/patients/${patient.id}/summary`;

type Summary = {
  status: "fresh" | "stale" | "waiting" | "generating" | "failed" | "blocked";
  narrative: string | null;
  generated_at: string | null;
  next_refresh_at: string | null;
  provider: string | null;
  error_code: string | null;
};

function summary(overrides: Partial<Summary> = {}) {
  const narrative =
    overrides.narrative === undefined ? "70-year-old with hypertension." : overrides.narrative;
  return {
    header: { allergies: [], conditions: [{ icd10_code: "I10", name: "Hypertension" }] },
    status: "fresh",
    generated_at: new Date(Date.now() - 3 * 60_000).toISOString(),
    next_refresh_at: null,
    provider: "Mock AI",
    error_code: null,
    ...overrides,
    narrative,
    is_ai_generated: narrative !== null,
  };
}

/** Answers the summary endpoint with each response in turn (the last one repeats). */
function summaryIs(...responses: ReturnType<typeof summary>[]) {
  let calls = 0;
  server.use(
    http.get(url, () => HttpResponse.json(responses[Math.min(calls++, responses.length - 1)])),
  );
  return () => calls;
}

const card = () => screen.findByRole("region", { name: "AI summary" });

describe("AI summary", () => {
  it("labels a fresh summary as AI-generated, with its age and provider", async () => {
    summaryIs(summary());
    renderApp(`/patients/${patient.id}`);

    const region = await card();
    expect(await within(region).findByText("70-year-old with hypertension.")).toBeInTheDocument();
    expect(region).toHaveTextContent("AI-generated: verify before clinical use");
    expect(region).toHaveTextContent("Updated 3 min ago");
    expect(region).toHaveTextContent("Mock AI");
  });

  it("counts down to a pending refresh after new changes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const soon = new Date(Date.now() + 12_000).toISOString();
      summaryIs(summary({ status: "stale", next_refresh_at: soon }));
      renderApp(`/patients/${patient.id}`);

      const region = await card();
      expect(
        await within(region).findByText(/New changes, refreshing in 1[12]s/),
      ).toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(5_000);
      // Rounds up, like any countdown: 7.2s left reads "8s".
      expect(within(region).getByText(/refreshing in [678]s/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("says the AI service is busy, not that the chart changed, on a first load", async () => {
    const soon = new Date(Date.now() + 20_000).toISOString();
    summaryIs(
      summary({
        status: "waiting",
        narrative: null,
        generated_at: null,
        error_code: "rate_limited",
        next_refresh_at: soon,
      }),
    );
    renderApp(`/patients/${patient.id}`);

    const region = await card();
    expect(
      await within(region).findByText(/AI service is busy, trying again in (19|20)s/),
    ).toBeInTheDocument();
    expect(region).not.toHaveTextContent("New changes");
  });

  it("keeps the last summary on screen while an update waits on the AI service", async () => {
    const soon = new Date(Date.now() + 20_000).toISOString();
    summaryIs(summary({ status: "waiting", error_code: "rate_limited", next_refresh_at: soon }));
    renderApp(`/patients/${patient.id}`);

    const region = await card();
    expect(await within(region).findByText("70-year-old with hypertension.")).toBeInTheDocument();
    expect(within(region).getByText(/Update queued, trying again in (19|20)s/)).toBeInTheDocument();
    expect(region).not.toHaveTextContent("New changes");
  });

  it("polls while generating and shows the result when it's ready", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const calls = summaryIs(summary({ status: "generating", narrative: null }), summary());
      renderApp(`/patients/${patient.id}`);

      const region = await card();
      expect(await within(region).findByText("Generating…")).toBeInTheDocument();
      await vi.advanceTimersByTimeAsync(2_100);

      expect(await within(region).findByText("70-year-old with hypertension.")).toBeInTheDocument();
      expect(calls()).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("explains a request the privacy check blocked", async () => {
    summaryIs(summary({ status: "blocked", narrative: null, error_code: "blocked" }));
    renderApp(`/patients/${patient.id}`);

    expect(
      await within(await card()).findByText(
        "Narrative unavailable: privacy check blocked this request",
      ),
    ).toBeInTheDocument();
  });

  it("offers a retry when generation failed", async () => {
    const user = userEvent.setup();
    summaryIs(summary({ status: "failed", narrative: null, error_code: "timeout" }));
    let refreshed = 0;
    server.use(
      http.post(`${url}/refresh`, () => {
        refreshed += 1;
        return HttpResponse.json(summary({ status: "generating", narrative: null }), {
          status: 202,
        });
      }),
    );
    renderApp(`/patients/${patient.id}`);

    const region = await card();
    expect(await within(region).findByText("Couldn't generate the narrative")).toBeInTheDocument();
    await user.click(within(region).getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(refreshed).toBe(1));
  });

  it("disables Refresh now with its own countdown while rate-limited", async () => {
    const user = userEvent.setup();
    summaryIs(summary());
    server.use(
      http.post(`${url}/refresh`, () =>
        HttpResponse.json(makeProblem(429, "RATE_LIMITED", { retry_after: 7 }), {
          status: 429,
          headers: { "Retry-After": "7" },
        }),
      ),
    );
    renderApp(`/patients/${patient.id}`);

    const region = await card();
    await user.click(await within(region).findByRole("button", { name: "Refresh now" }));

    const button = await within(region).findByRole("button", { name: /Refresh in [67]s/ });
    expect(button).toBeDisabled();
  });

  it("keeps the deterministic header even when there's no narrative", async () => {
    summaryIs(summary({ status: "failed", narrative: null, error_code: "timeout" }));
    renderApp(`/patients/${patient.id}`);

    expect(await screen.findByRole("region", { name: "Active problems" })).toBeInTheDocument();
  });
});
