import { format, parseISO } from "date-fns";

import { api } from "@/api";
import { queryKeys, useApiQuery } from "@/api/queries";
import { describeRole } from "@/auth/roles";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Who opened or changed this chart, newest first. Field names only, never values. */
export function AccessHistoryTab({ patientId }: { patientId: string }) {
  const log = useApiQuery(queryKeys.patients.chart(patientId, "access"), (signal) =>
    api.GET("/api/v1/patients/{patient_id}/access-log", {
      params: { path: { patient_id: patientId } },
      signal,
    }),
  );
  if (!log.data) return <Skeleton className="h-32 w-full rounded-xl" />;
  return (
    <div className="rounded-xl border bg-card">
      <Table aria-label="Access history">
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">When</TableHead>
            <TableHead>Who</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Fields changed</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {log.data.items.map((entry, i) => (
            <TableRow key={`${entry.occurred_at}-${i}`}>
              <TableCell className="pl-4">
                {format(parseISO(entry.occurred_at), "MMM d, yyyy h:mm a")}
              </TableCell>
              <TableCell>
                {entry.actor_name}
                <span className="text-muted-foreground">
                  {" "}
                  · {describeRole({ role: entry.actor_role, credential: null })}
                  {entry.via_demo_persona && " (demo)"}
                </span>
              </TableCell>
              <TableCell className="capitalize">{entry.action.replace("_", " ")}</TableCell>
              <TableCell className="text-muted-foreground">
                {entry.changed_fields.join(", ") || "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
