import { http, HttpResponse } from "msw";

import { makeMe } from "../factories";

/** Default handlers every test starts with; override per test with server.use(...). */
export const handlers = [http.get("/api/v1/auth/me", () => HttpResponse.json(makeMe()))];
