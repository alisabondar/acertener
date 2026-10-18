import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router";

import { personaStore } from "@/api/persona";
import { appRoutes } from "@/app/routes";

import type { Persona } from "./factories";

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
