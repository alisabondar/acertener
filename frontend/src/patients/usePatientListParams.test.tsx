import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vite-plus/test";

import { DEFAULT_LIST_PARAMS, usePatientListParams } from "./usePatientListParams";

function renderAt(url: string, defaultScope: "my" | "all" = "my") {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>
  );
  const { result } = renderHook(
    () => {
      const [params, setParams] = usePatientListParams({ defaultScope });
      return { params, setParams, search: useLocation().search };
    },
    { wrapper },
  );
  return result;
}

describe("usePatientListParams", () => {
  it("gives the defaults for an empty URL", () => {
    const result = renderAt("/patients");

    expect(result.current.params).toEqual(DEFAULT_LIST_PARAMS);
  });

  it("reads valid values with their real types", () => {
    const result = renderAt(
      "/patients?scope=all&filter=today_visits&status=inactive&include_archived=true&sort=age&order=asc&page=3&page_size=50",
    );

    expect(result.current.params).toEqual({
      scope: "all",
      filter: "today_visits",
      status: "inactive",
      include_archived: true,
      sort: "age",
      order: "asc",
      page: 3,
      page_size: 50,
    });
  });

  it.each([
    ["sort=name", { sort: "last_visit" }],
    ["page=-1", { page: 1 }],
    ["page=abc", { page: 1 }],
    ["page_size=1000", { page_size: 20 }],
    ["status=deleted", { status: null }],
    ["include_archived=yes", { include_archived: false }],
  ])("falls back to the default for %s and keeps the valid values", (bad, fallback) => {
    const result = renderAt(`/patients?order=asc&${bad}`);

    expect(result.current.params).toEqual({ ...DEFAULT_LIST_PARAMS, order: "asc", ...fallback });
  });

  it("removes unknown keys from the URL, since they could carry identifying text", () => {
    const result = renderAt("/patients?q=smith&last_name=osei&sort=age");

    expect(result.current.search).toBe("?sort=age");
  });

  it("writes only non-default values to the URL", () => {
    const result = renderAt("/patients?sort=age");

    act(() => result.current.setParams({ status: "deceased", sort: "last_visit" }));

    expect(result.current.search).toBe("?status=deceased");
    expect(result.current.params.status).toBe("deceased");
  });

  it("goes back to page 1 when a filter changes", () => {
    const result = renderAt("/patients?page=4");

    act(() => result.current.setParams({ status: "active" }));

    expect(result.current.params.page).toBe(1);
  });

  it("keeps the filters when only the page changes", () => {
    const result = renderAt("/patients?status=active");

    act(() => result.current.setParams({ page: 2 }));

    expect(result.current.search).toBe("?status=active&page=2");
  });

  it("keeps every change when several are made at once", () => {
    const result = renderAt("/patients");

    act(() => {
      result.current.setParams({ status: "active" });
      result.current.setParams({ sort: "age" });
    });

    expect(result.current.search).toBe("?status=active&sort=age");
  });

  it("uses the caller's default scope", () => {
    const result = renderAt("/patients", "all");

    expect(result.current.params.scope).toBe("all");
    act(() => result.current.setParams({ scope: "my" }));
    expect(result.current.search).toBe("?scope=my");
  });
});
