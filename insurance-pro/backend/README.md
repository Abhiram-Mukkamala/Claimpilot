# ClaimPilot AI — Backend Architecture & Integration Guide

> **FastAPI + Supabase + YOLOv11 / RT-DETR** — Production-grade motor insurance claim adjudication platform with dual-channel OTP, AI vision damage assessment, and agent workflow state machine.

| Stack Layer | Technology | Purpose |
|---|---|---|
| **Runtime** | Python 3.11+, FastAPI 0.110+ | Async API server with Pydantic v2 validation |
| **Database** | Supabase (PostgreSQL 15) | Auth, PostgREST, Row-Level Security, Storage |
| **AI Pipeline** | YOLOv11m, RT-DETR | Real-time vehicle damage detection & bounding box extraction |
| **Email** | Resend SMTP (`smtp.resend.com`) | OTP delivery, agent approval/rejection notifications |
| **SMS** | Twilio / Fast2SMS | Dual-channel OTP verification for Indian phone numbers |
| **Auth** | JWT (HS256) via `python-jose` | Stateless Bearer token auth with RBAC role enforcement |

---

## Table of Contents

1. [Repository Structure](#1-repository-structure)
2. [Quick Start](#2-quick-start)
3. [Environment Configuration](#3-environment-configuration)
4. [API Endpoints Reference](#4-api-endpoints-reference)
5. [Local Backend Code Updates — Policy-Based Agent Routing](#5-local-backend-code-updates--policy-based-agent-routing)
6. [Database Schema & Constraints](#6-database-schema--constraints)
7. [Dynamic OTP Verification & Provider Setup](#7-dynamic-otp-verification--provider-setup)
8. [Frontend Integration & Logic Migration Specification](#8-frontend-integration--logic-migration-specification)

---

## 1. Repository Structure

```
backend/
├── .env                          # Active environment variables (DO NOT COMMIT)
├── .env.example                  # Template for teammate onboarding
├── requirements.txt              # Python dependencies (fastapi, supabase, ultralytics, etc.)
├── schema.sql                    # Full Supabase DDL: tables, enums, indices
├── migration_v2.sql              # Incremental migration: OTP table, column additions
│
└── app/
    ├── __init__.py               # Package marker
    ├── main.py                   # FastAPI app factory: CORS, exception handlers, router mounts
    │
    ├── core/                     # Cross-cutting infrastructure
    │   ├── __init__.py
    │   ├── config.py             # Pydantic Settings: env parsing, CORS origins, JWT config
    │   └── security.py           # JWT encode/decode, get_current_user(), require_roles() RBAC
    │
    ├── db/                       # Database access layer
    │   ├── __init__.py
    │   └── supabase.py           # AsyncSupabaseDB: httpx-based PostgREST client + signed upload URLs
    │
    ├── api/                      # Versioned API routers
    │   ├── __init__.py
    │   └── v1/
    │       ├── __init__.py       # Router aggregator: mounts all sub-routers onto api_v1_router
    │       ├── auth.py           # POST /auth/register, GET /auth/me
    │       ├── auth_otp.py       # POST /auth/otp/send, POST /auth/otp/verify (Email + SMS)
    │       ├── claims.py         # Claims CRUD: create, list, detail, ai-analysis, settlement
    │       ├── agent.py          # Agent workbench: queue, detail, action (approve/reject/request)
    │       └── storage.py        # Presigned upload URLs, evidence catalog registration
    │
    ├── schemas/                  # Pydantic request/response DTOs
    │   ├── __init__.py
    │   └── claim.py              # UserRole, ClaimType, ClaimStatus, ClaimCreate, AgentActionRequest, etc.
    │
    ├── services/                 # Business logic & external integrations
    │   ├── __init__.py
    │   ├── ai_runner.py          # YOLOv11 + RT-DETR inference pipeline, damage cost estimation
    │   └── email.py              # Async SMTP dispatch: OTP, approval, rejection, info-request emails
    │
    └── models/
        └── weights/              # AI model weight files (yolov11m.pt, rt-detr.pt)
```

### Key Architectural Decisions

| Decision | Rationale |
|---|---|
| **httpx `AsyncSupabaseDB`** instead of sync Supabase SDK | The official `supabase-py` client is synchronous. Our custom `AsyncSupabaseDB` in `db/supabase.py` uses `httpx.AsyncClient` to hit the PostgREST API directly, guaranteeing non-blocking I/O inside FastAPI's async workers. |
| **Background AI tasks** via `BackgroundTasks` | `trigger_ai_assessment()` runs YOLO/RT-DETR inference after claim creation without blocking the HTTP response. The frontend polls `GET /claims/{id}/ai-analysis` until results appear. |
| **JWT issued by backend** (not Supabase Auth tokens) | We use `python-jose` to mint our own JWTs after registration/OTP verification. This decouples our auth flow from Supabase's GoTrue tokens and gives us full control over claims payload (`role`, `email`, `name`). |
| **Dual OTP channels** (Email + SMS) | Indian market compliance requires SMS fallback. The `auth_otp.py` router dispatches to Resend SMTP or Twilio/Fast2SMS based on the `channel` field. |

---

## 2. Quick Start

```bash
# 1. Clone and enter the backend directory
cd backend

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment template and fill in your Supabase credentials
cp .env.example .env
# Edit .env with your SUPABASE_URL, keys, SMTP credentials, etc.

# 5. Run database migrations in Supabase SQL Editor
# Paste contents of schema.sql → then migration_v2.sql

# 6. Start the dev server
uvicorn app.main:app --reload --reload-exclude "venv/*" --port 8000
```

The API will be live at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 3. Environment Configuration

### `.env.example`

```env
# ══════════════════════════════════════════════════════
# ClaimPilot Backend Environment Configuration
# ══════════════════════════════════════════════════════

# ── Supabase Credentials ─────────────────────────────
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_ANON_KEY="YOUR_VALUE_HERE"
SUPABASE_SERVICE_ROLE_KEY="YOUR_VALUE_HERE"
SUPABASE_STORAGE_BUCKET="claim-evidence"

# ── JWT Configuration ────────────────────────────────
JWT_SECRET="YOUR_VALUE_HERE"
JWT_ALGORITHM="HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440          # 24 hours

# ── Frontend & CORS ─────────────────────────────────
FRONTEND_URL="http://localhost:5173"
CORS_ORIGINS="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

# ── Email Configuration (Resend SMTP) ────────────────
SMTP_HOST="smtp.resend.com"
SMTP_PORT=587
SMTP_USER="resend"
SMTP_PASSWORD="YOUR_VALUE_HERE"       # Resend API Key as SMTP password
SMTP_FROM_EMAIL="onboarding@resend.dev"       # Resend sandbox sender (free tier)
SMTP_FROM_NAME="ClaimPilot"
SUPPORT_EMAIL="your-email@gmail.com"

# ── SMS Configuration (Choose ONE provider) ──────────
# Option A: Twilio
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""
TWILIO_PHONE_NUMBER=""

# Option B: Fast2SMS (India-only)
FAST2SMS_API_KEY=""

# ── OTP Security ─────────────────────────────────────
OTP_EXPIRE_MINUTES=10
MAX_OTP_ATTEMPTS=3
```

### Variable Resolution Priority

`config.py` uses `pydantic-settings` which resolves in this order:

1. **OS environment variables** (highest priority — use in Docker/CI)
2. **`.env` file** in the `backend/` working directory
3. **Field defaults** in `Settings` class (fallback)

---

## 4. API Endpoints Reference

> **Base URL:** `http://localhost:8000/api/v1`
>
> **Auth Header:** `Authorization: Bearer <jwt_access_token>` (required on all protected routes)

---

### 4.1 Authentication & User Management

#### `POST /api/v1/auth/register`

Create a new customer or agent account. Inserts into Supabase `auth.users` + `public.profiles`.

| Field | Details |
|---|---|
| **Auth Required** | ❌ No |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "full_name": "Rahul Sutar",
  "email": "rahul@example.com",
  "phone_number": "+919876543210",
  "dob": "1998-06-15",
  "role": "customer",
  "password": "securePass123"
}
```

| Field | Type | Validation |
|---|---|---|
| `full_name` | `string` | Required |
| `email` | `string` | Required, unique in `profiles` |
| `phone_number` | `string` | Required, unique, E.164 format |
| `dob` | `date` (ISO 8601) | Required |
| `role` | `enum` | `"customer"` \| `"agent"` \| `"admin"` |
| `password` | `string` | Required, min 6 chars |

**Success Response (201):**

```json
{
  "message": "User registered successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-v4",
    "full_name": "Rahul Sutar",
    "email": "rahul@example.com",
    "phone_number": "+919876543210",
    "dob": "1998-06-15",
    "role": "customer"
  }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `409` | Email already registered in `profiles` or `auth.users` |
| `400` | Supabase Auth creation failure (weak password, etc.) |
| `500` | Profile DB insert failed (auth user is rolled back) |

---

#### `GET /api/v1/auth/me`

Retrieve the authenticated user's profile from `public.profiles`.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |

**Success Response (200):**

```json
{
  "id": "uuid-v4",
  "full_name": "Rahul Sutar",
  "email": "rahul@example.com",
  "phone_number": "+919876543210",
  "dob": "1998-06-15",
  "role": "customer",
  "is_email_verified": true,
  "is_phone_verified": false,
  "created_at": "2026-09-28T14:30:00Z",
  "updated_at": "2026-09-28T14:30:00Z"
}
```

---

### 4.2 Dual OTP Authentication (Email & SMS)

#### `POST /api/v1/auth/otp/send`

Dispatch a 6-digit OTP to the user's email or phone number.

| Field | Details |
|---|---|
| **Auth Required** | ❌ No |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "identifier": "rahul@example.com",
  "channel": "email"
}
```

| Field | Type | Validation |
|---|---|---|
| `identifier` | `string` | Email address or E.164 phone (`+919876543210`) |
| `channel` | `enum` | `"email"` \| `"sms"` |

**Success Response (200):**

```json
{
  "message": "6-digit verification code dispatched via EMAIL.",
  "identifier": "rahul@example.com",
  "channel": "email",
  "expires_in_minutes": 10
}
```

**Backend Dispatch Flow:**

```
channel == "email"  →  send_otp_via_email()  →  _dispatch_email() via aiosmtplib
channel == "sms"    →  send_otp_via_sms()    →  Twilio REST API / Fast2SMS / Console mock
```

---

#### `POST /api/v1/auth/otp/verify`

Verify the 6-digit OTP. On success, issues a JWT access token and auto-creates a profile if the user doesn't exist yet.

| Field | Details |
|---|---|
| **Auth Required** | ❌ No |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "identifier": "rahul@example.com",
  "otp_code": "482916"
}
```

**Success Response (200):**

```json
{
  "message": "Identity successfully verified.",
  "is_verified": true,
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-v4",
    "full_name": "Rahul Sutar",
    "email": "rahul@example.com",
    "role": "customer",
    "is_email_verified": true
  }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Invalid OTP code (includes `attempts_remaining` count) |
| `400` | No active OTP found or code expired |
| `429` | Maximum 3 verification attempts exceeded |

---

### 4.3 Claims Submission & Evidence Processing

#### `POST /api/v1/claims`

Submit a new insurance claim. Triggers background AI assessment via `trigger_ai_assessment()`.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "incident_type": "Accident",
  "vehicle_name": "Maruti Suzuki Swift ZXi",
  "policy_number": "POL-M-847201",
  "hsrp_number": "MH12DE1433",
  "engine_number": "K12MN7654321",
  "chassis_number": "MA3FJEB1S00123456",
  "incident_date": "2026-09-25",
  "location_address": "Mumbai-Pune Expressway, KM 42",
  "location_city": "Pune",
  "location_state": "Maharashtra",
  "pincode": "411001",
  "description": "Rear-end collision at highway toll booth during heavy rain",
  "driver_name": "Rahul Sutar",
  "driver_dl_number": "MH0220180012345",
  "claimed_amount": 45000.00
}
```

| Field | Type | Validation |
|---|---|---|
| `incident_type` | `enum` | `"Accident"` \| `"Theft"` \| `"Fire"` \| `"Natural Event"` |
| `vehicle_name` | `string` | 2–100 chars |
| `policy_number` | `string` | 3–100 chars |
| `hsrp_number` | `string` | 4–20 chars |
| `engine_number` | `string` | 4–50 chars |
| `chassis_number` | `string` | 4–50 chars |
| `incident_date` | `date` | Cannot be in the future |
| `location_address` | `string` | Min 5 chars |
| `description` | `string` | Max 500 chars |
| `driver_name` | `string` | 2–255 chars |
| `driver_dl_number` | `string` | Regex: `^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$` (e.g. `MH0220180012345`) |
| `claimed_amount` | `float` | Optional, defaults to `0.00` |

**Success Response (201):**

```json
{
  "message": "Claim filed successfully. AI damage assessment initiated.",
  "claim_id": "uuid-v4",
  "claim_number": "CLM-2026-48271",
  "status": "pending_review",
  "claim": { "...full claim object..." }
}
```

> **⚠️ NOTE:** The backend currently does **not** perform policy-based agent routing on claim creation. See [Section 5](#5-local-backend-code-updates--policy-based-agent-routing) for required code changes.

---

#### `GET /api/v1/claims`

List all claims belonging to the authenticated customer.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |

**Success Response (200):**

```json
{
  "claims": [
    {
      "id": "uuid-v4",
      "claim_number": "CLM-2026-48271",
      "status": "under_review",
      "vehicle_name": "Maruti Suzuki Swift ZXi",
      "incident_type": "Accident",
      "created_at": "2026-09-28T14:30:00Z",
      "...other fields..."
    }
  ]
}
```

---

#### `GET /api/v1/claims/{claim_id}`

Fetch full claim details including evidence list and AI analysis results.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **Access Control** | Claim owner, or user with role `agent`/`admin` |

**Success Response (200):**

```json
{
  "claim": { "...full claim object..." },
  "evidence": [
    {
      "id": "uuid-v4",
      "claim_id": "uuid-v4",
      "file_url": "https://...supabase.co/storage/v1/object/public/claim-evidence/evidence/photo/...",
      "file_type": "image/jpeg",
      "category": "photo"
    }
  ],
  "ai_analysis": { "...or null if still processing..." }
}
```

---

#### `GET /api/v1/claims/{claim_id}/ai-analysis`

Retrieve itemized YOLO/RT-DETR damage detection results for a specific claim.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |

**Success Response (200):**

```json
{
  "id": "uuid-v4",
  "claim_id": "uuid-v4",
  "detected_damages": [
    {
      "id": "dmg_yolo_1",
      "type": "Front Bumper Dent",
      "part": "Front Bumper",
      "damage_type": "Deep Deformation & Fracture",
      "severity": "Severe",
      "confidence": 0.91,
      "location": "Panel Area 1",
      "repair_action": "Replacement",
      "estimated_cost": 5500.00,
      "boundingBox": {
        "x": 25.0,
        "y": 30.0,
        "width": 45.0,
        "height": 35.0
      }
    }
  ],
  "estimated_cost_min": 4675.00,
  "estimated_cost_max": 6325.00,
  "clahe_image_url": "https://...supabase.co/storage/.../evidence_0.jpg",
  "segmentation_masks": {
    "mask_count": 1,
    "polygon_density": 0.78,
    "primary_impact_zone": "front_quarter"
  },
  "surface_area_px": 142850,
  "relative_deformation_z": {
    "max_indentation_mm": 42.5,
    "structural_compromise": false
  },
  "dsine_vectors": {
    "normal_variance": 0.18,
    "surface_gradient_continuity": 0.86
  },
  "fraud_flags": []
}
```

**Bounding Box Coordinate System:**

| Field | Unit | Description |
|---|---|---|
| `x` | `%` | Left offset from image origin as percentage of image width |
| `y` | `%` | Top offset from image origin as percentage of image height |
| `width` | `%` | Box width as percentage of image width |
| `height` | `%` | Box height as percentage of image height |

> Percentage-based coordinates allow frontend rendering at any display resolution without pixel recalculation.

---

### 4.4 Customer Settlement Decisions

#### `POST /api/v1/claims/portal/decision`

Customer accepts or disputes the settlement offered after agent approval.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "claim_id": "uuid-v4",
  "decision": "ACCEPT",
  "dispute_notes": null
}
```

| Field | Type | Values |
|---|---|---|
| `decision` | `enum` | `"ACCEPT"` \| `"REJECT"` \| `"DISPUTE"` |
| `dispute_notes` | `string?` | Required when decision is `REJECT` or `DISPUTE` |

**Accept Response (200):**

```json
{
  "status": "success",
  "decision": "ACCEPT",
  "new_status": "settlement_accepted",
  "payout_pipeline": {
    "payout_status": "initiated",
    "batch_id": "PAY-BAT-A1B2C3D4",
    "disbursement_channel": "Direct Bank Account / UPI",
    "estimated_settlement_hours": 24
  }
}
```

**Dispute Response (200):**

```json
{
  "status": "disputed",
  "decision": "DISPUTE",
  "new_status": "disputed",
  "priority": "HIGH_PRIORITY_REQUEUE",
  "support_contact": {
    "support_email": "support@claimpilot.com",
    "phone_number": "+91 (800) 252-4674",
    "desk_hours": "24/7 Priority Dispute Assistance"
  }
}
```

---

### 4.5 Storage & Evidence Uploads

#### `POST /api/v1/storage/presigned-url`

Generate a direct client-to-Supabase signed upload URL. Allows the frontend to stream files up to 100 MB directly to Supabase Storage without routing through the backend.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "file_name": "damage_photo_front.jpg",
  "file_type": "image/jpeg",
  "category": "photo",
  "file_size_bytes": 2456789
}
```

| Field | Type | Validation |
|---|---|---|
| `category` | `enum` | `"photo"` \| `"walkaround_video"` \| `"dl_front"` \| `"dl_back"` |
| `file_size_bytes` | `int` | Max 104,857,600 (100 MB) |

**Success Response (200):**

```json
{
  "upload_url": "https://...supabase.co/storage/v1/object/upload/sign/claim-evidence/evidence/photo/...",
  "file_path": "evidence/photo/user-uuid/1696000000_abc123_damage_photo_front.jpg",
  "public_url": "https://...supabase.co/storage/v1/object/public/claim-evidence/evidence/photo/...",
  "expires_in_seconds": 900,
  "category": "photo"
}
```

**Evidence Quantity Limits Per Claim:**

| Category | Max Count |
|---|---|
| `photo` | 10 |
| `walkaround_video` | 2 |
| `dl_front` | 1 |
| `dl_back` | 1 |

---

#### `POST /api/v1/storage/evidence`

Register uploaded evidence in the `claim_evidence` catalog table. Triggers AI assessment when a `photo` category item is cataloged.

**Request Body:**

```json
{
  "claim_id": "uuid-v4",
  "file_url": "https://...supabase.co/storage/v1/object/public/claim-evidence/evidence/photo/...",
  "storage_path": "evidence/photo/user-uuid/1696000000_abc123_damage.jpg",
  "file_type": "image/jpeg",
  "category": "photo"
}
```

---

### 4.6 Agent Adjudication Workbench

#### `GET /api/v1/agent/claims`

Fetch the agent's claim adjudication queue with optional triage filters.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **RBAC** | Requires role `agent` or `admin` |

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `status` | `string?` | Filter by claim status (e.g. `pending_review`) |
| `risk` | `string?` | Filter by risk level (e.g. `High Risk`) |
| `search` | `string?` | Search across `claim_number`, `policy_number`, `driver_name` |
| `limit` | `int` | Max results, 1–100, default 50 |

**Success Response (200):**

```json
{
  "count": 12,
  "claims": [ "...array of claim objects..." ]
}
```

---

#### `GET /api/v1/agent/claims/{claim_id}`

Deep investigation view: claim + claimant profile + evidence + AI analysis.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **RBAC** | Requires role `agent` or `admin` |

**Success Response (200):**

```json
{
  "claim": { "...full claim object..." },
  "claimant": { "...profile of claim owner..." },
  "evidence": [ "...evidence array..." ],
  "ai_analysis": { "...AI results or null..." }
}
```

---

#### `POST /api/v1/agent/claims/{claim_id}/action`

Execute an agent adjudication action. This is the **workflow state machine** endpoint.

| Field | Details |
|---|---|
| **Auth Required** | ✅ Bearer Token |
| **RBAC** | Requires role `agent` or `admin` |
| **Content-Type** | `application/json` |

**Request Body (Approve):**

```json
{
  "action": "APPROVE"
}
```

**Request Body (Reject):**

```json
{
  "action": "REJECT",
  "reason": "Evidence photos show pre-existing damage inconsistent with reported incident date."
}
```

**Request Body (Request Info):**

```json
{
  "action": "REQUEST_INFO",
  "requested_items": ["dashcam_footage", "police_fir_copy", "repair_estimate_quote"],
  "custom_notes": "Please provide the FIR copy from the nearest police station."
}
```

**Action Validation Rules:**

| Action | Required Fields | Terminal State Guard |
|---|---|---|
| `APPROVE` | None | Cannot modify `settlement_accepted` or `rejected` claims |
| `REJECT` | `reason` (min 5 chars) | Cannot modify `settlement_accepted` or `rejected` claims |
| `REQUEST_INFO` | `requested_items` (min 1 item) | Cannot modify `settlement_accepted` or `rejected` claims |

**State Transition Diagram:**

```
pending_review ──→ under_review (auto, after AI completes)
under_review ────→ agent_approved (APPROVE action)
under_review ────→ rejected (REJECT action)
under_review ────→ action_required (REQUEST_INFO action)
action_required ─→ agent_approved / rejected (after re-review)
agent_approved ──→ settlement_accepted (customer ACCEPT)
agent_approved ──→ disputed (customer DISPUTE/REJECT)
```

**Email Side-Effects:**

| Action | Email Sent To Customer |
|---|---|
| `APPROVE` | Settlement confirmation with magic link + cost bounds |
| `REJECT` | Formal rejection notice with logged reason |
| `REQUEST_INFO` | Evidence upload portal link with 72-hour magic token |

---

## 5. Local Backend Code Updates — Policy-Based Agent Routing

> **Status:** The Supabase `policies` table has been created in the SQL Editor, but the local Python codebase has **not** been updated to perform policy lookups during claim creation. The following changes must be applied.

### 5.1 Database Context (Already Applied in Supabase)

The `policies` table was created with this structure:

```sql
CREATE TABLE IF NOT EXISTS public.policies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  policy_number VARCHAR(100) UNIQUE NOT NULL,
  holder_name VARCHAR(255),
  assigned_agent_id UUID REFERENCES public.profiles(id),
  vehicle_name VARCHAR(100),
  coverage_type VARCHAR(50) DEFAULT 'comprehensive',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed a demo policy for testing
INSERT INTO public.policies (policy_number, holder_name, assigned_agent_id, vehicle_name)
VALUES ('POL-M-847201', 'Demo Policyholder', NULL, 'Maruti Suzuki Swift ZXi');
```

### 5.2 Required Code Changes in `app/api/v1/claims.py`

Apply the following diff to add policy lookup + agent assignment logic to the `create_claim` endpoint:

```diff
  @router.post(
      "",
      response_model=Dict[str, Any],
      status_code=status.HTTP_201_CREATED,
      summary="Submit a new insurance claim"
  )
  async def create_claim(
      payload: ClaimCreate,
      background_tasks: BackgroundTasks,
      user: Dict[str, Any] = Depends(get_current_user)
  ):
      user_id = user.get("user_id") or user.get("id") or user.get("sub")
      claim_id = str(uuid.uuid4())
      claim_number = generate_claim_number()
      timestamp = datetime.now(timezone.utc).isoformat()

+     # ── Policy Lookup & Agent Assignment ────────────────────
+     policy_number = payload.policy_number or "POL-M-847201"
+     assigned_agent_id = None
+
+     try:
+         policy_record = await db.select(
+             "policies",
+             params={"policy_number": f"eq.{policy_number}", "is_active": "eq.true"},
+             single=True
+         )
+         if policy_record:
+             assigned_agent_id = policy_record.get("assigned_agent_id")
+         else:
+             # Fallback: try default demo policy
+             fallback_policy = await db.select(
+                 "policies",
+                 params={"policy_number": "eq.POL-M-847201"},
+                 single=True
+             )
+             if fallback_policy:
+                 assigned_agent_id = fallback_policy.get("assigned_agent_id")
+                 policy_number = "POL-M-847201"
+     except Exception as policy_err:
+         import logging
+         logging.getLogger("claimpilot.claims").warning(
+             f"Policy lookup failed for '{policy_number}': {policy_err}. "
+             f"Proceeding without agent assignment."
+         )
+     # ── End Policy Lookup ────────────────────────────────────

      claim_dict = {
          "id": claim_id,
          "claim_number": claim_number,
          "user_id": user_id,
          "incident_type": payload.incident_type.value,
          "vehicle_name": payload.vehicle_name,
-         "policy_number": payload.policy_number,
+         "policy_number": policy_number,
+         "assigned_agent_id": assigned_agent_id,
          "hsrp_number": payload.hsrp_number,
          # ...rest of claim_dict unchanged...
      }
```

### 5.3 Required Schema Update in `app/schemas/claim.py`

Make `policy_number` optional so the frontend can omit it during early testing:

```diff
  class ClaimCreate(BaseModel):
      incident_type: ClaimType
      vehicle_name: str = Field(..., min_length=2, max_length=100)
-     policy_number: str = Field(..., min_length=3, max_length=100)
+     policy_number: Optional[str] = Field(None, max_length=100)
      hsrp_number: str = Field(..., min_length=4, max_length=20)
```

### 5.4 Optional: New Policy Verification Endpoint

Add a new file `app/api/v1/policies.py` for frontend policy lookup:

```python
# app/api/v1/policies.py
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any

from app.core.security import get_current_user
from app.db.supabase import db

router = APIRouter(prefix="/policies", tags=["Policy Verification"])


@router.get(
    "/{policy_number}",
    summary="Verify policy and retrieve assigned agent"
)
async def verify_policy(
    policy_number: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    policy = await db.select(
        "policies",
        params={
            "policy_number": f"eq.{policy_number}",
            "is_active": "eq.true"
        },
        single=True
    )

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"No active policy found for '{policy_number}'",
                "policy_number": policy_number
            }
        )

    # Optionally fetch agent profile
    agent_profile = None
    if policy.get("assigned_agent_id"):
        agent_profile = await db.select(
            "profiles",
            params={"id": f"eq.{policy['assigned_agent_id']}"},
            single=True
        )

    return {
        "policy": policy,
        "assigned_agent": agent_profile,
        "is_active": policy.get("is_active", True)
    }
```

Register the router in `app/api/v1/__init__.py`:

```diff
  from app.api.v1.storage import router as storage_router
+ from app.api.v1.policies import router as policies_router

  api_v1_router.include_router(storage_router)
+ api_v1_router.include_router(policies_router)
```

---

## 6. Database Schema & Constraints

### Tables Overview

| Table | Purpose | Key Constraints |
|---|---|---|
| `profiles` | User profiles (extends `auth.users`) | `id` FK → `auth.users(id)` ON DELETE CASCADE, `email` UNIQUE, `phone_number` UNIQUE |
| `otp_verifications` | OTP lifecycle (email + SMS) | Auto-generated UUID PK, `expires_at` enforced in application code |
| `claims` | Insurance claim records | `claim_number` UNIQUE, `user_id` FK → `profiles`, `assigned_agent_id` FK → `profiles` (nullable) |
| `claim_evidence` | Uploaded media catalog | `claim_id` FK → `claims` ON DELETE CASCADE, `storage_path` NOT NULL |
| `claim_ai_analysis` | AI damage assessment results | `claim_id` FK → `claims` ON DELETE CASCADE **UNIQUE** (one analysis per claim) |
| `policies` | Policy → Agent mapping | `policy_number` UNIQUE, `assigned_agent_id` FK → `profiles` (nullable) |

### Claim Status Lifecycle

```
┌─────────────────┐
│  pending_review  │ ← Initial state on claim creation
└────────┬────────┘
         │ (AI assessment completes)
         ▼
┌─────────────────┐
│  under_review    │ ← Agent can now act
└────────┬────────┘
         │
    ┌────┼────────────────────┐
    │    │                    │
    ▼    ▼                    ▼
┌───────────┐  ┌──────────┐  ┌─────────────────┐
│ agent_    │  │ rejected │  │ action_required  │
│ approved  │  │ (terminal│  │ (re-upload loop) │
└────┬──────┘  └──────────┘  └────────┬────────┘
     │                                │
     ├──────────┐                     │ (agent re-reviews)
     │          │                     └──→ back to under_review
     ▼          ▼
┌──────────┐  ┌──────────┐
│settlement│  │ disputed │
│_accepted │  │ (re-queue│
│(terminal)│  │ HIGH PRI)│
└──────────┘  └──────────┘
```

### PostgreSQL ENUMs

```sql
-- user_role:    'customer' | 'agent' | 'admin'
-- claim_type:   'Accident' | 'Theft' | 'Fire' | 'Natural Event'
-- claim_status: 'pending_review' | 'under_review' | 'flagged' | 'action_required'
--               | 'agent_approved' | 'settlement_accepted' | 'disputed' | 'rejected'
```

### Performance Indices

```sql
CREATE INDEX idx_claims_user_id          ON public.claims(user_id);
CREATE INDEX idx_claims_status           ON public.claims(status);
CREATE INDEX idx_claims_assigned_agent   ON public.claims(assigned_agent_id);
CREATE INDEX idx_claim_evidence_claim_id ON public.claim_evidence(claim_id);
CREATE INDEX idx_otp_identifier          ON public.otp_verifications(identifier);
CREATE INDEX idx_otp_expires_at          ON public.otp_verifications(expires_at);
```

---

## 7. Dynamic OTP Verification & Provider Setup

This section guides teammates through setting up **real** OTP delivery so that verification codes arrive at their personal email addresses and phone numbers during development.

---

### 7.1 Email Verification — Resend SMTP Setup

#### Step 1: Create a Resend Account

1. Navigate to [https://resend.com](https://resend.com) and sign up with your GitHub account.
2. After onboarding, you'll land on the Resend dashboard.

#### Step 2: Generate an API Key

1. Go to **Settings → API Keys → Create API Key**.
2. Name it `claimpilot-dev` and grant **Full Access** (sending permission).
3. Copy the key — it looks like: `re_YOUR_RESEND_API_KEY_HERE`.

#### Step 3: Configure Sender Identity

**Option A — Sandbox Mode (Free Tier, No Domain Required):**

Use Resend's built-in sandbox sender. Emails are sent from `onboarding@resend.dev` and can be received at **any** email address.

```env
SMTP_FROM_EMAIL="onboarding@resend.dev"
```

> ⚠️ Sandbox emails may land in spam. Add `resend.dev` to your safe senders list.

**Option B — Custom Domain (Production):**

1. In Resend Dashboard → **Domains → Add Domain**.
2. Add your domain (e.g., `claimpilot.com`).
3. Add the DNS records Resend provides (MX, SPF, DKIM).
4. After verification, update:

```env
SMTP_FROM_EMAIL="notifications@claimpilot.com"
```

#### Step 4: Set Environment Variables

```env
SMTP_HOST="smtp.resend.com"
SMTP_PORT=587
SMTP_USER="resend"
SMTP_PASSWORD="YOUR_VALUE_HERE"   # Your API key
SMTP_FROM_EMAIL="onboarding@resend.dev"
SMTP_FROM_NAME="ClaimPilot"
SUPPORT_EMAIL="your-email@gmail.com"
```

#### Step 5: Understanding the Backend Email Routing Logic

The email dispatch chain lives in `app/services/email.py`:

```
_dispatch_email(to_email, subject, html_body, plain_body)
  │
  ├─ If SMTP_FROM_EMAIL == "onboarding@resend.dev":
  │    └─ DEV OVERRIDE: Redirects ALL recipients to SUPPORT_EMAIL
  │       (ensures you receive every test email at your personal inbox)
  │
  ├─ If SMTP_HOST != "smtp.claimpilot.internal" (real SMTP configured):
  │    └─ Sends via aiosmtplib with TLS (certifi CA bundle)
  │
  └─ Else (no SMTP configured):
       └─ Prints formatted mock email to server console (stdout)
```

**Key behavior for developers:** When using the Resend sandbox sender (`onboarding@resend.dev`), the backend **automatically redirects** all outgoing emails to the address in `SUPPORT_EMAIL`. This means:

- Register with any email → the OTP arrives at **your** inbox (`SUPPORT_EMAIL`)
- Agent approval/rejection emails → delivered to **your** inbox
- To test with multiple recipients, change `SUPPORT_EMAIL` per session

To **disable** this redirect and send to actual recipient addresses, switch to a custom verified domain sender.

---

### 7.2 SMS Verification — Twilio Setup

#### Step 1: Create a Twilio Account

1. Go to [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio) and create a free trial account.
2. Verify your personal phone number during signup (this becomes your first verified number).

#### Step 2: Get Your Credentials

From the Twilio Console dashboard, copy:

- **Account SID:** `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Auth Token:** `your_auth_token`

#### Step 3: Get a Twilio Phone Number

1. Go to **Phone Numbers → Manage → Buy a Number**.
2. Select a number with SMS capability (trial accounts get one free number).
3. Copy the number in E.164 format: `+1234567890`.

#### Step 4: Verify Trial Recipients

> ⚠️ **Twilio trial accounts can only send SMS to verified phone numbers.**

1. Go to **Phone Numbers → Manage → Verified Caller IDs**.
2. Add each team member's phone number and complete the verification call/SMS.

#### Step 5: Set Environment Variables

```env
TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN="your_auth_token"
TWILIO_PHONE_NUMBER="+1234567890"
```

#### SMS Provider Priority in Backend

The SMS dispatch chain in `app/api/v1/auth_otp.py` → `send_otp_via_sms()`:

```
1. Twilio (if TWILIO_ACCOUNT_SID + AUTH_TOKEN + PHONE_NUMBER all set)
   └─ POST to Twilio REST API via httpx

2. Fast2SMS (if FAST2SMS_API_KEY set, Twilio vars empty)
   └─ POST to fast2sms.com/dev/bulkV2 (India 10-digit numbers only)

3. Console Mock (if no SMS provider configured)
   └─ Prints OTP to terminal: "📱 [SMS OTP DISPATCH] Code: 482916"
```

### 7.3 Fast2SMS Setup (India-Specific Alternative)

1. Go to [https://www.fast2sms.com](https://www.fast2sms.com) and register.
2. Navigate to **Dev API** section and copy your API Authorization Key.
3. Set:

```env
FAST2SMS_API_KEY=""
```

4. Fast2SMS only accepts **10-digit Indian mobile numbers** (the backend strips the `+91` prefix automatically).

---

## 8. Frontend Integration & Logic Migration Specification

> **Context:** The team is migrating from a legacy frontend to a new UI built with React + Vite + TypeScript. The new UI currently renders mock/demo data from `src/mock/`. This section specifies **logic-only** updates — no visual/styling changes to the new UI components.

### Overview of Existing Frontend Service Layer

The new frontend already has a partial integration layer:

| File | Status | Purpose |
|---|---|---|
| `src/services/apiClient.ts` | ✅ **Production-ready** | Central `apiRequest()` with Bearer token injection, 401 interceptor, 422 error formatting |
| `src/services/analysisApi.ts` | ✅ **Production-ready** | `getDamageAnalysis()` mapping for `GET /claims/{id}/ai-analysis` |
| `src/services/claimsApi.ts` | 🔄 **Needs audit** | Verify all endpoints match backend routes |
| `src/store/authStore.ts` | ⚠️ **Hybrid** | Stores real tokens from OTP/register but falls back to mock tokens for demo sessions |
| `src/mock/claims.ts` | 🗑️ **To deprecate** | Hardcoded claim data — replace with live API calls |
| `src/mock/analysis.ts` | 🗑️ **To deprecate** | Hardcoded AI analysis data — replace with `analysisApi.ts` |

---

### 8.1 Video Compression & Button Enable States

#### Legacy UI Behavior

The old frontend displayed a live progress indicator during video compression:

```tsx
// Legacy implementation (reference only — do NOT port the UI)
<ProgressBar value={compressionProgress} label={`Compressing... ${compressionProgress}%`} />
<Button disabled={compressionProgress < 100}>Submit Claim</Button>
```

#### New UI — Required Logic Update

The new UI uses a different button layout. **Do not change the button's visual design.** Only wire the disabled state:

```tsx
// ── In your claim submission form component ──────────────

const [isCompressing, setIsCompressing] = useState(false);
const [videoFile, setVideoFile] = useState<File | null>(null);
const [compressionProgress, setCompressionProgress] = useState(0);

// Disable submit until compression completes (or no video selected)
const isSubmitDisabled = isCompressing || (videoFile && compressionProgress < 100);

// Apply to existing button — NO visual changes
<Button
  disabled={isSubmitDisabled || !formIsValid}
  onClick={handleSubmitClaim}
>
  {isCompressing ? 'Processing Video...' : 'Submit Claim'}
</Button>
```

**Rules:**
- If **no video** is attached, the submit button is enabled (photos-only claims are valid).
- If a video **is** attached, the button stays disabled until `compressionProgress === 100`.
- The compression state must be tracked even though the new UI does not show a percentage bar — the **logic guard** prevents premature submission of unfinished uploads.

---

### 8.2 Policy Number Assignment

#### Current State

The `ClaimCreate` schema requires `policy_number`. The new UI has a text input field for it but it may be left empty during early testing.

#### Required Wiring

```tsx
// In claim submission handler
const handleSubmitClaim = async () => {
  const claimPayload = {
    incident_type: formData.incidentType,
    vehicle_name: formData.vehicleName,
    // Send user-entered value, or let backend default to POL-M-847201
    policy_number: formData.policyNumber || undefined,
    hsrp_number: formData.hsrpNumber,
    engine_number: formData.engineNumber,
    chassis_number: formData.chassisNumber,
    incident_date: formData.incidentDate,
    location_address: formData.locationAddress,
    description: formData.description,
    driver_name: formData.driverName,
    driver_dl_number: formData.driverDlNumber,
    claimed_amount: formData.claimedAmount || 0,
  };

  const result = await apiRequest('/claims', {
    method: 'POST',
    body: JSON.stringify(claimPayload),
  });

  // result.claim_id → navigate to claim detail / upload evidence step
};
```

**Developer Note:** After applying the backend changes from [Section 5](#5-local-backend-code-updates--policy-based-agent-routing), the backend gracefully defaults:

```
policy_number provided  → lookup in policies table → assign agent
policy_number empty     → fallback to "POL-M-847201" → assign agent (if any)
policy not found        → claim created without agent assignment
```

---

### 8.3 JWT Authentication & Bearer Token Interceptor

#### Current State — Hybrid Auth

`authStore.ts` currently generates **mock tokens** (`demo-token-${Date.now()}`) for demo sessions. The `apiClient.ts` already reads from `localStorage.getItem('access_token')` and injects the Bearer header.

#### Migration Path

**Phase 1 — Already Done (No Changes Needed):**

The `apiClient.ts` centralized client already handles:

```typescript
// src/services/apiClient.ts (already implemented)
const token = localStorage.getItem('access_token');
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
};
```

The 401 interceptor is also implemented:

```typescript
// Already in apiClient.ts
if (response.status === 401) {
  localStorage.removeItem('access_token');
  localStorage.removeItem('auth_user');
  window.location.href = '/login';
  throw new Error('Session expired. Please log in again.');
}
```

**Phase 2 — Remove Mock Token Generation:**

In `src/store/authStore.ts`, remove the fallback mock token:

```diff
  login(email: string, name: string, phone?: string, dob?: string, token?: string) {
    const role: Role = email.toLowerCase() === AGENT_EMAIL ? 'agent' : 'customer';
    this.user = { id: Math.random().toString(36).substring(7), email, name, phone, dob, role };
    localStorage.setItem('auth_user', JSON.stringify(this.user));
    if (token) {
      localStorage.setItem('access_token', token);
-   } else if (!localStorage.getItem('access_token')) {
-     localStorage.setItem('access_token', `demo-token-${Date.now()}`);
    }
    this.notify();
  }
```

**Phase 3 — Wire OTP Login to Real Backend:**

Use the existing `authOtpApi` from `apiClient.ts`:

```typescript
import { authOtpApi } from '../services/apiClient';

// Step 1: Send OTP
await authOtpApi.sendOtp(email, 'email');

// Step 2: Verify OTP (auto-stores token in localStorage)
const result = await authOtpApi.verifyOtp(email, otpCode, 'email');
// result.access_token is now stored → all subsequent apiRequest() calls are authenticated
```

---

### 8.4 AI Evidence Rendering — Mock → Live Data

#### Current State

The new UI renders mock damage cards from `src/mock/analysis.ts`. These must be replaced with live data from `GET /api/v1/claims/{claim_id}/ai-analysis`.

#### Already-Implemented Mapping (`analysisApi.ts`)

The `analysisApi.ts` service already transforms the backend response:

```typescript
// src/services/analysisApi.ts (already implemented)
export const analysisApi = {
  getDamageAnalysis: async (claimId: string): Promise<DamageAnalysis | null> => {
    const response = await fetch(`${API_BASE_URL}/claims/${claimId}/ai-analysis`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();

    return {
      claimId: data.claim_id,
      imageUrl: sanitizeImageUrl(data.image_url || data.clahe_image_url),
      claheImageUrl: sanitizeImageUrl(data.clahe_image_url || data.image_url),
      damages: data.detected_damages || [],         // ← Array of damage objects
      totalEstimatedCost: (minCost + maxCost) / 2,
      estimatedCostMin: minCost,                    // ← Lower bound ₹
      estimatedCostMax: maxCost,                    // ← Upper bound ₹
    };
  }
};
```

#### Required Component-Level Changes

Replace mock imports with live API calls in damage card components:

```tsx
// ── BEFORE (mock data) ──
import { mockDamageAnalysis } from '../../mock/analysis';

const DamageCards = ({ claimId }: { claimId: string }) => {
  const analysis = mockDamageAnalysis; // ❌ Static mock
  // ...render cards
};

// ── AFTER (live API) ──
import { analysisApi } from '../../services/analysisApi';

const DamageCards = ({ claimId }: { claimId: string }) => {
  const [analysis, setAnalysis] = useState<DamageAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    analysisApi.getDamageAnalysis(claimId)
      .then(setAnalysis)
      .finally(() => setLoading(false));
  }, [claimId]);

  if (loading) return <Skeleton />;   // Keep existing skeleton component
  if (!analysis) return <EmptyState />;

  // Render damage cards using analysis.damages[]
  // Each damage object contains:
  return (
    <>
      {analysis.damages.map((dmg: any) => (
        <DamageCard
          key={dmg.id}
          type={dmg.type}                    // "Front Bumper Dent"
          severity={dmg.severity}            // "Severe" | "Moderate" | "Minor"
          confidence={dmg.confidence}        // 0.91
          repairAction={dmg.repair_action}   // "Replacement"
          estimatedCost={dmg.estimated_cost} // 5500.00
          boundingBox={dmg.boundingBox}       // { x, y, width, height } in %
        />
      ))}
    </>
  );
};
```

#### Bounding Box Overlay Rendering

For the damage image overlay, map bounding box percentages directly to CSS:

```tsx
// Render bounding boxes on the evidence image
<div style={{ position: 'relative', display: 'inline-block' }}>
  <img src={analysis.imageUrl} alt="Damage evidence" style={{ width: '100%' }} />

  {analysis.damages.map((dmg: any) => (
    <div
      key={dmg.id}
      style={{
        position: 'absolute',
        left: `${dmg.boundingBox.x}%`,
        top: `${dmg.boundingBox.y}%`,
        width: `${dmg.boundingBox.width}%`,
        height: `${dmg.boundingBox.height}%`,
        border: '2px solid #ff4444',
        borderRadius: '4px',
        backgroundColor: 'rgba(255, 68, 68, 0.1)',
        pointerEvents: 'none',
      }}
    >
      <span style={{
        position: 'absolute',
        top: '-20px',
        left: '0',
        fontSize: '11px',
        background: '#ff4444',
        color: '#fff',
        padding: '2px 6px',
        borderRadius: '3px',
        whiteSpace: 'nowrap',
      }}>
        {dmg.type} ({Math.round(dmg.confidence * 100)}%)
      </span>
    </div>
  ))}
</div>
```

---

### 8.5 Migration Checklist

Use this checklist to track frontend integration progress:

```
□ Phase 1: Auth Integration
  □ Wire login page to POST /api/v1/auth/otp/send + /verify
  □ Wire register page to POST /api/v1/auth/register
  □ Remove mock token generation from authStore.ts
  □ Verify 401 interceptor redirects to /login

□ Phase 2: Claims Submission
  □ Wire claim form to POST /api/v1/claims
  □ Connect policy_number input field (optional, backend defaults)
  □ Implement presigned upload flow: presigned-url → PUT → catalog
  □ Add video compression disabled-state guard on submit button
  □ Remove mock claims data imports from src/mock/claims.ts

□ Phase 3: AI Analysis Display
  □ Replace mock damage cards with analysisApi.getDamageAnalysis()
  □ Implement bounding box overlay on evidence images
  □ Wire cost bounds (estimatedCostMin/Max) to settlement cards
  □ Remove mock analysis data imports from src/mock/analysis.ts

□ Phase 4: Agent Dashboard
  □ Wire agent claims queue to GET /api/v1/agent/claims
  □ Wire agent actions to POST /api/v1/agent/claims/{id}/action
  □ Implement status filter dropdowns with query params

□ Phase 5: Customer Settlement
  □ Wire accept/dispute buttons to POST /api/v1/claims/portal/decision
  □ Handle payout pipeline response for ACCEPT
  □ Handle support contact modal for DISPUTE
```

---

## Appendix: Structured Error Response Format

All API errors follow a consistent envelope:

```json
{
  "success": false,
  "status_code": 422,
  "detail": {
    "message": "Input validation failed. Please check the supplied parameters.",
    "errors": [
      {
        "field": "driver_dl_number",
        "message": "driver_dl_number must match standard 15-character format",
        "type": "value_error"
      }
    ]
  }
}
```

| Status Code | Exception Type |
|---|---|
| `400` | Business logic validation failure |
| `401` | Missing or invalid Bearer token |
| `403` | RBAC role mismatch (`require_roles()` denied) |
| `404` | Resource not found (claim, policy, profile) |
| `409` | Duplicate registration (email exists) |
| `413` | File size exceeds 50 MB / 100 MB limit |
| `422` | Pydantic schema validation failure |
| `429` | OTP max attempts exceeded |
| `500` | Unhandled server error (catch-all) |
| `502` | Supabase Storage API failure |

---

> **Last updated:** 2026-10-01 | **Backend version:** 1.0.0 | **Schema version:** v2.0
