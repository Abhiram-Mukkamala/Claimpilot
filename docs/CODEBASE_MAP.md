# ClaimPilot Codebase Map

This document records the repository boundaries and behavior visible in the current working tree. It was checked on 2026-10-13. It is a code map, not a promise that every feature is production-ready.

## Which app is which

There are two React apps in this repository, and they have different data sources:

| Path | Role | Evidence |
|---|---|---|
| `insurance-pro/frontend/ClaimPilot/` | Backend-connected customer and agent UI | `src/services/claimsApi.ts` calls the `/api/v1` service; its Vite config proxies `/api` to `localhost:8000`. |
| Repository root (`src/`, root `package.json`) | Separate mock/demo UI | `src/services/claimsApi.ts` and `analysisApi.ts` use mock data and browser `sessionStorage`. The root README describes this mode. |

For requests about the integrated product, treat `insurance-pro/frontend/ClaimPilot/` as the frontend target. Check the requested path if a task explicitly concerns the demo app. The two apps have overlapping filenames and should not be treated as interchangeable.

## Main components

```text
insurance-pro/
  backend/
    app/
      main.py                 FastAPI app, middleware, error handlers, router mounting
      api/v1/                 Auth, claims, agent, and evidence HTTP routes
      core/                   Settings and JWT/RBAC helpers
      db/supabase.py          Supabase/PostgREST access
      schemas/claim.py        Pydantic API/data models
      services/
        ai_runner.py          Background damage inference and analysis persistence
        fraud_analysis_service.py  Cross-claim image and narrative checks
    schema.sql                Base PostgreSQL/Supabase schema
    migration_v2.sql          Incremental schema changes
    migration_v3_phash.sql    pHash/fraud analysis schema additions
    tests/                    Backend unit and integration-style tests
  frontend/ClaimPilot/
    src/pages/                Customer and agent screens
    src/services/             HTTP clients and API-to-UI mapping
    src/routes/               React Router setup
ml/
  scripts/                    Independent photo/video ML and geometry pipelines
```

The root `src/` app is another tracked frontend. It is omitted from the diagram to keep the integrated runtime path clear.

## Integrated request and analysis flow

1. The connected frontend sends requests through `src/services/claimsApi.ts` to the FastAPI `/api/v1` API. Its default API URL is `http://localhost:8000/api/v1`; `VITE_API_BASE_URL` can override it.
2. `POST /api/v1/claims` validates the policy mapping and creates a claim in Supabase. It begins in `pending_review`; the route tells the user to upload damage photos to start assessment.
3. The frontend obtains storage upload information and registers evidence through the storage API. Registering evidence with category `photo` schedules `trigger_ai_assessment` as a FastAPI background task.
4. `ai_runner.py` downloads up to ten photo URLs, runs available YOLO weights and uses RT-DETR when YOLO fails or returns no detections. It stores bounding boxes, severity labels, and rough repair-cost estimates in `claim_ai_analysis`.
5. The runner passes downloaded image bytes to `fraud_analysis_service.py`. That service computes perceptual hashes, compares them with hashes from other claims, checks narrative against detected severity, and stores its result. Image bytes are transient; the pHash string is persisted.
6. Customer and agent screens load claim and analysis data through the integrated frontend service clients and the customer/agent API routes.

The claim-analysis task uses FastAPI `BackgroundTasks`, so work is in-process. A durable queue, retry policy, and multi-worker coordination are not established by this path. The runner also uses a database status update as an idempotency guard; inspect its exact behavior before changing retries or statuses.

## What the AI path currently does

- The live API runner performs object detection with YOLO and RT-DETR. It does not currently invoke all scripts in `ml/`.
- The runner returns null/empty values for segmentation, depth, and surface-normal outputs in its current analysis payload. The connected frontend maps missing advanced fields to demo assets and fallback values in `advancedAnalysisApi.ts`.
- The connected frontend's `analysisApi.ts` also supplies fallback cost/confidence/risk values in some missing-data cases. Check the UI mapping before interpreting a displayed number as model output.
- Fraud analysis is implemented and called by the runner. pHash comparison and a narrative check are present. The narrative check uses an optional OpenAI client when configured; otherwise it falls back to a deterministic keyword/severity heuristic. Check installed dependencies and runtime settings before assuming the LLM path is active.
- `migration_v3_phash.sql` adds the pHash column and fraud-analysis table used by this flow. The code cannot establish whether that script has been applied to a particular Supabase project.

## Data and API boundaries

- FastAPI mounts versioned routes at the configured `API_V1_STR`, currently `/api/v1`.
- Core route modules are `auth.py`, `auth_otp.py`, `claims.py`, `agent.py`, and `storage.py`.
- The database access layer talks to Supabase/PostgREST. Backend settings are read from environment variables or a backend working-directory `.env` file; see `.env.example` for names and placeholder values.
- The base schema is in `schema.sql`; incremental changes are separate SQL files. Read all relevant definitions before editing persistence behavior.
- The ML package has its own requirements and CLI entry point. It should be treated as a separate analysis pipeline until an explicit API integration is implemented.

## Documentation conflicts to keep in mind

- The root README describes the mock/demo frontend and browser session storage, not the backend-connected frontend.
- The backend `README.md` and `ml/README.md` contain broad implementation claims; verify behavior in source before relying on them.
- `wt-*` folders beside this repository are other snapshots/worktrees in the surrounding workspace, not submodules of this project. Use only this repository unless the task names another snapshot.
