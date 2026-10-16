# ClaimPilot AI — End-to-End Demo Smoke Testing Guide

**Target:** MIT India Hackathon 2026 — ClaimPilot AI<br>
**Internal Code Freeze:** October 20, 2026<br>
**Demo Finale:** October 24, 2026

---

## 1. Overview & Architecture

ClaimPilot AI employs a two-tier testing strategy to guarantee truthfulness, security, tenant isolation, and deterministic reliability:

1. **Deterministic In-Process Test Suite (`tests/test_demo_smoke_suite.py`):**
   - Fast, repeatable, and completely isolated test suite running under `pytest` with FastAPI's `TestClient`.
   - Simulates database and storage boundaries in-memory without network dependencies or live cloud resources.
   - Fully exercises Stages A through G, verifying status codes, schema validation, state machines, and negative error branches.
2. **Opt-in Live Integration Smoke Runner (`smoke_test.py`):**
   - Standalone integration client that runs against a real, running backend instance (`SMOKE_BASE_URL`).
   - Requires explicit opt-in (`CLAIMPILOT_SMOKE_TESTS=1`) and refuses execution against production domains.
   - Evaluates each stage as **PASS**, **FAIL**, **BLOCKED**, or **NOT RUN** without masking errors or simulating false successes.

---

## 2. Test Stages & Scope (A through G)

| Stage | Name | Scope & Truthfulness Guarantees |
|---|---|---|
| **A** | **Authentication & RBAC** | Verifies 2FA login (password + OTP), JWT signature verification, session validation on `/auth/me`, rejection of missing/malformed tokens (HTTP 401), and strict customer-to-agent role barrier (HTTP 403). Redacts all secrets in logs. |
| **B** | **Claim Creation & Policy Assignment** | Files claim with valid test policy (`DEMO-POL-001`), maps to assigned agent, creates claim in `pending_review` status. Verifies unassigned policy fails safely (HTTP 400), and cross-customer claim isolation prevents Customer B from viewing Customer A's claim (HTTP 403). |
| **C** | **Evidence Upload & Storage** | Requests presigned upload URL for private bucket (`claim-evidence`), validates 50MB file size ceiling (HTTP 413), verifies canonical owner-scoped storage path (`evidence/{category}/{user_id}/...`), verifies storage object presence before cataloging, and enforces cross-customer upload rejection (HTTP 403). |
| **D** | **AI Inference & Persistence** | Triggers AI pipeline on damage photos. If model weights are present, validates nonnegative bounding boxes and cost bounds. If model weights or services are unavailable, verifies safe transition to `manual_review` with failed analysis record. **Zero fabricated detections, bounding boxes, or damage estimates.** |
| **E** | **Agent Authorization & Decision** | Verifies assigned agent can inspect claim while unassigned agent is rejected (HTTP 403). Verifies approval without valid AI estimates or explicit adjuster amount fails safely (HTTP 400, `manual_review_required`). Verifies explicit authorized amount persists truthfully. Enforces terminal status locks (HTTP 400). |
| **F** | **Customer Settlement Outcome** | Customer verifies persisted settlement offer, submits acceptance (`ACCEPT`) via `/claims/portal/decision`. Verifies state transition to `settlement_accepted`. **Truthful non-initiated payout:** `payout_status: "not_started"`, `batch_id: null`, disbursement channel null, and explicit message that no payout has started. Tests dispute behavior (`DISPUTE`) on separate claim, verifying note persistence and `High Risk` priority requeue. |
| **G** | **Failure & Recovery Matrix** | Tests negative branches: invalid source state transitions, concurrency conflicts on database updates (HTTP 409), invalid OTP codes, rate limits, and unconfirmed responses. |

---

## 3. Required Environment Variable Names (No Secrets)

The live integration smoke runner (`smoke_test.py`) reads only from the following environment variables:

| Variable Name | Purpose | Example / Format |
|---|---|---|
| `CLAIMPILOT_SMOKE_TESTS` | **Mandatory opt-in flag.** Must be `1` to allow live test execution. | `1` |
| `SMOKE_BASE_URL` | Base API URL of the running backend test instance (fail-closed allowlist; localhost or allowed staging hosts only). | `http://localhost:8000/api/v1` |
| `SMOKE_ALLOWED_HOSTS` | Optional comma-separated allowlist of explicitly approved remote test/staging hostnames (HTTPS required). | `staging-api.claimpilot.internal` |
| `SMOKE_ALLOWED_STORAGE_HOSTS` | Optional comma-separated allowlist of explicitly approved storage hosts for presigned upload URLs. | `supabase.staging.internal` |
| `SMOKE_CUSTOMER_EMAIL` | Dedicated test customer account email. | `test.customer@claimpilot.test` |
| `SMOKE_CUSTOMER_PASSWORD`| Test customer account password. | `[configured test password]` |
| `SMOKE_AGENT_EMAIL` | Dedicated test agent account email. | `test.agent@claimpilot.test` |
| `SMOKE_AGENT_PASSWORD` | Test agent account password. | `[configured test password]` |
| `SMOKE_IMAGE_DIR` | Local directory containing test damage photos (`.jpg`, `.png`). | `./test_images` |
| `SMOKE_OTP_CODE` | 6-digit OTP code configured for test accounts. | `123456` |
| `SMOKE_POLICY_NUMBER` | Seeded test policy number assigned to test agent (defaults to `DEMO-POL-001`). | `DEMO-POL-001` |
| `SMOKE_ANALYSIS_TIMEOUT` | Timeout in seconds to poll AI assessment (defaults to `120`). | `120` |

> [!WARNING]
> Never commit `.env` files, production credentials, passwords, or signed URLs. The test runner redacts all sensitive identifiers and credentials in terminal output. Automatic redirects are disabled on the HTTP client to prevent request diversion to unapproved targets.

---

## 4. Safe Execution Commands

### A. Deterministic In-Process Smoke Suite (Local / CI)
Requires only local Python dependencies; does not make external network calls:

```powershell
# Navigate to backend directory
cd insurance-pro/backend

# Run the deterministic demo smoke test suite
pytest tests/test_demo_smoke_suite.py -v

# Run the entire backend regression suite (97 tests)
pytest tests/ -v
```

### B. Frontend Verification (Unit Tests, Lint, Production Build)
```powershell
# Navigate to frontend directory
cd insurance-pro/frontend/ClaimPilot

# Run frontend unit tests (25 tests covering settlement decisions & error recovery)
npm test

# Run code linter
npm run lint

# Validate production build (TypeScript + Vite bundle)
npm run build
```

### C. Opt-In Live Integration Smoke Test (Real Test Environment)
```powershell
# Navigate to backend directory
cd insurance-pro/backend

# Set the safety opt-in and target URL
$env:CLAIMPILOT_SMOKE_TESTS="1"
$env:SMOKE_BASE_URL="http://localhost:8000/api/v1"
$env:SMOKE_CUSTOMER_EMAIL="customer@example.com"
$env:SMOKE_CUSTOMER_PASSWORD="your-test-password"
$env:SMOKE_AGENT_EMAIL="agent@example.com"
$env:SMOKE_AGENT_PASSWORD="your-test-password"
$env:SMOKE_IMAGE_DIR="C:\path\to\damage_photos"
$env:SMOKE_OTP_CODE="123456"

# Execute the runner
python smoke_test.py
```

---

## 5. Sanitized Test Results Summary

### Local Test Gates (Executed)

| Test Suite / Command | Working Directory | Exit Code | Result | Details |
|---|---|---|---|---|
| `pytest tests/test_demo_smoke_suite.py` | `insurance-pro/backend` | **0** | **20 passed** | 100% pass across Stages A through G (exercises real AI failure path) |
| `pytest tests/test_smoke_runner_regressions.py` | `insurance-pro/backend` | **0** | **42 passed** | Target allowlist, fail-closed guard, redirect & OTP regression coverage |
| `pytest tests/` (full backend suite) | `insurance-pro/backend` | **0** | **140 passed** | 0 failures, 9 warnings across all 9 test suites |
| `npm test` (frontend test runner) | `insurance-pro/frontend/ClaimPilot` | **0** | **25 passed** | 0 failures, 4 test suites |
| `npm run lint` | `insurance-pro/frontend/ClaimPilot` | **0** | **0 errors** | 15 compiler warnings |
| `npm run build` | `insurance-pro/frontend/ClaimPilot` | **0** | **Built in 1.88s** | Production client bundle generated |
| `git diff --check` | Root | **0** | **Clean** | No trailing whitespace or merge conflict markers |

### Live Integration Smoke Suite (`smoke_test.py`) Stage Status

When executed without a live backend target or credentials, the safety harness strictly isolates and honestly reports stages without mocking:

```text
==============================================================================
CLAIM_PILOT E2E DEMO SMOKE TEST SUMMARY
==============================================================================
Stage A (Authentication & RBAC)            : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage B (Claim Creation & Assignment)      : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage C (Evidence Upload & Storage)        : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage D (AI Inference & Persistence)       : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage E (Agent Authorization & Decision)   : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage F (Customer Settlement Outcome)      : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
Stage G (Failure & Recovery Matrix)        : [NOT RUN] (Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required to run live tests)
==============================================================================
```

---

## 6. Known Limitations & Demo-Gate Boundaries

1. **Payment Disbursement Provider:** No real banking or UPI disbursement provider is wired into this application. Payout status is truthfully persisted and displayed as `not_started`.
2. **Database Migrations:** Database migrations (`migration_v4_policies.sql`) and seed scripts must be executed manually by an authorized database administrator. The test suite never mutates or drops live schemas.
3. **Evidence Storage:** Supabase Storage bucket `claim-evidence` must be configured as **Private** with a 50MB file size limit.
4. **Machine Learning Model Weights:** In environments without local YOLO weights (`best.pt` or fallback), the system gracefully and truthfully routes claims to `manual_review` instead of inventing bounding boxes or repair amounts.

---

## 7. Troubleshooting Guide

- **`[BLOCKED] Opt-in flag CLAIMPILOT_SMOKE_TESTS=1 is required`:** Set `CLAIMPILOT_SMOKE_TESTS=1` before launching `smoke_test.py`.
- **`[BLOCKED] Refusing to run live smoke tests against production host`:** The configured `SMOKE_BASE_URL` contains a protected production domain. Use local or dedicated staging hosts only.
- **`ModuleNotFoundError: No module named 'app'`:** Run tests via `pytest` (using the repo's `pytest.ini`) or prefix with `python -m pytest`.
- **`Policy 'DEMO-POL-001' is invalid or not registered`:** Ensure `agent_policies` table has been seeded with an active agent assigned to `DEMO-POL-001`.
- **`Storage object does not exist in bucket claim-evidence`:** Confirm the test evidence was uploaded before calling `/storage/evidence`.
