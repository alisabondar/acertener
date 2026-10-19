import { format, parseISO } from "date-fns";

import type { components } from "@/api/schema";

export type SearchTerms = components["schemas"]["SearchTerms"];

// "MRN-100008", "mrn 100008", or just "100008": a number can't be a last name.
const MRN = /^(?:mrn[-\s]?)?(\d+)$/i;
const MIN_LAST_NAME = 3;

/**
 * Reads the search box ("osei", "osei, dan", or an MRN) plus an optional DOB as the API's
 * search terms. A search needs an anchor (last name, DOB, or MRN); otherwise `hint` says why
 * nothing is being searched yet.
 */
export function parseSearch(
  text: string,
  dob: string,
): { terms: SearchTerms | null; hint: string | null } {
  const query = text.trim();
  const terms: SearchTerms = {};
  if (dob) terms.dob = dob;

  const mrnDigits = MRN.exec(query)?.[1];
  if (mrnDigits) {
    terms.mrn = `MRN-${mrnDigits}`;
  } else if (query) {
    const [last = "", first = ""] = query.split(",").map((part) => part.trim());
    if (!last)
      return { terms: null, hint: "Start with the last name, then a comma and the first name" };
    if (last.length < MIN_LAST_NAME && !dob) {
      return { terms: null, hint: "Type at least 3 letters of the last name" };
    }
    if (last.length >= MIN_LAST_NAME) terms.last_name = last;
    if (first) terms.first_name = first;
  }

  // The API refuses a search without an anchor; never send one.
  const anchored = Boolean(terms.last_name || terms.dob || terms.mrn);
  return { terms: anchored ? terms : null, hint: null };
}

/** Why a DOB can't be searched yet, if it can't: incomplete, in the future, or before 1900. */
export function dobProblem(dob: string, incomplete: boolean, today = new Date()): string | null {
  if (incomplete) return "Enter the full date of birth (month, day, and year)";
  if (!dob) return null;
  if (dob > format(today, "yyyy-MM-dd")) return "Date of birth can't be in the future";
  if (parseISO(dob).getFullYear() < 1900) return "Enter a year from 1900 on";
  return null;
}
