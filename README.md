# ClaimPilot AI â€” Motor Insurance Claims Platform

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

## How It Works (Simple Workflow)

### 1. Customer Files a Claim (`/customer`)
- **Simple Stepper Form:** The customer enters vehicle details, incident location, policy info, and registration verification (HSRP, Engine/Chassis numbers, Driver's License photo).
- **Uploads Evidence:** The customer uploads multiple photos and video recordings of the vehicle damage.

### 2. AI Assessment & Customer Review
- **Instant Visual Breakdown:** The customer views their AI Damage Assessment (`/customer/claims/:id`), showing detected damage areas, severity badges, and estimated repair cost ranges.
- **Multi-Media Evidence Viewer:** The customer can click or tap through a gallery of all uploaded photos and watch uploaded video evidence to see how the AI evaluated their vehicle.

### 3. Agent Review & Adjudication (`/agent`)
- **Claims Queue:** The insurance agent sees new claims in a real-time queue with priority flags.
- **Deep Inspection:** The agent inspects damage bounding boxes, 3D deformation topology, AI surface normals, and a prototype fraud score (0–100, not a percentage) with a risk level.
  - The score combines three signals: cross-claim pHash image matching, narrative-versus-detected severity consistency, and—when claimant identity is available—whether the claimant has at least three claims in a rolling 183-day window.
  - An OpenAI classifier is optional and runs only when the OpenAI provider, API key, and client are available. Otherwise, or if the call fails, the narrative check uses a deterministic keyword fallback. The live OpenAI path is unverified.
  - The score supports human review. It is not proof of fraud and does not make autonomous claim decisions.
- **Adjudication:** The agent can **Approve** (setting a settlement amount), **Reject** (with justification notes), or **Request Information** from the customer.

### 4. Settlement & Finance Handoff
- **Client Response:** If approved, the customer receives the offer on their portal and can **Approve** or **Reject** the settlement offer.
- **Final Authorization:** When the customer approves, the agent sees the response live on their dashboard and clicks **"OK to Proceed"** to send the claim to the finance team for payment payout.

---

## Project Structure

```
ClaimPilot/
â”œâ”€â”€ insurance-pro/
â”‚   â”œâ”€â”€ backend/          # FastAPI backend (port 8000)
â”‚   â”‚   â”œâ”€â”€ app/          # Application code
â”‚   â”‚   â”‚   â”œâ”€â”€ api/      # API endpoints
â”‚   â”‚   â”‚   â”œâ”€â”€ core/     # Configuration, security
â”‚   â”‚   â”‚   â”œâ”€â”€ db/       # Supabase client
â”‚   â”‚   â”‚   â”œâ”€â”€ models/   # ML weights
â”‚   â”‚   â”‚   â””â”€â”€ services/ # AI runner, email
â”‚   â”‚   â”œâ”€â”€ .env.example  # Backend environment template
â”‚   â”‚   â”œâ”€â”€ Dockerfile    # Backend container
â”‚   â”‚   â””â”€â”€ requirements.txt
â”‚   â””â”€â”€ frontend/
â”‚       â””â”€â”€ ClaimPilot/   # React/Vite frontend (port 5173)
â”œâ”€â”€ scripts/              # Demo scripts
â”‚   â”œâ”€â”€ preflight.ps1     # Pre-demo validation
â”‚   â”œâ”€â”€ start_demo.ps1    # Start all services
â”‚   â””â”€â”€ stop_demo.ps1     # Stop all services
â””â”€â”€ docs/                 # Documentation
    â”œâ”€â”€ ARCHITECTURE.md    # System architecture
    â”œâ”€â”€ DEMO_RUNBOOK.md    # Demo execution guide
    â””â”€â”€ SECURITY_SCAN.md    # Security audit findings
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

1. **pHash Fraud Engine** â€” Implemented with cross-claim image similarity detection using perceptual hashing. Duplicate and near-duplicate images are flagged based on a configurable distance threshold. The `fraud_score` combines pHash duplicate detection, narrative-severity consistency checks, and claimant history analysis. Tested with automated unit tests.

2. **Narrative-Severity Check** â€” LLM-based text classification of claim descriptions is planned but not yet built.

3. **Weight Files** â€” YOLOv11m (39 MB) and RT-DETR (64 MB) model files must be present in `insurance-pro/backend/app/models/weights/` for AI inference to work. These are large files and should be managed with Git LFS.

4. **Container Orchestration** â€” While a Dockerfile exists for the backend, there are no Docker Compose or Kubernetes manifests for full-stack containerized deployment.

5. **Email Fallback** â€” If neither SendGrid nor SMTP is configured, OTP codes and notifications print to the backend terminal instead of being sent to users.

6. **SMS Fallback** â€” If neither Twilio nor Fast2SMS is configured, SMS notifications fall back to console logging.

---

## Scripts

| Script | Description |
|---|---|
| `scripts/preflight.ps1` | Validates all prerequisites: Python/Node versions, .env files, required variable names, weight files, port availability, Supabase reachability |
| `scripts/start_demo.ps1` | One-command demo launcher â€” validates, starts backend and frontend, opens browser |
| `scripts/stop_demo.ps1` | Stops all processes started by `start_demo.ps1` |

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) â€” System components, data flow, and Mermaid diagrams
- [Demo Runbook](docs/DEMO_RUNBOOK.md) â€” Step-by-step guide for running the demo
- [Security Scan Results](docs/SECURITY_SCAN.md) â€” Findings and remediation steps
- [Large Files Report](docs/LARGE_FILES.md) â€” Files over 50 MB and Git LFS recommendations

---

## License

Hackathon demo project â€” code freeze Oct 20, 2026.
