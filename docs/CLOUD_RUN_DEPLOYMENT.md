# ClaimPilot Backend Deployment — Google Cloud Run

**Purpose:** Host the ClaimPilot FastAPI and Ultralytics inference backend on Google Cloud Run while maintaining the Supabase project for Authentication, PostgreSQL database, and private evidence Storage.

> [!IMPORTANT]
> This runbook is strictly for deploying and configuring the container service on Cloud Run. It does **not** modify database schema, alter Row Level Security (RLS) policies, or seed data. Supabase remains the authoritative data plane.

---

## Architecture & Sizing Overview

- **GCP Project:** `claimpilot-512009`
- **Region:** `asia-south1` (Mumbai) — colocated near the Supabase region.
- **Service Name:** `claimpilot-api`
- **Supabase Project URL:** `https://zegygoxpmnxpdhutdpqf.supabase.co`
- **Private Evidence Bucket:** `claim-evidence`
- **Compute Sizing:**
  - **vCPU:** 1
  - **Memory:** 4 GiB (required to load YOLOv8s CarDD model weights `best.pt` and run metric depth/damage inference without OOM risks).
  - **Concurrency:** 1 (ensures dedicated CPU/memory per concurrent ML inference request).
  - **Request Timeout:** 300 seconds (accommodates cold starts and asynchronous/synchronous image processing pipelines).
  - **Minimum Instances:** 0 (scales to zero to eliminate idle compute costs during inactive periods).
  - **Maximum Instances:** 2 (prevents runaway costs while allowing burst handling).

---

## 1. Project Setup & Prerequisites

Authenticate your local gcloud CLI and target the production GCP project:

```bash
gcloud auth login
gcloud config set project claimpilot-512009
gcloud config set run/region asia-south1
```

Enable required Google Cloud APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

Create the Artifact Registry Docker repository (one-time setup):

```bash
gcloud artifacts repositories create claimpilot \
  --repository-format=docker \
  --location=asia-south1 \
  --description="ClaimPilot backend container images"
```

Create a dedicated least-privilege runtime service account for Cloud Run:

```bash
gcloud iam service-accounts create claimpilot-runtime \
  --display-name="ClaimPilot Cloud Run Runtime Account"
```

---

## 2. Container Build & Packaging

The backend container uses the hardened multi-stage Dockerfile located at `insurance-pro/backend/Dockerfile`. The build context is set to `./insurance-pro/backend` so that `.dockerignore` filters out non-backend artifacts and includes pre-trained model weights (`app/models/weights/best.pt`, ~22.5 MB).

Submit the container build to Google Cloud Build:

```bash
gcloud builds submit \
  --project=claimpilot-512009 \
  --region=asia-south1 \
  --tag=asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1 \
  ./insurance-pro/backend
```

*Note: If Cloud Build reports permissions errors pushing to Artifact Registry, grant the Cloud Build service account (`[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`) the role `roles/artifactregistry.writer`.*

---

## 3. Secret Manager Configuration & Verification

All sensitive credentials must be stored in Google Cloud Secret Manager and mounted as environment variables in Cloud Run. **Never hardcode secrets into Docker images, repository files, or `.env` templates.**

### Secret Mappings Table

| Cloud Run Environment Variable | Secret Manager Secret Name | Audit Status in `claimpilot-512009` | Purpose |
|--------------------------------|----------------------------|-----------------------------------|---------|
| `SUPABASE_ANON_KEY` | `claimpilot-supabase-anon-key` | Active (Version 1 enabled) | Client/Anon key for Supabase public auth/queries |
| `SUPABASE_SERVICE_ROLE_KEY` | `claimpilot-supabase-service-role-key` | Active (Version 1 enabled) | Backend admin key for private table/bucket operations |
| `JWT_SECRET` | `claimpilot-jwt-secret` | Active (Version 2 enabled) | Minimum 32-character secret for signing session JWTs |
| `SENDGRID_API_KEY` | `claimpilot-sendgrid-api-key` | Active (Version 1 enabled) | API key for transactional email OTP dispatch |
| `TWILIO_ACCOUNT_SID` | `claimpilot-twilio-account-sid` | Active (Version 2 enabled) | Twilio account identifier for SMS verification |
| `TWILIO_AUTH_TOKEN` | `claimpilot-twilio-auth-token` | Active (Version 1 enabled) | Twilio auth token for API authentication |
| `TWILIO_VERIFY_SERVICE_SID` | `claimpilot-twilio-verify-service-sid` | **Action Required** (Must be created) | Twilio Verify Service SID (`VA...`) for OTP flow |

### Pre-Deployment Action: Create Twilio Verify Secret

Before creating or updating the Cloud Run revision, create the missing `claimpilot-twilio-verify-service-sid` secret:

```bash
# Create secret in Secret Manager
gcloud secrets create claimpilot-twilio-verify-service-sid \
  --project=claimpilot-512009 \
  --replication-policy="automatic"

# Add version with your Twilio Verify Service SID (format: VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
echo -n "VA_YOUR_ACTUAL_SERVICE_SID" | gcloud secrets versions add claimpilot-twilio-verify-service-sid \
  --project=claimpilot-512009 \
  --data-file=-
```

### Grant Secret Access to the Runtime Service Account

Grant the runtime service account read access to each secret:

```bash
$SECRETS = @(
  "claimpilot-supabase-anon-key",
  "claimpilot-supabase-service-role-key",
  "claimpilot-jwt-secret",
  "claimpilot-sendgrid-api-key",
  "claimpilot-twilio-account-sid",
  "claimpilot-twilio-auth-token",
  "claimpilot-twilio-verify-service-sid"
)

foreach ($s in $SECRETS) {
  gcloud secrets add-iam-policy-binding $s `
    --project=claimpilot-512009 `
    --member="serviceAccount:claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com" `
    --role="roles/secretmanager.secretAccessor"
}
```

---

## 4. Twilio Verify SMS Service Configuration

ClaimPilot implements an integration with the **Twilio Verify v2 API** (`/Verifications` and `/VerificationCheck`):

### Why `TWILIO_PHONE_NUMBER` is Not Required for Verify
1. **Managed Delivery:** Twilio Verify dynamically routes and delivers SMS codes through Twilio's global alphanumeric and short-code sender pools.
2. **Source Implementation:**
   - [auth_otp.py](file:///C:/Projects/claimbot%20AI/wt-canonical-main/insurance-pro/backend/app/api/v1/auth_otp.py#L63-L121) checks `_is_twilio_verify_active()`. When `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID` are non-empty, requests are dispatched directly to `https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications`.
   - **No sender phone number (`From`) is passed to or accepted by the Twilio Verify API.**
   - In database records, `otp_code` is stored as `"VERIFY"`, and verification validation is delegated to `https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/VerificationCheck`.
3. **Legacy Fallback Behavior:**
   - If `TWILIO_VERIFY_SERVICE_SID` is omitted or empty, the backend falls back to legacy Programmable SMS (`send_otp_via_sms`), which *does* require `TWILIO_PHONE_NUMBER` (or `FAST2SMS_API_KEY`).
   - For production deployment, configure `TWILIO_VERIFY_SERVICE_SID` and leave `TWILIO_PHONE_NUMBER` unset.

---

## 5. Cloud Run Service Deployment

Deploy the service to Cloud Run with production environment variables and secret mappings:

```bash
gcloud run deploy claimpilot-api \
  --project=claimpilot-512009 \
  --region=asia-south1 \
  --image=asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1 \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com \
  --port=8080 \
  --cpu=1 \
  --memory=4Gi \
  --concurrency=1 \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=2 \
  --set-env-vars="ENVIRONMENT=production,SUPABASE_URL=https://zegygoxpmnxpdhutdpqf.supabase.co,SUPABASE_STORAGE_BUCKET=claim-evidence,SENDGRID_FROM_EMAIL=notifications@claimpilot.com,FRONTEND_URL=https://claimpilot.app,ALLOWED_ORIGINS=https://claimpilot.app,AI_PROCESSING_SYNC=false" \
  --set-secrets="SUPABASE_ANON_KEY=claimpilot-supabase-anon-key:latest,SUPABASE_SERVICE_ROLE_KEY=claimpilot-supabase-service-role-key:latest,JWT_SECRET=claimpilot-jwt-secret:latest,SENDGRID_API_KEY=claimpilot-sendgrid-api-key:latest,TWILIO_ACCOUNT_SID=claimpilot-twilio-account-sid:latest,TWILIO_AUTH_TOKEN=claimpilot-twilio-auth-token:latest,TWILIO_VERIFY_SERVICE_SID=claimpilot-twilio-verify-service-sid:latest"
```

### Environment Variables Detail

| Name | Production Value / Example | Notes |
|------|---------------------------|-------|
| `ENVIRONMENT` | `production` | Enforces production security; blocks hardcoded dev codes and mock OTP dispatch. |
| `SUPABASE_URL` | `https://zegygoxpmnxpdhutdpqf.supabase.co` | Verified Supabase project endpoint. |
| `SUPABASE_STORAGE_BUCKET` | `claim-evidence` | Target private Supabase storage bucket for car photos. |
| `SENDGRID_FROM_EMAIL` | Sender address verified in SendGrid | Must match a verified single sender or domain in SendGrid. |
| `FRONTEND_URL` | e.g. `https://claimpilot.app` | Exact HTTPS URL of the deployed frontend. |
| `ALLOWED_ORIGINS` | e.g. `https://claimpilot.app` | Exact HTTPS origin(s), comma-separated. No wildcards (`*`) and no trailing slashes. |
| `AI_PROCESSING_SYNC` | `false` | When `false`, image damage inference runs asynchronously in the background. Set `true` if an immediate synchronous response is needed. |

---

## 6. Post-Deployment Verification & End-to-End Checklist

Once Cloud Run outputs the service URL (`https://claimpilot-api-xxxx-el.a.run.app`), execute the following verification steps:

### 1. Health & Readiness Verification
- **Liveness probe:**
  ```bash
  curl -i https://<SERVICE_URL>/health
  ```
  *Expected Output:* HTTP 200 OK with `{"status":"healthy"}`.
- **Readiness probe:**
  ```bash
  curl -i https://<SERVICE_URL>/health/ready
  ```
  *Expected Output:* HTTP 200 OK with database connection verified, storage bucket accessible, and OTP providers active.

### 2. CORS Preflight Check
Verify that cross-origin preflight requests from the production frontend origin are permitted:
```bash
curl -i -X OPTIONS https://<SERVICE_URL>/api/v1/claims/ \
  -H "Origin: https://claimpilot.app" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization"
```
*Expected Output:* HTTP 200 OK with `access-control-allow-origin: https://claimpilot.app`.

### 3. Frontend Build Configuration
Update the frontend production build environment to route API calls to the Cloud Run backend:
- Set `VITE_API_BASE_URL=https://<SERVICE_URL>/api/v1` in the frontend build pipeline.
- Build and deploy the frontend bundle.

### 4. End-to-End User Journey Smoke Test
Execute a full user workflow using team-owned demo accounts:
1. **Claimant Sign Up / Login:**
   - Request Email OTP (dispatched via SendGrid) and Phone OTP (dispatched via Twilio Verify).
   - Enter received verification codes; confirm successful JWT session issuance.
2. **Claim Submission:**
   - Submit a new vehicle insurance claim with incident details and upload car damage imagery.
   - Confirm upload succeeds directly into the private `claim-evidence` bucket.
3. **AI Damage Assessment & Fraud Evaluation:**
   - Confirm backend inference processes the image with `best.pt`.
   - Confirm detection labels, damage severity, geometry-based cost estimates, and fraud risk score persist in Supabase.
4. **Authorized Private Evidence Access:**
   - Verify that private evidence URLs are signed URLs with finite expiration and reject unauthenticated requests.
5. **Agent Review & Settlement:**
   - Log in with agent credentials, review the assessed claim, verify the settlement amount calculation, and submit approval.
   - Refresh the customer view to verify the updated status.
