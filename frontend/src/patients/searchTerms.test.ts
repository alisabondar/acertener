import { describe, expect, it } from "vite-plus/test";

import { dobProblem, parseSearch } from "./searchTerms";

describe("parseSearch", () => {
  it.each([
    ["osei", "", { last_name: "osei" }],
    ["  Osei , Dan ", "", { last_name: "Osei", first_name: "Dan" }],
    ["MRN-100008", "", { mrn: "MRN-100008" }],
    ["mrn-100008", "", { mrn: "MRN-100008" }],
    ["100008", "", { mrn: "MRN-100008" }],
    ["mrn 100008", "", { mrn: "MRN-100008" }],
    ["", "1963-04-02", { dob: "1963-04-02" }],
    ["osei", "1963-04-02", { last_name: "osei", dob: "1963-04-02" }],
  ])("turns %j (DOB %j) into the API's search terms", (text, dob, terms) => {
    expect(parseSearch(text, dob)).toEqual({ terms, hint: null });
  });

  it.each([
    ["os", "Type at least 3 letters of the last name"],
    [", dan", "Start with the last name, then a comma and the first name"],
  ])("doesn't search for %j and says why", (text, hint) => {
    expect(parseSearch(text, "")).toEqual({ terms: null, hint });
  });

  it("is idle for an empty box", () => {
    expect(parseSearch("  ", "")).toEqual({ terms: null, hint: null });
  });
});

describe("dobProblem", () => {
  const today = new Date(2026, 9, 18);

  it.each([
    ["", false, null],
    ["1963-04-02", false, null],
    ["", true, "Enter the full date of birth (month, day, and year)"],
    ["2027-01-01", false, "Date of birth can't be in the future"],
    ["0019-04-02", false, "Enter a year from 1900 on"],
  ])("judges %j (incomplete: %s)", (dob, incomplete, problem) => {
    expect(dobProblem(dob, incomplete, today)).toBe(problem);
  });
});
