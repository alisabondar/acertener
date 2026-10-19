import type { ReactNode } from "react";

/** A section heading in the accent colour, so structure reads apart from content. */
export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-[15px] font-semibold text-brand">{children}</h2>;
}

/** Label/value pairs: small muted uppercase labels over darker, heavier values. */
export function Fields({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(({ label, value }) => (
        <div key={label}>
          <dt className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            {label}
          </dt>
          <dd className="mt-0.5 text-[15px] font-medium text-foreground">
            {value === null || value === undefined || value === false || value === "" ? "—" : value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** A titled card for one part of a page. */
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3 rounded-xl border bg-card p-4">
      <SectionTitle>{title}</SectionTitle>
      {children}
    </section>
  );
}
