import { Link, useRouteError } from "react-router";

import { ApiProblem } from "@/api/errors";

/** Shown when a page fails. Gives a reference for support, never a stack trace. */
export function RouteError() {
  const error = useRouteError();
  const requestId = error instanceof ApiProblem ? error.requestId : null;
  return (
    <section className="py-16 text-center">
      <h1 className="text-[28px] font-semibold">Something went wrong</h1>
      <p className="mt-2 text-[15px] text-muted-foreground">
        This page couldn't load. Try again or go to your home page.
      </p>
      {requestId && (
        <p className="mt-2 text-[13px] text-muted-foreground">Reference: {requestId}</p>
      )}
      <Link
        to="/"
        className="mt-6 inline-block font-medium text-primary underline underline-offset-4"
      >
        Go to your home page
      </Link>
    </section>
  );
}
