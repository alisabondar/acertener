import { Link } from "react-router";

/** A page the current role can't use. Says so plainly rather than redirecting. */
export function Forbidden() {
  return (
    <section className="py-16 text-center">
      <h1 className="text-[28px] font-semibold">You don't have access to this page</h1>
      <Link
        to="/"
        className="mt-4 inline-block font-medium text-primary underline underline-offset-4"
      >
        Go to your home page
      </Link>
    </section>
  );
}
