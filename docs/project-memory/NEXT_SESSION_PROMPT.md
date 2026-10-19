# Next-Session Prompt — ClaimPilot

You are taking over as ClaimPilot integration/release owner. Read README.md, CURRENT_HANDOFF.md, BRANCH_AND_MERGE_PLAN.md, and GCP_DEPLOYMENT_STATE.md first. Report evidence, not assumptions.

Canonical repository: Abhiram-Mukkamala/Claimpilot.
PR #5: https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5 — now merged.
Merged main SHA at last verified check: 03c10f5d97bfdbf7560b95ee6e6e7cfb44e8165 (re-verify before acting).
Old pushed GCP image: asia-south1-docker.pkg.dev/claimpilot-512009/claimpilot/claimpilot-api:v1, digest sha256:fdad2b67315e9e2f3ac373d3f95665d0ed715dad346de1efa215de15c9bea1d4. It predates the final merge's Twilio Verify integration; do not deploy it as final.
GCP project: claimpilot-512009, region asia-south1.

## Do first

1. Verify current main SHA, PR state, checks and branch heads.
2. Inspect both local worktrees before changing anything:
   - C:\Projects\claimbot AI\wt-release-canonical
   - C:\Projects\claimbot AI\ClaimPilot-Final
   Run git status --short --branch, git remote -v, git branch --show-current, and git log --oneline --decorate -12 in each.
3. Align the original local base to merged canonical main, preserving all uncommitted changes and untracked files. Do not use git reset --hard, force-push, remove worktrees, bulk-overwrite files, or push to shreyasshah707/ClaimPilot. Verify remotes; abhiram should point to https://github.com/Abhiram-Mukkamala/Claimpilot.git.
4. Main was inspected and contains TWILIO_VERIFY_SERVICE_SID configuration plus Twilio Verify /Verifications and /VerificationCheck API calls. It requires provider status approved and valid=true. tests/test_twilio_verify.py covers send/check outcomes. PR #5 reports 184 backend tests, including 9 Verify tests, 32 frontend tests, build pass, lint 0 errors/13 warnings, model load/inference, and diff check. These are PR-reported results, not necessarily freshly rerun in this session.
5. Review source diff and relevant CI. Do not merge PR #5 again; it is already merged. The old release branch is one merge commit behind main.
6. Correct docs/CLOUD_RUN_DEPLOYMENT.md on deploy/cloud-run: replace legacy Supabase URL https://tiwdktgeqifhumcrwniv.supabase.co with https://zegygoxpmnxpdhutdpqf.supabase.co.
7. Verify Secret Manager versions and mappings without printing values. Twilio Verify secrets planned: claimpilot-twilio-account-sid, claimpilot-twilio-auth-token, claimpilot-twilio-verify-service-sid. Existing Supabase/JWT/SendGrid secret containers already exist, but actual versions were not confirmed. Do not create/configure claimpilot-twilio-phone-number for the chosen Verify flow.
8. Once local source is aligned and environment/provider secrets are ready, build and push a new immutable/commit-specific image from the merged main SHA. Do not reuse old v1 blindly.
9. Only then configure/deploy Cloud Run and test live health/readiness, real email OTP, Twilio Verify SMS send and check, plus the full customer-to-agent journey.

## Guardrails

- Never expose credentials, OTP codes, service-role keys or .env content.
- Do not run Supabase migrations or seed demo data as a deployment shortcut.
- Preserve auth/security fixes, concurrency controls, AI sync mode, Docker changes and best.pt.
- No live Cloud Run deployment has been confirmed.
- GCP resource inventory and local Docker evidence are documented in GCP_DEPLOYMENT_STATE.md.
