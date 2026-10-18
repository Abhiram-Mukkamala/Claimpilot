# Claude Code Guide

## Start here

Before planning a change, read:

1. [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md) for the current repository layout and runtime boundaries.
2. [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for planning practices and evidence-based candidate work.
3. The nearest source files, API schemas, database definitions, and existing tests for the task.

These notes describe the checked-in tree. If code and documentation disagree, trust the current code and schema, then update the inaccurate documentation when it is in scope.

## Repository boundaries

- The backend used by the integrated app is `insurance-pro/backend/` (FastAPI, Supabase, claim assessment).
- The backend-connected React app is `insurance-pro/frontend/ClaimPilot/`.
- The repository-root `src/` and `package.json` are a separate mock/demo frontend. Its claim and analysis services use local mock data. Do not assume it is the integrated app or edit it for an integrated-app request without checking the requested target.
- `ml/` contains Python photo/video analysis scripts. The backend currently runs its own YOLO/RT-DETR inference path; do not assume the `ml/` pipelines are called by the API.
- The project has repeated app snapshots in the surrounding workspace. Work only in this Git repository unless the user names another path.

## Working conventions

- Inspect `git status` and the target files before editing. Preserve existing user changes and untracked files.
- Trace changes across the frontend, API, Pydantic schemas, and SQL when a behavior crosses those boundaries. Keep request and response shapes aligned.
- Read `insurance-pro/backend/schema.sql` and the relevant migration before changing database-backed behavior. Migrations are manual Supabase SQL scripts; do not apply them to a live database unless explicitly asked.
- Treat uploaded images, signed storage URLs, auth tokens, claim details, and environment values as sensitive. Do not put secrets or real customer data in docs, logs, fixtures, or examples.
- Keep mock/demo behavior clearly separated from live API behavior. Do not present placeholder AI values as measured results.
- Preserve the existing React, TypeScript, FastAPI, and Supabase patterns unless the task calls for a deliberate change.
- For broad or cross-layer requests, first outline the goal, affected paths, dependencies, data-contract changes, risks, and a way to verify completion. Call out assumptions that need a product or deployment decision.
- Do not deploy, publish, or modify external services as part of a code change unless the user requested that action.

## Useful commands

Run frontend commands from the app being changed.

```powershell
# Backend-connected frontend
Set-Location insurance-pro/frontend/ClaimPilot
npm install
npm run dev
npm run build
npm run lint
```

```powershell
# Repository-root mock/demo frontend
Set-Location .
npm install
npm run dev
npm run build
npm run lint
```

```powershell
# FastAPI backend
Set-Location insurance-pro/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Create a local .env from .env.example and supply local credentials.
uvicorn app.main:app --reload --port 8000
pytest
```

The backend requires Supabase and JWT settings at startup. Never copy real `.env` values into this file or any other documentation. The backend serves OpenAPI at `/docs` when running.

## Where to look first

| Concern | Main files |
|---|---|
| API setup and route mounting | `insurance-pro/backend/app/main.py`, `app/api/v1/__init__.py` |
| Auth, roles, and settings | `insurance-pro/backend/app/core/`, `app/api/v1/auth*.py` |
| Claim and agent operations | `insurance-pro/backend/app/api/v1/claims.py`, `agent.py` |
| Evidence uploads | `insurance-pro/backend/app/api/v1/storage.py`, `app/db/supabase.py` |
| Damage and fraud analysis | `insurance-pro/backend/app/services/ai_runner.py`, `fraud_analysis_service.py` |
| Database definitions | `insurance-pro/backend/schema.sql`, `migration_v2.sql`, `migration_v3_phash.sql` |
| Integrated frontend API client | `insurance-pro/frontend/ClaimPilot/src/services/` |
| Integrated frontend routes and pages | `insurance-pro/frontend/ClaimPilot/src/routes/`, `src/pages/` |
| Separate research pipeline | `ml/scripts/`, `ml/run_local_pipeline.py` |
