# 🚀 ClaimPilot — AI-Powered Motor Claims Platform

ClaimPilot is a modern motor insurance claims management web application. It connects policyholders (customers) with insurance adjusters (agents) to make claim filing, AI damage detection, and settlement approval fast, visual, and transparent.

---

## 📋 How It Works (Simple Workflow)

### 1. Customer Files a Claim (`/customer`)
* **Simple Stepper Form:** The customer enters vehicle details, incident location, policy info, and registration verification (HSRP, Engine/Chassis numbers, Driver's License photo).
* **Uploads Evidence:** The customer uploads multiple photos and video recordings of the vehicle damage.

### 2. AI Assessment & Customer Review
* **Instant Visual Breakdown:** The customer views their AI Damage Assessment (`/customer/claims/:id`), showing detected damage areas, severity badges, and estimated repair cost ranges.
* **Multi-Media Evidence Viewer:** The customer can click or tap through a gallery of all uploaded photos and watch uploaded video evidence to see how the AI evaluated their vehicle.

### 3. Agent Review & Adjudication (`/agent`)
* **Claims Queue:** The insurance agent sees new claims in a real-time queue with priority flags.
* **Deep Inspection:** The agent inspects damage bounding boxes, 3D deformation topology, AI surface normals, and algorithmic fraud risk scores (0–100%).
* **Adjudication:** The agent can **Approve** (setting a settlement amount), **Reject** (with justification notes), or **Request Information** from the customer.

### 4. Settlement & Finance Handoff
* **Client Response:** If approved, the customer receives the offer on their portal and can **Approve** or **Reject** the settlement offer.
* **Final Authorization:** When the customer approves, the agent sees the response live on their dashboard and clicks **"OK to Proceed"** to send the claim to the finance team for payment payout.

---

## 🔐 Storage & Data Handling

* **Browser Session Storage:** All claim records and active user logins are stored directly in your browser's `sessionStorage`. Data stays active while navigating or refreshing the tab, and automatically clears when the tab or browser is closed.
* **Frontend Prototype:** API requests are simulated locally with async delays (`src/services/claimsApi.ts`) for easy demonstration without needing a database setup.

---

## 🛠 Tech Stack

* **Frontend Framework:** [React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
* **Build Tool:** [Vite](https://vitejs.dev/)
* **Routing:** [React Router v7](https://reactrouter.com/)
* **3D Visualizations:** [Three.js](https://threejs.org/) + `@react-three/fiber` + `@react-three/drei`
* **Animations:** GSAP (GreenSock)
* **Icons:** Lucide React
* **Styling:** Modular Vanilla CSS with CSS Custom Properties (`src/index.css`)

---

## 🔑 Quick Demo Credentials

Sign in directly from the `/login` page using the one-click demo buttons or credentials below:

| Role | Email | Password | Landing Page |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer@example.com` | `password` | `/customer` |
| **Claims Agent** | `agent@example.com` | `password` | `/agent` |

---

## 🚀 Getting Started Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/shreyasshah707/ClaimPilot.git
   cd ClaimPilot/frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start local development server:**
   ```bash
   npm run dev
   ```

4. **Open in browser:** Navigate to `http://localhost:5173`
