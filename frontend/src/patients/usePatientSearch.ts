import { useMemo, useRef, useState } from "react";

import { useDebouncedValue } from "@/hooks/useDebouncedValue";

import { dobProblem, parseSearch } from "./searchTerms";

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Patient search state: the box, the DOB field, their problems, and the debounced terms to send.
 * Terms identify patients, so they live only here in component state, never in the URL.
 * `onEdit` runs on every change, e.g. so a list can go back to its first page.
 */
export function usePatientSearch({ onEdit }: { onEdit?: () => void } = {}) {
  const [text, setTextState] = useState("");
  const [dob, setDobState] = useState("");
  const [dobIncomplete, setDobIncomplete] = useState(false);
  const textInput = useRef<HTMLInputElement>(null);
  const dobInput = useRef<HTMLInputElement>(null);

  const dobNote = dobProblem(dob, dobIncomplete);
  // A DOB with a problem isn't searched; its field explains why.
  const searchableDob = dobNote ? "" : dob;
  const { hint } = parseSearch(text, searchableDob);
  // Typing is debounced; emptying a field applies at once, so a cleared search clears now.
  const debouncedText = useDebouncedValue(text, text ? SEARCH_DEBOUNCE_MS : 0);
  const debouncedDob = useDebouncedValue(searchableDob, searchableDob ? SEARCH_DEBOUNCE_MS : 0);
  const { terms } = useMemo(
    () => parseSearch(debouncedText, debouncedDob),
    [debouncedText, debouncedDob],
  );

  const setText = (value: string) => {
    setTextState(value);
    onEdit?.();
  };
  const setDob = (value: string) => {
    setDobState(value);
    onEdit?.();
  };
  const clearDob = () => {
    setDob("");
    setDobIncomplete(false);
    // A half-typed date is already "" to React, so clear what the browser is showing directly.
    if (dobInput.current) dobInput.current.value = "";
  };
  const clear = () => {
    setText("");
    clearDob();
  };

  return {
    terms,
    clear,
    fields: {
      text,
      setText,
      dob,
      setDob,
      setDobIncomplete,
      clearDob,
      hint,
      dobNote,
      textInput,
      dobInput,
    },
  };
}

export type PatientSearch = ReturnType<typeof usePatientSearch>;
