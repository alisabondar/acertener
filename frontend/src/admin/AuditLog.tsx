import { useInfiniteQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { useState } from "react";
import { Link } from "react-router";

import { api } from "@/api";
import { queryKeys, useApiQuery } from "@/api/queries";
import type { components } from "@/api/schema";
import { describeRole } from "@/auth/roles";
import { NativeSelect } from "@/components/NativeSelect";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { WriteError } from "@/chart/WriteError";

type Entry = components["schemas"]["AuditItemOut"];

const VERBS: Record<string, string> = {
  view: "Viewed",
  create: "Created",
  update: "Updated",
  status_change: "Changed status of",
  archive: "Archived",
  restore: "Restored",
  delete: "Deleted",
  access_denied: "Was refused",
  llm_payload_blocked: "AI summary blocked for",
};

/** Who did what, and when, across the practice. Field names only: values never leave the server. */
export function AuditLog() {
  const [actor, setActor] = useState("");
  const personas = useApiQuery(queryKeys.personas(), (signal) =>
    api.GET("/api/v1/personas", { signal }),
  );
  const log = useInfiniteQuery({
    queryKey: ["admin", "audit-log", actor],
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam, signal }) => {
      const { data } = await api.GET("/api/v1/admin/audit-log", {
        params: {
          query: { ...(actor && { actor_id: actor }), ...(pageParam && { before_id: pageParam }) },
        },
        signal,
      });
      return data ?? { items: [], next_before_id: null };
    },
    getNextPageParam: (last) => last.next_before_id,
  });
  const entries = log.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Audit log</h1>
          <p className="text-[14px] text-muted-foreground">
            Every view and change, newest first. Changed fields are listed by name only.
          </p>
        </div>
        <label className="space-y-1 text-[13px] text-muted-foreground">
          <span className="block">Person</span>
          <NativeSelect value={actor} onChange={(event) => setActor(event.target.value)}>
            <option value="">Everyone</option>
            {personas.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </NativeSelect>
        </label>
      </div>

      {log.error ? (
        <WriteError error={log.error} action="view the audit log" />
      ) : !log.data ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : entries.length === 0 ? (
        <p className="text-[14px] text-muted-foreground">No entries yet</p>
      ) : (
        <div className="rounded-xl border bg-card">
          <Table aria-label="Audit log">
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">When</TableHead>
                <TableHead>Who</TableHead>
                <TableHead>What</TableHead>
                <TableHead>Changed fields</TableHead>
                <TableHead>Patient</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((e) => (
                <EntryRow key={e.id} entry={e} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {log.hasNextPage && (
        <Button
          variant="outline"
          disabled={log.isFetchingNextPage}
          onClick={() => void log.fetchNextPage()}
        >
          Load older
        </Button>
      )}
    </div>
  );
}

function EntryRow({ entry }: { entry: Entry }) {
  return (
    <TableRow>
      <TableCell className="pl-4 whitespace-nowrap tabular-nums">
        {format(parseISO(entry.occurred_at), "MMM d, yyyy h:mm a")}
      </TableCell>
      <TableCell>
        <span className="font-medium">{entry.actor_name}</span>{" "}
        <span className="text-muted-foreground">
          {describeRole({ role: entry.actor_role, credential: null })}
        </span>
        {entry.via_demo_persona && (
          <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium">
            Demo
          </span>
        )}
      </TableCell>
      <TableCell>
        {VERBS[entry.action] ?? entry.action} {entry.entity.replaceAll("_", " ")}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {entry.changed_fields.length > 0 ? entry.changed_fields.join(", ") : "—"}
      </TableCell>
      <TableCell>
        {entry.patient_id ? (
          <Link className="text-brand underline" to={`/patients/${entry.patient_id}`}>
            Open chart
          </Link>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
    </TableRow>
  );
}
