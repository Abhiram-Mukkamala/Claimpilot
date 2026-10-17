# ClaimPilot — Handoff for Next Chat Iteration

**Prepared:** 17 October 2026 (Asia/Kolkata)  
**Urgent milestone:** build and deploy a copy tomorrow, 18 October 2026.  
**Project dates:** code freeze 20 October; finale 24 October.  
**Purpose:** Continue from the current state without repeating repository discovery or claiming unverified integration.

## 1. Repositories and verified heads

### Use this repository going forward
- Repo: https://github.com/Abhiram-Mukkamala/Claimpilot
- Private; default branch: `main`.
- Last verified `main` head: `2057129fdca7f3d830b4564490dfc0d4c6e6b902`.
- Head message: `fix(db): align cost estimate migration with applied Supabase version`.
- Last verified tracked file count: 225.

### Original source repository — reference only
- Repo: https://github.com/shreyasshah707/ClaimPilot
- Current default branch is `claimpilot`, not `main`.
- Last verified default head: `7afc541910fa115b4e95132dc3e067c72cf2690f`.
- Last verified tracked file count: 205.
- All 205 source-default file paths exist on destination `main`; destination had 20 additional file paths. Shared-file content differs for some intentionally adapted files.
- The repos are snapshot-based and do not have fully mirrored histories. Do not assume a wholesale merge of old branches will work.
- Original repo was not modified; don't write to it unless the user explicitly asks.

### Ayaan branch
- Original `ayaan/claimpilot`: `f47c5b67ccaaad751cc408b48fb7417529d7fca2`.
- Destination has `claimpilotayaan` at the same SHA.
- The selected About/onboarding implementation is in new `main`, but **not all Ayaan branch changes were migrated**.

## 2. Supabase state (verified)

Project ID `tiwdktgeqifhumcrwniv`, region `ap-south-1` (Mumbai).

Remote migration history lists:
1. `20261016194212_claimpilot_core_schema`
2. `20261016194327_claim_settlement_offer_compat`
3. `20261016195154_claimpilot_fk_indexes`
4. `20261016203544_cost_estimate_basis`

Verified earlier:
- Eight ClaimPilot tables exist: `profiles`, `otp_verifications`, `claims`, `claim_evidence`, `claim_ai_analysis`, `claim_fraud_analyses`, `agent_policies`, `policies`.
- RLS enabled on all eight. No direct table grants to `anon` or `authenticated`; use the service-role key only on the backend.
- Private `claim-evidence` bucket, 50 MiB limit, intended image/video MIME allow-list.
- Starter `public.tasks` preserved but broad client Data API grants revoked. Execute grants on `public.rls_auto_enable()` revoked.
- No demo agent, customer, policies, claims or evidence have been seeded.
- `insurance-pro/backend/seed_demo.sql` is revised to avoid broad `USING (true)` client policies and requires a real registered agent before policy seeding. Do not run until a real demo agent exists and its email replaces the placeholder.

## 3. Completed integration

### Backend/schema/auth
- Canonical backend: `insurance-pro/backend/`.
- OTP creation/verification persists and validates `purpose` and `user_id`; regressions cover wrong purpose/user.
- `ClaimStatus` Pydantic enum includes `manual_review`.
- Versioned schema, settlement compatibility, FK indexes, cost-estimate basis migration and private storage bucket are present.
- No live demo rows inserted.

### Cost estimator — files now on destination `main`
Ported from original branch `backend/cost-estimator`:
- `insurance-pro/backend/app/services/cost_estimator.py`
- `insurance-pro/backend/app/data/cost_table.json`
- `insurance-pro/backend/tests/test_cost_estimator.py`

The destination already has integration hooks in `app/core/config.py` (`COST_ESTIMATOR_*` settings) and `app/services/ai_runner.py` (imports/calls `estimate_damage_costs`). Cost-estimator test file contains six test functions.

**Critical warning:** Do not overwrite current destination `ai_runner.py` with the old cost branch version. The feature branch has an unverified TLS/SSL context and downloads raw signed URLs; destination uses the safer storage backend helper/canonical evidence path. Port only needed behavior, not the branch file wholesale.

**Must validate now:** Re-run CI after estimator and cost migration changes. Check Pydantic/API/UI/DB field contracts and ensure cost estimates are clearly marked indicative/uncalibrated, not insurer-calibrated. Confirm current migration history before applying any new SQL.

### Regression testing / CI
- Backend suites under `insurance-pro/backend/tests/`: authorization/claim flow, deterministic smoke, smoke runner, AI, auth-sensitive logging, security/JWT hardening, fraud analysis, config startup, backend security regressions, and schema-contract tests.
- Added `test_demo_smoke_suite.py`, `test_smoke_runner_regressions.py`, `test_supabase_schema_contract.py`.
- CI workflow: `.github/workflows/backend-tests.yml` with dummy creds/mocked dependencies.
- A previous run passed **146 tests with 10 warnings**, but it preceded the latest cost-estimator port. **Do not claim current HEAD is green until CI is rerun.**

## 4. Ayaan UI status — not fully migrated

Earlier base UI port commit: `5724e85085ea3f981a6fed9382e347786b9f8997`, followed by fixes for onboarding persistence, About navigation, and keyboard/focus accessibility. Port preserves current API/auth integration rather than wholesale copying Ayaan's branch.

Selected UI files on `main`:
- `insurance-pro/frontend/ClaimPilot/src/pages/About.tsx`
- `insurance-pro/frontend/ClaimPilot/src/pages/about.css`
- `insurance-pro/frontend/ClaimPilot/src/components/onboarding/ClaimPilotOnboarding.tsx`
- `insurance-pro/frontend/ClaimPilot/src/components/onboarding/OnboardingStep.tsx`
- `insurance-pro/frontend/ClaimPilot/src/components/onboarding/onboarding.css`
- `insurance-pro/frontend/ClaimPilot/src/components/onboarding/onboardingSteps.ts`
- `insurance-pro/frontend/ClaimPilot/src/store/onboardingStore.ts`
- `insurance-pro/frontend/ClaimPilot/src/components/layout/CustomerLayout.tsx`

Fixes made:
- Per-user onboarding completion persists against normalized user ID/email and checks the actual auth storage location.
- About “Who are We” menu maps to the real section ID.
- Dialog contains keyboard focus, restores focus, locks background scroll, and uses corrected step-navigation semantics.

Not ported wholesale: Ayaan branch's changed versions of connected Login, CustomerDashboard, AppRoutes, authStore, claimsApi, analysis API/types, global CSS, TopBar/DamageViewer, package manifests and other files. Some are deliberately adapted and others remain original. Answer to “is all Ayaan UI migrated?” is **no; only selected About/onboarding UI is ported**.

The frontend TypeScript check, production build and live app have **not** been verified on the latest destination head.

## 5. Relevant branch status

- `backend/cost-estimator`: service, cost table and tests ported. Re-run test suite; do not copy its old insecure raw-URL/TLS code.
- `frontend/agent-review`: **not ported**. Canonical `AgentClaimDetails.tsx` differs; branch also adds `docs/UI_PORT_ANALYSIS.md`.
- `frontend/new-claim`: **not ported**. Canonical customer `NewClaim.tsx` differs.
- `frontend/login` and `frontend/login3`: same root-prototype `src/pages/Login.tsx` variant. Don't merge both. Decide whether any useful behavior belongs in canonical `insurance-pro/frontend/ClaimPilot/src/pages/Login.tsx`; root `src/` is a prototype.
- `ui/onboarding-about`: partially ported, as above; don't merge wholesale.
- `tests/smoke-seed`: every file path exists in destination `main`; no commits ahead of original default. Current seed/smoke files evolved deliberately.
- `tests/model-eval`: every file path exists in destination `main`; no commits ahead of original default. This is an older snapshot, not a missing independent feature set.
- `test/e2e-demo-smoke`: docs, pytest config, smoke runner, demo smoke suite and smoke-runner regression tests present in destination. OTP fixtures were updated to purpose/user binding.
- `backend/fraud-port`, `fix/settlement-truthfulness`: no branch-only commits ahead of original default; relevant current behavior/tests/migrations represented in baseline.
- `models`: independent ML pipeline, no common history. Not yet imported as a complete pipeline. Contains frame extraction, depth/dense stereo, segmentation, photo/video pipeline, surface normals, scale calibration, inference, mesh reconstruction/measurement and dependencies/docs.
- `insurance-pro`: separate parallel app tree/no common ancestor; don't merge wholesale.
- `sutar`: alternative Node backend; don't mix into canonical FastAPI backend.

## 6. Minimal branch policy

Keep only two long-lived work branches:
1. **`main`** — deployable app, connected React frontend, FastAPI backend, Supabase migrations, and release-gating tests under `insurance-pro/backend/tests/`.
2. **`eval/model-evaluation`** — create from current `main` for model-evaluation cases, score outputs, benchmark metadata/provenance and standalone ML experiments/scripts (e.g. under `ml/` or `evaluation/`). Do not put unverified score results into the deployment app.

This branch **does not exist yet**. Create just this one branch for evaluation rather than one branch per old test branch. Keep backend regression tests on `main` to gate release code; keep model benchmark cases/results/scores on the evaluation branch. Do not present the old model README's mAP numbers as newly rerun results—score provenance and reproducibility need to be recorded.

## 7. Immediate next actions for 18 October deployment

1. Recheck live `main` and branch heads; last verified `main` SHA was `2057129fdca7f3d830b4564490dfc0d4c6e6b902`.
2. Re-run backend CI after estimator changes. Fix failures, verify cost estimator response/migration contracts.
3. Port `frontend/new-claim` and `frontend/agent-review` selectively into canonical frontend. Review diffs, preserve auth/API integration, add/update tests; do not merge stale snapshots wholesale.
4. Review the rest of Ayaan's connected UI changes (login/dashboard/routes/API/types) and port useful parts that are needed for the build, keeping current contracts. Run frontend typecheck and production build.
5. Create one `eval/model-evaluation` branch and port suitable `models` scripts/cases/scores there; include score provenance (dataset/split, checkpoint, run command, date, hardware, metrics). Do not let the entire optional ML pipeline migration block main app deployment.
6. Configure runtime secrets only in the deployment provider/local env, never git: Supabase URL, service-role key backend-only, independent JWT secret, frontend API base URL, CORS/origin configuration, email/SMS credentials. Never expose service-role key through Vite.
7. Register a real demo agent/customer; run safe policy seeding using that agent's actual email. Test signed evidence upload/read, claim creation, AI/fraud analysis, agent decision, customer accept/dispute and persistence.
8. Only claim deploy readiness after frontend production build and hosted E2E pass. Do not confuse mocked backend CI with live end-to-end validation.

## 8. Safety rules

- Work in `Abhiram-Mukkamala/Claimpilot`; original repo is reference-only unless explicitly asked.
- Don't print/commit secrets; service-role key must never be in frontend variables.
- Don't run legacy `schema.sql`, `migration_v2.sql`, `migration_v3_phash.sql` over the live project; versioned migrations are already applied.
- Don't seed fake user/claim records.
- Don't replace storage-backed secure `ai_runner.py` with old branch code using unverified TLS/raw URL downloads.
- Don't wholesale merge all branches or alternate Node backend.
- Don't delete old branches as part of consolidation.

## 9. Links

- New deploy repo: https://github.com/Abhiram-Mukkamala/Claimpilot
- New main: https://github.com/Abhiram-Mukkamala/Claimpilot/tree/main
- Branch/migration notes: https://github.com/Abhiram-Mukkamala/Claimpilot/blob/main/docs/BRANCH_CONSOLIDATION.md
- Migration status: https://github.com/Abhiram-Mukkamala/Claimpilot/blob/main/docs/MIGRATION_STATUS.md
- Supabase guide: https://github.com/Abhiram-Mukkamala/Claimpilot/blob/main/docs/SUPABASE_SETUP_GUIDE.md
- Backend CI: https://github.com/Abhiram-Mukkamala/Claimpilot/blob/main/.github/workflows/backend-tests.yml
- Original source default: https://github.com/shreyasshah707/ClaimPilot/tree/claimpilot
- Ayaan source: https://github.com/shreyasshah707/ClaimPilot/tree/ayaan/claimpilot
- Cost estimator: https://github.com/shreyasshah707/ClaimPilot/tree/backend/cost-estimator
- Agent review: https://github.com/shreyasshah707/ClaimPilot/tree/frontend/agent-review
- New claim: https://github.com/shreyasshah707/ClaimPilot/tree/frontend/new-claim
- E2E smoke: https://github.com/shreyasshah707/ClaimPilot/tree/test/e2e-demo-smoke
- Model pipeline: https://github.com/shreyasshah707/ClaimPilot/tree/models
