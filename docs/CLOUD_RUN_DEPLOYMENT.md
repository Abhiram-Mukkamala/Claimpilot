# ClaimPilot Backend Hosting Runbook — Google Cloud Run

**Last reviewed:** 20 October 2026  
**Scope:** Prepare and verify the FastAPI/Ultralytics backend for Cloud Run. This document does not itself deploy a service, change Supabase data/schema/RLS, create demo records, or expose secrets.

## 1. Current intended hosting layout

- **GCP project:** `claimpilot-512009`
- **Cloud Run / Artifact Registry region:** `asia-south1` (Mumbai)
- **Cloud Run service:** `claimpilot-api`
- **Supabase project:** `zegygoxpmnxpdhutdpqf`
- **Supabase URL:** `https://zegygoxpmnxpdhutdpqf.supabase.co`
- **Supabase region:** reported as Sydney (`ap-southeast-2`); it is **not** colocated with Cloud Run in Mumbai. Verify latency during the E2E test.
- **Evidence bucket:** `claim-evidence`, intended to remain private.

The API runs in Cloud Run; Supabase remains the auth/database/storage provider. No live Cloud Run deployment was confirmed in the previous handoff. Treat all resources and credentials as needing a current check rather than relying on old screenshots or these notes.

### Proposed initial sizing (not a benchmark result)

- 1 vCPU, 4 GiB RAM
- Request-based billing
- Minimum instances 0, maximum instances 2
- Concurrency 1
- Request timeout 300 seconds
- Container port 8080

These are starting values for the hackathon demo. Check latency, cold start, memory, inference behavior, and cost with real test images before the finale. Scaling limits and timeout do not establish production capacity.

## 2. Safe preflight — inspect, don't mutate

Run these from PowerShell. Confirm your active account and the target project before running any command that changes resources.

```powershell
gcloud auth list
gcloud config get-value project
gcloud projects describe claimpilot-512009 --format="value(projectId)"
gcloud services list --enabled --project=claimpilot-512009 --filter="name:(run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com)"
gcloud artifacts repositories describe claimpilot --location=asia-south1 --project=claimpilot-512009
gcloud iam service-accounts describe claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com --project=claimpilot-512009
gcloud run services list --project=claimpilot-512009 --region=asia-south1
```

If an inspect command says the resource is missing, stop and confirm the project ID before creating it. Historical notes say the APIs, Artifact Registry repository `claimpilot`, and runtime service account were previously created, but recheck them. Do not repeatedly create resources just because a list command returned an unexpected result.

Before any billing-impacting activity, confirm billing is enabled and that any displayed credits are actually applicable to this project's billing account. A prior screenshot showed monthly Google credits, but their applicability/remaining value was not conclusively confirmed.

## 3. Secret Manager audit (metadata only)

### Required secrets for the email-OTP demo

The customer/agent demo can use email OTP, so these four secrets are required for the first deployment:

| Cloud Run variable | Secret Manager name | Notes |
|---|---|---|
| `SUPABASE_ANON_KEY` | `claimpilot-supabase-anon-key` | For backend Supabase client configuration |
| `SUPABASE_SERVICE_ROLE_KEY` | `claimpilot-supabase-service-role-key` | Backend-only privileged key; never expose to browser |
| `JWT_SECRET` | `claimpilot-jwt-secret` | Independent random signing secret, at least 32 characters |
| `SENDGRID_API_KEY` | `claimpilot-sendgrid-api-key` | Email OTP provider |

### Optional secrets if SMS login is enabled

Do **not** block the email-only demo on Twilio configuration. Phone/SMS login requires all three of these secrets:

| Cloud Run variable | Secret Manager name | Notes |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | `claimpilot-twilio-account-sid` | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | `claimpilot-twilio-auth-token` | Twilio API credential |
| `TWILIO_VERIFY_SERVICE_SID` | `claimpilot-twilio-verify-service-sid` | Twilio Verify Service SID, usually starts with `VA` |

### Latest read-only GCP audit (20 October 2026)

The user-provided audit reports:
- Project `claimpilot-512009`, region `asia-south1`, Artifact Registry repo `claimpilot`, and runtime service account exist.
- **No Cloud Run service exists yet.**
- The four core secrets exist with enabled versions: anon key v1, service-role key v1, JWT v1 and v2, SendGrid v1.
- Twilio account SID v2 and auth token v1 are enabled; Twilio account SID v1 is destroyed.
- `claimpilot-twilio-verify-service-sid` does not exist.
- The runtime service account has `roles/secretmanager.secretAccessor` on each of the six existing secrets.
- No secret payloads were read during this audit.

This is a dated snapshot, not a permanent guarantee; re-run metadata checks before deployment.

First list secret names; then check version/IAM metadata without displaying payloads:

```powershell
gcloud secrets list --project=claimpilot-512009 --format="table(name,createTime)"
```

For each of the four required names above, run:

```powershell
gcloud secrets versions list SECRET_NAME --project=claimpilot-512009 --format="table(name,state,createTime,expireTime)"
gcloud secrets get-iam-policy SECRET_NAME --project=claimpilot-512009
```

If enabling SMS, run the same commands for the three optional Twilio names after they have been provisioned. Never use `gcloud secrets versions access`, never print secret payloads, and never paste secret values into chat, source control, logs, or screenshots.

If a secret or enabled version is missing, pause and create/populate it through the approved GCP Console or a locally controlled secure process. Do not insert placeholder values. Generate a fresh JWT secret if needed, independently of the Supabase keys.

After checking the current policy for each secret, add access only when the runtime service account is not already granted access:

```powershell
gcloud secrets add-iam-policy-binding SECRET_NAME --project=claimpilot-512009 --member="serviceAccount:claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

Run this for one secret name at a time and only for secrets the service needs. Avoid broad project-level grants when per-secret bindings suffice.

Verify the runtime account exists:

`claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com`

Do not create duplicate resources or change IAM until you have inspected current state.

### Twilio Verify (optional for this email-first demo)

The intended SMS flow uses the Verify API with all three values: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID`. The application sends a verification request and accepts an SMS code only when Twilio's check indicates approved/valid. `TWILIO_PHONE_NUMBER` is not required for this flow.

The code retains a legacy Programmable SMS fallback if Verify is not configured. For the email-only demo, omit Twilio secrets and use email addresses for authentication. If phone/SMS login is required, create/populate the missing Verify Service SID secret, verify it has an enabled version and the runtime service account has secret access, then add all three Twilio mappings to Cloud Run. The previous handoff reported that the `claimpilot-twilio-phone-number` secret was deleted; leave it absent unless the owner deliberately chooses the legacy fallback.

### SendGrid

Email OTP requires both `SENDGRID_API_KEY` and a sender address in `SENDGRID_FROM_EMAIL` that is verified in SendGrid. Secret Manager can hold the API key; the sender address is a non-secret Cloud Run environment variable. The actual verified sender address and real delivery were not confirmed in the last handoff. Do not use a guessed address.

## 4. Source and image: rebuild, do not deploy old `v1`

The previously pushed image was:

```text
asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1
sha256:fdad2b67315e9e2f3ac373d3f95665d0ed715dad346de1efa215de15c9bea1d4
```

It predates the final merged Twilio Verify implementation. **Do not deploy this image as the final release.**

After the configuration PR is reviewed/merged, prepare a clean checkout of the **latest canonical `main`** at the intended release commit. Verify `git remote -v` points to `Abhiram-Mukkamala/Claimpilot`; a historical local checkout had an unrelated repository as `origin`. Ensure there are no local modifications that could change the build input.

From the repository root in PowerShell:

```powershell
git status --short --branch
git remote -v
git log -1 --oneline
$Commit = (git rev-parse --short=12 HEAD).Trim()
$Image = "asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:git-$Commit"
Write-Host "Building source commit $(git rev-parse HEAD) as $Image"
gcloud builds submit --project=claimpilot-512009 --region=asia-south1 --tag=$Image .\insurance-pro\backend
```

The command uses `insurance-pro/backend` as the build context. Record the full Git SHA and the image digest reported by the build/Artifact Registry. Do not overwrite `v1`; the new tag should be tied to the commit that was actually built.

The prior local Docker checks verified loading `best.pt` and running synthetic-image inference, plus local `/health`, `/health/ready`, and a Supabase REST request on a **pre-merge image**. They do not establish that the current image is deployed or that real OTP and full E2E work.

## 5. Configure and deploy a Cloud Run revision — only after preflight

Do not run this section until:
- The source/image is rebuilt from the intended canonical commit.
- The four required email-demo secrets have usable enabled versions. Verify current metadata and IAM again immediately before deployment.
- Runtime IAM bindings allow the service account to access the required secrets.
- A verified SendGrid sender address is known.
- The actual deployed frontend HTTPS origin is known and approved.
- The team has explicitly authorized a live deployment.

For the demo, synchronous assessment is recommended because Cloud Run request-based CPU allocation can be unsuitable for in-process background work after the response finishes. The code supports `AI_PROCESSING_SYNC=true` for inline assessment; keep the 300-second timeout and verify actual inference time. This is not a substitute for a durable task queue for production workloads.

Set the exact frontend values interactively (these are configuration, not secrets):

```powershell
$FrontendOrigin = (Read-Host "Enter the actual deployed frontend HTTPS origin, with no trailing slash").TrimEnd("/")
$SendGridFrom = Read-Host "Enter the exact sender address verified in SendGrid"
```

Do not use the example domain `claimpilot.app` unless the project owner has confirmed that it is the real deployed frontend. Set only the approved origin(s); never use wildcard CORS.

Deploy the commit-specific image:

```powershell
gcloud run deploy claimpilot-api `
  --project=claimpilot-512009 `
  --region=asia-south1 `
  --image=$Image `
  --platform=managed `
  --allow-unauthenticated `
  --service-account=claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com `
  --port=8080 `
  --cpu=1 `
  --memory=4Gi `
  --concurrency=1 `
  --timeout=300 `
  --min-instances=0 `
  --max-instances=2 `
  "--set-env-vars=^~^ENVIRONMENT=production~SUPABASE_URL=https://zegygoxpmnxpdhutdpqf.supabase.co~SUPABASE_STORAGE_BUCKET=claim-evidence~SENDGRID_FROM_EMAIL=$SendGridFrom~FRONTEND_URL=$FrontendOrigin~ALLOWED_ORIGINS=$FrontendOrigin~AI_PROCESSING_SYNC=true" `
  "--set-secrets=SUPABASE_ANON_KEY=claimpilot-supabase-anon-key:latest,SUPABASE_SERVICE_ROLE_KEY=claimpilot-supabase-service-role-key:latest,JWT_SECRET=claimpilot-jwt-secret:latest,SENDGRID_API_KEY=claimpilot-sendgrid-api-key:latest"
```

`--allow-unauthenticated` makes the API network-reachable by the browser; it is not user authorization. Each protected endpoint must continue to enforce application authentication, roles, and ownership. CORS is not a substitute for auth.

If you later choose to demonstrate SMS login, first provision the optional Verify Service SID secret and verify all three Twilio secrets plus IAM. Then attach them to the existing service:

```powershell
gcloud run services update claimpilot-api `
  --project=claimpilot-512009 `
  --region=asia-south1 `
  --update-secrets=TWILIO_ACCOUNT_SID=claimpilot-twilio-account-sid:latest,TWILIO_AUTH_TOKEN=claimpilot-twilio-auth-token:latest,TWILIO_VERIFY_SERVICE_SID=claimpilot-twilio-verify-service-sid:latest
```

Do not run that optional command for the email-only demo.

If a command fails, stop and inspect the error. Do not work around auth/authorization failures by making Supabase storage public, loosening RLS, exposing the service-role key, or enabling OTP development codes.

## 6. Post-deployment verification

Get the service URL from the successful `gcloud run deploy` output or:

```powershell
gcloud run services describe claimpilot-api --project=claimpilot-512009 --region=asia-south1 --format="value(status.url)"
```

Check liveness and readiness:

```powershell
$ServiceUrl = Read-Host "Enter the exact Cloud Run service URL"
Invoke-WebRequest "$ServiceUrl/health" -Method Get
Invoke-WebRequest "$ServiceUrl/health/ready" -Method Get
```

Current `/health` is a liveness check and should return HTTP 200 with `{"status":"healthy"}`. Current `/health/ready` checks Supabase Data API access and email-OTP configuration; it does **not** verify Twilio SMS delivery, private evidence authorization, the frontend, or the whole E2E flow. Expected ready dependencies include `database: reachable` and `email_otp: configured`. Do not infer more from it than it checks.

Then complete the live test with team-owned accounts:

1. Send and verify a real email OTP through SendGrid; reject invalid and expired codes.
2. Sign in as a customer and submit a claim with required real demo details.
3. Upload evidence and register the canonical storage path returned by the upload flow.
4. Confirm inference runs with the deployed model and a real result or explicit flagged/manual-review failure is persisted. Do not treat synthetic-image loading as accuracy evidence.
5. Confirm fraud-analysis result persistence where applicable; don't assert advanced segmentation/depth outputs unless the deployed API actually returns them.
6. Sign in as an authorized agent, inspect the claim, and submit the permitted decision.
7. Refresh the customer view and verify status/decision persistence and correct actor-level access.
8. Test private evidence access, unauthorized requests, and a CORS preflight from the exact approved frontend origin.
9. Review Cloud Logging for sanitized errors; inspect latency, memory, cold starts, and costs. Never capture OTPs, authorization headers, signed URLs, secret payloads, or customer PII in shared logs.
10. Only if Twilio Verify has been configured and the SMS trial policy is understood, separately test SMS send/check, rejected codes, and expired codes.

Only mark full E2E as passed after the entire journey succeeds against the deployed service, not based on unit tests or health checks alone.

## 7. Frontend integration

The integrated frontend lives at `insurance-pro/frontend/ClaimPilot/`. Its production build must point its documented API base variable to `https://<CLOUD_RUN_SERVICE_URL>/api/v1` (inspect that checkout's `.env.example` and client configuration before setting the variable). Vite `VITE_*` values are embedded at build time, so rebuild/redeploy after changing them. Confirm the actual deployed frontend origin and keep `FRONTEND_URL` and `ALLOWED_ORIGINS` aligned with it.

No frontend host/domain or full live customer-to-agent E2E was confirmed in the prior handoff.

## 8. Hard guardrails

- Do not run database migrations, schema scripts, or seed scripts as part of hosting. Supabase migration state must be audited separately.
- Never print/inspect secret payloads in shared output. Use version metadata only.
- Never put actual `.env` files into the image or commit them.
- Do not enable `OTP_DEV_FIXED_CODE` in production.
- Do not expose Supabase service-role keys to frontend variables.
- Do not make evidence storage public to work around an access error.
- Don't claim SendGrid/Twilio works until you complete real delivery and verification.
- Don't deploy the old `v1` image as the final release.
- Don't claim full E2E based solely on a successful build, unit tests, YOLO checkpoint load, `/health`, or `/health/ready`.
