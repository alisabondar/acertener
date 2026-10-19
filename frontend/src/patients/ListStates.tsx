import { ApiProblem } from "@/api/errors";
import { Button } from "@/components/ui/button";

export function EmptyState({
  message,
  detail,
  action,
  onAction,
}: {
  message: string;
  detail?: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-xl border border-dashed bg-card py-16 text-center">
      <p className="text-[15px] font-medium">{message}</p>
      {detail && <p className="mt-1 text-[13px] text-muted-foreground">{detail}</p>}
      {action && onAction && (
        <Button variant="outline" className="mt-4" onClick={onAction}>
          {action}
        </Button>
      )}
    </div>
  );
}

/** A failed load: retryable, except a 403, which retrying can't fix. */
export function ListError({
  error,
  what,
  onRetry,
}: {
  error: Error;
  /** What failed to load, e.g. "patients". */
  what: string;
  onRetry: () => void;
}) {
  const forbidden = error instanceof ApiProblem && error.status === 403;
  return (
    <div role="alert" className="rounded-xl border bg-card py-16 text-center">
      <p className="text-[15px] font-medium">
        {forbidden ? "You don't have permission to view this list" : `Couldn't load ${what}`}
      </p>
      {!forbidden && (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
