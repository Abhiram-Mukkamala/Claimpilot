# ClaimPilot backend deployment — Google Cloud Run

**Purpose:** host the FastAPI/Ultralytics backend on Cloud Run while keeping the existing Supabase project for Auth, PostgreSQL/Data API and private evidence Storage. This is a deployment guide; it does not change Supabase schema or data.

## Why this setup

- Region: `asia-south1` (Mumbai), near the current Supabase project.
- Service: `claimpilot-api`.
- Initial sizing: 1 vCPU, 4 GiB RAM, request-based billing, minimum instances 0, maximum instances 2, concurrency 1, request timeout 300 seconds.
- Keep min instances at 0 while testing to avoid ongoing idle instance costs. Cold starts are a known trade-off.
- Keep Supabase in place. Do not run migrations or seed demo data as part of deployment.

These settings are starting values. Exercise real model inference under load and adjust only if measured memory/latency requires it. Cloud Run, build, artifact storage, logging, network egress and Secret Manager may have separate costs. Check the GCP billing page and credit expiry.

## 1. Check your Google Cloud project

In the Google Cloud Console, select the project whose billing account has the ₹3,200 credits. Confirm billing is enabled and the credits are still valid before creating resources.

Install and authenticate the Google Cloud CLI if you plan to use the commands below:

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud config get-value project
```

Replace `PROJECT_ID` with the project ID shown in the Console. It is not a secret; do not share billing/account IDs or credentials.

Enable the APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

Create the Docker image repository once:

```bash
gcloud artifacts repositories create claimpilot \
  --repository-format=docker \
  --location=asia-south1 \
  --description="ClaimPilot backend images"
```

If it already exists, do not recreate it.

## 2. Build and push the container

Run this from the repository root. The backend directory is the build context, so its `.dockerignore` applies and frontend files are not sent to the build.

```bash
gcloud builds submit \
  --region=asia-south1 \
  --tag=asia-south1-docker.pkg.dev/PROJECT_ID/claimpilot/claimpilot-api:v1 \
  ./insurance-pro/backend
```

Replace `PROJECT_ID` in the image path. If the build cannot push to Artifact Registry, grant the Cloud Build build service account the Artifact Registry Writer role on the `claimpilot` repository, then retry.

## 3. Prepare secrets before deploying

Use **Secret Manager** in the Google Cloud Console. Create a secret and add its value for each item below. Do not commit values, put them in the Docker image, or paste them into chat or source-control issues.

| Secret name | Value |
|---|---|
| `claimpilot-supabase-anon-key` | Supabase project's anon/publishable key required by the current backend settings |
| `claimpilot-supabase-service-role-key` | Supabase service-role key; backend only |
| `claimpilot-jwt-secret` | Fresh random secret of at least 32 characters, independent of Supabase keys |
| `claimpilot-sendgrid-api-key` | SendGrid API key for production email OTP |

Create a dedicated runtime service account `claimpilot-runtime` (IAM & Admin → Service Accounts). Grant it **Secret Manager Secret Accessor** on only those four secrets. Use that service account for Cloud Run.

Do not set `OTP_DEV_FIXED_CODE` in production.

## 4. Create the Cloud Run service

In Cloud Run → Create Service, deploy the image:

`asia-south1-docker.pkg.dev/PROJECT_ID/claimpilot/claimpilot-api:v1`

Configure:

- Service name: `claimpilot-api`
- Region: `asia-south1` (Mumbai)
- Authentication: allow unauthenticated invocations so the browser can reach the API; application endpoints must still enforce ClaimPilot's own authentication/authorization.
- Container port: `8080`
- CPU: `1`
- Memory: `4 GiB`
- Request timeout: `300` seconds
- Concurrency: `1`
- Minimum instances: `0`
- Maximum instances: `2`
- Runtime service account: `claimpilot-runtime`

Set the following environment variables in the service revision:

| Name | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `SUPABASE_URL` | `https://tiwdktgeqifhumcrwniv.supabase.co` |
| `SUPABASE_STORAGE_BUCKET` | `claim-evidence` |
| `SENDGRID_FROM_EMAIL` | A sender address verified in SendGrid |
| `FRONTEND_URL` | The frontend's actual deployed HTTPS origin; use localhost only for an explicitly temporary local-browser smoke test |
| `ALLOWED_ORIGINS` | The exact frontend origin, no trailing wildcard and no `*` |

Map secrets to environment variables using Cloud Run's Secret Manager integration:

| Environment variable | Secret |
|---|---|
| `SUPABASE_ANON_KEY` | `claimpilot-supabase-anon-key` |
| `SUPABASE_SERVICE_ROLE_KEY` | `claimpilot-supabase-service-role-key` |
| `JWT_SECRET` | `claimpilot-jwt-secret` |
| `SENDGRID_API_KEY` | `claimpilot-sendgrid-api-key` |

Do not make the service live for the full frontend demo until the frontend origin and verified SendGrid sender are set correctly.

## 5. Verify the deployed service

After deployment, copy the Cloud Run service URL from the Console and check:

1. `https://SERVICE_URL/health` returns HTTP 200 and `{"status":"healthy"}`.
2. `https://SERVICE_URL/health/ready` returns HTTP 200 with database reachable and email OTP configured.
3. Configure the frontend's public build variable `VITE_API_BASE_URL=https://SERVICE_URL/api/v1`, rebuild/redeploy the frontend, and ensure `ALLOWED_ORIGINS` exactly matches its HTTPS origin.
4. Run the complete end-to-end journey with team-owned demo accounts: email OTP login, create claim, upload evidence to the private bucket, verify inference/fraud outcomes persist (or an explicit manual-review/failure state persists), agent decision, and customer status after refresh.
5. Confirm private evidence is only returned through authorized/signed URLs. The readiness check alone is not a substitute for the end-to-end journey.
6. Check Cloud Logging, Cloud Run instance memory, request latency, and Billing → Reports after model inference tests.

Do not seed `seed_demo.sql` or rerun legacy schema migrations as a deployment shortcut. Keep the existing Supabase database and storage unchanged.
