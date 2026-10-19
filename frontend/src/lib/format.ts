import { format, parseISO } from "date-fns";

/** A date of birth as US clinics write it. parseISO reads it as local, so it never shifts a day. */
export function formatDob(dob: string): string {
  return format(parseISO(dob), "MM/dd/yyyy");
}
