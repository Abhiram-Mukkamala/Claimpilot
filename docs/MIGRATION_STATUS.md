# Migration status — ClaimPilot Release

**Status: PARTIAL SNAPSHOT — NOT READY TO DEPLOY**

This repository was populated from the public source repository's remote branch `test/e2e-demo-smoke` at commit `265c3934674a0070d7314af064d4a62a1acd3fe0` on 16 October 2026.

Source: https://github.com/shreyasshah707/ClaimPilot/tree/test/e2e-demo-smoke

## What was migrated

- 206 text/source/documentation file paths from that branch snapshot.
- One intended integration branch only: `main`.
- No source branches were deleted or modified.

This is a **snapshot import**, not a Git history mirror: old commits and the source repository's 23 branches were not copied to this repository. The initial destination-repository commit remains in history.

## Files that still need restoration

The GitHub connector used for this migration can transfer UTF-8 blobs but cannot retrieve binary blobs through the same path. These two model weights were therefore not copied:

- `insurance-pro/backend/app/models/weights/rt-detr.pt` (66,248,189 bytes)
- `insurance-pro/backend/app/models/weights/yolov11m.pt` (40,511,404 bytes)

Original files are available in the source branch:
- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/rt-detr.pt
- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/yolov11m.pt

The following image assets were replaced with tiny valid PNG placeholders so frontend imports resolve. Restore the original files before judging the UI:

- `insurance-pro/frontend/ClaimPilot/src/assets/hero.png`
- `src/assets/hero.png`

Original assets:
- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/frontend/ClaimPilot/src/assets/hero.png
- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/src/assets/hero.png

## Local work not included

The separately reported uncommitted Phase 1 security changes in the local worktree `C:\Projects\claimbot AI\wt-impl-phase1` / `ClaimPilot-Final` were not present as a remote commit in the inspected source tree and could not be included. Review and reapply those changes deliberately; do not overwrite the local staged/unstaged work or backups.

## Before deployment

1. Restore both model weights and original PNG assets from the links above.
2. Reconcile and apply only reviewed database migrations; do not run unreviewed SQL against production.
3. Configure environment variables and secrets outside Git. Never commit `.env` files or credentials.
4. Run backend tests, frontend typecheck/build, security tests, and hosted end-to-end workflow from customer login through agent review and customer settlement decision.
5. Verify CI and runtime readiness. No tests were run as part of this snapshot import.
6. Keep the old repository as the backup until the new repo is fully validated.
