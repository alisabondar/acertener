# Security

Someone with database access can't read patient identifiers or notes without the key. The running
app can, because it has to for search, display, and summaries; in production the key would live in
a managed key service controlled by the practice.

**Built in this demo, and how to check it:**

| Control | In plain English | How a reviewer verifies it |
|---|---|---|
| **Field-level encryption** | The app scrambles patient details before saving them. The database only ever holds unreadable data. | `./dev.sh proof` shows the app's view next to the raw database row, then searches the whole database for the patient's name and finds 0 matches. |
| **Encrypted search** (fingerprints) | Search uses one-way fingerprints of name prefixes and DOB, so you can find a patient without storing their name readably. | Search in the UI, then look at `patients.last_name_fp`: it holds only hashes. |
| **Demo identity, server-enforced** | No login in the demo: a persona picker chooses who you are, but every permission is still checked on the server. It only works in demo mode. | Persona tests, and `curl /api/v1/auth/me` without `X-Persona` (or with `DEMO_MODE=false`) returns `401`. |
| **No PHI in URLs or logs** | Names and DOBs never appear in web addresses, browser history, or log files. | Canary log test. Check browser history after a search. |
| **Role permissions + audit trail** | Each role can do only its allowed actions, and every view and edit is recorded. | Permission-matrix tests, the role switcher, and the Access history tab. |
| **AI leak check** | Nothing identifying is ever sent to the AI. A suspected leak blocks the request. | The payload preview, `GET /api/v1/dev/patients/{id}/ai-payload` (demo mode, never calls the AI), and `./dev.sh test privacy`. |
| **Security headers** | Tell the browser not to cache patient data, among other things. | `curl -I http://localhost:8000/api/v1/patients`. |

**Production only (designed for, not switched on in the demo):**

| Control | Why it isn't active in the demo | What production uses |
|---|---|---|
| **HTTPS (TLS 1.2+) and HSTS** | The demo runs entirely on your machine, so traffic never leaves it. | TLS at the load balancer. The HSTS header code exists but turns on only when `ENV=production`. |
| **Encrypted database connection** | The API and database share a private Docker network. | Managed Postgres with `sslmode=verify-full`, which encrypts the connection *and* checks it's talking to the real database server. |
| **Managed key service** (KMS) | Needs a cloud account. | A KMS-backed `FieldCipher` (AWS KMS, GCP KMS, or Vault), ideally with the practice holding its own key. |
| **Disk and backup encryption** | This is an infrastructure setting. | Turned on in the managed database. |
| **BAA-covered AI provider** | The demo uses only synthetic data. | See [Production readiness](#production-readiness). |
| **Login, sessions, and CSRF** | The MVP uses a demo persona picker instead of login. | Password login (argon2) and short-lived server sessions (opaque tokens in an httpOnly cookie, double-submit CSRF), behind `current_user`. |
| **Badge/SSO login and MFA** | Needs an identity provider. | A new identity provider behind `current_user`. |
| **Encryption v2** | v1 is enough for the demo, and v2 needs a KMS to be worthwhile. | Per-patient keys (envelope encryption), each encrypted value tied to its row, and crypto-shredding. It's a new `FieldCipher` implementation using the `v2:` tag, rolled out by re-encrypting records. |
| **Key rotation** | This is an operational process. | MultiFernet already supports it. Add a re-encryption script when it's needed. |

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
