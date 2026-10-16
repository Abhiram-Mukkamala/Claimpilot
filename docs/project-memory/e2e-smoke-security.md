# ClaimPilot Project Memory — E2E Smoke & OTP Safety

**Prepared:** 2026-10-15 (Asia/Kolkata)  
**Scope:** End-to-end smoke runner safety, OTP-login verification, and integration readiness.  
**Source brief:** `PROJECT_BRIEF.md` and `CURRENT_STATUS_AND_DECISIONS.md` supplied in the shared project context. The status brief is explicitly a 14 October snapshot, not live state.

## 1. Current status and repository identity

### Remote repository facts verified during this review

- Repository: [`shreyasshah707/ClaimPilot`](https://github.com/shreyasshah707/ClaimPilot).
- Relevant remote branch: [`test/e2e-demo-smoke`](https://github.com/shreyasshah707/ClaimPilot/tree/test/e2e-demo-smoke).
- Verified branch HEAD: [`a83e197d3ce7c76460e2404172ccb749b507c510`](https://github.com/shreyasshah707/ClaimPilot/commit/a83e197d3ce7c76460e2404172ccb749b507c510), `fix(smoke): harden target guard and persisted-state checks`.
- Base branch `claimpilot` resolves to `164c29cc1425e7c697d1c34235f5d159d12b64b6` (`docs(security): clarify private evidence bucket setup`).
- GitHub compare says `test/e2e-demo-smoke` is **8 commits ahead, 0 behind** `claimpilot`, with the same merge base as `claimpilot` HEAD.
- The compare contains **39 changed paths**, including smoke runner/tests/docs, backend authorization/claim changes, and substantial connected-frontend changes. This is not a smoke-tests-only branch. Review the exact compare before integration: [compare](https://github.com/shreyasshah707/ClaimPilot/compare/claimpilot...test/e2e-demo-smoke).
- GitHub combined commit statuses returned no status entries for `a83e197...`; the workflow-run query returned no workflow runs. This is **not evidence of CI passing**.
- The remote branch did not contain `docs/project-memory/e2e-smoke-security.md` when checked. This memory artifact is being created outside the checkout available to this session, so no repository commit is being made.

### Local worktree state — not verifiable from this session

The project brief names the main checkout as `C:\Projects\claimbot AI\ClaimPilot-Final` and lists several separate worktrees. It does **not** identify the local worktree path for `test/e2e-demo-smoke`. The session filesystem contains the supplied project-context files but no ClaimPilot Git checkout. Therefore I could not verify local `git status`, local branch, local HEAD, staged/unstaged/untracked files, or whether the local branch matches the remote HEAD.

**Do not infer a clean worktree.** Preserve all local work. Before any implementation/integration, obtain a read-only status report from the exact smoke worktree and compare its HEAD with `a83e197...`.

## 2. Important files and observed behavior

All code observations below refer to the remotely fetched `test/e2e-demo-smoke` branch at HEAD `a83e197...`, not an inspected local checkout.

### `insurance-pro/backend/smoke_test.py`

- Requires explicit `CLAIMPILOT_SMOKE_TESTS=1` opt-in before live test execution.
- Reads the target from `SMOKE_BASE_URL`; permits localhost/loopback and explicitly allowlisted remote hosts, requires HTTPS for remote targets, and checks storage upload URLs against an allowlist.
- Configures `httpx.Client(..., follow_redirects=False)` to prevent automatic redirect following.
- Redacts credentials, tokens, OTPs, challenge IDs, and URLs from output in common structured/text cases.
- Login requires a successful password-login response with `requires_otp is True`, a non-empty challenge ID, and an OTP verification call.
- **Confirmed remaining defect:** after OTP verification, it rejects only when `v_data.get("is_verified") is False`. It then accepts any non-empty string `access_token`. Thus `is_verified` missing, `null`, or a non-boolean value can pass if the response includes a token. The check must require the literal boolean `True`.
- The runner includes checks for claim/policy assignment, evidence upload, analysis state, agent action, and customer settlement outcome. The runner is a test client, not proof that a live deployment succeeds.
- Potential hardening follow-ups: production-host detection uses a broad substring check and may reject unrelated hostnames; URL validation does not visibly validate every netloc/port/userinfo edge case. These are review items, not verified exploit findings.

### `insurance-pro/backend/tests/test_smoke_runner_regressions.py`

- Contains tests for allowed/rejected target URLs, redirects configuration, OTP challenge flow, `requires_otp` failure, explicit `is_verified=False`, invalid/missing access tokens, and output redaction.
- **Coverage gap confirmed:** it has a test for `is_verified=False`, but no test for `is_verified` missing, `null`, string, integer, or other non-boolean values paired with a valid token.

### `insurance-pro/backend/tests/test_demo_smoke_suite.py`

- Deterministic in-process tests use mocked/in-memory external boundaries rather than a live Supabase project.
- Exercises safe AI failure/manual-review behavior and agent/customer claim flow branches, according to the test source and smoke guide.
- Passing this suite cannot establish real storage permissions, real OTP delivery, live model-weight availability, or deployed database correctness.

### `docs/SMOKE_TESTING.md`

- Documents the two-layer strategy: deterministic in-process tests and an explicitly opted-in live integration runner.
- The guide states the evidence bucket should be private and documents environment-variable *names* only. Never place values, credentials, signed URLs, or `.env` content in project memory.
- It records test results listed below, but those results were not independently reproduced in this session.

### Additional paths in the branch compare

The branch also changes backend `app/api/v1/agent.py`, `claims.py`, `app/schemas/claim.py`, and `tests/test_authorization_claim_flow.py`; and multiple connected-frontend files, including claim/analysis services, login, claim creation/analysis pages, routes, onboarding, and a settlement-decision test. These need ownership/dependency review before integration. Do not assume these changes are all part of the smoke-test task or safe to merge as one unit.

## 3. Verified facts vs. reports and unknowns

### Verified directly in this review

- Remote branch HEAD and base HEAD as listed above.
- Remote compare is 8 commits ahead / 0 behind, and the changed-file list is much broader than the smoke runner.
- Current remote smoke-runner code accepts a token when `is_verified` is absent/null/non-boolean because it only rejects the literal `False`.
- The current regression test file covers `False` but does not cover missing/null/non-boolean `is_verified` values.
- No GitHub combined status entries or workflow runs were returned for `a83e197...`.
- No local ClaimPilot checkout was available to inspect in this session; local worktree cleanliness is unknown.

### Reported in checked-in documentation / prior handoff, not independently rerun

The smoke guide at this branch records these local test results:

| Command / suite | Reported result | Verification status here |
|---|---:|---|
| `pytest tests/test_smoke_runner_regressions.py` | 42 passed | Not rerun; documentation claim only |
| `pytest tests/test_demo_smoke_suite.py` | 20 passed | Not rerun; documentation claim only |
| `pytest tests/` | 140 passed, 9 warnings | Not rerun; documentation claim only |
| `npm test` in connected frontend | 25 passed | Not rerun; documentation claim only |
| `npm run lint` | 0 errors, 15 warnings | Not rerun; documentation claim only |
| `npm run build` | successful, reported 1.88s | Not rerun; documentation claim only |
| `git diff --check` | clean | Not rerun; local worktree not accessible |
| Live `python smoke_test.py` against Supabase/staging | Not run | Explicitly unverified |

No tests were run during this memory task. Static remote-source inspection is not a test run.

## 4. Blockers and dependencies

### P0 — OTP smoke login does not require explicit verification success

**Evidence:** `smoke_test.py` checks `is_verified is False` rather than `is_verified is True`; the regression suite lacks tests for missing/null/non-boolean values.  
**Risk:** a malformed or contract-regressed OTP response with a token may be treated as verified.  
**Closure evidence:** make the verification acceptance condition require literal `True`; add regression cases for `True` succeeds and `False`, missing, `null`, string, integer, and other non-boolean values fail even when a non-empty token is present. Retain missing/empty/non-string token failures and redaction tests. Run the focused regression suite and full backend suite; provide exact command, exit code, and counts.

### P1 — Live end-to-end behavior is not proven

**Evidence:** the guide explicitly says the deterministic suite uses in-memory fakes; live smoke was not run; no GitHub Actions runs/statuses were found.  
**Dependencies:** Supabase/deployment workstream (private bucket, schema/migrations, policy seed/RLS, service-role storage operations), authentication/OTP delivery configuration, and ML inference/weights availability.  
**Closure evidence:** after P0 and integration review, run the opt-in smoke test only against a dedicated local/staging target with approved test accounts and storage hosts. Record stage-by-stage PASS/FAIL/BLOCKED/NOT RUN, verify persisted database state through an authorized read-only inspection, and confirm no real payout was initiated or claimed. Do not run against production or alter the database without explicit approval.

### P1 — Branch scope is too broad for blind integration

**Evidence:** compare shows 39 changed paths across smoke, backend behavior, and connected frontend, with 8 commits unique to the branch.  
**Risk:** unrelated feature work and integration dependencies could be unintentionally bundled into the security/smoke change.  
**Closure evidence:** enumerate all eight commits with SHA/subject and changed paths; classify smoke-only vs backend feature vs frontend feature; map overlapping worktrees and dependencies; have the manager approve a smallest-safe integration plan. No merge/cherry-pick is authorized by this memory task.

### P1 — Private evidence storage and deployed schema remain unverified

**Evidence:** project status notes identify storage URLs, migration/schema, policy mapping, and RLS as items needing runtime verification; the smoke guide says the bucket should be private. No live Supabase verification was performed here.  
**Dependencies:** Supabase/deployment and backend API workstreams.  
**Closure evidence:** authorized, non-secret configuration checklist plus read-only verification of bucket privacy, required migrations/tables/columns, policy-to-agent mapping, signed upload, evidence catalog ownership, and backend-only evidence retrieval. Do not expose signed URLs or execute database writes during verification.

### P2 — URL guard and redirect regression depth

**Evidence:** remote source uses substring matching for prohibited hostnames and tests the HTTP client's `follow_redirects=False` setting; the available evidence does not establish behavior for every malformed authority, unusual port, userinfo, DNS/IP, or redirect response case.  
**Closure evidence:** add focused URL parser tests for ambiguous/malformed URLs and a mock redirect response; verify no redirected request is sent. Review hostname matching to avoid unsafe bypasses and unnecessary false positives. Keep the allowlist fail-closed.

### P2 — Claim outcome checks may need stricter persisted-state assertions

**Evidence:** prior review of the runner found that the customer reload path accepts missing payout status as well as `not_started`, and does not reassert every payout metadata field from the reloaded claim. Reconfirm these checks against the current exact lines before changing them.  
**Closure evidence:** tests should require the persisted outcome to explicitly state `payout_status == "not_started"`, with `batch_id` and disbursement channel null, and `settlement_accepted` persisted for the customer view. Never represent a payout as started without an actual provider integration.

## 5. Next recommended action

1. **First obtain local state without modifying it.** In the exact local worktree that owns `test/e2e-demo-smoke`, capture `git status --short --branch`, `git rev-parse HEAD`, `git branch --show-current`, and `git diff --check`. Do not switch branches or clean files. Confirm whether HEAD is `a83e197...` and list all untracked files without printing secrets.
2. **Fix only the P0 OTP predicate and its regression tests** in the designated smoke worktree after reviewing/preserving its existing changes. Stage only the intended files if/when separately authorized. This memory task itself made no application-code changes and did not stage or commit anything.
3. Run the focused regression suite, `pytest tests/test_demo_smoke_suite.py`, then the full backend suite; record fresh exact outputs. Verify redaction canaries do not leak.
4. Review the eight-commit/39-path branch scope and dependencies before any integration. Do not merge the branch wholesale by default.
5. Once security, frontend contract, Supabase/storage, and ML prerequisites are ready, run the opt-in smoke flow against dedicated local/staging infrastructure and preserve sanitized stage evidence.

## 6. Change-control boundary for this memory task

No application code was edited. No files were staged or committed. Nothing was pushed, merged, reset, or deleted. No database was accessed or modified. No `.env` values, credentials, tokens, or signed URLs were read or included. The Markdown artifact was saved at the session-visible path `docs/project-memory/e2e-smoke-security.md` under `/mnt/data`; it is **not yet written into the ClaimPilot Git checkout** because that checkout is unavailable in this session and repository writes are explicitly out of scope.
