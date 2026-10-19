import { http, HttpResponse } from "msw";

import { PERSONA_HEADER } from "@/api/client";

import {
  makeCounts,
  makeDay,
  makeDetail,
  makeMe,
  makePage,
  makePatient,
  makeProblem,
  PERSONAS,
} from "../factories";

/** Default handlers every test starts with; override per test with server.use(...). */
export const handlers = [
  http.get("/api/v1/personas", () => HttpResponse.json(PERSONAS)),
  http.get("/api/v1/auth/me", ({ request }) => {
    const persona = PERSONAS.find((p) => p.id === request.headers.get(PERSONA_HEADER));
    return persona
      ? HttpResponse.json(makeMe(persona))
      : HttpResponse.json(makeProblem(401, "NOT_AUTHENTICATED"), { status: 401 });
  }),
  http.get("/api/v1/patients", () => HttpResponse.json(makePage([makePatient()]))),
  http.post("/api/v1/patients/search", () => HttpResponse.json(makePage([]))),
  http.get("/api/v1/patients/filter-counts", () => HttpResponse.json(makeCounts())),
  http.get("/api/v1/visits/today", () => HttpResponse.json(makeDay([]))),
  http.get("/api/v1/patients/:patientId", ({ params }) =>
    HttpResponse.json(makeDetail({ id: String(params["patientId"]) })),
  ),
  http.get("/api/v1/patients/:patientId/allergies", () => HttpResponse.json({ items: [] })),
];
