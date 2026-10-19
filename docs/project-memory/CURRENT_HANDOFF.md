# ClaimPilot Current Handoff

Last updated: 2026-10-19 (Asia/Kolkata)

## Mission and priority

MIT India Hackathon ClaimPilot. Immediate goal: reconcile the latest backend updates with the canonical release branch, validate them, merge reviewed fixes into canonical main, and align the correct files in the original local base checkout. Resume GCP deployment only after that source-of-truth alignment.

## Canonical GitHub state last observed

- Repository: Abhiram-Mukkamala/Claimpilot.
- main was at 8f83ffca575697ba6a2e090e607c49c8d76cb005 when PR #5 was inspected.
- PR #5: [Harden auth, AI processing, and Cloud Run packaging](https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5), open and draft; head release/cloud-run-container-hardening, SHA 91dfc4d6c1f8066b2185c177b5ca9e851191a25c; four commits, 20 files changed, +1040/-56 at the time of inspection.
- PR #4 is separate: [Prepare ClaimPilot backend for Cloud Run](https://github.com/Abhiram-Mukkamala/Claimpilot/pull/4), using branch deploy/cloud-run. It has a runbook defect: its deployment doc references the wrong legacy Supabase URL. Correct it before any deployment.
- Branch release/predeploy-integration was 15 commits ahead and 18 behind main in the last compare. Do not merge it wholesale.
- Most recent connector inspection of release/cloud-run-container-hardening and release/predeploy-integration showed the older custom SMS implementation: regular Twilio Messages API, phone-number sender config, and local OTP validation. This is not evidence about the contents of the user's subsequently uploaded backend files.

## Local workspace (Windows)

- Canonical release worktree: C:\Projects\claimbot AI\wt-release-canonical.
- Original local checkout/base: C:\Projects\claimbot AI\ClaimPilot-Final.
- The original checkout uses remote origin pointing to shreyasshah707/ClaimPilot; do not use it for canonical pushes.
- Canonical remote alias in the release worktree is abhiram, pointing to https://github.com/Abhiram-Mukkamala/Claimpilot.git.
- Original local .env path used for container smoke test: C:\Projects\claimbot AI\ClaimPilot-Final\insurance-pro\backend\.env. Its Supabase URL and key lines originally had surrounding quote issues; user removed the literal quotes. Never copy or expose its values.

## Local Docker evidence already completed

Image claimpilot-api:release-test built successfully from insurance-pro/backend before latest backend reconciliation.

- Model file inside container existed at /app/app/models/weights/best.pt, 22,501,482 bytes.
- YOLO loaded; task detect; classes: dent, scratch, crack, glass shatter, lamp broken, tire flat.
- Synthetic-image inference completed. This tests load/execution, not detection accuracy.
- Container initially failed because local environment values had literal quote characters; after correcting .env and recreating the container without rebuilding image, GET /health returned HTTP 200 {"status":"healthy"}.
- GET /health/ready returned HTTP 200, database reachable and email OTP configured.
- Direct Supabase REST query from inside the container returned HTTP 200 with one row.
- These are local-container results only; not a deployed-service or full end-to-end result.

## Latest uploaded backend files — inspection gap

The user uploaded the updated backend modules individually, including auth_otp.py, config.py, main.py, supabase.py, backend services and multiple tests. They also uploaded a file named Pasted text.txt. The current session's container/Python file-reading tools repeatedly returned internal ClientError, so the uploaded source and pasted report were not inspected. Do not ask them to re-upload everything by default. First retry access to the specific existing attachments, then inspect the actual files. If they are expired/unavailable, request only app/api/v1/auth_otp.py or its relevant excerpts as a fallback.

## OTP/Twilio design decision still to settle

The teammate stated the project uses custom FastAPI OTP logic with Supabase database records and Twilio/SendGrid for delivery; it does not use Supabase built-in signInWithOtp/verifyOtp.

The user says they intend to use a Twilio Verify Service SID and it has not been working. The old GitHub release code:
- calls Twilio regular Messages API using TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER;
- generates its own code and validates it against Supabase OTP records;
- does not configure a Verify Service SID or call Twilio Verify's verification-check API.

Do not infer the latest uploaded code is the same as that old GitHub version. Verify the actual current source. Decide with the teammate whether final SMS delivery is regular Twilio Messages API or Twilio Verify. If using Verify, backend must call Verify for both starting and checking the verification, and tests must confirm approved/rejected/provider-error handling. Keep the frontend API contract compatible, including any challenge_id expectations. Email OTP remains a separate SendGrid flow unless explicitly changed.
