import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vite-plus/test";

import { server } from "@/test/msw/server";
import { makeMe, makeProblem } from "@/test/factories";

import { createApiClient } from "./client";
import { ApiProblem, NetworkError } from "./errors";

const PERSONA = "11111111-1111-4111-8111-111111111111";

describe("api client", () => {
  it("sends the active persona", async () => {
    let seen: string | null = null;
    server.use(
      http.get("/api/v1/auth/me", ({ request }) => {
        seen = request.headers.get("X-Persona");
        return HttpResponse.json(makeMe());
      }),
    );

    const { data } = await createApiClient({ getPersona: () => PERSONA }).GET("/api/v1/auth/me");

    expect(seen).toBe(PERSONA);
    expect(data?.name).toBe("Dr. Wei Chen");
  });

  it("omits the header when no persona is chosen", async () => {
    let had = true;
    server.use(
      http.get("/api/v1/auth/me", ({ request }) => {
        had = request.headers.has("X-Persona");
        return HttpResponse.json(makeMe());
      }),
    );

    await createApiClient({ getPersona: () => null }).GET("/api/v1/auth/me");

    expect(had).toBe(false);
  });

  it("turns problem responses into ApiProblem with their code, request id, and extras", async () => {
    server.use(
      http.post("/api/v1/patients", () =>
        HttpResponse.json(makeProblem(409, "POSSIBLE_DUPLICATE", { matches: ["p1"] }), {
          status: 409,
        }),
      ),
    );

    const call = createApiClient({ getPersona: () => PERSONA }).POST("/api/v1/patients", {
      body: {
        first_name: "Ada",
        last_name: "Smith",
        mrn: "MRN-1",
        dob: "1990-01-01",
        gender: "female",
        phone: "555-867-5309",
      },
    });

    await expect(call).rejects.toMatchObject({
      name: "ApiProblem",
      status: 409,
      code: "POSSIBLE_DUPLICATE",
      requestId: "req-123",
      extras: { matches: ["p1"] },
    });
    await expect(call).rejects.toBeInstanceOf(ApiProblem);
  });

  it("reports network failures clearly", async () => {
    server.use(http.get("/api/v1/auth/me", () => HttpResponse.error()));

    await expect(
      createApiClient({ getPersona: () => PERSONA }).GET("/api/v1/auth/me"),
    ).rejects.toBeInstanceOf(NetworkError);
  });

  it("fails any request that no test handler expects", async () => {
    await expect(
      createApiClient({ getPersona: () => PERSONA }).GET("/api/v1/admin/audit-log"),
    ).rejects.toBeInstanceOf(NetworkError);
  });
});
