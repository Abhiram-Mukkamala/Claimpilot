# ClaimPilot AI — Migration Status

**Status: PARTIAL MIGRATION SNAPSHOT — NOT READY TO DEPLOY**

Destination: https://github.com/Abhiram-Mukkamala/Claimpilot (private)

## Snapshot source

- Code and documentation snapshot: `test/e2e-demo-smoke` at `265c3934674a0070d7314af064d4a62a1acd3fe0`.
- The current `claimpilot` branch is also divergent. GitHub comparison reported one unique commit on `claimpilot`, changing only `README.md`; the README in this repository was taken from the current `claimpilot` branch so that documentation update is retained.
- The original source repository and all its branches remain unchanged: https://github.com/shreyasshah707/ClaimPilot
- This is a single-branch snapshot, **not** a full Git history mirror. Source commits, tags, and other remote branches were not copied. The original repository remains the history/backup reference.

## Included

- 206 text/source/documentation file paths from the selected E2E branch.
- The newer README from `claimpilot`.
- Both `hero.png` assets restored byte-for-byte from the source branch; source and destination blob SHA match.
- `docs/BRANCH_CONSOLIDATION.md`, which tracks feature work that still needs review/porting.
- Only `.env.example` templates; no real `.env` file was migrated.

## Required model weights not included

The migration interface cannot transfer these binary model blobs:

- `insurance-pro/backend/app/models/weights/rt-detr.pt` (66,248,189 bytes)
- `insurance-pro/backend/app/models/weights/yolov11m.pt` (40,511,404 bytes)

Retrieve them from the original public release-candidate branch and place them at the exact same paths:

- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/rt-detr.pt
- https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/yolov11m.pt

AI inference has not been validated without these files.

## Local security work not included

Previously reported uncommitted Phase 1 security changes in local worktrees `C:\Projects\claimbot AI\wt-impl-phase1` and `ClaimPilot-Final` were not present as remote commits in the inspected tree. Those modifications were not copied into this migration. Review and apply them deliberately from the local worktree; preserve its staged/unstaged work and backups. Do not replace files wholesale without comparing the patch.

## Other branch work not yet integrated

The branch-specific changes listed in `docs/BRANCH_CONSOLIDATION.md` remain in the original repo and were not silently merged into this snapshot. Review and selectively port them with focused tests.

## Validation status

- File tree created and verified on destination `main`.
- Source-file blob hashes were checked when copying text blobs.
- Original PNG blobs restored and hash-verified.
- **Tests/build were not run as part of this migration.**
- The two model weights are missing and branch work/local security changes remain to be reviewed. Do not deploy this repository as a release candidate until those blockers are resolved and end-to-end tests pass.
