/** A titled page whose content arrives in a later milestone. */
export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <section>
      <h1 className="text-[28px] font-semibold">{title}</h1>
      <p className="mt-1 text-[15px] text-muted-foreground">{note}</p>
    </section>
  );
}
