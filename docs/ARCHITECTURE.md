# Architecture — ClaimPilot AI


## Components (what exists today)

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | React + Vite (insurance-pro/frontend/ClaimPilot) | Single-page app with claim submission, dashboard, agent workbench, and 3D damage mesh viewer. |
| **Backend** | FastAPI (insurance-pro/backend) | REST API with JWT auth, OTP verification (email/SMS), claim CRUD, AI assessment triggers. |
| **Auth & DB** | Supabase (PostgreSQL + GoTrue + Storage) | Supabase Auth for user management, Row-Level Security, storage bucket `claim-evidence` for claim evidence. |
| **AI: Damage Detection** | YOLOv11m + RT-DETR (insurance-pro/backend/app/models/weights/) | YOLOv11m (39 MB) and RT-DETR (64 MB) weight files for vehicle damage detection. Inference runs as background task via `ai_runner.py`. |
| **Fraud Engine** | pHash similarity cross-claim check | Implemented with perceptual hashing for duplicate image detection. The `fraud_score` combines pHash matches, narrative-severity consistency, and claimant history. |
| **Narrative-Severity Check** | LLM-based text classification | Planned — no code or model exists yet. |
| **SMS Provider** | Fast2SMS (India) / Twilio | Both supported via config. Twilio uses `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`. Fast2SMS uses `FAST2SMS_API_KEY`. Falls back to console logging if neither configured. |
| **Email Provider** | SendGrid API + SMTP fallback | SendGrid via `SENDGRID_API_KEY`. SMTP via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`. Falls back to console logging if neither configured. |

## Data Flow: One Claim from Upload to Agent Decision

1. **Customer uploads** 2–3 damage photos via the React frontend → files posted to `POST /api/v1/claims` with multipart/form-data.
2. **Backend creates** a Claim row in Supabase PostgreSQL (table: `claims`), sets status to `pending_review`, and enqueues `trigger_ai_assessment()` as a FastAPI background task.
3. **AI inference** (`app/services/ai_runner.py`) downloads photos from Supabase Storage, runs YOLOv11m and RT-DETR on each image → generates bounding boxes + confidence scores → stored as JSON in `claim_ai_analysis` table.
4. **Fraud score calculation** uses pHash-based cross-claim image similarity detection, narrative-severity consistency checks, and claimant history analysis to compute a weighted score. Results are stored in the claims table as `fraud_score` and `risk_level`.
5. **Narrative-severity check** (planned) — no implementation exists yet.
6. **Agent reviews** the claim via the Agent Dashboard (`/agent/claims`) → sees AI results (bounding boxes, estimated costs), fraud_score, risk_level → clicks **Approve** or **Reject**.
7. **Agent action** calls `POST /api/v1/agent/claims/{claim_id}/action` → updates claim status, sends email notification via SMTP (Resend), and optionally triggers SMS via Fast2SMS.

## Mermaid Diagram

```mermaid
flowchart TD
    A[Customer uploads photos] --> B[POST /api/v1/claims]
    B --> C[Supabase DB: claims row created]
    C --> D[Background task: trigger_ai_assessment]
    D --> E[ai_runner.py downloads images]
    E --> F[YOLOv11m / RT-DETR inference]
    F --> G[Damage detection: bounding boxes, confidence]
    G --> H[Supabase: claim_ai_analysis row]
    H --> I[claims.fraud_score updated]
    I --> J[Agent Dashboard /agent/claims]
    J --> K{Approve/Reject/Request Info}
    K -- Approve --> L[POST /api/v1/agent/claims/{id}/action]
    K -- Reject --> M[POST /api/v1/agent/claims/{id}/action]
    K -- Request Info --> N[POST /api/v1/agent/claims/{id}/action]
    L --> O[Status: agent_approved]
    M --> P[Status: rejected]
    N --> Q[Status: info_requested]
    O --> R[SMTP email to customer]
    P --> R
    Q --> R
    style A fill:#e1f5fe,stroke:#0b5394
    style B fill:#e1f5fe,stroke:#0b5394
    style C fill:#e1f5fe,stroke:#0b5394
    style D fill:#e1f5fe,stroke:#0b5394
    style E fill:#e1f5fe,stroke:#0b5394
    style F fill:#e1f5fe,stroke:#0b5394
    style G fill:#e1f5fe,stroke:#0b5394
    style H fill:#e1f5fe,stroke:#0b5394
    style I fill:#e1f5fe,stroke:#0b5394
    style J fill:#e1f5fe,stroke:#0b5394
    style K fill:#e1f5fe,stroke:#0b5394
    style L fill:#c6e2ff,stroke:#0b5394
    style M fill:#c6e2ff,stroke:#0b5394
    style N fill:#c6e2ff,stroke:#0b5394
    style O fill:#c6e2ff,stroke:#0b5394
    style P fill:#c6e2ff,stroke:#0b5394
    style Q fill:#c6e2ff,stroke:#0b5394
    style R fill:#c6e2ff,stroke:#0b5394
```

## Planned / Not Yet Built


- **Narrative-severity check** — LLM-based text classification of claim descriptions to auto-assign severity levels; no code or model exists yet.
- **Containerized deployment** — Dockerfile exists for backend but no Docker Compose or Kubernetes manifests exist yet for full stack orchestration.
