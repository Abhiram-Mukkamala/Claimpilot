# ClaimPilot AI

AI-assisted motor insurance claim assessment with vehicle-damage detection and cross-claim fraud analysis.

ClaimPilot combines a React web application, a FastAPI backend, Supabase authentication/database/object storage, and computer-vision models. The application supports customer claim submission and evidence upload, AI-assisted assessment, and agent review. **AI assessments and repair-cost estimates are decision support, not guarantees or automatic payouts.**

> **Project status:** This README documents the intended project layout and local development workflow. It does not certify that a live Supabase deployment, email/SMS delivery, private evidence access, or the complete customer-to-agent flow is currently working. Verify those integrations in your own environment.

**Current runtime wiring checklist:** see [Supabase runtime connection guide](docs/SUPABASE_RUNTIME_CONNECTION.md) for the project URL, backend-only secrets, readiness probe, and required live verification.

## Contents

- [Project layout](#project-layout)
- [Core workflow](#core-workflow)
- [Requirements](#requirements)
- [Local setup](#local-setup)
- [Run the application](#run-the-application)
- [Tests and quality checks](#tests-and-quality-checks)
- [API overview](#api-overview)
- [ML notes](#ml-notes)
- [Security and data handling](#security-and-data-handling)
- [Troubleshooting](#troubleshooting)
- [Project milestones](#project-milestones)

## Project layout

The backend-connected application lives in `insurance-pro/`. Use that frontend for integration work; do not substitute a separate mock or prototype frontend.

```text
ClaimPilot-Final/
├── insurance-pro/
│   ├── backend/                 # FastAPI API, auth, claims, storage, inference
│   │   ├── app/
│   │   ├── tests/
│   │   ├── .env.example
│   │   └── README.md
│   └── frontend/
│       └── ClaimPilot/          # Connected React + Vite + TypeScript frontend
│           ├── src/
│           ├── package.json
│           └── README.md
├── ml/                          # Model evaluation and research utilities
├── docs/                        # Project documentation, where present
├── README.md
└── ...
```

Some model checkpoints and local configuration files may not be committed. Check the actual checkout before assuming a file exists.

## Core workflow

The target end-to-end demonstration is:

1. A customer signs in.
2. The customer submits a claim with real, required policy, vehicle, incident, and driver details.
3. Evidence files are uploaded and registered against the claim.
4. The backend runs the configured damage-detection model.
5. Available damage detections and fraud-analysis findings are persisted and shown.
6. An authorized agent reviews the claim and submits a decision.
7. The customer can view the persisted decision/status.

Do not replace missing API responses or model outputs with invented detections, confidence values, fraud scores, cost estimates, images, or success messages. If a value is unavailable, show that it is unavailable. Claim approval must not be described as a payout having been initiated or completed.

## Requirements

Install these tools before starting:

- Python 3.11 or the Python version supported by the backend dependencies.
- Node.js and npm compatible with the frontend lockfile.
- Git.
- A configured Supabase project for live authentication, database, and storage integration.
- The model checkpoint required by the backend configuration, if running real inference locally.

Exact package versions should come from the repository's dependency and lock files rather than from this README.

## Local setup

Run commands from the indicated directory in PowerShell. Keep backend and frontend terminals separate.

### 1. Get the code

```powershell
git clone <repository-url>
Set-Location .\ClaimPilot
```

If the repository was already cloned, open the project root instead. The expected root contains `insurance-pro\backend` and `insurance-pro\frontend\ClaimPilot`.

### 2. Configure the backend

```powershell
Set-Location .\insurance-pro\backend
Copy-Item .env.example .env
```

Open `.env` locally and fill in the required values using the comments in `.env.example` and the backend README. Do not commit `.env`, paste its contents into chat, or put secrets in screenshots or logs.

Create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the repository's dependency file has a different name, follow the file that is actually present in `insurance-pro\backend`; do not create a new dependency list from memory.

Before using a live Supabase project, an authorized project owner should verify the deployed schema, migrations, Row Level Security (RLS) policies, storage bucket privacy, and access policies. Do not run schema scripts or database writes against a shared or production project without explicit approval.

### 3. Configure the connected frontend

Open a second PowerShell terminal from the repository root:

```powershell
Set-Location .\insurance-pro\frontend\ClaimPilot
Copy-Item .env.example .env
npm ci
```

If `insurance-pro\frontend\ClaimPilot\.env.example` is absent in the checkout, inspect the frontend README and configuration files to identify the supported variable names before creating `.env`. Do not guess between similarly named API URL variables.

Set the frontend API base URL to the locally running backend using the exact variable name documented by the checked-out frontend configuration. Vite embeds `VITE_*` values at build time; restart the dev server after changing local environment configuration.

## Run the application

### Backend

From `insurance-pro\backend`, with the virtual environment activated and local environment configured:

```powershell
uvicorn app.main:app --reload
```

The default local API address is usually `http://127.0.0.1:8000`; confirm the actual host and port in the backend startup output. If the app exposes OpenAPI documentation, visit `http://127.0.0.1:8000/docs`.

### Frontend

From `insurance-pro\frontend\ClaimPilot`:

```powershell
npm run dev
```

Open the local URL printed by Vite. Keep the backend running in its own terminal.

For a production-like frontend preview, use the scripts declared in `package.json` (commonly `npm run build` followed by `npm run preview`). Use the actual scripts in the checked-out package file as the source of truth.

## Tests and quality checks

### Backend tests

From `insurance-pro\backend`:

```powershell
python -m pytest -q
```

### Frontend checks

From `insurance-pro\frontend\ClaimPilot`:

```powershell
npm ci
npx tsc --noEmit
npm run build
npm run lint
```

The available TypeScript script and lint command can vary by branch; if a command is not defined, inspect `package.json` and use the repository's configured equivalent.

A recorded integrated-backend run on 15 October 2026 reported **97 passed, 9 deprecation warnings**. This is a historical result for that local tree, not a guarantee for another branch or checkout. Run the commands above after changing code and report the exact output. Passing unit tests does not establish that live Supabase, email/SMS delivery, storage permissions, model files, or the full E2E flow work.

## API overview

The following route families were observed in the project code; request/response schemas and live behavior must be checked against the running version.

| Purpose | Route |
|---|---|
| Create/list claims | `POST /claims`, `GET /claims` |
| Retrieve a claim | `GET /claims/{claim_id}` |
| Retrieve claim AI analysis | `GET /claims/{claim_id}/ai-analysis` |
| Customer portal decision | `POST /claims/portal/decision` |
| Request a storage upload URL | `POST /storage/presigned-url` |
| Register uploaded evidence | `POST /storage/evidence` |
| Agent claim queue | `GET /agent/claims` |
| Agent claim details | `GET /agent/claims/{claim_id}` |
| Agent action | `POST /agent/claims/{claim_id}/action` |

The route list is a navigation aid, not an API contract. Inspect the current FastAPI schemas and generated OpenAPI document before integrating a client.

## ML notes

- The project includes YOLO and RT-DETR vehicle-damage detection work.
- The target damage categories include crack, dent, glass shatter, broken lamp, scratch, and flat tire; confirm the class names and ordering for the exact checkpoint being loaded.
- Perceptual hashing (pHash) is used for cross-claim duplicate-image/fraud analysis.
- Research scripts for depth estimation or 3D reconstruction may exist under `ml/`; do not assume they are exposed as working backend API features.
- Confirm the configured model-weight path and run inference on real sample images before a demo.
- Report evaluation metrics only with the dataset, split, class ordering, and evaluation method. Metrics from different splits or class orderings are not directly comparable.
- Any repair-cost estimate must be labelled as indicative unless calibrated and validated. It must not independently determine a payout.

## Security and data handling

- Never commit `.env` files, passwords, API keys, JWTs, service-role keys, OTPs, signed URLs, or customer evidence.
- Treat previously exposed credentials as compromised and rotate them through the relevant provider. Do not reproduce them in documentation or rewrite Git history casually.
- Use customer/agent/admin authorization checks on every protected claim and evidence operation.
- Confirm evidence storage is private where required and that reads use properly scoped authorization or short-lived signed URLs.
- OTP flows must enforce expiry, attempt limits, resend throttling, and one-time consumption. Development OTP behavior must never be enabled in production.
- CORS origins and backend secrets must be configured explicitly for each environment.
- Do not log passwords, OTPs, authorization headers, signed URLs, or sensitive customer data.
- Never run database migrations or write operations against shared Supabase environments without the project owner's approval.
- A successful agent decision is not proof that money has been transferred. The product does not perform autonomous payouts.

## Troubleshooting

**Frontend cannot reach the backend**
- Confirm the backend is running and note its actual URL.
- Check the API base URL variable name used by the current frontend source.
- Restart Vite after changing environment variables.
- Check browser network errors and backend logs without sharing secrets.

**Authentication or OTP fails**
- Verify backend configuration and the configured email/SMS provider in the local environment.
- Check expiry, rate-limit, and provider error logs without printing OTPs or credentials.
- Do not use a fixed development OTP against production.

**Evidence upload succeeds but analysis cannot read the file**
- Check that upload and evidence-catalog registration both completed.
- Verify the stored object path, bucket privacy, and authorized read mechanism.
- Do not switch to public evidence URLs as a workaround for an authorization problem.

**Analysis is missing or looks suspicious**
- Confirm the configured checkpoint exists and loads.
- Check backend inference logs and the API response.
- Show missing results as unavailable; do not substitute sample detections or fabricated costs.

**Tests fail on a different branch**
- Confirm the current directory, branch, and dependency environment.
- Use the dependency lockfiles and exact test output to diagnose the failure.
- Preserve existing uncommitted changes; do not reset or clean the worktree to make tests pass.

## Project milestones

The project context records an internal code freeze of **20 October 2026** and the MIT India Hackathon finale on **24 October 2026 in New Delhi**. Treat those as planning dates, not evidence that any particular feature is complete.

## Contributing and change control

Before making changes:

1. Confirm the repository root, current branch, and working-tree status.
2. Read the relevant backend/frontend README and current project status notes.
3. Make the smallest scoped change that addresses the issue.
4. Run relevant tests and capture exact results.
5. Report what changed, what was tested, and what remains unverified.

Preserve uncommitted work. Do not reset, rebase, merge, push, delete files, change branches, or modify databases without explicit authorization.
