# Planning Guide and Candidate Work

This is a planning aid for future Claude sessions, not an approved product roadmap. The candidates below come from code paths visible in this repository. Recheck the current source and user priorities before implementing any item.

## Plan each change

For a feature or bug that crosses layers, identify these before editing:

1. **User outcome:** what the customer or agent should be able to do or understand.
2. **Canonical app:** the integrated frontend under `insurance-pro/frontend/ClaimPilot/`, the root mock/demo frontend, the backend, or the independent `ml/` package.
3. **Current path:** the screen, API route, service, schema, and database tables involved.
4. **Contract changes:** request/response fields, status transitions, error behavior, and frontend mapping.
5. **State and rollout:** whether a SQL migration, environment setting, model weight, or external provider is required, and how it will be introduced safely.
6. **Acceptance evidence:** observable behavior and the narrow checks that demonstrate it.

Keep a plan small enough to implement in reviewable pieces. Mark assumptions as assumptions. Ask for a product decision when a user-visible behavior, policy rule, or deployment target cannot be derived from the code.

## Candidate work to prioritize with the product owner

### 1. Establish one documented run path

**Why it surfaced:** the repository root README describes the mock frontend, while the backend-connected frontend has a separate package and API client under `insurance-pro/frontend/ClaimPilot/`.

**Plan:** decide which app is the default developer/demo entry point, then update the relevant READMEs with correct working directories, environment setup, API startup, and data-source behavior. Keep the other app labeled as a demo if it remains useful.

**Acceptance:** a new developer can start the intended frontend and backend from the documented commands and can tell mock behavior from live Supabase behavior before logging in.

### 2. Make analysis status and UI provenance explicit

**Why it surfaced:** the API runner emits real detection results but currently leaves segmentation/depth/normal fields empty. The connected UI contains fallback costs, confidence/risk values, and mock visualization assets for missing fields.

**Plan:** trace the analysis status and data from the database through API response mapping to the customer and agent screens. Decide which results should be hidden, labeled as estimates, or shown as unavailable. Avoid introducing guessed values as if measured.

**Acceptance:** each displayed analysis value can be traced to a stored API result or is visibly identified as a demo/fallback; pending and failed analysis states are understandable to the user.

### 3. Review backend security and evidence fetching

**Why it surfaced:** `main.py` currently configures wildcard CORS with credentials; `ai_runner.py` creates an unverified TLS context for evidence downloads; and the generic error handler returns exception text. Claim routes also contain raw `print` diagnostics.

**Plan:** confirm the actual deployment origins and storage URL patterns first. Replace broad settings with environment-driven allowlists, use normal certificate verification, return sanitized errors, and use structured logs that omit tokens, signed URLs, and customer data. Add focused regression checks as each behavior changes.

**Acceptance:** approved origins work, unapproved origins fail, storage downloads verify TLS, API errors do not expose internal exception details, and logs do not include secrets or claim PII.

### 4. Verify schema rollout for fraud analysis

**Why it surfaced:** the fraud service reads/writes `claim_evidence.phash` and stores rows in `claim_fraud_analyses`; those objects are added by `migration_v3_phash.sql`, not the base `schema.sql`.

**Plan:** confirm the migration is included in the actual environment's deployment procedure, document its prerequisites and recovery path, and make app behavior clear when a database has not been upgraded. Do not infer remote migration state from local files.

**Acceptance:** a clean database setup plus ordered migrations creates the objects expected by the running backend, and a missing migration produces an actionable operator error without hiding the damage-analysis result.

### 5. Define the integration boundary for the ML package

**Why it surfaced:** `ml/` includes photo/video pipelines for depth, segmentation, surface normals, reconstruction, and measurement, while the HTTP runner currently calls YOLO/RT-DETR directly and returns empty advanced fields.

**Plan:** decide whether those scripts remain research/CLI tools or should become a backend service. If integration is desired, specify input/output contracts, model-weight deployment, latency/resource needs, failure behavior, and how results are persisted before wiring screens to them.

**Acceptance:** either the separation is documented and the UI presents unavailable stages accurately, or an end-to-end API contract is implemented with explicit stage status and tested failure handling.

### 6. Close the customer settlement response path

**Why it surfaced:** the backend exposes a customer portal decision endpoint, while the connected frontend README labels its full UI wiring as pending. Confirm the current screen code before taking this on.

**Plan:** inspect current customer claim detail and agent queue pages, then define allowed decisions and status transitions with the product owner. Preserve authorization checks and explain the consequences of accept, reject, or dispute.

**Acceptance:** a customer decision is submitted once, persists with any required notes, is reflected in both customer and agent views, and invalid/repeated transitions produce clear responses.

## Suggested order

For a production-readiness effort, first settle the run path and current data contracts, then address security and migration deployment. After that, choose whether to integrate the advanced ML pipeline or label it as unavailable, and complete the settlement response flow according to product policy. This ordering is a proposal; follow the user's requested outcome when it differs.
