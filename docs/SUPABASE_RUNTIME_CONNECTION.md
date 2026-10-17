# ClaimPilot — Supabase Runtime Connection

**Updated:** 17 October 2026  
**Scope:** Runtime connection and deployment verification; not a schema migration.

## Current project

- Supabase project: `tiwdktgeqifhumcrwniv`
- Region: `ap-south-1` (Mumbai)
- Project URL: `https://tiwdktgeqifhumcrwniv.supabase.co`
- The live project is active. The eight ClaimPilot application tables exist, RLS is enabled, and four versioned migrations are recorded.
- `anon` and `authenticated` have no direct table privileges on the ClaimPilot tables. Application data access is through FastAPI and its backend-only service-role key. Do not add client table grants just to remove the RLS-without-policies advisor notice.
- The `claim-evidence` Storage bucket is private. The live app tables currently have no demo records; no test users/claims/evidence were seeded.

## Application connection model

`insurance-pro/frontend/ClaimPilot/` calls the FastAPI API under `insurance-pro/backend/`. The frontend must not connect directly to application tables using a service-role key.

The backend uses the Supabase URL and server-side keys from its environment. Claim records, OTP challenges, evidence catalog entries, AI/fraud results, agent decisions and customer settlement decisions are written through the backend Supabase Data API / Storage API code paths.

## Required backend environment

Configure these in `insurance-pro/backend/.env` for local runs, or in the backend host's secret/environment settings for deployment:

- `SUPABASE_URL=https://tiwdktgeqifhumcrwniv.supabase.co`
- `SUPABASE_ANON_KEY` — the project's anon/publishable key required by the current backend settings.
- `SUPABASE_SERVICE_ROLE_KEY` — required for backend database, Auth admin and private Storage operations; **backend only, never a Vite variable**.
- `JWT_SECRET` — independent random secret for ClaimPilot's own API JWTs; do not reuse Supabase keys.
- `ENVIRONMENT=production` on the deployed backend.
- `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` — active email provider settings for OTP verification. The current email dispatcher uses SendGrid; legacy `SMTP_*` settings are not used by `app/services/email.py`.
- `FRONTEND_URL` — deployed frontend origin, used to build customer action links.
- `ALLOWED_ORIGINS` — exact deployed frontend origin(s), comma-separated; no wildcard.

Actual keys are not in Git. Enter them directly into the hosting provider or local ignored `.env`; never paste them into chat or commit them.

For local-only testing without email delivery, configure `ENVIRONMENT=development` and a six-digit `OTP_DEV_FIXED_CODE`. Do not set this variable in staging or production. Missing email-provider configuration now fails closed rather than pretending an OTP was delivered.

## Required frontend environment

Configure `insurance-pro/frontend/ClaimPilot/.env` or the frontend host build environment:

- `VITE_API_BASE_URL` — the backend HTTPS URL ending in `/api/v1`. For local development the default is `http://localhost:8000/api/v1`.

Vite variables are public and baked into the build. Never put Supabase service-role keys, JWT signing secrets, SendGrid keys or other server-side credentials into frontend variables.

## Readiness verification

- `GET /health` confirms the FastAPI process is alive only.
- `GET /health/ready` performs a read-only query against `public.profiles` using the configured backend Supabase connection and checks email OTP configuration (or an explicitly configured local fixed code). It returns HTTP 503 if the Data API or required OTP setup is unavailable. It does not prove that SendGrid credentials are valid or that a full claim succeeds.

The local launcher checks this readiness endpoint instead of treating liveness or API docs as proof of Supabase connectivity.

## Final live integration gate

After setting environment variables, verify with real team-controlled accounts:

1. Register a real demo agent and customer through the application.
2. Confirm OTP arrives at the intended inbox; verify login returns the backend-issued user ID and role.
3. Associate the actual policy number with that registered agent using the reviewed safe seed workflow. Do not run `seed_demo.sql` while its agent email placeholder remains.
4. Submit a claim, upload evidence to the private bucket, and verify evidence cataloging succeeds.
5. Confirm AI/fraud result rows persist, or an explicit failure/manual-review state is persisted if real model inference is unavailable.
6. Review the claim as its assigned agent, save the decision, then confirm the customer sees the persisted status after refresh.

GitHub Actions uses dummy credentials and mocked dependencies; a passing CI run is not a substitute for the live steps above. Do not rerun legacy `schema.sql`, `migration_v2.sql` or `migration_v3_phash.sql` against the connected project; current versioned migrations are already applied.
