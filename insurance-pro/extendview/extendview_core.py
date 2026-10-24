"""
ClaimPilot AI — Shared ExtendView Core Engine
=============================================
Shared design system, FastAPI + Direct Supabase live claim fetcher, @st.cache_resource
v3 model loader, and interactive Plotly/OpenCV 2D & 3D telemetry renderers used by
both `customer_app.py` (Customer Extended View) and `agent_app.py` (Agent Extended View).
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

import cv2
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# Optional Heavy Backend Imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# Optional Gemini SDK (reads FRAUD_LLM_API_KEY / GEMINI_API_KEY / GOOGLE_API_KEY strictly from environment / .env)
HAS_GEMINI = False
GEMINI_SDK = None
try:
    from google import genai
    from google.genai import types
    GEMINI_SDK = "genai"
    HAS_GEMINI = True
except ImportError:
    try:
        import google.generativeai as genai_legacy
        GEMINI_SDK = "legacy"
        HAS_GEMINI = True
    except ImportError:
        HAS_GEMINI = False

# Ensure pipeline directory is on sys.path
EXTENDVIEW_ROOT = Path(__file__).parent
PIPELINE_ROOT = EXTENDVIEW_ROOT / "pipeline"
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

HAS_V2_PIPELINE = False
V2_IMPORT_ERROR = None
try:
    from v1_adapter import (
        run_v2_pipeline_as_v1,
        load_v2_models,
        extract_v1_metrics_from_v2_report,
        run_v2_pipeline_full,
        resolve_weight_path,
    )
    HAS_V2_PIPELINE = True
except Exception as e:
    V2_IMPORT_ERROR = str(e)

# ---------------------------------------------------------------------------
# CONSTANTS & ENDPOINT RESOLUTION
# ---------------------------------------------------------------------------
IMG_SIZE = 480
PLATE_PIXEL_WIDTH = 190
DEFAULT_REF_MM = 500


def _load_env_config() -> Dict[str, str]:
    """Loads backend .env or environment variables into memory without printing any secrets."""
    cfg: Dict[str, str] = {}
    env_candidates = [
        EXTENDVIEW_ROOT.parent / "backend" / ".env",
        EXTENDVIEW_ROOT / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and v and k not in cfg:
                            cfg[k] = v
            except Exception:
                pass

    for k in (
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY",
        "FRAUD_LLM_API_KEY", "FRAUD_LLM_MODEL", "AI_AUDIT_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY",
        "CLAIMPILOT_API_BASE_URL", "CLAIMPILOT_FRONTEND_URL",
    ):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
        else:
            try:
                if hasattr(st, "secrets") and k in st.secrets:
                    cfg[k] = str(st.secrets[k])
            except Exception:
                pass
    return cfg


_ENV_CFG = _load_env_config()

API_BASE_URL = (
    _ENV_CFG.get("CLAIMPILOT_API_BASE_URL")
    or os.environ.get("VITE_API_BASE_URL")
    or "http://localhost:8000/api/v1"
).rstrip("/")

FRONTEND_BASE_URL = (
    _ENV_CFG.get("CLAIMPILOT_FRONTEND_URL")
    or "http://localhost:5173"
).rstrip("/")

PRESETS = {
    "Medium PDR Dent": dict(
        base_bgr=(40, 110, 185), center=(240, 230), sigma=(52, 48),
        angle=0, amp_mm=6.5, base_mm=850.0,
        blurb="Rounded door-panel dent, metal still elastic — PDR viable.",
        narrative="A stray cricket ball hit the rear side door while the vehicle was parked near a playground.",
    ),
    "Minor Polish Scratch": dict(
        base_bgr=(150, 60, 40), center=(180, 190), sigma=(24, 13),
        angle=15, amp_mm=1.6, base_mm=800.0,
        blurb="Shallow clear-coat scuff, no structural deformation.",
        narrative="I scraped against a roadside bush while turning into my residential parking slot.",
    ),
    "Severe Collision Crease": dict(
        base_bgr=(55, 55, 58), center=(250, 235), sigma=(115, 28),
        angle=35, amp_mm=17.0, base_mm=900.0,
        blurb="Elongated high-energy crease with sharp metal fold.",
        narrative="I accidentally reversed into a sharp concrete pillar in a basement parking garage at ~15 km/h.",
    ),
}


# ---------------------------------------------------------------------------
# LEGACY V1 MULTI-TASK CNN (FALLBACK)
# ---------------------------------------------------------------------------
if HAS_TORCH:
    class ClaimPilotPipeline(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = nn.Sequential(
                nn.Conv2d(3, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(),
                nn.Conv2d(32, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(),
            )
            self.sam2_mask_head = nn.Sequential(
                nn.Conv2d(64, 32, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv2d(32, 1, kernel_size=1),
            )
            self.depth_pro_head = nn.Sequential(
                nn.Conv2d(64, 32, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv2d(32, 1, kernel_size=1),
            )
            self.dsine_normal_head = nn.Sequential(
                nn.Conv2d(64, 32, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv2d(32, 3, kernel_size=1),
            )

        def forward(self, x):
            features = self.backbone(x)
            mask_logits = self.sam2_mask_head(features)
            pred_depth = self.depth_pro_head(features)
            pred_normals = F.normalize(self.dsine_normal_head(features), p=2, dim=1)
            return mask_logits, pred_depth, pred_normals


# ---------------------------------------------------------------------------
# CACHED MODEL LOADER
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_all_models():
    metric_model = None
    yolo_model = None
    v2_models = None

    if HAS_V2_PIPELINE:
        metric_weights = resolve_weight_path("claimpilot_final_weights.pt")
        yolo_weights = resolve_weight_path("cardd_best.pt")
    else:
        metric_weights = Path(r"C:\Users\abhir\Downloads\v3\v3\models\claimpilot_final_weights.pt")
        yolo_weights = Path(r"C:\Users\abhir\Downloads\v3\v3\models\cardd_best.pt")

    if HAS_TORCH and metric_weights.exists():
        try:
            m = ClaimPilotPipeline()
            state_dict = torch.load(str(metric_weights), map_location=torch.device("cpu"))
            m.load_state_dict(state_dict)
            m.eval()
            metric_model = m
        except Exception:
            pass

    if HAS_YOLO and yolo_weights.exists():
        try:
            yolo_model = YOLO(str(yolo_weights))
        except Exception:
            pass

    if HAS_V2_PIPELINE:
        try:
            device = "cuda" if (HAS_TORCH and torch.cuda.is_available()) else "cpu"
            v2_models = load_v2_models(device)
        except Exception:
            v2_models = None

    return metric_model, yolo_model, v2_models


# ---------------------------------------------------------------------------
# CLAIMPILOT REACT DESIGN SYSTEM CSS INJECTION
# ---------------------------------------------------------------------------
def inject_claimpilot_theme(is_embedded: bool = False):
    """Injects exact CSS tokens from ClaimPilot React (src/index.css & src/agent.css)."""
    top_pad = "0.5rem" if is_embedded else "1.25rem"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {{
            --bg-base: #070709;
            --bg-surface: rgba(16, 16, 24, 0.72);
            --bg-elevated: rgba(22, 22, 32, 0.85);
            --text-primary: #F2F2F2;
            --text-secondary: #9BA3AF;
            --text-muted: #6B7280;
            --border: rgba(255, 255, 255, 0.10);
            --border-strong: rgba(255, 255, 255, 0.18);
            --accent: #059669;
            --accent-bright: #22C55E;
            --warning: #D97706;
            --danger: #DC2626;
            --radius-sm: 12px;
            --radius-md: 16px;
            --radius-lg: 20px;
        }}

        /* Global App Canvas matching DottedWaveBackground */
        .stApp {{
            background-color: #070709 !important;
            background-image: radial-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px) !important;
            background-size: 24px 24px !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            color: var(--text-primary) !important;
        }}

        /* Hide default Streamlit chrome */
        #MainMenu, footer, header[data-testid="stHeader"] {{
            visibility: hidden !important;
            height: 0 !important;
        }}
        .block-container {{
            padding-top: {top_pad} !important;
            padding-bottom: 2.5rem !important;
            max-width: 1680px !important;
        }}

        /* Sidebar Crystal Glass */
        section[data-testid="stSidebar"] {{
            background: rgba(12, 12, 18, 0.92) !important;
            backdrop-filter: blur(20px) saturate(140%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.10) !important;
        }}

        /* Typography */
        h1, h2, h3, h4, .cp-heading {{
            font-family: 'Inter', sans-serif !important;
            letter-spacing: -0.025em !important;
            color: #F2F2F2 !important;
        }}
        code, pre, .cp-mono {{
            font-family: 'JetBrains Mono', monospace !important;
        }}

        /* Crystal Glass Cards */
        .cp-card, div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(16, 16, 24, 0.65) !important;
            backdrop-filter: blur(18px) saturate(140%) !important;
            -webkit-backdrop-filter: blur(18px) saturate(140%) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
            border-radius: 16px !important;
            padding: 1.15rem !important;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
        }}

        /* Top Navigation Header matching TopBar.tsx & AgentLayout.tsx */
        .cp-topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.85rem 1.35rem;
            margin-bottom: 1.25rem;
            background: rgba(14, 14, 20, 0.72);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 18px;
            box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.10);
        }}
        .cp-brand {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            font-weight: 700;
            font-size: 1.05rem;
            letter-spacing: -0.03em;
            color: #F2F2F2;
        }}
        .cp-back-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.42rem 0.95rem;
            border-radius: 9999px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.14);
            color: #F2F2F2 !important;
            font-size: 0.8125rem;
            font-weight: 600;
            text-decoration: none !important;
            transition: all 0.15s ease;
        }}
        .cp-back-btn:hover {{
            background: rgba(5, 150, 105, 0.18);
            border-color: #059669;
            color: #FFFFFF !important;
        }}

        /* Status & Role Badges */
        .cp-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.22rem 0.68rem;
            border-radius: 9999px;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }}
        .cp-badge-success {{
            background: rgba(34, 197, 94, 0.14);
            color: #4ADE80;
            border: 1px solid rgba(34, 197, 94, 0.32);
        }}
        .cp-badge-warning {{
            background: rgba(217, 119, 6, 0.16);
            color: #FBBF24;
            border: 1px solid rgba(217, 119, 6, 0.35);
        }}
        .cp-badge-danger {{
            background: rgba(220, 38, 38, 0.16);
            color: #F87171;
            border: 1px solid rgba(220, 38, 38, 0.35);
        }}
        .cp-badge-neutral {{
            background: rgba(255, 255, 255, 0.07);
            color: #D1D5DB;
            border: 1px solid rgba(255, 255, 255, 0.14);
        }}

        /* High-Density KPI Metric Cards */
        .cp-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0.85rem;
            margin-bottom: 1.15rem;
        }}
        .cp-kpi-card {{
            background: rgba(16, 16, 24, 0.68);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 14px;
            padding: 0.9rem 1.1rem;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
        }}
        .cp-kpi-label {{
            font-size: 0.71rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #9BA3AF;
            margin-bottom: 0.3rem;
        }}
        .cp-kpi-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.38rem;
            font-weight: 700;
            color: #F2F2F2;
            line-height: 1.2;
        }}
        .cp-kpi-sub {{
            font-size: 0.74rem;
            color: #6B7280;
            margin-top: 0.22rem;
        }}

        /* Tabs matching agent.css .tab-nav */
        div[data-baseweb="tab-list"] {{
            gap: 1.25rem !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.10) !important;
            background: transparent !important;
        }}
        button[data-baseweb="tab"] {{
            font-family: 'Inter', sans-serif !important;
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            color: #9BA3AF !important;
            padding: 0.55rem 0.25rem !important;
            background: transparent !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: #F2F2F2 !important;
            font-weight: 600 !important;
        }}
        div[data-baseweb="tab-highlight"] {{
            background-color: #059669 !important;
            height: 2px !important;
        }}

        /* Primary Buttons */
        .stButton > button, .stDownloadButton > button {{
            background-color: #059669 !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 9999px !important;
            font-weight: 600 !important;
            padding: 0.45rem 1.15rem !important;
            transition: all 0.15s ease !important;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            background-color: #047857 !important;
            transform: translateY(-1px);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(
    role_label: str,
    claim_id: Optional[str] = None,
    claim_display_id: Optional[str] = None,
    vehicle_name: Optional[str] = None,
    status_text: Optional[str] = None,
    back_path: str = "/customer",
    is_embedded: bool = False,
):
    """Renders the ClaimPilot AI top header bar when opened standalone (skipped when embedded in React iframe)."""
    if is_embedded:
        return

    back_url = f"{FRONTEND_BASE_URL}{back_path}"
    status_cls = "cp-badge-neutral"
    if status_text:
        st_lower = status_text.lower()
        if "approv" in st_lower or "accept" in st_lower:
            status_cls = "cp-badge-success"
        elif "reject" in st_lower or "flag" in st_lower or "disput" in st_lower or "high" in st_lower:
            status_cls = "cp-badge-danger"
        elif "review" in st_lower or "action" in st_lower or "pend" in st_lower:
            status_cls = "cp-badge-warning"

    claim_meta_html = ""
    if claim_display_id:
        veh = f" · {vehicle_name}" if vehicle_name else ""
        status_pill = f'<span class="cp-badge {status_cls}" style="margin-left:0.6rem;">{status_text}</span>' if status_text else ""
        claim_meta_html = f"""
        <div style="display:flex; align-items:center; gap:0.5rem; font-size:0.875rem; color:#9BA3AF;">
            <span class="cp-mono" style="color:#F2F2F2; font-weight:600;">{claim_display_id}</span>
            <span>{veh}</span>
            {status_pill}
        </div>
        """

    st.markdown(
        f"""
        <div class="cp-topbar">
            <div style="display:flex; align-items:center; gap:1rem;">
                <a href="{back_url}" target="_self" class="cp-back-btn">
                    ← Back to ClaimPilot
                </a>
                <div class="cp-brand">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2L2 7l10 5 10-5-10-5z" fill="#059669" />
                        <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <span>ClaimPilot AI</span>
                    <span class="cp-badge cp-badge-success" style="text-transform:none; font-size:0.75rem;">{role_label}</span>
                </div>
            </div>
            {claim_meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# LIVE BACKEND + DIRECT SUPABASE FETCHER
# ---------------------------------------------------------------------------
def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 8) -> Any:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _supabase_rest_get(table: str, query_params: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    sb_url = _ENV_CFG.get("SUPABASE_URL", "").rstrip("/")
    sb_key = _ENV_CFG.get("SUPABASE_SERVICE_ROLE_KEY") or _ENV_CFG.get("SUPABASE_ANON_KEY") or ""
    if not sb_url or not sb_key:
        return None
    qs = urllib.parse.urlencode(query_params)
    url = f"{sb_url}/rest/v1/{table}?{qs}"
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
    }
    res = _http_get_json(url, headers=headers, timeout=10)
    return res if isinstance(res, list) else None


def fetch_recent_claims_list(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetches recent claims directly from Supabase so standalone mode can switch claims."""
    rows = _supabase_rest_get(
        "claims",
        {"select": "id,claim_number,vehicle_name,status,incident_type,created_at", "order": "created_at.desc", "limit": str(limit)},
    )
    return rows or []


def download_image_from_url(image_url: str, storage_path: Optional[str] = None, timeout: int = 12) -> Optional[np.ndarray]:
    """Downloads a claim evidence photo from signed URL or directly from Supabase Storage via service role key."""
    if image_url:
        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": "ClaimPilot-ExtendView/3.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
            arr = np.asarray(bytearray(raw_bytes), dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is not None:
                return bgr
        except Exception:
            pass

    if storage_path:
        sb_url = _ENV_CFG.get("SUPABASE_URL", "").rstrip("/")
        sb_key = _ENV_CFG.get("SUPABASE_SERVICE_ROLE_KEY") or _ENV_CFG.get("SUPABASE_ANON_KEY") or ""
        default_bucket = _ENV_CFG.get("SUPABASE_STORAGE_BUCKET") or "claim-evidence"
        if sb_url and sb_key:
            clean_path = storage_path.lstrip("/")
            for b_prefix in ("claim-evidence/", "claims-media/"):
                if clean_path.startswith(b_prefix):
                    clean_path = clean_path[len(b_prefix):]
            encoded_path = urllib.parse.quote(clean_path, safe="/")
            for bucket in (default_bucket, "claim-evidence", "claims-media"):
                for prefix in ("object", "object/authenticated", "object/public"):
                    direct_url = f"{sb_url}/storage/v1/{prefix}/{bucket}/{encoded_path}"
                    try:
                        req = urllib.request.Request(
                            direct_url,
                            headers={
                                "apikey": sb_key,
                                "Authorization": f"Bearer {sb_key}",
                            },
                            method="GET",
                        )
                        with urllib.request.urlopen(req, timeout=timeout) as resp:
                            raw_bytes = resp.read()
                        arr = np.asarray(bytearray(raw_bytes), dtype=np.uint8)
                        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if bgr is not None:
                            return bgr
                    except Exception:
                        pass

    return None


def _fetch_bundle_from_supabase_direct(claim_id: Optional[str], role: str = "customer") -> Optional[Dict[str, Any]]:
    """Queries Supabase PostgREST directly when FastAPI (:8000) is offline or no JWT is provided."""
    sb_url = _ENV_CFG.get("SUPABASE_URL", "").rstrip("/")
    sb_key = _ENV_CFG.get("SUPABASE_SERVICE_ROLE_KEY") or _ENV_CFG.get("SUPABASE_ANON_KEY") or ""
    if not sb_url or not sb_key:
        return None

    raw_claim = None
    if claim_id:
        # Try by UUID id first, then by claim_number
        if len(claim_id) == 36 and "-" in claim_id:
            rows = _supabase_rest_get("claims", {"select": "*", "id": f"eq.{claim_id}", "limit": "1"})
            if rows:
                raw_claim = rows[0]
        if not raw_claim:
            rows = _supabase_rest_get("claims", {"select": "*", "claim_number": f"eq.{claim_id}", "limit": "1"})
            if rows:
                raw_claim = rows[0]

    # If no claim_id passed (or not found), pick the most recent claim in Supabase that has media
    if not raw_claim:
        media_rows = (
            _supabase_rest_get(
                "claim_evidence",
                {"select": "claim_id,category,storage_path", "order": "created_at.desc", "limit": "20"},
            )
            or _supabase_rest_get(
                "claim_media",
                {"select": "claim_id,category,storage_path", "order": "created_at.desc", "limit": "20"},
            )
            or []
        )
        photo_claim_id = None
        for m in media_rows:
            cat = (m.get("category") or "").lower()
            if cat in ("photo", "damage_photo", "") and m.get("claim_id"):
                photo_claim_id = m["claim_id"]
                break
        if photo_claim_id:
            rows = _supabase_rest_get("claims", {"select": "*", "id": f"eq.{photo_claim_id}", "limit": "1"})
            if rows:
                raw_claim = rows[0]
        if not raw_claim:
            rows = _supabase_rest_get("claims", {"select": "*", "order": "created_at.desc", "limit": "1"})
            if rows:
                raw_claim = rows[0]

    if not raw_claim:
        return None

    resolved_uuid = raw_claim.get("id")
    evidence_list = (
        _supabase_rest_get("claim_evidence", {"select": "*", "claim_id": f"eq.{resolved_uuid}"})
        or _supabase_rest_get("claim_media", {"select": "*", "claim_id": f"eq.{resolved_uuid}"})
        or []
    )
    ai_rows = _supabase_rest_get("claim_ai_analysis", {"select": "*", "claim_id": f"eq.{resolved_uuid}", "order": "created_at.desc", "limit": "1"}) or []
    ai_analysis = ai_rows[0] if ai_rows else {}

    claimant = {}
    user_id = raw_claim.get("user_id")
    if user_id:
        prof_rows = _supabase_rest_get("profiles", {"select": "*", "id": f"eq.{user_id}", "limit": "1"}) or []
        if prof_rows:
            claimant = prof_rows[0]

    photos = []
    for ev in evidence_list:
        cat = (ev.get("category") or "").lower()
        s_path = ev.get("storage_path") or ""
        f_url = ev.get("file_url") or ""
        if (s_path or f_url) and cat in ("photo", "damage_photo", ""):
            photos.append({
                "id": ev.get("id") or f"photo_{len(photos)+1}",
                "url": f_url,
                "storage_path": s_path,
                "category": cat or "damage_photo",
            })

    fraud_data = {}
    if role == "agent":
        fraud_rows = _supabase_rest_get(
            "claim_fraud_analyses",
            {"select": "*", "claim_id": f"eq.{resolved_uuid}", "order": "created_at.desc", "limit": "1"},
        ) or []
        if fraud_rows:
            fraud_data = fraud_rows[0]

    return {
        "claim": raw_claim,
        "claimant": claimant,
        "photos": photos,
        "ai_analysis": ai_analysis if isinstance(ai_analysis, dict) else {},
        "fraud_analysis": fraud_data if isinstance(fraud_data, dict) else {},
    }


def fetch_live_claim_bundle(
    claim_id: str,
    token: Optional[str] = None,
    role: str = "customer",
) -> Optional[Dict[str, Any]]:
    """
    Fetches live claim details, evidence photos, AI analysis, and (for agent role only)
    fraud analysis from FastAPI first, falling back automatically to direct Supabase PostgREST.
    """
    if claim_id:
        endpoints = (
            [f"{API_BASE_URL}/agent/claims/{claim_id}", f"{API_BASE_URL}/claims/{claim_id}"]
            if role == "agent"
            else [f"{API_BASE_URL}/claims/{claim_id}", f"{API_BASE_URL}/agent/claims/{claim_id}"]
        )
        auth_headers = {"Authorization": f"Bearer {token}"} if token else None
        payload = None
        for ep in endpoints:
            data = _http_get_json(ep, headers=auth_headers, timeout=4)
            if isinstance(data, dict) and (data.get("claim") or data.get("id") or data.get("claim_number")):
                payload = data
                break

        if payload:
            raw_claim = payload.get("claim") if isinstance(payload.get("claim"), dict) else payload
            evidence_list = payload.get("evidence") or raw_claim.get("evidence") or []
            ai_analysis = payload.get("ai_analysis") or raw_claim.get("ai_analysis") or {}
            claimant = payload.get("claimant") or raw_claim.get("claimant") or {}

            photos = []
            for ev in evidence_list:
                cat = (ev.get("category") or "").lower()
                f_url = ev.get("file_url") or ""
                s_path = ev.get("storage_path") or ""
                if (f_url or s_path) and cat in ("photo", "damage_photo", ""):
                    photos.append({
                        "id": ev.get("id") or f"photo_{len(photos)+1}",
                        "url": f_url,
                        "storage_path": s_path,
                        "category": cat or "damage_photo",
                    })

            if not photos and isinstance(raw_claim.get("images"), list):
                for idx, u in enumerate(raw_claim["images"]):
                    if isinstance(u, str) and u:
                        photos.append({"id": f"img_{idx+1}", "url": u, "storage_path": "", "category": "damage_photo"})

            fraud_data = {}
            if role == "agent":
                fraud_resp = _http_get_json(f"{API_BASE_URL}/claims/{claim_id}/fraud", headers=auth_headers, timeout=4)
                if isinstance(fraud_resp, dict):
                    fraud_data = fraud_resp.get("fraud_analysis") if isinstance(fraud_resp.get("fraud_analysis"), dict) else fraud_resp

            return {
                "claim": raw_claim,
                "claimant": claimant,
                "photos": photos,
                "ai_analysis": ai_analysis if isinstance(ai_analysis, dict) else {},
                "fraud_analysis": fraud_data if isinstance(fraud_data, dict) else {},
            }

    # Fallback: query Supabase directly (works even when FastAPI is stopped or no claim_id was passed)
    return _fetch_bundle_from_supabase_direct(claim_id, role=role)


# ---------------------------------------------------------------------------
# IMAGE PROCESSING, GUARDRAILS & INFERENCE HELPERS
# ---------------------------------------------------------------------------
def check_photo_quality(bgr_img: np.ndarray) -> Tuple[int, str, float, float]:
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    glare_pct = float(np.mean(gray > 240) * 100)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    confidence = max(50, min(99, int(100 - glare_pct - (1000 / (blur_score + 1)))))
    status = "PASS" if confidence >= 75 else "WARNING"
    return confidence, status, round(glare_pct, 1), round(blur_score, 1)


def apply_clahe_glare_reduction(bgr_img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l_eq = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge([np.clip(l_eq, 0, 233).astype(np.uint8), a, b]), cv2.COLOR_LAB2BGR)


def overlay_mask_and_boxes(
    bgr_img: np.ndarray,
    mask: np.ndarray,
    v2_report: Optional[Dict[str, Any]] = None,
    orig_shape: Optional[Tuple[int, int]] = None,
    show_boxes: bool = True,
) -> np.ndarray:
    """Draws SAM2 segmentation contour & fill in ClaimPilot Emerald (#22C55E) + optional YOLO boxes."""
    mask_bool = mask.astype(bool)
    colored = np.zeros_like(bgr_img)
    colored[mask_bool] = (94, 197, 34)  # BGR for #22C55E emerald
    blended = cv2.addWeighted(colored, 0.40, bgr_img, 0.60, 0)
    out = bgr_img.copy()
    out[mask_bool] = blended[mask_bool]
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, contours, -1, (128, 222, 74), 2)

    if show_boxes and v2_report and v2_report.get("damage_instances"):
        h_out, w_out = out.shape[:2]
        img_size = v2_report.get("image_size") or [w_out, h_out]
        orig_w = float(img_size[0]) if img_size[0] else float(w_out)
        orig_h = float(img_size[1]) if img_size[1] else float(h_out)
        sx, sy = w_out / orig_w, h_out / orig_h

        for inst in v2_report.get("damage_instances", []):
            bbox = inst.get("bbox_xyxy")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = int(bbox[0] * sx), int(bbox[1] * sy), int(bbox[2] * sx), int(bbox[3] * sy)
                cv2.rectangle(out, (x1, y1), (x2, y2), (16, 185, 129), 2)
                cls_name = inst.get("class_name", "damage")
                conf = inst.get("confidence", 0.0)
                label = f"{cls_name} {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                ty = max(y1 - 6, th + 6)
                cv2.rectangle(out, (x1, ty - th - 6), (x1 + tw + 8, ty + 2), (16, 24, 16), -1)
                cv2.putText(out, label, (x1 + 4, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (74, 222, 128), 1, cv2.LINE_AA)

    return out


def normal_to_rgb(
    normal_map: np.ndarray,
    mode: str = "Inverted B&W",
    draw_vectors: bool = False,
    mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Maps 3D DSINE surface normal vectors to displayable RGB + optional real vector needle field."""
    nx = normal_map[:, :, 0]
    ny = normal_map[:, :, 1]

    if mode == "Inverted B&W":
        slope = np.sqrt(nx ** 2 + ny ** 2)
        stretched = cv2.normalize(slope, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        sharpened = clahe.apply(stretched)
        inv_bw = cv2.bitwise_not(sharpened)
        rgb = cv2.cvtColor(inv_bw, cv2.COLOR_GRAY2RGB)
    elif mode == "Negative Color":
        boosted = normal_map.copy()
        boosted[:, :, 0] *= 10.0
        boosted[:, :, 1] *= 10.0
        norm = np.linalg.norm(boosted, axis=-1, keepdims=True)
        norm[norm == 0] = 1.0
        raw_rgb = np.clip(((boosted / norm) + 1.0) / 2.0 * 255.0, 0, 255).astype(np.uint8)
        rgb = cv2.bitwise_not(raw_rgb)
    else:  # Standard Color
        boosted = normal_map.copy()
        boosted[:, :, 0] *= 10.0
        boosted[:, :, 1] *= 10.0
        norm = np.linalg.norm(boosted, axis=-1, keepdims=True)
        norm[norm == 0] = 1.0
        rgb = np.clip(((boosted / norm) + 1.0) / 2.0 * 255.0, 0, 255).astype(np.uint8)

    if draw_vectors:
        out = rgb.copy()
        h, w = normal_map.shape[:2]
        step = 22
        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                in_damage = bool(mask[y, x]) if (mask is not None and mask.shape[:2] == (h, w)) else True
                vx = float(normal_map[y, x, 0])
                vy = float(normal_map[y, x, 1])
                mag = np.hypot(vx, vy)
                if not in_damage and mag < 0.08:
                    continue
                scale = 14.0 if in_damage else 9.0
                ex = int(np.clip(x + vx * scale * 2.2, 0, w - 1))
                ey = int(np.clip(y + vy * scale * 2.2, 0, h - 1))
                color = (34, 197, 94) if in_damage else (148, 163, 184)
                cv2.arrowedLine(out, (x, y), (ex, ey), color, 1, tipLength=0.32)
        return out

    return rgb


def compute_relative_depth(depth_map: np.ndarray, mask: np.ndarray) -> np.ndarray:
    mask_bool = mask.astype(bool)
    if mask_bool.sum() > 0:
        ring_u8 = cv2.dilate(mask.astype(np.uint8), np.ones((17, 17), np.uint8), iterations=1).astype(bool) & (~mask_bool)
        if ring_u8.sum() > 0:
            baseline = float(np.median(depth_map[ring_u8]))
        elif (~mask_bool).sum() > 0:
            baseline = float(np.median(depth_map[~mask_bool]))
        else:
            baseline = float(np.median(depth_map))
    else:
        baseline = float(np.median(depth_map))

    delta = np.abs(depth_map - baseline)
    if mask_bool.sum() > 0:
        in_mask_p95 = float(np.percentile(delta[mask_bool], 95))
        cap = max(in_mask_p95 * 1.45, 5.0)
        delta = np.clip(delta, 0.0, min(cap, 65.0))
    return delta.astype(np.float32)


def compute_normal_map(depth_map: np.ndarray, mm_per_px: float) -> np.ndarray:
    dzdy, dzdx = np.gradient(depth_map.astype(np.float32))
    dzdx = dzdx / (mm_per_px + 1e-6)
    dzdy = dzdy / (mm_per_px + 1e-6)
    nx, ny, nz = -dzdx, -dzdy, np.ones_like(dzdx)
    norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    norm[norm == 0] = 1.0
    return np.stack([nx / norm, ny / norm, nz / norm], axis=-1).astype(np.float32)


def compute_metrics(depth_map: np.ndarray, normal_map: np.ndarray, mask: np.ndarray, mm_per_px: float) -> Dict[str, float]:
    mask_bool = mask.astype(bool)
    if mask_bool.sum() == 0:
        return dict(max_depth_mm=0.0, area_cm2=0.0, angle_deg=0.0)

    delta_depth = compute_relative_depth(depth_map, mask)
    mask_deltas = delta_depth[mask_bool]
    max_depth_mm = float(np.percentile(mask_deltas, 95)) if mask_deltas.size > 0 else 0.0

    area_px = int(mask_bool.sum())
    area_cm2 = float(area_px * (mm_per_px ** 2) / 100.0)

    ref = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    normals_in_mask = normal_map[mask_bool]
    dots = np.clip(normals_in_mask @ ref, -1.0, 1.0)
    angles = np.degrees(np.arccos(dots))
    angle_deg = float(np.percentile(angles, 95)) if angles.size > 0 else 0.0

    if max_depth_mm < 0.1:
        max_depth_mm = round(float(np.std(depth_map[mask_bool]) * 2.5 + 1.2), 2)

    return dict(
        max_depth_mm=round(max_depth_mm, 2),
        area_cm2=round(area_cm2, 1),
        angle_deg=round(max(angle_deg, 2.5), 2),
    )


def approval_engine(depth_mm: float, angle_deg: float, multiplier: float = 1.0) -> Dict[str, Any]:
    if depth_mm > 10.0 or angle_deg >= 15.0:
        base_cost = 18000
        return dict(status="MANUAL REVIEW", action="Panel Replacement + Full Respray", cost=int(base_cost * multiplier), color="orange", tier=3)
    if depth_mm < 3.0 and angle_deg < 5.0:
        base_cost = 2500
        return dict(status="AUTO-APPROVED", action="Compound Polish & Minor Touch-Up", cost=int(base_cost * multiplier), color="green", tier=1)
    base_cost = 6500
    return dict(status="AUTO-APPROVED", action="Paintless Dent Repair (PDR) + Blend", cost=int(base_cost * multiplier), color="green", tier=2)


# ---------------------------------------------------------------------------
# SYNTHETIC DEMO & FALLBACK PIPELINES
# ---------------------------------------------------------------------------
def _rotated_gaussian(size, center, sigma_x, sigma_y, angle_deg):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    theta = np.deg2rad(angle_deg)
    x0, y0 = center
    xp = (xx - x0) * np.cos(theta) + (yy - y0) * np.sin(theta)
    yp = -(xx - x0) * np.sin(theta) + (yy - y0) * np.cos(theta)
    return np.exp(-((xp ** 2) / (2 * sigma_x ** 2) + (yp ** 2) / (2 * sigma_y ** 2)))


def _generate_car_panel(size, base_bgr, seed=42):
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size * 0.35, size * 0.30
    shade = 1.0 - 0.45 * (np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (size * np.sqrt(2)))
    img = np.zeros((size, size, 3), dtype=np.float32)
    for c in range(3):
        img[:, :, c] = base_bgr[c] * shade
    rng = np.random.default_rng(seed)
    img = np.clip(img + rng.normal(0, 3.5, (size, size, 3)), 0, 255).astype(np.uint8)
    glare = np.zeros((size, size), dtype=np.float32)
    cv2.ellipse(glare, (int(size * 0.30), int(size * 0.22)), (58, 28), 25, 0, 360, 1.0, -1)
    glare = cv2.GaussianBlur(glare, (41, 41), 18)
    for c in range(3):
        img[:, :, c] = np.clip(img[:, :, c].astype(np.float32) + glare * 165, 0, 255).astype(np.uint8)
    px0, py0 = size - PLATE_PIXEL_WIDTH - 25, size - 65
    cv2.rectangle(img, (px0, py0), (px0 + PLATE_PIXEL_WIDTH, py0 + 38), (232, 232, 232), -1)
    cv2.rectangle(img, (px0, py0), (px0 + PLATE_PIXEL_WIDTH, py0 + 38), (35, 35, 35), 2)
    cv2.putText(img, "REF PLATE", (px0 + 14, py0 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (25, 25, 25), 1, cv2.LINE_AA)
    return img


def build_scenario(preset_name: str, size: int = IMG_SIZE, real_mm: float = DEFAULT_REF_MM):
    cfg = PRESETS.get(preset_name, PRESETS["Medium PDR Dent"])
    bgr_img = _generate_car_panel(size, cfg["base_bgr"])
    g = _rotated_gaussian(size, cfg["center"], cfg["sigma"][0], cfg["sigma"][1], cfg["angle"])
    depth_map = cfg["base_mm"] + cfg["amp_mm"] * g
    depth_map = cv2.GaussianBlur(depth_map, (9, 9), 3).astype(np.float32)
    mm_per_px = real_mm / PLATE_PIXEL_WIDTH
    normal_map = compute_normal_map(depth_map, mm_per_px)
    mask = (g > 0.18).astype(np.uint8)
    return bgr_img, depth_map, normal_map, mask, mm_per_px


def run_live_inference(bgr_img, metric_model, yolo_model=None, real_mm=DEFAULT_REF_MM, size=IMG_SIZE):
    img_out = cv2.resize(bgr_img, (size, size))
    mask = np.zeros((size, size), dtype=np.uint8)
    if yolo_model is not None:
        try:
            results = yolo_model(img_out, verbose=False)
            for r in results:
                if r.boxes is not None and len(r.boxes) > 0:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        mask[y1:y2, x1:x2] = 1
        except Exception:
            pass

    rgb = cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB)
    rgb_resized = cv2.resize(rgb, (256, 256)).astype(np.float32) / 255.0
    tensor_in = torch.from_numpy(rgb_resized).permute(2, 0, 1).unsqueeze(0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    metric_model = metric_model.to(device)
    tensor_in = tensor_in.to(device)

    with torch.no_grad():
        mask_logits, pred_depth, pred_normals = metric_model(tensor_in)
        if mask.sum() == 0:
            mask_prob = torch.sigmoid(mask_logits).squeeze().cpu().numpy()
            mask = (mask_prob > 0.35).astype(np.uint8)
            mask = cv2.resize(mask, (size, size), interpolation=cv2.INTER_NEAREST)
        depth_map = pred_depth.squeeze().cpu().numpy()
        depth_map = cv2.resize(depth_map, (size, size), interpolation=cv2.INTER_LINEAR)
        normals = pred_normals.squeeze().permute(1, 2, 0).cpu().numpy()
        normal_map = cv2.resize(normals, (size, size), interpolation=cv2.INTER_LINEAR)
        norm = np.linalg.norm(normal_map, axis=-1, keepdims=True)
        norm[norm == 0] = 1.0
        normal_map = (normal_map / norm).astype(np.float32)

    if mask.sum() == 0:
        gray = cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 100)
        edges_dilated = cv2.dilate(edges, np.ones((7, 7), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 100:
                cv2.drawContours(mask, [largest], -1, 1, -1)
        if mask.sum() == 0:
            cy, cx = size // 2, size // 2
            mask[cy - 50:cy + 50, cx - 50:cx + 50] = 1

    mm_per_px = real_mm / PLATE_PIXEL_WIDTH
    return img_out, depth_map, normal_map, mask, mm_per_px


def run_heuristic_pipeline(bgr_img, real_mm=DEFAULT_REF_MM, size=IMG_SIZE):
    img = cv2.resize(bgr_img, (size, size))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
    edges_dilated = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros((size, size), dtype=np.uint8)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > 250:
            cv2.drawContours(mask, [largest], -1, 1, -1)
    if mask.sum() == 0:
        cv2.circle(mask, (size // 2, size // 2), 55, 1, -1)
    dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dist_norm = dist_transform / dist_transform.max() if dist_transform.max() > 0 else dist_transform
    amp_mm = 3.0 + 12.0 * float(np.clip(edges_dilated.mean() / 255.0 * 6.0, 0.0, 1.0))
    depth_map = 800.0 + amp_mm * dist_norm
    depth_map = cv2.GaussianBlur(depth_map, (15, 15), 6).astype(np.float32)
    mm_per_px = real_mm / PLATE_PIXEL_WIDTH
    normal_map = compute_normal_map(depth_map, mm_per_px)
    return img, depth_map, normal_map, mask, mm_per_px


@st.cache_data(show_spinner=False, ttl=600)
def execute_cached_pipeline(
    image_bytes: bytes,
    engine_mode: str = "v3",
    real_mm: float = 500.0,
    imgsz: int = 640,
    use_tta: bool = False,
):
    """
    Runs the selected vision pipeline on raw image bytes and caches the output arrays
    and telemetry report in memory so UI interactions are instantaneous.
    """
    arr = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("Could not decode image bytes.")

    metric_model, yolo_model, v2_models = load_all_models()
    device = "cuda" if (HAS_TORCH and torch.cuda.is_available()) else "cpu"

    if engine_mode == "v3" and v2_models is not None and HAS_V2_PIPELINE:
        yolo_m, depth_proc, depth_m, sam2_proc, sam2_m, dsine_m = v2_models
        bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report = run_v2_pipeline_full(
            decoded,
            yolo_m,
            depth_proc,
            depth_m,
            sam2_proc,
            sam2_m,
            dsine_m,
            real_mm=real_mm,
            size=IMG_SIZE,
            device=device,
            imgsz=imgsz,
            use_tta=use_tta,
        )
        active_label = "Advanced v3 (YOLOv11m + Depth Anything V2 + SAM2 + DSINE)"
        return bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report, active_label

    if metric_model is not None:
        bgr_img, depth_map, normal_map, mask, mm_per_px = run_live_inference(
            decoded, metric_model, yolo_model, real_mm, IMG_SIZE
        )
        metrics = compute_metrics(depth_map, normal_map, mask, mm_per_px)
        return bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, None, "Legacy v1 (Multi-Task CNN)"

    bgr_img, depth_map, normal_map, mask, mm_per_px = run_heuristic_pipeline(decoded, real_mm, IMG_SIZE)
    metrics = compute_metrics(depth_map, normal_map, mask, mm_per_px)
    return bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, None, "Heuristic Fallback"


# ---------------------------------------------------------------------------
# INTERACTIVE PLOTLY CHARTS (DARK CRYSTAL GLASS THEME)
# ---------------------------------------------------------------------------
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(16,16,24,0.45)",
    font=dict(family="Inter, sans-serif", color="#E5E7EB", size=12),
)


def plot_depth_heatmap(delta_depth: np.ndarray) -> go.Figure:
    fig = go.Figure(
        data=go.Heatmap(
            z=delta_depth,
            colorscale="Turbo",
            colorbar=dict(
                title=dict(text="ΔZ (mm)", font=dict(size=11, color="#9BA3AF")),
                thickness=14,
                tickfont=dict(size=10, color="#9BA3AF"),
            ),
            hovertemplate="<b>Pixel</b> (%{x}, %{y})<br><b>Deformation ΔZ:</b> %{z:.2f} mm<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", visible=False)
    fig.update_xaxes(visible=False)
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        margin=dict(l=0, r=0, t=8, b=0),
        height=350,
    )
    return fig


def plot_3d_mesh(depth_map: np.ndarray, delta_depth: Optional[np.ndarray] = None) -> go.Figure:
    surface_data = delta_depth if delta_depth is not None else depth_map
    z_sub = surface_data[::3, ::3]
    fig = go.Figure(
        data=[
            go.Surface(
                z=z_sub,
                colorscale="Turbo",
                colorbar=dict(
                    title=dict(text="mm", font=dict(size=11, color="#9BA3AF")),
                    thickness=12,
                    tickfont=dict(size=10, color="#9BA3AF"),
                ),
                contours=dict(
                    z=dict(show=True, usecolormap=True, highlightcolor="#22C55E", project_z=True)
                ),
                hovertemplate="<b>Span X:</b> %{x}<br><b>Span Y:</b> %{y}<br><b>Deformation:</b> %{z:.2f} mm<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        scene=dict(
            bgcolor="rgba(7,7,9,0.85)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(
                title="ΔZ Indentation (mm)",
                gridcolor="rgba(255,255,255,0.08)",
                zerolinecolor="rgba(255,255,255,0.15)",
                color="#9BA3AF",
            ),
            camera=dict(eye=dict(x=1.25, y=-1.25, z=0.85)),
            aspectratio=dict(x=1, y=1, z=0.40),
        ),
        margin=dict(l=0, r=0, t=8, b=0),
        height=350,
    )
    return fig


def plot_depth_cross_section(delta_depth: np.ndarray, mask: np.ndarray, mm_per_px: float) -> go.Figure:
    """Plots horizontal & vertical millimeter indentation profiles through the peak dent centroid."""
    h, w = delta_depth.shape[:2]
    mask_bool = mask.astype(bool)
    if np.any(mask_bool):
        masked_vals = np.where(mask_bool, delta_depth, -1.0)
        peak_y, peak_x = np.unravel_index(int(np.argmax(masked_vals)), delta_depth.shape)
    else:
        peak_y, peak_x = h // 2, w // 2

    horiz_profile = delta_depth[peak_y, :]
    vert_profile = delta_depth[:, peak_x]
    x_mm = np.arange(w) * mm_per_px
    y_mm = np.arange(h) * mm_per_px

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_mm,
            y=-horiz_profile,
            mode="lines",
            name=f"Horizontal Slice (y={peak_y}px)",
            line=dict(color="#22C55E", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.14)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=y_mm,
            y=-vert_profile,
            mode="lines",
            name=f"Vertical Slice (x={peak_x}px)",
            line=dict(color="#F59E0B", width=2, dash="dot"),
        )
    )
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        title=dict(
            text=f"Dent Basin Cross-Section Profile at Peak Locus ({peak_x}, {peak_y})",
            font=dict(size=12, color="#D1D5DB"),
        ),
        xaxis=dict(title="Panel Span (mm)", gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(title="Indentation Profile -ΔZ (mm)", gridcolor="rgba(255,255,255,0.06)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=16, t=40, b=36),
        height=320,
    )
    return fig


def plot_glare_histogram_plotly(before_bgr: np.ndarray, after_bgr: np.ndarray) -> go.Figure:
    """Interactive Plotly histogram of HSV V-channel brightness before vs. after CLAHE."""
    v_before = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2HSV)[:, :, 2].flatten()
    v_after = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2HSV)[:, :, 2].flatten()

    hist_b, bins = np.histogram(v_before, bins=48, range=(0, 255))
    hist_a, _ = np.histogram(v_after, bins=48, range=(0, 255))
    bin_centers = 0.5 * (bins[:-1] + bins[1:])

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=bin_centers,
            y=hist_b,
            name="Raw Input (With Specular Glare)",
            marker_color="rgba(239, 68, 68, 0.55)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=bin_centers,
            y=hist_a,
            name="After CLAHE De-glare",
            marker_color="rgba(5, 150, 105, 0.78)",
        )
    )
    fig.add_vline(
        x=233,
        line_dash="dash",
        line_color="#F59E0B",
        annotation_text="Glare Clipping Cutoff (233)",
        annotation_position="top left",
        annotation_font=dict(size=10, color="#FBBF24"),
    )
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        barmode="overlay",
        title=dict(text="Specular Glare & Luminance Distribution (V-Channel)", font=dict(size=12, color="#D1D5DB")),
        xaxis=dict(title="Luminance Intensity (0–255)", gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(title="Pixel Count", gridcolor="rgba(255,255,255,0.06)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
        margin=dict(l=36, r=12, t=38, b=32),
        height=230,
    )
    return fig


def plot_instance_telemetry_chart(v2_report: Dict[str, Any]) -> Optional[go.Figure]:
    """Dual-axis bar/line chart of per-instance Damaged Area (cm²) and Crease Angle (°)."""
    instances = v2_report.get("damage_instances") or []
    if not instances:
        return None

    labels = [f"#{i['instance_id']} {i['class_name']} ({int(i.get('confidence', 0)*100)}%)" for i in instances]
    areas = [float(i.get("area_cm2") or 0.0) for i in instances]
    depths = [float(i.get("max_depth_mm") or 0.0) for i in instances]
    angles = [float(i.get("crease_angle_deg") or 0.0) for i in instances]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=areas,
            name="Surface Area (cm²)",
            marker_color="#059669",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=depths,
            name="Max Depth ΔZ (mm)",
            marker_color="#3B82F6",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=angles,
            name="DSINE Crease Angle (°)",
            mode="lines+markers",
            line=dict(color="#F59E0B", width=2.5),
            marker=dict(size=8),
        )
    )
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        barmode="group",
        title=dict(text="Per-Instance Physical Severity Telemetry", font=dict(size=13, color="#F2F2F2")),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(title="Magnitude (cm² / mm / deg)", gridcolor="rgba(255,255,255,0.06)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=42, b=36),
        height=310,
    )
    return fig


def plot_stage_timing_chart(v2_report: Dict[str, Any]) -> Optional[go.Figure]:
    timing = v2_report.get("timing_sec") or {}
    stages = [(k.capitalize(), float(v)) for k, v in timing.items() if k != "total"]
    if not stages:
        return None

    names = [s[0] for s in stages]
    secs = [round(s[1], 3) for s in stages]

    fig = go.Figure(
        go.Bar(
            x=secs,
            y=names,
            orientation="h",
            marker=dict(
                color=["#10B981", "#059669", "#34D399", "#6EE7B7"][: len(names)],
            ),
            text=[f"{s:.2f}s" for s in secs],
            textposition="auto",
        )
    )
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        title=dict(
            text=f"Pipeline Stage Execution Latency (Total: {timing.get('total', sum(secs)):.2f}s)",
            font=dict(size=13, color="#F2F2F2"),
        ),
        xaxis=dict(title="Seconds (s)", gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(autorange="reversed", gridcolor="rgba(255,255,255,0.06)"),
        margin=dict(l=90, r=20, t=42, b=36),
        height=260,
    )
    return fig


# ---------------------------------------------------------------------------
# GEMINI NARRATIVE AUDIT (ENVIRONMENT KEY ONLY — NO HARDCODED KEYS)
# ---------------------------------------------------------------------------
DEFAULT_AUDIT_MODEL = "gemini-3.8-flash"


def _resolve_audit_model() -> str:
    """AI_AUDIT_MODEL wins; otherwise reuse FRAUD_LLM_MODEL only if it names a Gemini model."""
    explicit = (_ENV_CFG.get("AI_AUDIT_MODEL") or "").strip()
    if explicit:
        return explicit
    shared = (_ENV_CFG.get("FRAUD_LLM_MODEL") or "").strip()
    if shared.lower().startswith("gemini"):
        return shared
    return DEFAULT_AUDIT_MODEL


def generate_gemini_inr_estimate(
    bgr_img: np.ndarray,
    metrics: Dict[str, Any],
    decision: Dict[str, Any],
    panel_type: str,
    user_narrative: str,
    api_key: Optional[str] = None,
) -> Optional[str]:
    resolved_key = (
        api_key
        or _ENV_CFG.get("FRAUD_LLM_API_KEY")
        or _ENV_CFG.get("GEMINI_API_KEY")
        or _ENV_CFG.get("GOOGLE_API_KEY")
    )
    if not resolved_key or not HAS_GEMINI:
        return None
    model_name = _resolve_audit_model()

    _, encoded_img = cv2.imencode(".jpg", bgr_img)
    img_bytes = encoded_img.tobytes()

    prompt = f"""
You are an expert Senior Insurance Adjuster and Automotive Body Repair Estimator in India.
Analyze the provided vehicle damage photo alongside the user's incident narrative and 3D Metric Sensor Telemetry:

[USER INCIDENT NARRATIVE / STATEMENT]
"{user_narrative}"

[3D METRIC SENSOR TELEMETRY]
- Max Dent Depth (ΔZ): {metrics['max_depth_mm']} mm
- Damaged Surface Area: {metrics['area_cm2']} cm²
- Surface Normal Crease Angle: {metrics['angle_deg']}°
- Panel Material: {panel_type}
- Baseline Rule Engine Status: {decision['status']} ({decision['action']})

Provide a concise, professional assessment report formatted in clean Markdown:
1. **User Narrative vs. Physical Severity Consistency Audit:**
   - Cross-examine the user's statement against the visual image and 3D metric sensor measurements.
   - State an explicit Verdict: `[CONSISTENT WITH STATEMENT]` or `[INCONSISTENCY / POTENTIAL FRAUD FLAG]`.
2. **Itemized Repair Cost Estimate in INR (₹):**
   - Itemize Body Repair Labor (Denting/PDR), Surface Primer & Paint Respray, and Material Surcharge.
3. **Final Adjuster Recommendation:**
   - State whether to auto-approve or route to a senior physical surveyor.
"""
    try:
        if GEMINI_SDK == "genai":
            client = genai.Client(api_key=resolved_key)
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
            )
            return response.text
        elif GEMINI_SDK == "legacy":
            genai_legacy.configure(api_key=resolved_key)
            model = genai_legacy.GenerativeModel(model_name)
            response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_bytes}])
            return response.text
    except Exception as e:
        return f"⚠️ AI audit notice: {str(e)}"
    return None
