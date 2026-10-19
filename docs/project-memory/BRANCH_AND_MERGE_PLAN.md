# ClaimPilot Branch Reconciliation and Local Alignment Plan

Last updated: 2026-10-19 (Asia/Kolkata), updated after PR #5 merged.

## Current status

The source merge step is complete in GitHub:
- PR #5 merged: https://github.com/Abhiram-Mukkamala/Claimpilot/pull/5
- Merge commit / main SHA at last check: 03c10f5d97bfdbf7560b95ee6be6e7cfb44e8165
- PR #5 head: 5b671713d579a2bfb054317c1d36494c2c4b9852
- PR description reports 184 backend tests passed (including 9 Twilio Verify tests), 32 frontend tests passed, frontend build passed, lint 0 errors / 13 warnings, YOLO check and git diff check passed.
- The release branch is one merge commit behind main. Do not merge PR #5 again.

## Next work: align local checkout

Windows paths:
- Canonical release worktree: C:\Projects\claimbot AI\wt-release-canonical
- Original local checkout/base: C:\Projects\claimbot AI\ClaimPilot-Final
- Canonical remote alias abhiram in release worktree points to https://github.com/Abhiram-Mukkamala/Claimpilot.git
- Original checkout origin points to shreyasshah707/ClaimPilot (unrelated history). Do not push to it.

Before modifying either checkout, inspect and record:
- git status --short --branch
- git remote -v
- git branch --show-current
- git log --oneline --decorate -12

Then verify main's current SHA on GitHub and fetch only from a remote confirmed to point to Abhiram-Mukkamala/Claimpilot. Back up all uncommitted changes and untracked files before any sync. Do not use git reset --hard, force-push, remove worktrees or overwrite directories wholesale. Align source files deliberately and preserve personal/local edits.

## Twilio OTP source status

Main source now includes TWILIO_VERIFY_SERVICE_SID in config and the Twilio Verify Verifications + VerificationCheck API paths in auth_otp.py. The Verify check requires approved and valid=true. test_twilio_verify.py covers sending, approved checks, rejected codes, expired codes and provider errors according to the merged PR description/source test listing.

The design remains custom FastAPI + Supabase database records + Twilio Verify for SMS + SendGrid for email. It is not Supabase built-in phone OTP auth. The code still has legacy regular Twilio Messages API fallback, which uses TWILIO_PHONE_NUMBER, but don't configure that fallback when the chosen deployment path is Verify. The deleted claimpilot-twilio-phone-number secret should remain absent for the Verify path.

## Keep these changes while aligning

Preserve the security fixes, auth hardening, sensitive-data logging controls, optimistic concurrency fixes, AI synchronous-processing configuration and tests, Docker packaging, best.pt checkpoint, frontend auth/API compatibility, and Twilio Verify implementation/tests.

## Verification gate before GCP deployment

- Verify current merged main SHA and local working tree.
- Run backend pytest / Twilio Verify tests, frontend tests/build, lint and git diff --check if any source changes occur during alignment.
- Inspect the final diff for secrets and unintended files.
- Correct the Cloud Run deployment runbook's wrong legacy Supabase URL.
- Confirm production secrets have values and test real email/SMS delivery and the whole customer-to-agent workflow.
- Rebuild/push a new versioned image from merged main only after source verification. Do not deploy previously pushed v1 image as the final version.

## Outstanding

- Original local checkout alignment not yet reported complete.
- Latest local backend attachments could not be read by the runtime when first uploaded; current GitHub main was subsequently inspected and shows Twilio Verify code. Avoid asking for all files again; use available source and only request one targeted file if the discrepancy remains material.
- SendGrid key/sender and secret versions remain unconfirmed.
- No Cloud Run service deployment confirmed.
