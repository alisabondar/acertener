import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vite-plus/test";

import { makePage, makePatient } from "@/test/factories";
import { server } from "@/test/msw/server";
import { renderApp } from "@/test/render";

const rowRenders = vi.hoisted(() => ({ count: 0 }));

// Count how often table rows render, to catch work the user's typing shouldn't cause.
vi.mock("@/components/ui/table", async (importOriginal) => {
  const table = await importOriginal<typeof import("@/components/ui/table")>();
  return {
    ...table,
    TableRow: (props: ComponentProps<typeof table.TableRow>) => {
      rowRenders.count += 1;
      return <table.TableRow {...props} />;
    },
  };
});

describe("patient list performance", () => {
  it("doesn't re-render the table on each keystroke, only when results change", async () => {
    const user = userEvent.setup();
    const page = Array.from({ length: 20 }, () => makePatient());
    server.use(http.get("/api/v1/patients", () => HttpResponse.json(makePage(page))));
    renderApp("/patients");
    await screen.findAllByRole("row", { name: /MRN-/ });
    const box = screen.getByRole("searchbox", { name: "Search patients" });
    rowRenders.count = 0;

    // Two letters: below the search threshold, so the results can't change.
    await user.type(box, "os");

    expect(rowRenders.count).toBe(0);
  });
});
