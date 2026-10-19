import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { memo, Profiler, type ComponentProps, type ProfilerOnRenderCallback } from "react";
import { describe, expect, it, vi } from "vite-plus/test";

import { makePage, makePatient } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const commits = vi.hoisted(() => ({ list: [] as { phase: string; duration: number }[] }));

// React's Profiler around the patient table: every commit of the table's tree is recorded, with
// how long it took. The wrapper is memoized like the table, so it adds no renders of its own.
vi.mock("@/patients/PatientTable", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/patients/PatientTable")>();
  const record: ProfilerOnRenderCallback = (_id, phase, actualDuration) => {
    commits.list.push({ phase, duration: actualDuration });
  };
  return {
    ...original,
    PatientTable: memo((props: ComponentProps<typeof original.PatientTable>) => (
      <Profiler id="patient-table" onRender={record}>
        <original.PatientTable {...props} />
      </Profiler>
    )),
  };
});

describe("patient list performance (React Profiler)", () => {
  it("doesn't re-render the table on each keystroke, only when results change", async () => {
    const user = userEvent.setup();
    const page = Array.from({ length: 20 }, () => makePatient());
    server.use(
      http.get("/api/v1/patients", () => HttpResponse.json(makePage(page))),
      http.post("/api/v1/patients/search", () =>
        HttpResponse.json(makePage([makePatient({ last_name: "Osei" })])),
      ),
    );
    const { queryClient } = renderApp("/patients");
    await screen.findAllByRole("row", { name: /MRN-/ });
    // Count only after the first load settles: every request (list, counts, the next page's
    // prefetch) has finished, so nothing but typing can re-render the table.
    await screen.findByRole("button", { name: /^Active \d/ });
    await waitFor(() => expect(queryClient.isFetching()).toBe(0));
    const box = screen.getByRole("searchbox", { name: "Search patients" });
    commits.list = [];

    // Two letters: below the search threshold, so the results can't change.
    await user.type(box, "os");
    expect(commits.list).toEqual([]);

    // The third letter searches, and the new results are the table's first commit since.
    await user.type(box, "e");
    await screen.findByRole("row", { name: /Osei/ });
    expect(commits.list.length).toBeGreaterThan(0);
  });
});
