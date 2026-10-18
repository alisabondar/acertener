import type { Persona } from "./context";

const ROLE_LABELS: Record<string, string> = {
  provider: "Provider",
  nurse: "Nurse",
  front_desk: "Front desk",
  admin: "Admin",
};

/** "Provider, MD", "Nurse, RN", "Front desk". */
export function describeRole({ role, credential }: Pick<Persona, "role" | "credential">): string {
  return [ROLE_LABELS[role] ?? role, credential].filter(Boolean).join(", ");
}

export function initials(name: string): string {
  const words = name.replace(/^Dr\.\s+/, "").split(/\s+/);
  return words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}
