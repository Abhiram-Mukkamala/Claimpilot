# Branch Consolidation Queue

This checklist explains what was intentionally not blindly merged into the new private release repository. Source branches remain intact at https://github.com/shreyasshah707/ClaimPilot.

## Current destination branches

- `main`: selected E2E release snapshot, with the latest `claimpilot` README. This is the intended integration/release branch.
- `claimpilotayaan`: still present at `f47c5b67ccaaad751cc408b48fb7417529d7fca2`. Its About-page/onboarding UI was selectively ported into `main` in commit `5724e85085ea3f981a6fed9382e347786b9f8997`. The branch remains as a reference for other UI differences and must not be deleted until its remaining unique work is accounted for.

These two destination branches have no common ancestor according to GitHub's compare endpoint; do not attempt an automatic merge. Compare their file trees and port selected files/features instead.

## Selected baseline

The new repository's `main` is a snapshot of remote `test/e2e-demo-smoke` at `265c3934674a0070d7314af064d4a62a1acd3fe0`, plus the current `claimpilot` README. The E2E branch has unique smoke/security and connected-frontend changes; it is not just a smoke-test-only branch.

## Unique work to review and port selectively

| Source branch | Work identified in comparison | Decision |
|---|---|---|
| `ayaan/claimpilot` / destination `claimpilotayaan` | Connected-frontend onboarding/about, login and customer dashboard changes, plus root-level prototype removals | **Ported:** About page + CSS, onboarding modal/steps/CSS/store, and `CustomerLayout` wiring. **Still pending:** review Login, CustomerDashboard, and other page differences individually. API/auth/store/smoke files were intentionally kept from `main`; do not merge the branch wholesale. |
| `ui/onboarding-about` | Alternative onboarding/about implementation, layout, styling and security-library changes in connected app | Compare with Ayaan's version; choose one onboarding implementation, don't combine blindly. |
| `frontend/new-claim` | Significant connected customer `NewClaim.tsx` changes | Review API contract and claim creation/evidence flow; port only with tests. |
| `frontend/agent-review` | Connected agent `AgentClaimDetails.tsx` changes | Review agent state transitions, authorization and settlement truthfulness before porting. |
| `backend/cost-estimator` | Cost-estimator service/data plus AI-runner/config/test changes | Port only if in demo scope; run estimator and AI-runner tests. |
| `frontend/login` / `frontend/login3` | Overlapping login/claims API variants; much login work is in root prototype | Compare variants; select one only if the change belongs in the connected app. |
| `ayaan-frontend-v2` | Another root-prototype onboarding/UI variant | Do not merge wholesale; use only specific, reviewed changes if needed. |
| `insurance-pro` | Separate app-tree/history with no common ancestor with `claimpilot` | Do not merge by Git ancestry; inspect manually for components absent from the selected snapshot. |
| `models` | Separate ML pipeline/research tree with no common ancestor | Keep as ML reference and port only explicitly required scripts/configs/weights. |
| `main` | Documentation-only divergence in the recorded comparison | Latest `claimpilot` README is already used in this destination. |
| `sutar` | Alternate Node.js backend | Do not mix it into the FastAPI backend architecture. |
| `Backend---Work` / `ayaan-frontend` | Same remote commit SHA | Duplicate pointers, not separate workstreams. |
| `legacy` / `tests/model-eval` | Same remote commit SHA in the recorded branch inventory | Historical/reference only unless a specific missing test is found. |

## Folder-layout caution

The snapshot intentionally preserves both frontend trees: root-level `src/` (prototype) and the connected app under `insurance-pro/frontend/ClaimPilot/`. Confirm the actual build/deployment target is the connected app before removing the root prototype. Do not delete either tree without checking imports, package scripts, deployment configuration and team worktrees.

## UI port applied on 16 October 2026

Commit: `5724e85085ea3f981a6fed9382e347786b9f8997` (`feat(ui): port Ayaan onboarding and about page design`). This ports the About page design and its stylesheet, the six-step onboarding UI and state store, and the CustomerLayout wiring. The onboarding auto-trigger tracks completion per user/email rather than letting one user's global completion flag suppress onboarding for everyone. A follow-up review found and fixed per-user completion persistence (auth user storage location and legacy key normalization), the About page's team-section navigation target, and onboarding modal focus/background-scroll accessibility plus correct semantics for step-jump controls in commits `12f8c78f7dd9143ca2fb53f05ced60f22d55379c`, `a0fbc909ae9fb275f0bd1ca1366d27a2246cc4de`, `e9f4bea8cbe8eb5ae817c08b5e1dd5f770b84e58`, and `c9307de4a9869765596b8cbe1402d5c44603b5c5`. The existing `claimsApi.ts`, `authStore.ts`, `Login.tsx`, backend claim/agent endpoints, and smoke-test runner were not changed by the UI port or these fixes. The onboarding modal now traps keyboard focus, restores focus on close, and locks background scrolling. Build and automated tests remain unrun.

## Safe integration procedure

1. Compare the baseline to one source feature branch at a time and review its complete changed-file list.
2. Confirm the feature is absent from `main` before porting.
3. Port only files needed by the canonical connected frontend (`insurance-pro/frontend/ClaimPilot`) or FastAPI backend (`insurance-pro/backend`).
4. Preserve local unstaged/staged security work. Never reset, clean, or overwrite it to match remote.
5. Run focused tests, backend suite, frontend typecheck/build, then hosted end-to-end smoke.
6. Keep the old repo and branches until successful validation. Do not delete branches as part of consolidation.
