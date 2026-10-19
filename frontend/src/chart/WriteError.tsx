import { CircleAlert } from "lucide-react";

import { ApiProblem } from "@/api/errors";

/** Why a save failed, next to the form: a plain 403 message, or the API's own detail. */
export function WriteError({ error, action }: { error: Error | null; action: string }) {
  if (!error) return null;
  const message =
    error instanceof ApiProblem && error.status === 403
      ? `You don't have permission to ${action}`
      : error instanceof ApiProblem && error.status !== 422
        ? error.detail
        : error instanceof ApiProblem
          ? "Some fields need attention."
          : "Couldn't save. Check your connection and try again.";
  return (
    <p role="alert" className="flex items-center gap-1.5 text-[13px] text-severe">
      <CircleAlert className="size-4 shrink-0" aria-hidden />
      {message}
    </p>
  );
}
