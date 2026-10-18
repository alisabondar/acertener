import { Link } from "react-router";

export function NotFound() {
  return (
    <section className="py-16 text-center">
      <h1 className="text-[28px] font-semibold">Page not found</h1>
      <p className="mt-2 text-[15px] text-muted-foreground">
        That address doesn't match a page in the dashboard.
      </p>
      <Link
        to="/"
        className="mt-6 inline-block font-medium text-primary underline underline-offset-4"
      >
        Go to My day
      </Link>
    </section>
  );
}
