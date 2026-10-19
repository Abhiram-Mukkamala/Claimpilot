# ClaimPilot GCP Deployment State

Last updated: 2026-10-19 (Asia/Kolkata), after PR #5 merged.

## Project and region

- GCP project ID: claimpilot-512009.
- Active gcloud project, CLI billing/quota_project and ADC quota project were set to claimpilot-512009.
- Billing command returned billingEnabled: true.
- Screenshot showed four Google Developer Program monthly credit entries at 100%, ₹955.46 each (₹3,821.84 across those displayed entries); it was not conclusively verified that all credits are applicable to this project's billing account. Check credits/account before cost-bearing deployment.
- Target region: asia-south1 (Mumbai), provisional for India demo users.
- Correct Supabase project: zegygoxpmnxpdhutdpqf, URL https://zegygoxpmnxpdhutdpqf.supabase.co (Supabase region Sydney). Measure cross-region latency.

## APIs enabled

User reported successful enablement for:
- run.googleapis.com
- cloudbuild.googleapis.com
- artifactregistry.googleapis.com
- secretmanager.googleapis.com
- cloudresourcemanager.googleapis.com
- cloudbilling.googleapis.com

## Artifact Registry and old image

- Repository name intended: claimpilot in asia-south1.
- gcloud artifacts repositories create returned ALREADY_EXISTS.
- A previous artifacts repositories list returned no rows despite ALREADY_EXISTS; verify with gcloud artifacts repositories describe claimpilot --location=asia-south1 --project=claimpilot-512009.
- Docker auth configured using gcloud auth configure-docker asia-south1-docker.pkg.dev.
- Old image pushed: asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1.
- Digest: sha256:fdad2b67315e9e2f3ac373d3f95665d0ed715dad346de1efa215de15c9bea1d4.
- **Do not deploy this old v1 image as final.** It was built before PR #5's final merged Twilio Verify implementation.
- Create a new versioned tag from exact merged main SHA after local alignment; e.g. a commit-specific tag. Verify pushed digest before Cloud Run deploy.

## Runtime service account

Created:
claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com

## Secret Manager

Secret containers created and roles/secretmanager.secretAccessor granted for runtime account on:
- claimpilot-supabase-anon-key
- claimpilot-supabase-service-role-key
- claimpilot-jwt-secret
- claimpilot-sendgrid-api-key

Actual secret versions/values were not confirmed populated. Check version listings without displaying values.

Twilio Verify secret names planned but their successful creation/population was not reported:
- claimpilot-twilio-account-sid
- claimpilot-twilio-auth-token
- claimpilot-twilio-verify-service-sid

Use those three to map to TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID in Cloud Run. For Verify mode, do not create/configure claimpilot-twilio-phone-number. The code still supports legacy regular Messages API fallback, but the intended deployment path is Twilio Verify when the three Verify settings are present.

SendGrid API key and verified sender address were pending user check. SendGrid sender email is config (SENDGRID_FROM_EMAIL) and needs to be mapped as a non-secret environment variable; API key should come from Secret Manager.

Never print or paste secret values. Do not use local .env files as an image layer or commit any credential.

## No live deployment confirmed

No Cloud Run service was created/deployed in the conversation. No frontend deployment, custom domain or actual HTTPS CORS origin is confirmed.

Local pre-merge Docker tests passed:
- best.pt packaged and loaded (22,501,482 bytes), YOLO detect classes dent/scratch/crack/glass shatter/lamp broken/tire flat.
- synthetic-image inference ran.
- after fixing local .env quote issues, /health and /health/ready returned HTTP 200.
- Supabase REST query from the container returned HTTP 200 and one row.
These results are from the pre-merge local image, not the current merged Verify implementation, not Cloud Run and not full E2E.

## Runbook defect and proposed sizing

- Runbook: docs/CLOUD_RUN_DEPLOYMENT.md on branch deploy/cloud-run.
- It references wrong legacy Supabase URL https://tiwdktgeqifhumcrwniv.supabase.co. Correct to https://zegygoxpmnxpdhutdpqf.supabase.co before using.
- Proposed starting service claimpilot-api: 1 vCPU, 4 GiB RAM, request-based billing, min instances 0, max instances 2, concurrency 1, timeout 300s, port 8080. Provisional only; verify latency and memory under actual inference.
- Set ENVIRONMENT=production; do not set OTP_DEV_FIXED_CODE in production.
- Set FRONTEND_URL and ALLOWED_ORIGINS to the actual deployed HTTPS frontend origin (no wildcard).

## GCP next actions, in order

1. Align local base/worktree to merged canonical main and verify commit SHA.
2. Correct the runbook Supabase URL.
3. Verify repository exists and check remaining/applicable credits.
4. Confirm required secret versions exist (only status/name metadata; do not print values).
5. Verify exact Cloud Run image build context and build from merged source, then push a fresh versioned tag.
6. Map Secret Manager secrets and environment variables to Cloud Run runtime account.
7. Deploy only after correct frontend origin, SendGrid API/sender and Twilio Verify service values are in place.
8. Check live /health and /health/ready, send and verify a real email OTP and Twilio Verify SMS OTP, then exercise customer login, claim creation, photo upload, persisted AI assessment, agent decision and customer status after refresh.
