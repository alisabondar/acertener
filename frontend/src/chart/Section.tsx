import { Lock, Pencil } from "lucide-react";
import type { ReactNode } from "react";

import { SectionTitle } from "@/components/Fields";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * A chart section in view mode by default. Roles that may edit get an Edit toggle; others see
 * a lock explaining who can.
 */
export function Section({
  title,
  canEdit,
  lockedReason,
  editing,
  onEditingChange,
  children,
}: {
  title: string;
  canEdit: boolean;
  /** Shown on the lock when the role can't edit, e.g. "Requires a provider role". */
  lockedReason: string;
  editing: boolean;
  onEditingChange: (editing: boolean) => void;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <SectionTitle>{title}</SectionTitle>
        {canEdit ? (
          <Button
            variant={editing ? "default" : "outline"}
            size="sm"
            aria-pressed={editing}
            aria-label={`Edit ${title.toLowerCase()}`}
            onClick={() => onEditingChange(!editing)}
          >
            <Pencil /> {editing ? "Done" : "Edit"}
          </Button>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                role="img"
                aria-label={lockedReason}
                tabIndex={0}
                className="rounded-sm p-1 text-muted-foreground"
              >
                <Lock className="size-4" aria-hidden />
              </span>
            </TooltipTrigger>
            <TooltipContent>{lockedReason}</TooltipContent>
          </Tooltip>
        )}
      </div>
      {children}
    </section>
  );
}
