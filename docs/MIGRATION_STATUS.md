# ClaimPilot AI — Migration Status

**Status: MIGRATED SNAPSHOT + SELECTED UI PORT — VALIDATION AND REMAINING FEATURE PORTING STILL REQUIRED**

Destination: https://github.com/Abhiram-Mukkamala/Claimpilot (private)

## Snapshot source

- Code and documentation snapshot: `test/e2e-demo-smoke` at `265c3934674a0070d7314af064d4a62a1acd3fe0`.
- The current `claimpilot` branch had one unique commit in the comparison, changing only `README.md`; the current `claimpilot` README is used in this repository.
- The original repository and all source branches remain unchanged: https://github.com/shreyasshah707/ClaimPilot
- This is a single-branch snapshot, **not** a full Git-history mirror. Source commits, tags and all source branches were not copied into `main`; the original repository remains the history/backup reference.
- The destination also contains the separate `claimpilotayaan` branch at commit `f47c5b67ccaaad751cc408b48fb7417529d7fca2`. Its About/onboarding UI was selectively ported into `main`; the branch itself remains unchanged and should be kept until remaining unique work is reviewed.

## Included in main

- 206 text/source/documentation file paths from the selected E2E branch.
- The newer README from current `claimpilot`.
- Both original `hero.png` assets, byte-for-byte restored from the source branch; source and destination blob SHA matches.
- Both model weights: `rt-detr.pt` and `yolov11m.pt`. The migration API could not return their binary content, but the same exact Git blob objects were already present in the destination's `claimpilotayaan` branch and were referenced into `main`.
- `docs/BRANCH_CONSOLIDATION.md`, tracking remaining feature work.
- Selected Ayaan UI in commit `5724e85085ea3f981a6fed9382e347786b9f8997`: About page + CSS, onboarding modal/steps/CSS/state store, and CustomerLayout onboarding wiring. Review follow-up fixes: `12f8c78f7dd9143ca2fb53f05ced60f22d55379c` corrects per-user onboarding completion persistence; `a0fbc909ae9fb275f0bd1ca1366d27a2246cc4de` fixes the About page team-section anchor; `e9f4bea8cbe8eb5ae817c08b5e1dd5f770b84e58` adds keyboard focus containment and background-scroll locking to onboarding; `c9307de4a9869765596b8cbe1402d5c44603b5c5` corrects the step-jump controls' accessibility semantics.
- Only `.env.example` templates; no real `.env` file was migrated.

## Automated regression result (17 October 2026)

GitHub Actions run for the integrated backend/schema regression suite completed successfully: **146 passed, 10 warnings in 2.71 seconds**. The run used dummy Supabase credentials and mocked test dependencies; it did not create or modify demo data in the live Supabase project. Warnings are FastAPI/Starlette/httpx deprecations and are non-failing. The workflow actions were upgraded to `actions/checkout@v7` and `actions/setup-python@v7` for Node 24 compatibility; the follow-up run also passed 146 tests.

## Local security work not included

Previously reported uncommitted Phase 1 security changes in local worktrees `C:\Projects\claimbot AI\wt-impl-phase1` and `ClaimPilot-Final` were not present as remote commits in the inspected source tree. Those modifications were not copied into this migration. Review and apply them deliberately from the local worktree; preserve staged/unstaged work and backups. Do not replace files wholesale without comparing the patch.

## Release-prep port review (17 October 2026)

### Backend cost-estimator port

The useful part of `backend/cost-estimator` is now staged for release: `app/services/cost_estimator.py`, `app/data/cost_table.json`, estimator settings, unit tests, and geometry metadata emitted from the existing inference path. This was **not a wholesale branch merge**. The source branch replaces private-storage downloads with direct URL fetching and creates an unverified TLS context, while dropping the existing canonical evidence-path/owner checks. Those changes were explicitly excluded. The release version continues downloading evidence through the backend's private Supabase storage client and persists only public response fields (no temporary `_estimator_*` geometry keys).

A versioned migration adds `claim_ai_analysis.estimate_basis`; the same additive column was applied to the connected Supabase project. The frontend maps and displays the estimate basis with a clear uncalibrated/indicative disclaimer. The seeded INR table is **not insurer-calibrated** and its figures must not be described as final payouts.

### Feature branches reviewed, not copied blindly

- `frontend/new-claim`: its current delta discards the real `file_path` returned by `storageApi.uploadFile` and fabricates `storage_path` using the claim ID. The backend's evidence-path authorization expects the canonical user-owned path, so this change risks cataloging evidence under the wrong owner and stopping AI analysis. The existing canonical `NewClaim.tsx` remains in use.
- `frontend/agent-review`: its current delta changes the update call from `claim.backendId || claim.id` to `claim.id`. The canonical backend claim UUID must be preferred. It also weakens the score type guard for no material UI benefit. The existing canonical `AgentClaimDetails.tsx` remains in use.
- `frontend/login` / `frontend/login3` and the login changes in `ayaan/claimpilot`: not copied wholesale. The Ayaan variant drops the required OTP challenge ID, removes the six-digit validation and useful dispatch/resend error handling. Those are incompatible with the current challenge-bound backend.
- `ui/onboarding-about`: its alternate full-branch CSS/layout variant was not overlaid on top of the selected Ayaan onboarding design. This avoids replacing the already-integrated layout/state wiring with a competing variant.

### Ayaan connected UI migration status

The **core About/onboarding design is already integrated on the original new `main`** and therefore is inherited by this release branch: About page styling, onboarding steps/modal, onboarding state/storage, first-time onboarding behavior, and manual entry from the customer layout. The integration deliberately keeps the behavior wired through `CustomerLayout` rather than rendering a second modal from `CustomerDashboard`. The About page accepts the current route/API contract, retains the existing not-found route and full page metadata, and includes the fixed team-section anchor. Not every Ayaan branch file is byte-identical: login, dashboard status presentation, route wrapper and index metadata were reviewed individually; only compatible behavior was carried over.

### Evaluation branch organization

The separate branch `tests/model-evaluation-scores` holds the imported photo/video/3D pipeline under `model-evaluation/`, a test plan, and an evaluation-score provenance page. The listed mAP metrics are inherited from the old `models` branch README and were not rerun. Existing release-critical backend regression tests remain on the deployment branch so CI can validate the product code; model-evaluation scripts/results stay isolated from the deploy copy.


## Other branch work not yet integrated

The remaining branch-specific changes listed in `docs/BRANCH_CONSOLIDATION.md` remain in the original repo (and the separate destination branch noted above where applicable) and have not been silently merged. The UI commit intentionally did not replace Login, claims API/auth store, claim submission, agent actions, or backend integrations.

## Validation status

- Destination `main` contains the selected release-candidate tree, latest README and migration documentation, plus the selected About/onboarding UI port.
- Source-file blob hashes were checked when copying text blobs; both PNG assets and both model-weight blob hashes match the source objects.
- **Tests/build were not run as part of this migration.**
- Other feature-branch work and the separate local security changes still need review. Do not declare the release ready until those items are resolved and the end-to-end workflow passes.


## Supabase integration (17 October 2026)

The connected Supabase project `tiwdktgeqifhumcrwniv` (Mumbai region, `ap-south-1`) now has the versioned ClaimPilot schema applied. Remote migration history was verified against the files in `supabase/migrations/`:

- `20261016194212_claimpilot_core_schema.sql` — profiles, OTPs, claims, evidence, AI analysis, fraud analysis, policy mappings, enums, indexes, RLS, service-role privileges, and the private `claim-evidence` bucket.
- `20261016194327_claim_settlement_offer_compat.sql` — compatibility column used by the current agent approval handler.
- `20261016195154_claimpilot_fk_indexes.sql` — indexes for OTP-user and policy-agent foreign keys.

Live verification confirms all eight ClaimPilot tables exist, RLS is enabled, and `anon`/`authenticated` have no table grants on ClaimPilot tables or the starter `public.tasks` table. The `claim-evidence` bucket is private, has a 50 MB limit, and permits the configured image/video MIME types. No test customer, agent, claim, evidence, or policy data has been seeded into Supabase.

### Regression tests in the destination repository

The destination includes the existing authorization claim-flow, deterministic demo smoke, smoke-runner, AI-runner, sensitive-logging, JWT/security-hardening, and backend security-regression suites. OTP tests were expanded to assert stored purpose/user binding and reject mismatched bindings; the smoke OTP fixture was aligned with those fields. `test_supabase_schema_contract.py` checks the versioned schema, RLS/client grants, private bucket, settlement compatibility, and foreign-key indexes. The repository contains 106 test functions across the eight inventoried suites; parametrized cases produce 146 collected pytest cases.

**Execution status:** The live schema is verified, and the backend/schema regression suite passed twice in GitHub Actions (146 passed, 10 warnings; latest run used Node 24-compatible actions). CI uses dummy credentials and mocked dependencies, so it did not touch live claim/user data. Remaining operational steps: configure real backend environment variables without committing secrets, verify Supabase Auth email/SMS delivery, register an actual demo agent and customer, run the safe demo-policy seed with the real agent email, then exercise signed evidence upload/read and the hosted end-to-end claim journey. Frontend TypeScript/production build remains to be run.
