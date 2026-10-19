import { formatDistanceToNowStrict, parseISO } from "date-fns";
import { LoaderCircle, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";

import { api } from "@/api";
import { ApiProblem } from "@/api/errors";
import { queryKeys, useApiMutation, useApiQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { Panel } from "@/components/Fields";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/useNow";

type Summary = components["schemas"]["SummaryOut"];

const GENERATING_POLL_MS = 2_000;

/** When to ask again: every 2s while generating, at the refresh time while pending, else never. */
function nextPoll(summary: Summary | undefined): number | false {
  if (!summary) return false;
  if (summary.status === "generating") return GENERATING_POLL_MS;
  if ((summary.status === "stale" || summary.status === "waiting") && summary.next_refresh_at) {
    return Math.max(1_000, parseISO(summary.next_refresh_at).getTime() - Date.now() + 500);
  }
  return false;
}

function secondsUntil(iso: string | number, now: Date): number {
  const at = typeof iso === "number" ? iso : parseISO(iso).getTime();
  return Math.max(0, Math.ceil((at - now.getTime()) / 1000));
}

export function SummaryCard({ patientId }: { patientId: string }) {
  const now = useNow(1_000);
  const key = queryKeys.patients.chart(patientId, "summary");
  const summary = useApiQuery(
    key,
    (signal) =>
      api.GET("/api/v1/patients/{patient_id}/summary", {
        params: { path: { patient_id: patientId } },
        signal,
      }),
    { refetchInterval: nextPoll },
  );
  // "Refresh now" is rate-limited per patient; remember until when, to count down on the button.
  const [blockedUntil, setBlockedUntil] = useState<number | null>(null);
  const refresh = useApiMutation(
    () =>
      api.POST("/api/v1/patients/{patient_id}/summary/refresh", {
        params: { path: { patient_id: patientId } },
      }),
    { invalidate: [key] },
  );
  const refreshNow = () =>
    void refresh.mutateAsync(undefined).catch((error: unknown) => {
      const retryAfter =
        error instanceof ApiProblem && error.status === 429
          ? Number(error.extras["retry_after"])
          : 0;
      if (retryAfter > 0) setBlockedUntil(Date.now() + retryAfter * 1000);
    });
  const waitSeconds = blockedUntil ? secondsUntil(blockedUntil, now) : 0;

  const data = summary.data;
  return (
    <Panel title="AI summary">
      {!data ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <div className="space-y-3">
          <Body summary={data} now={now} onRetry={refreshNow} />
          <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[12px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-brand" aria-hidden />
              AI-generated: verify before clinical use
              {data.provider && (
                <span className="rounded-full bg-muted px-2 py-0.5 font-medium text-foreground">
                  {data.provider}
                </span>
              )}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={waitSeconds > 0 || refresh.isPending || data.status === "generating"}
              onClick={refreshNow}
            >
              <RefreshCw /> {waitSeconds > 0 ? `Refresh in ${waitSeconds}s` : "Refresh now"}
            </Button>
          </div>
        </div>
      )}
    </Panel>
  );
}

function Body({ summary, now, onRetry }: { summary: Summary; now: Date; onRetry: () => void }) {
  if (summary.status === "blocked") {
    return (
      <p className="flex items-center gap-2 text-[14px] text-status-inactive">
        <ShieldAlert className="size-4 shrink-0" aria-hidden />
        Narrative unavailable: privacy check blocked this request
      </p>
    );
  }
  if (summary.status === "failed") {
    return (
      <div className="flex items-center justify-between gap-3">
        <p className="text-[14px] text-muted-foreground">Couldn't generate the narrative</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }
  if (summary.status === "waiting" && !summary.narrative) {
    return (
      <p role="status" className="flex items-center gap-2 text-[14px] text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        Generating… the AI service is busy, trying again in{" "}
        {secondsUntil(summary.next_refresh_at ?? now.getTime(), now)}s
      </p>
    );
  }
  if (summary.status === "generating" && !summary.narrative) {
    return (
      <p role="status" className="flex items-center gap-2 text-[14px] text-muted-foreground">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        Generating…
      </p>
    );
  }
  return (
    <div className="space-y-1.5">
      {summary.narrative && <p className="text-[15px] leading-relaxed">{summary.narrative}</p>}
      <p className="text-[12px] text-muted-foreground" aria-live="polite">
        {summary.status === "stale" && summary.next_refresh_at
          ? `New changes, refreshing in ${secondsUntil(summary.next_refresh_at, now)}s`
          : summary.status === "waiting" && summary.next_refresh_at
            ? `Update queued, trying again in ${secondsUntil(summary.next_refresh_at, now)}s`
            : summary.status === "generating"
              ? "Updating…"
              : summary.generated_at
                ? `Updated ${formatDistanceToNowStrict(parseISO(summary.generated_at), {
                    addSuffix: true,
                  })
                    .replace(" minutes", " min")
                    .replace(" minute", " min")}`
                : null}
      </p>
    </div>
  );
}
