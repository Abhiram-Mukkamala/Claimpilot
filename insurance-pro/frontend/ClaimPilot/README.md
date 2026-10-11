# 🚀 ClaimPilot — AI-Powered Motor Claims Platform (Frontend)

ClaimPilot is a modern motor insurance claims management web application. It connects policyholders (customers) with insurance adjusters (agents) to make claim filing, AI damage detection, and settlement approval fast, visual, and transparent.

This document serves as the comprehensive architectural reference and integration guide for the **New React Frontend** (`frontend/ClaimPilot/`) and its real-time connectivity to the **FastAPI + Supabase Backend**.

---

## 📋 How It Works (Workflow Overview)

### 1. Customer Files a Claim (`/customer`)
* **Secure Auth:** Customers log in via Dual OTP Authentication (Email/SMS).
* **Smart Stepper Form:** The customer enters vehicle details, incident location, policy info, and registration verification.
* **Evidence Uploads:** Customers upload photos and a 30-60s walkaround video.

### 2. AI Assessment & Customer Review
* **Instant Visual Breakdown:** Customers view AI Damage Assessments with detected damage areas, bounding boxes, severity badges, and estimated repair cost ranges.
* **Multimedia Evidence Viewer:** Customers navigate their evidence gallery and view their processed AI data.

### 3. Agent Review & Adjudication (`/agent`)
* **Secure Auth:** Insurance agents log in using pre-provisioned credentials via standard Email + Password.
* **Claims Queue:** Agents see new claims in a real-time queue with priority and high-risk flags.
* **Deep Inspection Workspace:** 
  * Agents inspect damage bounding boxes and multi-angle shots.
  * **3D AI Engine:** View 3D deformation topology, AI surface normals, and depth maps.
  * **Fraud Detection:** Algorithmic fraud risk scores (0–100%) and multi-point validation flags.
* **Adjudication Actions:** Agents can **Approve** (with settlement offer), **Reject** (with reason), or **Request Information** (smart parsed for specific missing items).

### 4. Settlement & Finance Handoff
* **Client Response:** If approved, customers review the settlement offer on their portal to either **Accept** or **Dispute**.

---

## 🏗 Project Structure

```text
ClaimPilot/frontend/ClaimPilot/src/
├── components/
│   ├── analysis/             # AI visualizations: 3D Deformation, Segmentation, Surface Normals
│   ├── layout/               # Role-based Layouts (AgentLayout, CustomerLayout, TopBar)
│   ├── three/                # Three.js Canvas and Mesh Renderers for 3D views
│   └── ui/                   # Reusable UI primitives: Cards, Badges, Modals, Drawers
├── pages/
│   ├── agent/                # Agent Flows: Dashboard, Claims Queue, Claim Deep-Dive
│   ├── customer/             # Customer Flows: Dashboard, New Claim Form, Claim Analysis
│   ├── Login.tsx             # Unified Authentication Portal
│   └── About.tsx             # Marketing/Product Narrative
├── routes/                   # React Router configurations & RBAC Role Guards
├── services/                 # Centralized API Clients (Backend Bridge)
│   ├── claimsApi.ts          # Auth, OTP, Storage uploads, and Claims CRUD
│   ├── analysisApi.ts        # AI Damage and Fraud metrics mapping
│   └── advancedAnalysisApi.ts# 3D Topology mapping and visual fallbacks
├── store/                    # Zustand-style state stores (Auth, Theme)
├── types/                    # TypeScript interfaces for Claims, Auth, and AI payloads
└── index.css                 # Vanilla CSS Design System and custom properties
```

---

## 🔌 API Connectivity & Backend Integration

The frontend has been completely migrated off static mock files. It strictly communicates with the live FastAPI (`localhost:8000`) backend via Vite's local `/api` proxy.

### 🔐 Authentication Flow
| Actor | Auth Method | Backend Endpoint | Status |
|---|---|---|---|
| **Customer** | OTP Request | `POST /auth/otp/send` | ✅ Wired dynamically |
| **Customer** | OTP Verify | `POST /auth/otp/verify` | ✅ Wired dynamically |
| **Agent** | Password Login | `POST /auth/login` | ✅ Wired dynamically |
| **All Roles** | Token Minting | Supabase standard JWT | ✅ Sessions stored locally |

*(Note: Agents **do not** register. Their accounts are pre-provisioned in Supabase via Admin dashboard).*

### 👨‍💼 Agent-Side Connectivity (Fully Connected)
| Feature | Endpoint Used | Method | Integration Status |
|---|---|---|---|
| Load Claims Queue | `/api/v1/agent/claims` | `GET` | ✅ Live data mapping |
| Claim Detail Fetch | `/api/v1/agent/claims/{id}` | `GET` | ✅ Live evidence + AI data |
| Approve Claim | `/api/v1/agent/claims/{id}/action` | `POST` | ✅ Connected (Payload: `APPROVE`) |
| Reject Claim | `/api/v1/agent/claims/{id}/action` | `POST` | ✅ Connected (Payload: `REJECT`) |
| Request More Info | `/api/v1/agent/claims/{id}/action` | `POST` | ✅ Connected (Smart item parsing) |
| Damage Analysis | `/api/v1/agent/claims/{id}` | `GET` | ✅ Live bbox & repair mappings |
| Fraud Metrics | `/api/v1/agent/claims/{id}` | `GET` | ✅ Live risk scores & indicators |
| 3D Visualization | `/api/v1/agent/claims/{id}` | `GET` | ✅ Live map processing & rendering |

### 🧑‍💻 Customer-Side Connectivity
| Feature | Endpoint Used | Method | Integration Status |
|---|---|---|---|
| Load Dashboard | `/api/v1/claims` | `GET` | ✅ Connected |
| Create Claim | `/api/v1/claims` | `POST` | ✅ Connected |
| View Claim Details | `/api/v1/claims/{id}` | `GET` | ✅ Connected |
| Accept/Dispute | `/api/v1/claims/portal/decision`| `POST` | ⚠️ Pending full UI wire-up |
| Get Upload URLs | `/api/v1/storage/presigned-url` | `POST` | ✅ Connected |
| Catalog Evidence | `/api/v1/storage/evidence` | `POST` | ✅ Connected |

---

## 📊 Supabase Database Schema

The backend architecture relies on the following core Supabase tables:

1. **`profiles`**
   - Stores user data (`id`, `full_name`, `phone_number`, `role: 'customer' | 'agent' | 'admin'`).
   - Links 1:1 with `auth.users`.
2. **`claims`**
   - The master record (`id`, `user_id`, `policy_number`, `status`, `risk_level`, `fraud_score`, `location_address`, `approved_amount`).
   - Driven by a strict backend state machine.
3. **`claim_evidence`**
   - Media references (`id`, `claim_id`, `category`, `file_url`, `storage_path`, `file_type`).
   - Supports: `photo`, `walkaround_video`, `dl_front`, `dl_back`.
4. **`claim_ai_analysis`**
   - The AI output buffer (`id`, `claim_id`, `detected_damages`, `segmentation_masks`, `fraud_flags`, `estimated_cost_max`, `estimated_cost_min`).
   - Stores rich JSON structures for frontend rendering.

---

## ✅ Work Completed

- **Visual Frozen State Maintained:** App logic refactored without breaking UI, layouts, or CSS animations.
- **Removed Static Mocks:** Purged `mockClaims`, `mockDamageAnalysis`, and `mockFraudAnalysis`.
- **Agent Login Support:** Implemented `POST /auth/login` on the backend and wired `authStore.ts` to strictly require it.
- **Smart Agent Inputs:** Automated parsing of agent Request Info notes to extract specific missing items (`photo`, `video`, `dl_front`).
- **Dynamic 3D Analysis Fixing:** Wired `claimId` deep-links for `advancedAnalysisApi.ts` to hydrate 3D meshes dynamically from live Supabase evidence.
- **Upload States:** Implemented simulated video compression delays and button safeguards in `NewClaim.tsx`.

## 🚧 Work Pending / Roadmap

- **Evidence Upload Pipe:** Finalize direct PUT requests to Supabase Storage using generated presigned URLs in the frontend `NewClaim` form.
- **Customer Decision Flow:** Build out the UI for the `Accept/Dispute` final settlement phase after an agent approves a claim.
- **Server-Side Filtering:** Wire query parameters (`?status=`, `?risk=`) in the `AgentClaims.tsx` data table fetch to shift filtering load to the backend.
- **Agent Activity Feed:** Connect the Agent Dashboard's timeline to a backend event stream (currently no backend endpoint exists for this).

---

## 🚀 Getting Started Locally

1. **Start the FastAPI Backend** (in `../backend`):
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start the Frontend** (in this directory):
   ```bash
   npm install
   npm run dev
   ```

3. **Log in:**
   - Go to `http://localhost:5173/login`
   - Use any provisioned Agent credentials (e.g., `agent@example.com` / `password`).
   - Start managing live claims!
