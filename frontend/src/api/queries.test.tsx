import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vite-plus/test";

import { CHEN, makeMe, makeProblem } from "@/test/factories";
import { server } from "@/test/msw/server";

import { api } from "./index";
import { personaStore } from "./persona";
import { ApiProblem } from "./errors";
import { queryKeys, useApiQuery } from "./queries";

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

describe("useApiQuery", () => {
  beforeEach(() => personaStore.set(CHEN.id));

  it("returns the response data", async () => {
    const { wrapper } = setup();
    const { result } = renderHook(
      () => useApiQuery(queryKeys.me(CHEN.id), (signal) => api.GET("/api/v1/auth/me", { signal })),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.name).toBe(makeMe().name);
  });

  it("surfaces API problems as the query error", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json(makeProblem(403, "PERMISSION_DENIED"), { status: 403 }),
      ),
    );
    const { wrapper } = setup();

    const { result } = renderHook(
      () => useApiQuery(queryKeys.me(CHEN.id), (signal) => api.GET("/api/v1/auth/me", { signal })),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiProblem);
    expect((result.current.error as ApiProblem).code).toBe("PERMISSION_DENIED");
  });

  it("aborts the request when the query is cancelled", async () => {
    let requestSignal: AbortSignal | undefined;
    server.use(
      http.get("/api/v1/auth/me", async ({ request }) => {
        requestSignal = request.signal;
        await new Promise(() => {});
      }),
    );
    const { client, wrapper } = setup();

    renderHook(
      () => useApiQuery(queryKeys.me(CHEN.id), (signal) => api.GET("/api/v1/auth/me", { signal })),
      { wrapper },
    );
    await waitFor(() => expect(requestSignal).toBeDefined());
    await client.cancelQueries({ queryKey: queryKeys.me(CHEN.id) });

    expect(requestSignal?.aborted).toBe(true);
  });
});

describe("queryKeys", () => {
  it("keys patient queries so a whole group can be invalidated together", () => {
    expect(queryKeys.patients.detail("p1").slice(0, 1)).toEqual(queryKeys.patients.all);
    expect(queryKeys.patients.list({ scope: "my" }).slice(0, 1)).toEqual(queryKeys.patients.all);
  });

  it("only accepts the list endpoint's own query params", () => {
    // @ts-expect-error: "search" isn't a parameter of GET /patients
    queryKeys.patients.list({ search: "osei" });
  });
});
