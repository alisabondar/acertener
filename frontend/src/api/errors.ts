const STANDARD_MEMBERS = new Set(["type", "title", "status", "detail", "code", "request_id"]);

/** A non-2xx API response in RFC 9457 Problem Details form. Never carries PHI. */
export class ApiProblem extends Error {
  override readonly name: string = "ApiProblem";
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly requestId: string | null;
  /** Extra members, e.g. `errors` (field errors), `matches`, or `current`. */
  readonly extras: Record<string, unknown>;

  constructor(init: {
    status: number;
    code: string;
    detail: string;
    requestId: string | null;
    extras?: Record<string, unknown>;
  }) {
    super(init.detail);
    this.status = init.status;
    this.code = init.code;
    this.detail = init.detail;
    this.requestId = init.requestId;
    this.extras = init.extras ?? {};
  }

  static async fromResponse(response: Response): Promise<ApiProblem> {
    const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    const { status, detail, code, request_id } = body;
    const extras = Object.fromEntries(
      Object.entries(body).filter(([key]) => !STANDARD_MEMBERS.has(key)),
    );
    const init = {
      status: typeof status === "number" ? status : response.status,
      code: typeof code === "string" ? code : "UNKNOWN_ERROR",
      detail: typeof detail === "string" ? detail : response.statusText,
      requestId: typeof request_id === "string" ? request_id : response.headers.get("X-Request-ID"),
      extras,
    };
    return new ApiProblem(init);
  }
}

/** The request never got a response (offline, server down, CORS). */
export class NetworkError extends Error {
  override readonly name = "NetworkError";

  constructor(cause: unknown) {
    super("Couldn't reach the server. Check your connection and try again.", { cause });
  }
}
