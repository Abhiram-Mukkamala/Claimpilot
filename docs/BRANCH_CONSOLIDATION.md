# Branch Consolidation Queue

This checklist explains what was intentionally not blindly merged into the new private release repository. Source branches remain intact at https://github.com/shreyasshah707/ClaimPilot.

## Selected baseline

The new repository's `main` is a snapshot of remote `test/e2e-demo-smoke` at `265c3934674a0070d7314af064d4a62a1acd3fe0`, with the latest `claimpilot` README copied separately. The E2E branch has unique smoke/security and connected-frontend changes; it is not just a smoke-test-only branch.

## Unique work to review and port selectively

| Source branch | Work identified in comparison | Decision |
|---|---|---|
| `ayaan/claimpilot` | Connected-frontend onboarding/about, login and customer dashboard changes, plus root-level prototype changes/deletions | Review the connected app paths only; verify onboarding, routing and auth before porting. |
| `ui/onboarding-about` | Alternative onboarding/about implementation, layout, styling and security-library changes in the connected app | Compare with `ayaan/claimpilot`; choose one onboarding implementation, don't combine blindly. |
| `frontend/new-claim` | Significant connected customer `NewClaim.tsx` changes | Review API contract and claim creation/evidence flow; port only with tests. |
| `frontend/agent-review` | Connected agent `AgentClaimDetails.tsx` changes | Review agent state transitions, authorization and settlement truthfulness before porting. |
| `backend/cost-estimator` | Cost-estimator service/data plus AI-runner/config/test changes | Port only if in demo scope; run estimator and AI-runner tests. |
| `frontend/login` / `frontend/login3` | Overlapping login/claims API variants; much login work is in root prototype | Compare the variants; select one only if the change belongs in the connected app. |
| `ayaan-frontend-v2` | Another root-prototype onboarding/UI variant | Do not merge wholesale; use only specific, reviewed changes if needed. |
| `insurance-pro` | Separate app-tree/history with no common ancestor with `claimpilot` | Do not merge by Git ancestry; inspect manually for components absent from the selected snapshot. |
| `models` | Separate ML pipeline/research tree with no common ancestor | Keep as an ML reference and port only explicitly required scripts/configs/weights. |
| `main` | Documentation-only divergence in the recorded comparison | Latest `claimpilot` README was already used in this destination; no code merge needed from `main`. |
| `sutar` | Alternate Node.js backend | Do not mix it into the FastAPI backend architecture. |
| `Backend---Work` / `ayaan-frontend` | Same remote commit SHA | Duplicate pointers, not separate workstreams. |
| `legacy` / `tests/model-eval` | Same remote commit SHA in the recorded branch inventory | Historical/reference only unless a specific missing test is found. |

## Safe integration procedure

1. Compare the candidate branch to one source feature branch at a time and review the complete changed-file list.
2. Confirm the feature is absent from the release baseline before porting.
3. Port only files needed by the canonical connected frontend (`insurance-pro/frontend/ClaimPilot`) or FastAPI backend (`insurance-pro/backend`).
4. Preserve local unstaged/staged security work. Never reset, clean, or overwrite it to match remote.
5. Run focused tests, backend suite, frontend typecheck/build, then hosted end-to-end smoke.
6. Keep old repo and branches until successful validation. Do not delete branches as part of consolidation.
