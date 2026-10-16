# ClaimPilot AI — Migration Status

**Status: MIGRATED SNAPSHOT — VALIDATION AND SELECTIVE FEATURE PORTING STILL REQUIRED**

Destination: https://github.com/Abhiram-Mukkamala/Claimpilot (private)

## Snapshot source

- Code and documentation snapshot: `test/e2e-demo-smoke` at `265c3934674a0070d7314af064d4a62a1acd3fe0`.
- The current `claimpilot` branch had one unique commit in the comparison, changing only `README.md`; the current `claimpilot` README is used in this repository.
- The original repository and all source branches remain unchanged: https://github.com/shreyasshah707/ClaimPilot
- This is a single-branch snapshot, **not** a full Git-history mirror. Source commits, tags and all source branches were not copied into `main`; the original repository remains the history/backup reference.
- The destination also contains the separate `claimpilotayaan` branch at commit `f47c5b67ccaaad751cc408b48fb7417529d7fca2`. It contains Ayaan's onboarding/about snapshot and was not modified in this migration. Keep it until its unique work is reviewed and accounted for.

## Included in main

- 206 text/source/documentation file paths from the selected E2E branch.
- The newer README from current `claimpilot`.
- Both original `hero.png` assets, byte-for-byte restored from the source branch; source and destination blob SHA matches.
- Both model weights: `rt-detr.pt` and `yolov11m.pt`. The migration API could not return their binary content, but the same exact Git blob objects were already present in the destination's `claimpilotayaan` branch and were referenced into `main`.
- `docs/BRANCH_CONSOLIDATION.md`, tracking feature work that still needs review/porting.
- Only `.env.example` templates; no real `.env` file was migrated.

## Local security work not included

Previously reported uncommitted Phase 1 security changes in local worktrees `C:\Projects\claimbot AI\wt-impl-phase1` and `ClaimPilot-Final` were not present as remote commits in the inspected source tree. Those modifications were not copied into this migration. Review and apply them deliberately from the local worktree; preserve staged/unstaged work and backups. Do not replace files wholesale without comparing the patch.

## Other branch work not yet integrated

The branch-specific changes listed in `docs/BRANCH_CONSOLIDATION.md` remain in the original repo (and the separate destination branch noted above where applicable) and were not silently merged into this snapshot. Review and selectively port them with focused tests.

## Validation status

- Destination `main` contains the selected release-candidate tree, with the latest README and migration documentation.
- Source-file blob hashes were checked when copying text blobs; both PNG assets and both model-weight blob hashes match the source objects.
- **Tests/build were not run as part of this migration.**
- Other feature-branch work and the separate local security changes still need review. Do not declare the release ready until those items are resolved and the end-to-end workflow passes.
