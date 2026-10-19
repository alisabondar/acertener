# Roadmap

Deliberately out of the MVP, and designed for: each item names the seam it plugs into, so none of
them needs a rewrite.

## Up next

The items with the most value for clinicians, roughly in order.

- **Vitals trends and charts:** line charts of BP, heart rate, weight, and the rest over time on
  the Vitals tab, with the change against the last few visits called out ("systolic up 12% over
  three visits") and readings outside the usual range marked. Computed from stored vitals in the
  app, so it's exact and needs no AI.
- **Cmd+K patient search:** a command palette available on every page, suggesting patients as you
  type with the same rules as the Patients search (3+ letters of the last name, an MRN, or a DOB;
  terms never in the URL). The `command` component is already installed.
- **Autosave with conflict handling:** debounced saves, a saving indicator, and a prompt when
  someone else changed the record. Edits already carry `base_version`, and a stale save returns
  `409` with the current record.
- **New patient page and form:** a "New patient" nav entry for providers, nurses, and front desk,
  with inline validation and the duplicate-patient check (the API supports both).

## Clinical workflow

- **Visit workflow:** scheduled → checked in → roomed → with provider → completed (plus no-show and
  cancelled) as an audited, role-checked state machine with one-click actions on My day.
- **Medications and prescriptions:** a medication list per patient, included in the AI summary.
  - *Known issue this fixes:* the leak check's name detector can read a bare drug name as a
    person ("Started Losartan." is flagged), which would block that summary. Today only drugs in
    the chart's allergies and conditions are recognized as clinical terms; once medications are in
    the payload, their names become clinical terms too, through the same mechanism.
- **Note addenda:** corrections to finalized notes, shown alongside the original.
- **"No known allergies"** as an explicit, audited action.

## Privacy and access

- **Break-the-glass access:** opening a chart outside your care team asks for a reason, which is
  recorded in the audit trail and flagged for review, so access stays open in an emergency but a
  curiosity lookup is a deliberate, logged act.
- **Admin audit-log page:** browse and filter the full audit trail in the app (the
  `GET /admin/audit-log` endpoint already exists).
- **Login and SSO** behind `current_user`, replacing the persona picker: short-lived server
  sessions, idle and absolute timeouts, and MFA.
- **Encryption v2:** per-patient keys in a KMS, each value bound to its row, and crypto-shredding.

## AI summary

- **Real dates in summaries,** substituted locally after the leak check so they're never sent.
- **A BAA-covered provider** in the `SUMMARY_PROVIDER=baa` slot, before any real patient data.

## Search and interface

- **Phonetic name search** (`Smyth` finds `Smith`) as one more fingerprint.
- **Dark mode:** a Light / Dark / System choice in the avatar menu, after a WCAG AA contrast pass on
  the dark palette (already defined in `index.css`).

## Scale and operations

- **A 100,000-patient load test** with several API workers, before a real deployment.
- **A shared rate-limit store** (Redis or the database) for "Refresh now", once the API runs as more
  than one instance.

## Features changelog

- **Encryption and storage:** encrypted patient schema, fingerprint and prefix search, encryption proof.
- **Identity and audit:** demo personas, permission matrix, append-only audit trail.
- **Patients API:** list, search, filter counts, detail, create, edit, status, archive, access log.
- **Frontend:** persona picker, role-aware navigation, patients list with quick filters, My day.
- **Clinical chart:** notes, vitals, allergies, conditions, access history.
- **AI summary:** de-identified, leak-checked summaries with Gemini or a mock provider.
- **Hardening:** end-to-end tests, privacy test group, coverage gates, load test and deadlock fix.
- **Docker:** one-line setup with `./dev.sh`, the whole stack in Compose.
- **Validation:** names, MRNs, phone numbers, emails, states, ZIP codes, and addresses are checked
  on the server, with plain-language messages.
