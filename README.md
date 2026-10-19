# Patient Dashboard

A clinician-facing patient dashboard, built HIPAA-ready: encrypted at rest, audited on every view,
and an AI summary that can't leak who the patient is. All data is synthetic.

```bash
git clone https://github.com/alisabondar/acertener.git && cd acertener && ./dev.sh
```

Docker is the only prerequisite. Then open http://localhost:5173: there's no login, and the
"Viewing as" menu switches roles. See [Getting started](docs/getting-started.md) for the tour.

## Features

- **Encrypted at rest, still searchable:** the database never holds a readable name, yet `smi` finds Smith.
- **AI summaries that can't leak identity:** de-identified, leak-checked both ways, and blocked rather than sent on any doubt.
- **Every view audited:** an append-only trail records who viewed or changed each chart, and when.
- **Server-enforced roles:** providers, nurses, front desk, and admins each see and do only what their role allows.
- **Clinically realistic charting:** finalized notes lock, vitals are range-checked, and nothing clinical is ever deleted.
- **No PHI in URLs or logs:** canary tests guard the database, logs, error responses, and every byte sent to the AI.
- **Fast under load:** 50 concurrent staff on 30,000 patients with zero failures and p95 under 100 ms.
- **Tested end to end:** 100% branch coverage on encryption, permissions, and AI, plus Playwright in CI.

**Docs:** [getting started](docs/getting-started.md) · [development](docs/development.md) ·
[security](docs/security.md) · [AI privacy](docs/ai-privacy.md) ·
[performance](docs/performance.md) · [roadmap](docs/roadmap.md) · [decisions](docs/decisions.md)
