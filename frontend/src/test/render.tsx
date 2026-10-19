import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router";
import { beforeAll } from "vite-plus/test";

import { personaStore } from "@/api/persona";
import { appRoutes } from "@/app/routes";

import type { Persona } from "./factories";

// Lazily loaded pages compile on first import. Only files that render the app import this module,
// so only they pay for it, once, before their tests; under heavy parallel load compiling can take a
// while, which is why the hook gets longer than the default 10 s.
beforeAll(async () => {
  await Promise.all([
    import("@/patients/PatientList"),
    import("@/home/MyDay"),
    import("@/chart/PatientChart"),
  ]);
}, 60_000);

/** Renders the app at `path`, optionally already acting as `persona`, with a fresh cache. */
export function renderApp(
  path = "/",
  { persona, routes = appRoutes }: { persona?: Persona; routes?: RouteObject[] } = {},
) {
  if (persona) personaStore.set(persona.id);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { queryClient, router };
}
