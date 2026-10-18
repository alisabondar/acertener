# Performance

Measured on a developer laptop against the local Docker Postgres 16, with field-level encryption on.
Re-run after seeding with:

```bash
cd backend && uv run python -m scripts.explain_queries      # query plans and execution times
cd backend && uv run python -m scripts.time_endpoints       # API latency, needs the API running
```

## Baseline at 10,000 patients (2026-10-17)

**Seed:** 10,000 patients with care teams, visits, vitals, notes, allergies, and conditions in **58.2 s** (target: under 90 s).

### API latency (single client, 200 requests each, includes decrypting each page)

| Endpoint | p50 | p95 | Target (p95) |
|---|---|---|---|
| list: all | 8.9 ms | 27.4 ms | < 200 ms ✅ |
| list: my patients | 8.9 ms | 18.1 ms | < 200 ms ✅ |
| list: by age | 7.2 ms | 13.0 ms | < 200 ms ✅ |
| list: today's visits | 5.1 ms | 7.4 ms | < 200 ms ✅ |
| search: last-name prefix | 5.8 ms | 8.5 ms | < 200 ms ✅ |
| search: MRN | 3.8 ms | 5.3 ms | < 200 ms ✅ |
| filter counts: all | 12.8 ms | 21.3 ms | < 150 ms ✅ |
| filter counts: my | 9.0 ms | 14.3 ms | < 150 ms ✅ |
| detail | 3.3 ms | 8.1 ms | < 150 ms ✅ |

### Query plans (`EXPLAIN ANALYZE`, before the index fix)

| Query | Time | Plan note |
|---|---|---|
| list: all, last visit | 5.0 ms | seq scan + sort: the `last_visit_at` index is ascending, the list sorts `DESC NULLS LAST` |
| list: all, page 50 | 11.8 ms | same; cost grew with page depth |
| list: my patients | 5.4 ms | seq scan on `patients` with the care-team join |
| list total / filter counts: all | 2.8 / 12.6 ms | seq scan, expected: counting every patient visits every patient |
| list: by age, today's visits | 1.1 / 1.3 ms | index |
| search: prefix / prefix + first name / DOB / MRN | 1.5 / 3.0 / 0.05 / 0.05 ms | fingerprint indexes |
| detail / access log | 0.02 / 0.03 ms | primary key / tiny table |

### Fixes

- **`ix_patients_current_by_last_visit`**: `(last_visit_at DESC NULLS LAST, id) WHERE archived_at IS NULL`, matching the default list's sort and filter, so a page is an index walk that stops after `page_size` rows instead of sorting every patient.
- **`audit_log (patient_id, id)` and `(actor_id, id)`** replace the `occurred_at` indexes, matching the newest-first keyset paging (`ORDER BY id DESC`). Not visible at today's table size; it matters at ~1M audit rows (T-9.2).

### After the fixes

| Query | Before | After | Plan |
|---|---|---|---|
| list: all, last visit | 5.0 ms | 2.1 ms | index walk on `ix_patients_current_by_last_visit` |
| list: all, page 50 | 11.8 ms | 1.7 ms | same index; a deep page now costs about the same as page 1 |
| list: my patients | 5.4 ms | 0.8 ms | no sequential scan |
| list total: all | 2.8 ms | 1.3 ms | uses the partial index |
| filter counts: all / my | 12.6 / 7.0 ms | 19.2 / 7.3 ms | seq scan, expected (see below) |

### Known and accepted

- **Filter counts and list totals scan every current patient.** Roughly linear: ~10× at 100k ≈ 125–200 ms, still under the 400 ms 100k target. If it isn't at T-9.2, the next step is a maintained counts table.
- **Search terms are fingerprint lookups**, so their cost doesn't depend on table size the way a `LIKE` scan would.

## Next measurement

T-9.2 repeats this at **100,000 patients** and ~1M audit rows, with Locust across roles (including autosave traffic).
