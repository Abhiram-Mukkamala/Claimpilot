# ClaimPilot AI — Motor Insurance Claims Platform

**Note:** The following statements must be updated once `feat/fraud-port` merges: pHash fraud engine implementation status, Narrative-severity check implementation status.

**ClaimPilot** is an AI-powered motor insurance claims management system that connects policyholders with insurance adjusters to streamline claim filing, AI damage detection, and settlement approval. Built for a hackathon demo on Oct 24, 2026.

---

## Tech Stack

| Component | Technology | Details |
|---|---|---|
| **Backend** | FastAPI (Python 3.11+) | REST API with JWT auth, OTP verification, claim CRUD, AI assessment triggers |
| **Frontend** | React 19 + TypeScript + Vite | Single-page app with claim submission, dashboard, agent workbench, 3D damage mesh viewer |
| **Database & Auth** | Supabase | PostgreSQL database, GoTrue authentication, Storage for claim evidence |
| **AI/ML** | YOLOv11m, RT-DETR | Ultralytics models for vehicle damage detection from images |
| **Email** | SendGrid API + SMTP | Configurable via environment variables, falls back to console logging |
| **SMS** | Twilio + Fast2SMS | Both providers supported, configurable via environment variables |

---

## Project Structure

```
ClaimPilot/
├── insurance-pro/
│   ├── backend/          # FastAPI backend (port 8000)
│   │   ├── app/          # Application code
│   │   │   ├── api/      # API endpoints
│   │   │   ├── core/     # Configuration, security
│   │   │   ├── db/       # Supabase client
│   │   │   ├── models/   # ML weights
│   │   │   └── services/ # AI runner, email
│   │   ├── .env.example  # Backend environment template
│   │   ├── Dockerfile    # Backend container
│   │   └── requirements.txt
│   └── frontend/
│       └── ClaimPilot/   # React/Vite frontend (port 5173)
├── scripts/              # Demo scripts
│   ├── preflight.ps1     # Pre-demo validation
│   ├── start_demo.ps1    # Start all services
│   └── stop_demo.ps1     # Stop all services
└── docs/                 # Documentation
    ├── ARCHITECTURE.md    # System architecture
    ├── DEMO_RUNBOOK.md    # Demo execution guide
    └── SECURITY_SCAN.md    # Security audit findings
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Demo Launch (Recommended)

Run the one-command demo launcher:

```powershell
# From the repo root (wt-ops branch)
.\scripts\start_demo.ps1
```

This automatically:
1. Validates Python/Node versions
2. Checks required `.env` files and variables
3. Starts the FastAPI backend on port 8000
4. Builds and starts the React frontend on port 5173
5. Opens the browser to http://localhost:5173

To stop all services:

```powershell
.\scripts\stop_demo.ps1
```

### Manual Setup

#### Backend

```bash
# Create virtual environment
cd insurance-pro/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Required backend environment variables:**
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JWT_SECRET`

**Optional backend environment variables:**
- `SENDGRID_API_KEY` or `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `FAST2SMS_API_KEY`

#### Frontend

```bash
cd insurance-pro/frontend/ClaimPilot
npm ci
npm run dev
```

**Required frontend environment variables:**
- `VITE_API_BASE_URL=http://localhost:8000`

---

## Known Limitations

1. **pHash Fraud Engine** — Not yet implemented. The `fraud_score` field in claims uses a simple placeholder calculation (12 if < 5 damages, else 45) based on damage count, not actual perceptual hashing.

2. **Narrative-Severity Check** — LLM-based text classification of claim descriptions is planned but not yet built.

3. **Weight Files** — YOLOv11m (39 MB) and RT-DETR (64 MB) model files must be present in `insurance-pro/backend/app/models/weights/` for AI inference to work. These are large files and should be managed with Git LFS.

4. **Container Orchestration** — While a Dockerfile exists for the backend, there are no Docker Compose or Kubernetes manifests for full-stack containerized deployment.

5. **Email Fallback** — If neither SendGrid nor SMTP is configured, OTP codes and notifications print to the backend terminal instead of being sent to users.

6. **SMS Fallback** — If neither Twilio nor Fast2SMS is configured, SMS notifications fall back to console logging.

---

## Scripts

| Script | Description |
|---|---|
| `scripts/preflight.ps1` | Validates all prerequisites: Python/Node versions, .env files, required variable names, weight files, port availability, Supabase reachability |
| `scripts/start_demo.ps1` | One-command demo launcher — validates, starts backend and frontend, opens browser |
| `scripts/stop_demo.ps1` | Stops all processes started by `start_demo.ps1` |

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) — System components, data flow, and Mermaid diagrams
- [Demo Runbook](docs/DEMO_RUNBOOK.md) — Step-by-step guide for running the demo
- [Security Scan Results](docs/SECURITY_SCAN.md) — Findings and remediation steps
- [Large Files Report](docs/LARGE_FILES.md) — Files over 50 MB and Git LFS recommendations

---

## License

Hackathon demo project — code freeze Oct 20, 2026.
