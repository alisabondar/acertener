import type { components } from "@/api/schema";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type Scope = components["schemas"]["Scope"];

/** A single-choice switch between my care team and everyone (radio semantics, not tabs). */
export function ScopeToggle({
  value,
  onChange,
  label,
  myLabel,
  allLabel,
}: {
  value: Scope;
  onChange: (scope: Scope) => void;
  /** What's being scoped, for screen readers, e.g. "Whose patients". */
  label: string;
  myLabel: string;
  allLabel: string;
}) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      aria-label={label}
      value={value}
      // Radix reports "" when the pressed item is clicked again; a scope is always chosen.
      onValueChange={(next) => {
        if (next === "my" || next === "all") onChange(next);
      }}
    >
      <ToggleGroupItem value="my" className="px-3">
        {myLabel}
      </ToggleGroupItem>
      <ToggleGroupItem value="all" className="px-3">
        {allLabel}
      </ToggleGroupItem>
    </ToggleGroup>
  );
}
