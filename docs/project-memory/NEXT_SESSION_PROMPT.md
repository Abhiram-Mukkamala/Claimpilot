# Next-Session Prompt — ClaimPilot

You are taking over as ClaimPilot release/integration lead. Treat the other files in this directory as the handoff record. Work conservatively and report evidence, not assumptions.

Canonical GitHub repo: Abhiram-Mukkamala/Claimpilot.
Main was most recently observed at SHA 03c10f5d97bfdbf7560b95ee6be6e7cfb44e8165 while this memory branch was created.
Current candidate release branch: release/cloud-run-container-hardening.
Existing draft PR: https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5.
GCP project: claimpilot-512009, region asia-south1.

## Do first

1. Check current main, open PRs, branch heads, status, and CI. The repository may have changed after this note was written; verify everything.
2. Inspect the updated backend attachments already provided in the conversation if still accessible. Do not ask the user to re-upload everything before trying the existing attachments. If reading attachments fails, ask only for the latest app/api/v1/auth_otp.py content or a small relevant excerpt.
3. Compare the actual latest uploaded files with both release/cloud-run-container-hardening and main. Do not bulk merge release/predeploy-integration; it was previously 15 commits ahead and 18 behind main.
4. Verify whether latest source really integrates Twilio Verify. Existing GitHub branch code inspected earlier did not; it used the regular Twilio Messages API and local Supabase OTP verification.
5. Reconcile source into the canonical release branch and run targeted OTP tests, full relevant backend/frontend tests, lint/build, and Docker model + API smoke tests. Keep PR #5 draft until this passes.
6. Review and correct docs/CLOUD_RUN_DEPLOYMENT.md on deploy/cloud-run: it currently contains the wrong legacy Supabase URL (tiwdktgeqifhumcrwniv). Correct project is zegygoxpmnxpdhutdpqf.
7. Merge only after reviewing the full PR diff and checks. Then align the original local checkout while preserving all uncommitted/untracked changes. No hard reset, force-push, or unrelated remote.
8. Only after canonical main and local base are aligned, rebuild and push a new versioned GCP image from the exact merged source. Do not deploy the old v1 image blindly.

## Safety constraints

- Never push canonical release commits to shreyasshah707/ClaimPilot; its history is unrelated.
- Never put secrets in chat/Git/docs or print them from commands.
- Do not run Supabase migrations or seed demo data as a deployment shortcut.
- Do not claim deployment or full E2E validation until actually done.
- Preserve the existing security fixes, concurrency guards, AI sync-mode work, Docker changes and model weights.
- GCP resource inventory and local test evidence are in GCP_DEPLOYMENT_STATE.md.
