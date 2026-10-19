# ClaimPilot GCP Deployment State

Last updated: 2026-10-19 (Asia/Kolkata)

## Project and region

- GCP project ID: claimpilot-512009.
- Active gcloud project and CLI billing/quota_project were set to claimpilot-512009.
- ADC quota project was successfully set to claimpilot-512009.
- Billing command returned billingEnabled: true.
- A screenshot showed four Google Developer Program monthly credit entries at 100%, ₹955.46 each (₹3,821.84 total displayed across those entries); the conversation did not conclusively verify that all credits apply to this project. Check Billing credits page/account before cost-bearing deployment.
- Target region: asia-south1 (Mumbai), provisional for India demo users.
- Correct Supabase project: zegygoxpmnxpdhutdpqf, URL https://zegygoxpmnxpdhutdpqf.supabase.co (Supabase region is Sydney). Expect cross-region backend-to-DB latency; measure it.

## APIs enabled

The user ran gcloud services enable successfully for:
- run.googleapis.com
- cloudbuild.googleapis.com
- artifactregistry.googleapis.com
- secretmanager.googleapis.com

Cloud Resource Manager and Cloud Billing APIs were also enabled while aligning project/ADC/billing commands.

## Artifact Registry

- Docker repository name: claimpilot.
- Location: asia-south1.
- A create command returned ALREADY_EXISTS, so the repository already existed.
- The prior list command returned an empty table, so verify with gcloud artifacts repositories describe claimpilot --location=asia-south1 --project=claimpilot-512009 before relying on it.
- Docker auth configured with gcloud auth configure-docker asia-south1-docker.pkg.dev.
- Image pushed to: asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1.
- Push result digest: sha256:fdad2b67315e9e2f3ac373d3f95665d0ed715dad346de1efa215de15c9bea1d4.
- This image was built before reconciliation of the latest uploaded backend source. Current GitHub branch code at time of inspection uses the older SMS Messages API and local OTP validation. Do not deploy this image as the final release if the latest backend changes alter auth/OTP or other runtime behavior.

## Runtime service account and secrets

- Runtime service account created: claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com.
- Secret containers created and roles/secretmanager.secretAccessor granted on each to that service account:
  - claimpilot-supabase-anon-key
  - claimpilot-supabase-service-role-key
  - claimpilot-jwt-secret
  - claimpilot-sendgrid-api-key
- Actual secret versions/values were not confirmed populated in conversation. Verify each secret's versions before deploying.
- SendGrid API key and verified sender availability were pending user check.
- Twilio secrets for Account SID, Auth Token and Verify Service SID were discussed but no successful creation/population was reported. The phone-number secret was deleted by the user; do not assume it exists. Whether it is needed depends on confirmed implementation (regular Messages API needs a sender number; Twilio Verify does not use the application's From field).
- Never print or ask the user to paste secret values. Use Secret Manager's add-version UI or a secure local input method, and don't commit values.

## No live deployment yet

- No Cloud Run service was created/deployed in the conversation.
- No frontend deployment/custom domain/CORS origin has been confirmed.
- Production email delivery has not been proven. /health/ready in the local container showed email OTP configuration present; that is a config check, not a real inbox-delivery test.
- Proposed Cloud Run starting configuration from the runbook: service claimpilot-api, 1 vCPU, 4 GiB RAM, request-based billing, min instances 0, max instances 2, concurrency 1, 300-second timeout, port 8080. Treat this as provisional until request latency/memory and full-flow behavior are measured.
- Runbook path on deploy/cloud-run: docs/CLOUD_RUN_DEPLOYMENT.md. It incorrectly points to legacy Supabase URL https://tiwdktgeqifhumcrwniv.supabase.co; correct to the current verified project URL before using the runbook.

## Safe next GCP actions

1. Stop before Cloud Run deploy until source reconciliation and PR merge plan are complete.
2. Verify registry using gcloud artifacts repositories describe.
3. Check credit applicability/remaining balance in the Cloud Billing console.
4. Verify required secret versions exist without displaying values.
5. After code is merged and reviewed, build a new versioned image tag from the exact merged commit, push it, then configure Cloud Run using Secret Manager bindings.
6. Set ENVIRONMENT=production; do not set OTP_DEV_FIXED_CODE in production.
7. Set exact actual HTTPS frontend origin in FRONTEND_URL and ALLOWED_ORIGINS.
8. Verify deployed /health, /health/ready, actual email and SMS OTP delivery/verification, private evidence handling, AI persistence, agent decision and customer status after refresh.
