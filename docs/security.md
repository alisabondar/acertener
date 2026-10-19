# Security

Someone with database access can't read patient identifiers or notes without the key. The running
app can, because it has to for search, display, and summaries; in production the key would live in
a managed key service controlled by the practice.

**Built in this demo, and how to check it:**

| Control | Verify |
|---|---|
| Field-level encryption (Fernet behind one `FieldCipher` interface, `v1:`-tagged values) | `./dev.sh proof`; CI's `test_no_plaintext_phi_at_rest` |
| Encrypted search (HMAC prefix and DOB fingerprints, separate key) | Search in the UI, then look at `patients.last_name_fp`: hashes only |
| Server-enforced identity and permissions | `curl -i localhost:8000/api/v1/auth/me` without `X-Persona` returns `401`; permission-matrix tests |
| Append-only audit trail of every view and change | A chart's Access history tab; the admin audit log |
| No PHI in URLs, logs, or error bodies | `./dev.sh test privacy` |
| AI leak check, fail closed | `./dev.sh test privacy`; payload preview: `GET /api/v1/dev/patients/{id}/ai-payload` (demo mode) |
| Security headers (`no-store` on PHI, CSP, `nosniff`, no referrer) | `curl -I localhost:8000/api/v1/patients` |

**Production only (designed for, not switched on in the demo):**

| Control | In production |
|---|---|
| HTTPS (TLS 1.2+) and HSTS | TLS at the load balancer; the HSTS header turns on when `ENV=production`. |
| Encrypted database connection | Managed Postgres with `sslmode=verify-full`. |
| Managed keys | A KMS-backed `FieldCipher` (AWS KMS, GCP KMS, or Vault), ideally with the practice holding the key. |
| Disk and backup encryption | Turned on in the managed database. |
| Login, sessions, CSRF, SSO, MFA | Short-lived server sessions or an identity provider, behind the single `current_user` seam. |
| Key rotation | MultiFernet already reads old keys; add a re-encryption job. |

## Production readiness

- **AI provider:** the summary uses Gemini's free tier for development with synthetic data only.
  Before any real patient data, switch to a HIPAA-eligible service covered by a signed Business
  Associate Agreement (Google Vertex AI, Azure OpenAI, AWS Bedrock, or an enterprise API with a
  BAA), configured for zero data retention and no training. Switch with `SUMMARY_PROVIDER`.
- **Demo mode:** the persona picker exists only when `DEMO_MODE=true`, and the app refuses to start
  with `DEMO_MODE=true` and `ENV=production`.
- **Scaling out:** the "Refresh now" rate limit lives in process memory; move it to Redis or the
  database before running more than one API instance.

For exactly what the AI summary sends and never sends, see [AI privacy](ai-privacy.md).
