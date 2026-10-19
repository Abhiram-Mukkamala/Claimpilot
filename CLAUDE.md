# ClaimPilot AI — Claude Code Project Memory and Engineering Guide

Last consolidated: **19 October 2026 (Asia/Kolkata)**  
Purpose: give a fresh Claude session the project history, current technical truth, release state, and safe working rules. This document is a handoff, not proof that every integration is production-ready.

## 0. First instructions for every new session

Before editing anything:

1. Run git status, identify the repository root, branch, HEAD SHA, and remotes.
2. Fetch/inspect canonical GitHub main. Do not assume this file remains current forever.
3. Read README.md, docs/CODEBASE_MAP.md, docs/IMPLEMENTATION_PLAN.md, and the relevant backend/frontend README. Read schema and ordered migrations before persistence changes.
4. Check whether the task is for the integrated app, mock/demo app, model-evaluation work, or deployment.
5. Preserve user changes, stashes, untracked files, worktrees, and backups. Never run destructive cleanup just to make a worktree look clean.
6. Make the smallest scoped change, run its targeted tests, inspect the whole diff, and report verified facts separately from assumptions.

**Do not deploy, change live Supabase data/schema, create/delete cloud resources, rotate secrets, merge PRs, push to main, reset/rebase, or delete branches/worktrees unless the user explicitly asks.** Work on a task branch and open a PR when repository changes are intended.

## 1. Repository identity and the actual start of its history

### Canonical repository

- Canonical repository: https://github.com/Abhiram-Mukkamala/Claimpilot
- Canonical branch: main
- Last verified main commit in this handoff: **03c10f5d97bfdbf7560b95ee6be6e7cfb44e8165**, merge of PR #5 on 19 October 2026.
- PR #5: https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5 — merged.
- PR #4: https://github.com/Abhiram-Mukkamala/Claimpilot/pull/4 — draft/open Cloud Run preparation PR; not merged.
- GitHub repository metadata reported visibility as **public** when this guide was assembled. Treat committed content as externally visible. Never put credentials, private customer evidence, OTPs, signed URLs, or secret values in the repository.

### Important history caveat: this is a snapshot migration

The canonical repository history starts on **16 October 2026** with the parentless commit:

- 036010f8de95d0198f17e25762b50ab3b04031c8 — “chore: initialize release repository with migration status”.

This destination repository is **not a full Git-history mirror** of the original source repository. The original source snapshot used for migration was branch **test/e2e-demo-smoke** at **265c3934674a0070d7314af064d4a62a1acd3fe0** in https://github.com/shreyasshah707/ClaimPilot. The README was reconciled against the source repository's then-current claimpilot branch. The initial migration documentation records 206 paths from the selected E2E snapshot plus selected additions; later commits changed the destination. Source commit ancestry, tags, and all source branches were not mirrored into destination main.

Therefore:
- Use this repository's Git history to understand changes since the 16 October release snapshot.
- Use the original repository and its branches only as historical/reference sources when needed.
- Do not expect an old source feature branch to merge cleanly into this snapshot-based history.
- Do not push to or mutate the original repository unless explicitly requested.
- Avoid blanket branch merges. Review and selectively port compatible files.

## 2. Project goal and end-to-end demo contract

ClaimPilot AI is an AI-assisted motor-insurance claim workflow for MIT India Hackathon 2026. The target demo journey is:

1. Customer authenticates.
2. Customer creates a claim with real required policy, vehicle, incident, and driver details.
3. Customer uploads evidence and the backend registers it against the claim.
4. Backend assesses damage from available photos and persists the analysis.
5. Fraud-analysis findings are persisted where supported.
6. Authorized agent opens the claim, reviews evidence/analysis, and submits a decision.
7. Customer can see the persisted state/decision after refresh.

Claim freeze target: **20 October 2026**. Hackathon finale: **24 October 2026**. These are schedule constraints, not proof of readiness.

AI is decision support. A detection, risk score, or repair-cost estimate is not a guarantee, a final settlement, or evidence that money was paid. Never fabricate detections, confidence, fraud scores, advanced-analysis output, prices, customer records, or success messages.

## 3. Product architecture and code map

### Canonical runtime components

- **Integrated frontend:** insurance-pro/frontend/ClaimPilot/ — React, Vite, TypeScript, customer pages, agent workbench, claim submission, analysis display and API clients.
- **Backend:** insurance-pro/backend/ — FastAPI, Supabase access, authentication/OTP, claims, evidence upload/catalog, damage inference, fraud analysis, email integration and agent actions.
- **Database/storage/auth:** Supabase PostgreSQL, Supabase Auth and private object storage. SQL schema and migrations are checked into the repo but remote migration state must be verified independently.
- **Damage inference:** tracked model weights under insurance-pro/backend/app/models/weights/, including best.pt. The backend uses its own YOLO/RT-DETR path.
- **Independent research pipeline:** ml/ — photo/video/depth/geometry scripts. Do not assume these scripts are called by the running API.
- **Model evaluation:** branch tests/model-evaluation-scores is intentionally separate from release-critical backend tests and deployment code. Its inherited metrics were not freshly rerun in the historical handoff; preserve provenance and re-evaluate before claiming model performance.

### There are different frontend trees

Do not confuse app targets. The backend-connected product is insurance-pro/frontend/ClaimPilot/. The repository-root src/ and root package.json represent a separate mock/demo frontend where present in the checked-out tree. Check the current tree before assuming path presence. For an integrated product request, use the frontend under insurance-pro/frontend/ClaimPilot/ unless the user explicitly identifies the root demo app.

### Important runtime paths

- API startup and middleware: insurance-pro/backend/app/main.py
- Versioned route modules: insurance-pro/backend/app/api/v1/
- Auth and OTP: app/api/v1/auth.py and app/api/v1/auth_otp.py
- Claims / agent actions / evidence: app/api/v1/claims.py, agent.py and storage.py
- Settings / authorization: app/core/config.py and app/core/authorization.py (inspect current filenames before editing)
- Supabase data access: app/db/supabase.py
- AI orchestration: app/services/ai_runner.py
- Fraud/pHash analysis: app/services/fraud_analysis_service.py
- Email: app/services/email.py
- SQL base schema and migrations: insurance-pro/backend/schema.sql, migration_v2.sql, migration_v3_phash.sql, plus supabase/migrations/ if present in the current tree
- Integrated UI API clients: insurance-pro/frontend/ClaimPilot/src/services/
- Customer and agent UI: insurance-pro/frontend/ClaimPilot/src/pages/

The usual integrated API prefix is /api/v1. Inspect current router mounting and OpenAPI schemas rather than relying on old route lists.

### Known AI/runtime behavior and limitations

- Damage inference runs through the backend's YOLO/RT-DETR implementation.
- The six classes reported for the packaged best.pt checkpoint are dent, scratch, crack, glass shatter, lamp broken, and tire flat. Confirm the currently loaded checkpoint/class ordering before any claims about performance.
- pHash-based cross-claim duplicate-image analysis is implemented. The narrative/severity path has used a deterministic heuristic when the optional LLM provider is not configured; verify current source/settings before claiming an LLM is active.
- Most advanced 3D/depth/segmentation paths in ml/ are separate research work, not proof of live API capabilities. Earlier codebase documentation found empty advanced fields and UI fallback/demo assets or values. Trace each displayed value from model output through DB/API mapping to UI. Label unavailable/fallback/demo values honestly.
- Normal evidence upload schedules assessment with FastAPI BackgroundTasks, which runs in-process and is not a durable task queue. A configurable synchronous assessment mode was added to improve demo reliability under request-based Cloud Run CPU. Verify the current setting and failure behavior before altering it.
- Repair-cost figures are indicative and the INR cost table is not insurer-calibrated. Never label it a final payout.

## 4. Repository timeline — how the project reached current main

This timeline summarizes the canonical destination history from 16–19 October 2026. It is intentionally grouped by workstream; use git log and commit/PR diffs for exact per-file details.

### 16 October — release snapshot, UI migration, schema and test foundation

- Initialized the destination release repository and documented its migration state.
- Imported the chosen E2E-ready source snapshot from the original repo. This was a snapshot transfer, not a full history mirror.
- Ported the selected Ayaan About/onboarding design into the canonical integrated frontend: About page, onboarding modal/steps/state, per-user completion persistence, team-section navigation fix, and accessibility/focus behavior. The port was selective; Ayaan's entire branch was not merged.
- Added/aligned the secure Supabase schema and versioned migrations for claim settlement compatibility, OTP identity binding, foreign-key indexes and repair-cost estimate basis.
- Added or strengthened backend schema-contract, auth, authorization, AI-runner, smoke and sensitive-logging regression coverage.
- Aligned DB/Pydantic claim-status contracts and migration files with the then-applied schema.
- Added workflow/CI compatibility changes. A recorded GitHub Actions backend/schema regression run passed 146 cases with 10 warnings on 17 October (dummy credentials and mocked dependencies; no live demo-data mutation).

### 17 October — real runtime integration, OTP challenge binding and preflight

- Worked through integration gaps across authentication, frontend/backend contract alignment, evidence uploads, claim fields and status behavior.
- Required explicit OTP challenge binding and explicit verification success before completing login/session flows. The frontend must keep passing the challenge ID expected by the backend; do not copy old login branches that omit it.
- Tightened OTP purpose/user binding in storage/verification and kept development OTP behavior from silently masquerading as a real provider delivery.
- Improved runtime readiness/preflight checks for Supabase and OTP provider configuration, PowerShell environment handling and backend virtual-environment use.
- Aligned evidence category/path handling. Keep the canonical path returned by the upload service; do not fabricate a storage path from a claim ID because backend ownership/path authorization depends on it.
- Improved schema compatibility, foreign-key indexing, backend-only demo seeding, and cost estimator integration.
- The cost estimator was selectively ported rather than merged wholesale. An alternate branch bypassed private-storage access/ownership checks and disabled normal TLS verification; those unsafe changes were excluded.
- The chosen About/onboarding design remained wired through the customer layout. Competing UI/login branches were reviewed but not applied wholesale where they broke current routing, OTP challenge IDs, or API contracts.
- Model-evaluation assets and score provenance were kept isolated from release-critical runtime work.

### 18 October — security, containers, model packaging and demo reliability

- Addressed security/authentication regressions, sensitive token/log exposure and claim concurrency/stale-update behavior.
- Added backend container packaging for Cloud Run, dynamic PORT handling and required runtime OS libraries.
- Tracked the production YOLO best.pt asset and validated that the checkpoint loads/inference executes in the local Python/Docker environment.
- Added configurable synchronous AI assessment so the demo could return assessment data more reliably in a request-based Cloud Run setup, while preserving the default background-task path.
- Added root Claude engineering notes, codebase map and implementation planning guide.
- Docker/readiness tests at this point were local, pre-merge evidence only. They did not establish a live Cloud Run deployment or end-to-end customer journey.

### 19 October — phone login, Twilio Verify and PR #5 merge

- Added phone-number login identifier support with profile email resolution and duplicate-registration conflict checks.
- Added Twilio Verify SMS OTP delivery via the provider's Verifications endpoint and verification via VerificationCheck; the application requires provider status approved and valid=true.
- Added tests for Verify configuration/phone formatting, send success and failures, approved verification, rejected codes, expiry and provider check failures.
- Preserved the existing custom FastAPI OTP challenge contract and frontend challenge binding. This is not the Supabase built-in phone OTP flow.
- Merged PR #5, “Harden auth, AI processing, and Cloud Run packaging,” to canonical main. Merge commit: 03c10f5d97bfdbf7560b95ee6be6e7cfb44e8165. Source branch commit: 5b671713d579a2bfb054317c1d36494c2c4b9852.
- PR #5 description reports 184 backend pytest passed (including 9 Twilio Verify tests), 32 frontend tests passed, frontend build passed, and lint with 0 errors / 13 warnings. It also records model-load/inference and diff checks. These are reported PR results; don't represent them as a fresh rerun unless the current checkout actually reruns them.
- In a clean worktree based on canonical main, the nine Twilio Verify tests were rerun and passed (9 passed, approximately 15 seconds). This is the independently rerun check recorded in this handoff.
- No CI status check was present in the prior combined commit-status lookup; do not claim GitHub CI passed for the merge commit unless a fresh workflow/status lookup confirms it.

## 5. Important branch/PR history and merge decisions

### Canonical vs original repo

- Canonical development/release repo: Abhiram-Mukkamala/Claimpilot.
- Original source/preservation repo: shreyasshah707/ClaimPilot. Its default branch was reported as claimpilot rather than main.
- A local checkout called ClaimPilot-Final previously had remote origin pointing to the original repository and an abhiram remote pointing to the canonical repository in some worktrees. Always inspect git remote -v and confirm the URL before fetch/push. Never push to the wrong origin.

### PR #5 — merged

https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5

Contains the security/auth/concurrency work, phone login and duplicate-registration checks, Twilio Verify, synchronous AI assessment option, Docker/cloud packaging and model assets. It is already merged; do not re-merge or rebase it.

### PR #4 — open draft, do not merge wholesale

https://github.com/Abhiram-Mukkamala/Claimpilot/pull/4

- Title: “Prepare ClaimPilot backend for Cloud Run”
- Branch: deploy/cloud-run
- Status at last verified point: draft/open and based on an older main.
- It contains Docker/runbook work, but the runbook references the wrong old Supabase URL and predates the final PR #5 implementation.
- Do not merge it wholesale. Port only reviewed deployment docs/config changes into a fresh branch off latest main; leave PR #4 open/untouched unless the user explicitly requests otherwise.

### Other branch cautions

- release/cloud-run-container-hardening was one merge commit behind main immediately after PR #5 merged; don't re-merge PR #5.
- release/predeploy-integration was previously measured as substantially diverged from main. Do not merge it wholesale.
- tests/model-evaluation-scores is intentionally separate for model evaluation/provenance. Don't mix model results into deployment code without the agreed structure.
- Branch lists change. Re-query GitHub before deciding a branch is active, stale, or safe to delete.

## 6. Supabase: current intended project and migration caution

The intended current Supabase project as recorded on 19 October is:

- Project reference: zegygoxpmnxpdhutdpqf
- URL: https://zegygoxpmnxpdhutdpqf.supabase.co
- Supabase region reported for this project: Sydney, ap-southeast-2.

The older project reference tiwdktgeqifhumcrwniv and URL https://tiwdktgeqifhumcrwniv.supabase.co appear in older migration notes and some configuration templates. Treat that as a **legacy/wrong target for the current release** unless the project owner explicitly states otherwise. The backend .env.example and the Cloud Run runbook on the separate deploy/cloud-run branch were reported stale and need correction. Check the current branch before assuming they are fixed.

Do not run schema.sql, migrations, seed_demo.sql, or arbitrary writes against a remote project without explicit approval. Verify migration history, RLS, bucket privacy, grants and expected tables in the target environment. Local SQL files do not prove a remote migration was applied.

Supabase design assumptions:
- Service-role key is backend-only; never expose it to Vite or the browser.
- Evidence bucket should remain private where required; use server authorization and scoped/short-lived signed URLs rather than public URLs as a workaround.
- Preserve OTP purpose/user binding and claim/evidence ownership checks.
- Seed data only when explicitly asked and after confirming the expected real agent identity; don't create fake customer/claim success to make the UI look populated.

## 7. Cloud Run / GCP state as of 19 October

### Cloud project and planned shape

- GCP project: claimpilot-512009
- Target region: asia-south1 (Mumbai), provisional
- Billing was reported enabled. A screen showed four monthly credit entries at ₹955.46 each, but eligibility/association to this project was not conclusively established. Check billing and remaining applicable credits before cost-bearing actions.
- APIs reported enabled: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Cloud Resource Manager and Cloud Billing.
- Artifact Registry repository named claimpilot was reported to exist in asia-south1; verify with describe if it matters.
- Runtime service account created: claimpilot-runtime@claimpilot-512009.iam.gserviceaccount.com
- No live Cloud Run service deployment was confirmed in the handoff. Do not assume the app has a public URL or deployed frontend.

### Old image — not a release image

Previously pushed image:

    asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1

Recorded digest:

    sha256:fdad2b67315e9e2f3ac373d3f95665d0ed715dad346de1efa215de15c9bea1d4

This image was built before the final merged Twilio Verify implementation. **Do not deploy it as the final image.** After source/config review, build and push a fresh commit-specific tag from the exact current canonical commit, record its digest, and deploy that image only after explicit authorization.

### Secret Manager status — names/containers do not prove versions exist

Containers were reported created for:

- claimpilot-supabase-anon-key
- claimpilot-supabase-service-role-key
- claimpilot-jwt-secret
- claimpilot-sendgrid-api-key

Secret accessor IAM was reportedly granted to the runtime account for these secrets. The actual enabled versions/value population was not confirmed in the last status. Check metadata/version existence only; never print secret payloads.

Twilio Verify secret names planned (creation and populated versions were not confirmed in the last report):

- claimpilot-twilio-account-sid
- claimpilot-twilio-auth-token
- claimpilot-twilio-verify-service-sid

Map these to TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID. The intended Verify flow does **not** require TWILIO_PHONE_NUMBER. The source retains a legacy Twilio Messages API fallback, but don't activate it unintentionally. A phone-number secret named claimpilot-twilio-phone-number was reported deleted; leave it absent for the Verify path unless the product owner deliberately chooses the legacy fallback.

### Email, CORS and sizing still need live verification

- Email OTP uses SendGrid; key population, verified sender and actual delivery were not confirmed.
- Set ENVIRONMENT=production.
- Set FRONTEND_URL and ALLOWED_ORIGINS to the actual deployed HTTPS frontend origin. Never use wildcard CORS with credentials.
- Map secrets through Secret Manager, not Dockerfile build args or committed .env files.
- OTP_DEV_FIXED_CODE and development-only fallback behavior must not be enabled in production.
- Proposed initial sizing: 1 vCPU, 4 GiB RAM, request-based billing, min instances 0, max instances 2, concurrency 1, timeout 300 seconds, port 8080. This is provisional; load-test real inference latency/memory and check cost first.

### Local Docker observations — useful but limited

The user/handoff reported successful local Docker checks on the **pre-merge** image/source:
- Container included best.pt (22,501,482 bytes); Ultralytics loaded it and synthetic-image inference completed.
- After fixing surrounding quotes in a local .env and recreating the container, GET /health returned HTTP 200.
- GET /health/ready returned HTTP 200 and reported database reachable/email OTP configured.
- A Supabase REST query from inside the container returned HTTP 200 and one row.
- These validate a local, pre-merge container path only. They do not prove SendGrid delivered mail, Twilio Verify works in the container, Cloud Run is live, or full customer-agent E2E passes.

## 8. Immediate outstanding work and release gates

**Always re-check whether these were completed after this guide's timestamp before starting.** The last handoff reported:

1. Correct the current release's backend .env.example to the intended Supabase URL and update the Cloud Run runbook on a fresh branch based on latest main. Avoid merging PR #4 wholesale.
2. Verify Secret Manager secret-version metadata for Supabase/JWT/SendGrid/Twilio Verify without displaying values; confirm the correct runtime IAM bindings.
3. Confirm SendGrid sender address and real email OTP delivery; verify real SMS delivery and VerificationCheck approval through Twilio Verify.
4. Build/push a new versioned backend image from exact canonical main, not old v1. Verify model weights and dynamic port behavior.
5. Deploy only when explicitly requested and when production env/CORS/secrets are ready.
6. After deployment, test /health and /health/ready, then the real full journey: customer login, claim creation, evidence upload/catalog registration, persisted AI assessment/fraud result where supported, agent review/decision, and customer status after refresh.
7. Run the relevant backend and frontend tests/build/lint on the exact final branch/commit, recording exact command and output. Do not infer live E2E from unit tests.

### Proposed Cloud Run E2E checklist

- Health endpoint passes.
- Readiness endpoint confirms database and required OTP delivery configuration.
- Real email OTP can be sent and verified; expired/rejected OTP is rejected.
- Real Twilio Verify SMS code is sent, then accepted only after provider says approved and valid.
- Customer can create a claim with required persisted fields.
- Evidence upload returns the canonical authorized storage path and evidence is registered.
- Inference uses the shipped checkpoint and persists actual results; errors leave an explicit flagged/unavailable state rather than fabricated success.
- Authorized agent can inspect and decide on a claim.
- Status/decision persists after full refresh and is visible to the right actor only.
- Test with approved and unapproved CORS origins and verify private evidence access.
- Confirm that no endpoint/response/log leaks credentials, OTP values, signed URLs, or internal exception details.

## 9. Local Windows workspace and preservation warnings

Known workspace paths in the historical handoff:

- Original checkout: C:\Projects\claimbot AI\ClaimPilot-Final
- Older release worktree: C:\Projects\claimbot AI\wt-release-canonical
- Clean canonical worktree: C:\Projects\claimbot AI\wt-canonical-main

The clean canonical worktree was created from canonical main at 03c10f5d97bfdbf7560b95ee6be6e7cfb44e8165 on branch local/canonical-main. Its Twilio Verify suite was rerun: 9 passed. The original checkout was later reported at the same merge SHA with a clean tracked/untracked status, but verify every local checkout before relying on this static fact.

Local preservation items reported in the original Windows workspace:
- stash@{0}: On test/e2e-demo-smoke: backup-local-changes-and-untracked-20261019
- C:\Projects\claimbot AI\ClaimPilot-Final-unstaged.patch
- C:\Projects\claimbot AI\backup_ClaimPilot_Final_untracked (includes SQL migration/seed and pre-security backup material)
- backup branches backup/local-test-e2e-demo-smoke and backup/old-local-main

Never pop/drop the stash, delete these backups, reset --hard, git clean, or overwrite local folders without explicit permission. Before modifying a checkout, inspect git status, remotes, branch, worktrees, stash list and recent log. Avoid using origin unless you have verified it points to the intended canonical repository. Prefer a new worktree from latest canonical main for isolated tasks.

## 10. Security and implementation rules

- Treat uploaded evidence, customer identities, OTPs, auth/session tokens, signed URLs and all environment data as sensitive.
- Do not log request authorization, passwords, OTPs, provider response bodies containing sensitive data, signed URLs or personal claim payloads.
- Use certificate verification for downloads. Don't introduce unverified TLS contexts or direct unscoped URLs that bypass private Supabase storage ownership checks.
- Sanitize API errors; do not return raw exception messages to customers.
- Preserve RBAC and per-resource ownership checks across claim, evidence, AI result and agent routes.
- Preserve challenge IDs, OTP purpose/user binding, expiry, attempt limits and resend rate limits. A session must not be created solely because the OTP-send endpoint succeeded.
- Keep the service-role credential backend-only.
- Use optimistic concurrency/claim-state validation when changing agent transitions. Reject stale decisions instead of overwriting fresh state.
- Keep migrations additive/versioned and explicit. Never assume local schema files reflect remote state.
- Clearly distinguish persisted model results, estimated values, missing values, and demo fallbacks in the UI.
- Keep evaluation scores on their provenance/evaluation track; don't invent metrics or claim inherited metrics were rerun.
- Do not claim AI-driven approval or money transfer. Agent decision and payout are different events.
- Do not ask the user to re-upload a whole set of files already available in the repo. Ask for only a specific missing file/log when it changes the answer materially.

## 11. Useful commands and validation

Run commands from the correct directory in PowerShell. Use dependency lockfiles and scripts from the checked-out branch.

Backend (from insurance-pro/backend):

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest -q
    uvicorn app.main:app --reload --port 8000

Twilio Verify focused test:

    python -m pytest tests/test_twilio_verify.py -q

Integrated frontend (from insurance-pro/frontend/ClaimPilot):

    npm ci
    npm run build
    npm run lint

If package.json defines a type-check script, run it too (or npx tsc --noEmit if that is the intended project command). Always inspect package scripts before assuming a script exists.

Before a commit:

    git status --short --branch
    git diff --check
    git diff --stat
    git diff

Report precise test output, warnings and the tested SHA. Passing unit tests are not a live-provider or end-to-end guarantee.

## 12. What a good handoff to the next agent must state

Every handoff must include:

- Canonical repo, branch, exact HEAD SHA, and working-tree status.
- The specific goal and scope of the task.
- Files changed and the reasoning for non-obvious decisions.
- Exact commands run and actual results (distinguish prior reported results from tests rerun now).
- Live integrations verified versus only locally mocked.
- Current PR URL/state and whether anything was deployed or written to Supabase/GCP.
- Remaining blockers, next one or two actions, and the relevant preservation warnings.

**Current-source rule:** this history was assembled from the canonical GitHub commit history, repo docs, merged PR #5 description and the 19 October handoff. It is intentionally explicit about provenance and uncertainty. Re-check current source, branches, PRs, secret metadata and deployed resources before acting.
