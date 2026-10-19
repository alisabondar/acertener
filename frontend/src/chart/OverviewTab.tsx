import { Sparkles } from "lucide-react";
import { Panel } from "@/components/Fields";
import { cn } from "@/lib/utils";

import { useChartAllergies, useChartConditions } from "./chartData";

/** The clinical picture first: the AI summary, then what's active. */
export function OverviewTab({ patientId }: { patientId: string }) {
  const allergies = useChartAllergies(patientId, true);
  const conditions = useChartConditions(patientId, true);
  const active = <T extends { status: string }>(items: T[] | undefined) =>
    (items ?? []).filter((i) => i.status === "active");

  return (
    <div className="space-y-4">
      <Panel title="AI summary">
        <p className="flex items-center gap-2 text-[14px] text-muted-foreground">
          <Sparkles className="size-4 text-brand" aria-hidden /> A de-identified AI summary arrives
          here soon.
        </p>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Active problems">
          <Items
            empty="None recorded"
            items={active(conditions.data?.items).map((c) => ({
              key: c.id,
              main: c.name,
              detail: c.icd10_code,
            }))}
          />
        </Panel>
        <Panel title="Active allergies">
          <Items
            empty="No allergies recorded"
            items={active(allergies.data?.items).map((a) => ({
              key: a.id,
              main: a.substance,
              detail: [a.reaction, a.severity].filter(Boolean).join(" · "),
              severe: a.severity === "severe",
            }))}
          />
        </Panel>
      </div>
    </div>
  );
}

function Items({
  items,
  empty,
}: {
  items: { key: string; main: string; detail: string; severe?: boolean }[];
  empty: string;
}) {
  if (items.length === 0) return <p className="text-[14px] text-muted-foreground">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.key} className="flex items-baseline justify-between gap-3">
          <span className={cn("text-[15px] font-medium", item.severe && "text-severe")}>
            {item.main}
          </span>
          {item.detail && (
            <span className="text-[13px] text-muted-foreground tabular-nums">{item.detail}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
