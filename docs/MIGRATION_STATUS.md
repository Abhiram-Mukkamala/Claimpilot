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

## Local security work not included

Previously reported uncommitted Phase 1 security changes in local worktrees `C:\Projects\claimbot AI\wt-impl-phase1` and `ClaimPilot-Final` were not present as remote commits in the inspected source tree. Those modifications were not copied into this migration. Review and apply them deliberately from the local worktree; preserve staged/unstaged work and backups. Do not replace files wholesale without comparing the patch.

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

The destination includes the existing authorization claim-flow, deterministic demo smoke, smoke-runner, AI-runner, sensitive-logging, JWT/security-hardening, and backend security-regression suites. OTP tests were expanded to assert stored purpose/user binding and reject mismatched bindings; the smoke OTP fixture was aligned with those fields. `test_supabase_schema_contract.py` checks the versioned schema, RLS/client grants, private bucket, settlement compatibility, and foreign-key indexes. The repository currently contains 106 test functions across these eight suites.

**Execution status:** The live schema has been queried and verified, but the Python test suite has not yet been run against a local checkout and no CI results are available. Do not treat this as a passing build. The remaining operational steps are to configure real backend environment variables without committing secrets, register an actual demo agent and customer, run the safe demo-policy seed using the real agent email, then run the backend suite and hosted end-to-end smoke test.
