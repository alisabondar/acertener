import { CircleAlert, Search, X } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import type { PatientSearch } from "./usePatientSearch";

/** The search box and DOB field, each with its own × and an inline note when there's a problem. */
export function PatientSearchFields({ search }: { search: PatientSearch }) {
  const {
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
  } = search.fields;
  const ids = useId();

  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="min-w-72 flex-1">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            ref={textInput}
            type="search"
            aria-label="Search patients"
            aria-describedby={hint ? `${ids}-search` : undefined}
            aria-invalid={hint !== null}
            placeholder="Last name, “last, first”, or MRN"
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoComplete="off"
            // One clear control: ours, not the browser's built-in search ×.
            className="bg-card pr-9 pl-9 [&::-webkit-search-cancel-button]:appearance-none"
          />
          {text && (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label="Clear search text"
              onClick={() => {
                setText("");
                textInput.current?.focus();
              }}
              className="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground"
            >
              <X />
            </Button>
          )}
        </div>
        {hint && <FieldNote id={`${ids}-search`} problem={hint} />}
      </div>
      <div>
        <div className="flex items-center gap-1">
          <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
            Date of birth
            <Input
              ref={dobInput}
              type="date"
              aria-describedby={dobNote ? `${ids}-dob` : undefined}
              aria-invalid={dobNote !== null}
              value={dob}
              onChange={(event) => setDob(event.target.value)}
              // A half-typed date reads as "" with badInput set; say so rather than ignore it.
              onInput={(event) => setDobIncomplete(event.currentTarget.validity.badInput)}
              className="w-40 bg-card"
            />
          </label>
          {(dob || dobNote) && (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Clear date of birth"
              onClick={() => {
                clearDob();
                dobInput.current?.focus();
              }}
            >
              <X />
            </Button>
          )}
        </div>
        {dobNote && <FieldNote id={`${ids}-dob`} problem={dobNote} />}
      </div>
    </div>
  );
}

/** A problem with a field's value, shown under it and announced as its description. */
function FieldNote({ id, problem }: { id: string; problem: string }) {
  return (
    <p id={id} className="mt-1.5 flex items-center gap-1.5 text-[12px] text-status-inactive">
      <CircleAlert className="size-3.5 shrink-0" aria-hidden />
      {problem}
    </p>
  );
}
