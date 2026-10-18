import createClient, { type Middleware } from "openapi-fetch";

import { ApiProblem, NetworkError } from "./errors";
import type { paths } from "./schema";

export const PERSONA_HEADER = "X-Persona";

type ClientOptions = {
  /** Who to act as (demo mode). Read on every request, so switching takes effect at once. */
  getPersona: () => string | null;
  /** Defaults to this page's origin; in development Vite proxies /api to FastAPI. */
  baseUrl?: string;
};

export function createApiClient({ getPersona, baseUrl = window.location.origin }: ClientOptions) {
  // Look fetch up per request, not once at creation, so anything that wraps it later
  // (test mocks, monitoring) still sees every call.
  const client = createClient<paths>({ baseUrl, fetch: (request) => globalThis.fetch(request) });
  const middleware: Middleware = {
    onRequest({ request }) {
      const persona = getPersona();
      if (persona) request.headers.set(PERSONA_HEADER, persona);
      return request;
    },
    async onResponse({ response }) {
      if (!response.ok) throw await ApiProblem.fromResponse(response);
      return response;
    },
    onError({ error }) {
      throw new NetworkError(error);
    },
  };
  client.use(middleware);
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;
