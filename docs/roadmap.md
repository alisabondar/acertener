# Roadmap

Deliberately out of the MVP, and designed for:

- **Create-patient form** with inline validation and the duplicate-patient check (the API already
  supports both).
- **Autosave with conflict handling:** debounced saves, a saving indicator, and a prompt when
  someone else changed the record.
- **Visit workflow:** scheduled → checked in → roomed → with provider → completed (plus no-show and
  cancelled) as an audited, role-checked state machine with one-click actions on My day.
- **Note addenda:** corrections to finalized notes, shown alongside the original.
- **"No known allergies"** as an explicit, audited action.
- **Real dates in AI summaries,** substituted locally after the leak check so they're never sent.
- **Encryption v2:** per-patient keys in a KMS, each value bound to its row, and crypto-shredding.
- **Login and SSO** behind `current_user`, replacing the persona picker.
- **Phonetic name search** (`Smyth` finds `Smith`) as one more fingerprint.
- **A 100,000-patient load test** with several API workers, before a real deployment.

## Features changelog

- **Encryption and storage:** encrypted patient schema, fingerprint and prefix search, encryption proof.
- **Identity and audit:** demo personas, permission matrix, append-only audit trail.
- **Patients API:** list, search, filter counts, detail, create, edit, status, archive, access log.
- **Frontend:** persona picker, role-aware navigation, patients list with quick filters, My day.
- **Clinical chart:** notes, vitals, allergies, conditions, access history.
- **AI summary:** de-identified, leak-checked summaries with Gemini or a mock provider.
- **Hardening:** end-to-end tests, privacy test group, coverage gates, load test and deadlock fix.
- **Docker:** one-line setup with `./dev.sh`, the whole stack in Compose.
