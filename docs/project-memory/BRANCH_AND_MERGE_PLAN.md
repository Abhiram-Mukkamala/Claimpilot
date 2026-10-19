# ClaimPilot Branch Reconciliation and Merge Plan

Last updated: 2026-10-19 (Asia/Kolkata)

## Intended order

1. Inspect exact branch/remote/status in both local worktrees.
2. Read the latest backend files the user uploaded and compare them to the canonical source. Do not assume uploaded files equal either existing GitHub branch.
3. Reconcile only intentional backend/front-end/test/documentation changes into release/cloud-run-container-hardening. Preserve existing security fixes, claim concurrency protection, AI sync-mode work, Docker packaging, and the primary model checkpoint.
4. Decide and implement the agreed SMS OTP provider (regular Twilio Messages vs Twilio Verify) in one consistent flow. Keep email OTP on SendGrid unless the team has changed that deliberately.
5. Run backend test suite, specific OTP tests, frontend tests/build, lint, git diff --check, Docker build, model-load/inference smoke test, and container health/readiness checks. Record actual commands/results.
6. Inspect PR #5's complete diff and latest main commit; update the PR branch and description as needed. Keep draft until review and checks are complete.
7. Merge the reviewed release into canonical main only after the latest backend is included and validations pass.
8. Align the original local base checkout to the merged canonical main without destroying local work.
9. Rebuild/push a new versioned GCP image from the exact merged commit. Do not deploy v1 blindly.

## Local branches and paths

- Canonical repository: Abhiram-Mukkamala/Claimpilot.
- Canonical release worktree: C:\Projects\claimbot AI\wt-release-canonical.
- Original local checkout: C:\Projects\claimbot AI\ClaimPilot-Final.
- Remote alias abhiram points to the canonical repository in the release worktree.
- The original checkout's origin points to shreyasshah707/ClaimPilot, which has unrelated history. Never push the canonical release there.

## Before any local sync

In each worktree run and review:
- git status --short --branch
- git remote -v
- git branch --show-current
- git log --oneline --decorate -12
- git fetch abhiram main only in worktree where remote alias is verified; don't fetch/push the wrong remote.

Back up uncommitted changes/untracked files from the original base before switching files. Do not use git reset --hard, force-push, delete branches/worktrees, or replace directories in bulk. Preserve or explicitly port user-local changes one file/commit at a time.

## Merge gates

Do not merge until:
- latest user-uploaded backend implementation has been read/reconciled;
- Twilio Verify vs Messages API design is resolved;
- SMS send/check path and frontend contract are covered by tests;
- secrets/config requirements match actual code;
- entire PR diff has been reviewed;
- no accidental .env, API keys, or other secrets are present;
- relevant CI and local validations have real, recorded results.

## Current blockers

- Latest individual backend source files and Pasted text.txt were uploaded to chat, but the file-reading runtime failed with internal ClientError; their contents were not verified. Retry fetching these already-attached files before asking for a re-upload. Some older uploads may have expired. If truly inaccessible, ask for the single critical file app/api/v1/auth_otp.py (or relevant excerpt) only.
- Current GitHub release branch code inspected through connector did not implement Twilio Verify.
- Runbook uses wrong Supabase URL.
- SendGrid key/sender setup and secret version population remain unconfirmed.
- No Cloud Run deployment exists yet.
