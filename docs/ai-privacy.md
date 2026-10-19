# AI summary privacy

The chart's AI summary is written from a **de-identified, leak-checked** payload. This page says
exactly what is sent, what never is, how that's enforced, and which tests prove it.

## The path to the AI

```
chart rows ──► de-identifier ──► DeidentifiedClinicalContext ──► leak check ──► gateway ──► provider
 (database)    app/ai/deidentify.py   app/ai/payload.py          app/ai/leak_check.py  app/ai/gateway.py
                                                                       ▲                      │
                                                                       └── leak check on the reply
```

- **One door out.** `app/ai/gateway.py` is the only module allowed to import an HTTP client; an
  `import-linter` contract fails CI if anything else does (`uv run lint-imports`).
- **One shape out.** The gateway accepts only a `DeidentifiedClinicalContext`. That model checks a
  private seal when it's built, so only the de-identifier can create one; a `Patient`, a dict, or
  any other object is refused.
- **One host out.** Requests go only to `generativelanguage.googleapis.com`; the API key travels in
  a header, never in a URL (URLs end up in logs).

## What is sent

| Field | Form |
|---|---|
| Age | Years, with 90 and over sent as `"90+"` (Safe Harbor aggregates ages above 89) |
| Sex | `female` / `male` only; any other value isn't sent |
| Visits | Day offset from today (e.g. `-412`), reason (scrubbed), status |
| Notes | **Finalized notes only**, scrubbed, with day offsets. Drafts never leave |
| Vitals | Day offset and the readings |
| Diagnoses | ICD-10 code, name, and status (active or resolved); entered-in-error ones are dropped |

## What is never sent

Name, MRN, patient or record IDs, date of birth, exact dates, contact details, address, staff
names, or anything else on the HIPAA Safe Harbor list.

## Scrubbing free text

Notes and visit reasons pass through `app/ai/scrub.py`:

- the patient's names in every form (titles, possessives, any case, with or without apostrophes)
  → `[PATIENT]`
- known staff → `[CLINICIAN]`; anyone else a name detector finds → `[PERSON]`
- dates in common formats → `[DATE -17d]` (an offset from today); impossible dates → `[DATE]`
- phone numbers (including spelled out), emails, street addresses, the patient's city and ZIP, SSNs,
  MRNs, URLs, and IP addresses → `[REDACTED]`

## The leak check (fail closed)

`app/ai/leak_check.py` runs on the final serialized payload **and** on the model's reply. It shares
no code with the scrubber, so one module's bug can't hide in the other.

- **This patient's identifiers**, exact and normalized: name tokens, MRN (with or without prefix),
  patient ID, date of birth in about ten formats, phone digits (any separators), email, address
  parts, ZIP, and staff names.
- **Generic patterns:** any UUID, SSN, URL, IP address, email, phone, MRN number, or absolute date.
- **Name and place detection** with Presidio (spaCy's small English model).

On any hit nothing is sent (or the reply isn't shown): the summary's status becomes `blocked`, the
narrative is empty, and an `llm_payload_blocked` audit entry records **which detectors fired and
at which stage, never the values**.

## Prompt injection

Notes are data, not instructions: the system prompt is fixed, the chart is delimited inside
`<chart>…</chart>`, the reply must be JSON matching a strict schema (`{"narrative": "…"}`, at most
1,500 characters), and the UI renders it as plain text, never HTML.

## Regeneration

Clinical changes mark the summary stale (editing a *draft* doesn't, since drafts are never sent).
A view of a stale summary regenerates it once the last change is at least
`SUMMARY_DEBOUNCE_SECONDS` (15 s) old, in the background, with an atomic claim so concurrent
viewers start one generation. Only charts someone opens are summarized. An unchanged payload
(same hash) reuses the cached narrative without calling the AI. "Refresh now" skips the wait,
once per 10 seconds per patient.

## Providers

`SUMMARY_PROVIDER=auto` (the default) uses Gemini when `GEMINI_API_KEY` is set and otherwise a
deterministic `MockProvider`, so every path above works without a key. The UI shows which provider
wrote the narrative.

To see exactly what would be sent for a patient, without sending it (demo mode only):

```bash
curl -H "X-Persona: <persona id>" http://localhost:8000/api/v1/dev/patients/<patient id>/ai-payload
```

## The tests

| Test | Proves |
|---|---|
| `tests/ai/test_scrub.py` | The tricky corpus ("Mr. O'Neil", "3/4/56", "Rose" as a name and as a colour, spelled-out phone numbers, addresses in sentences) |
| `tests/ai/test_leak_check.py` | Each detector fires, a clean payload passes, and results never contain values |
| `tests/ai/test_properties.py` | Hypothesis: 1,000 generated patients with identifiers injected in random forms; none reaches an allowed payload |
| `tests/ai/test_payload.py` | The payload's contents, the 90+ cap, the seal, and a **golden snapshot** (`golden_payload.json`) so any change to what's sent shows in review |
| `tests/ai/test_gateway.py` | The canary (no identifier in any outbound byte, recorded at the transport), the host allowlist, blocking before sending and after replying, prompt injection, every failure mode, and the rate limiter |
| `tests/ai/test_architecture.py` | Only the gateway can reach a provider |
| `tests/ai/test_summary_api.py` | Debounce, one generation per change, caching, manual refresh limits, blocked auditing, failures that keep the header, role access, and the payload preview |
