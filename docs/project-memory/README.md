# ClaimPilot Project Memory Index

Last updated: 2026-10-19 (Asia/Kolkata)

This directory contains short, atomic handoff notes so a fresh ChatGPT/Antigravity session can resume ClaimPilot without repeating setup or making unsafe assumptions. These files are persisted on branch docs/project-memory-handoff-2026-10-19 and are not merged into main.

## Read in this order

1. [Current handoff](CURRENT_HANDOFF.md) — the immediate state and blockers.
2. [Next-session prompt](NEXT_SESSION_PROMPT.md) — copy-paste instructions for resuming work.
3. [Branch and merge plan](BRANCH_AND_MERGE_PLAN.md) — safe sequence for reconciling files, validating, merging to main, and aligning the local base.
4. [GCP deployment state](GCP_DEPLOYMENT_STATE.md) — resources already created, image already pushed, and remaining deployment work.

## Non-negotiable guardrails

- Canonical repository: Abhiram-Mukkamala/Claimpilot.
- Do not push ClaimPilot release work to the unrelated shreyasshah707/ClaimPilot repository.
- Do not bulk-merge release/predeploy-integration; it diverged from main (15 commits ahead and 18 behind in the last observed comparison).
- Do not merge PR #5 or deploy the currently pushed v1 image until the latest backend source is reconciled and Twilio integration is verified.
- Preserve existing local edits and untracked files. Never use git reset --hard, force-push, or overwrite the original local checkout.
- Never request or put credentials, OTP codes, API keys, or .env contents in chat, Git, logs, or handoff files.
- Supabase production project is zegygoxpmnxpdhutdpqf, URL https://zegygoxpmnxpdhutdpqf.supabase.co. Do not use legacy project tiwdktgeqifhumcrwniv.
- No Supabase schema migration or demo-data seeding as a deployment shortcut.

## Evidence labels

- Verified in current conversation: command output was pasted and reviewed.
- Observed via GitHub connector: canonical branch/repository state was queried.
- Not verified: depends on latest uploaded files that the file-reading runtime could not open, or a step not yet performed.

These notes are a working handoff, not a claim that the release has been merged or deployed.
