"""
ClaimPilot AI — Agent / Adjuster Full 3D & DSINE Telemetry Workspace (agent_app.py)
===================================================================================
Dedicated Streamlit application for Insurance Agents & Senior Adjusters.
Linked from React's `AgentClaimDetails.tsx` (/agent/claims/:id).

Displays ALL adjuster telemetry, interactive graphs, and forensic audits:
  - CLAHE Glare Suppression + Interactive Specular Glare Histogram (Plotly)
  - SAM2 + YOLOv11m Instance Segmentation with Bounding Boxes & IoU Scores
  - 2D ΔZ Millimeter Indentation Heatmap + Interactive 3D Surface Mesh + Dent Cross-Section Profile
  - DSINE 3D Surface Normal Vectors with Real Sampled Vector Field Needles
  - 3-Tier Scale Calibration Telemetry (Plate / Wheel / Metric Prior) + Stage Latency Graphs
  - Live Fraud Risk Score & Indicators from Supabase (`claim_fraud_analyses`)
  - Gemini 2.5 Flash Narrative vs. 3D Physical Severity Consistency Audit
  - Official Audit Certificate & JSON Deliverables

Run standalone on Port 8502:
    streamlit run agent_app.py --server.port 8502
"""

import json
import hashlib
from datetime import datetime, timezone

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from extendview_core import (
    DEFAULT_REF_MM,
    HAS_V2_PIPELINE,
    IMG_SIZE,
    PLATE_PIXEL_WIDTH,
    PRESETS,
    apply_clahe_glare_reduction,
    approval_engine,
    build_scenario,
    check_photo_quality,
    compute_metrics,
    compute_relative_depth,
    download_image_from_url,
    execute_cached_pipeline,
    fetch_live_claim_bundle,
    generate_gemini_inr_estimate,
    inject_claimpilot_theme,
    load_all_models,
    normal_to_rgb,
    overlay_mask_and_boxes,
    plot_3d_mesh,
    plot_depth_cross_section,
    plot_depth_heatmap,
    plot_glare_histogram_plotly,
    plot_instance_telemetry_chart,
    plot_stage_timing_chart,
    render_topbar,
)


def build_export_payload(
    scenario_label,
    metrics,
    decision,
    mm_per_px,
    backend_mode,
    claim_id,
    panel_type,
    quality_conf,
    img_hash,
    user_narrative,
    gemini_narrative,
    v2_report=None,
    fraud_analysis=None,
):
    payload = {
        "claim_id": claim_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "digital_fingerprint_sha256": img_hash,
        "photo_quality_score": f"{quality_conf}%",
        "user_incident_narrative": user_narrative,
        "pipeline": {
            "backend_mode": backend_mode,
            "detector_2d": "YOLOv11m (Per-Class Tuned)",
            "depth_3d_engine": "Depth Anything V2 + 3-Tier Metric Calibration",
            "segmentation_engine": "SAM2.1 Hiera Small",
            "surface_normals_engine": "DSINE",
        },
        "scenario": scenario_label,
        "panel_specification": panel_type,
        "calibration": {
            "mm_per_pixel": round(mm_per_px, 4),
        },
        "measurements": {
            "max_dent_depth_mm": metrics["max_depth_mm"],
            "damaged_area_cm2": metrics["area_cm2"],
            "angular_shift_deg": metrics["angle_deg"],
        },
        "decision_engine": {
            "status": decision["status"],
            "recommended_action": decision["action"],
            "benchmark_cost_inr": f"₹{decision['cost']:,}",
            "rule_tier": decision["tier"],
        },
        "live_fraud_assessment": fraud_analysis or {},
        "gemini_narrative_analysis": gemini_narrative or "Not executed",
    }
    if v2_report:
        payload["v3_detailed_report"] = {k: v for k, v in v2_report.items() if k != "_artifacts"}
    return payload


def run_agent_extendview(set_page_cfg: bool = True):
    if set_page_cfg:
        st.set_page_config(
            page_title="ClaimPilot AI | Adjuster 3D & DSINE Telemetry",
            layout="wide",
            page_icon="🔬",
            initial_sidebar_state="expanded",
        )

    inject_claimpilot_theme()
    metric_model, yolo_model, v2_models = load_all_models()

    qp = st.query_params
    claim_id = qp.get("claim_id") or qp.get("id") or ""
    token = qp.get("token") or ""

    live_bundle = None
    if claim_id:
        with st.spinner("Fetching live claim, AI telemetry, and fraud analysis from ClaimPilot backend..."):
            live_bundle = fetch_live_claim_bundle(claim_id, token=token, role="agent")

    claim_obj = (live_bundle or {}).get("claim") or {}
    claimant_obj = (live_bundle or {}).get("claimant") or {}
    ai_analysis = (live_bundle or {}).get("ai_analysis") or {}
    fraud_analysis = (live_bundle or {}).get("fraud_analysis") or {}
    photos = (live_bundle or {}).get("photos") or []

    claim_display_id = claim_obj.get("claim_number") or claim_obj.get("id") or (claim_id if claim_id else "CLM-WORKBENCH")
    vehicle_name = claim_obj.get("vehicle_name") or claim_obj.get("vehicle") or "Vehicle Inspection"
    raw_status = (claim_obj.get("status") or "Under Review").replace("_", " ").title()
    back_path = f"/agent/claims/{claim_id}" if claim_id else "/agent/claims"

    render_topbar(
        role_label="Adjuster 3D & DSINE Workbench",
        claim_id=claim_id,
        claim_display_id=claim_display_id,
        vehicle_name=vehicle_name,
        status_text=raw_status,
        back_path=back_path,
    )

    # ---- Sidebar Adjuster Controls ----
    st.sidebar.markdown("## 🔬 Adjuster Telemetry Controls")
    st.sidebar.caption("Full 2D/3D Vision, DSINE Normals & Forensic Audit")
    st.sidebar.markdown("---")

    engine_options = []
    if v2_models is not None and HAS_V2_PIPELINE:
        engine_options.append("Advanced v3 (YOLOv11m + Depth Anything V2 + SAM2 + DSINE)")
    if metric_model is not None:
        engine_options.append("Legacy v1 (Multi-Task CNN)")
    engine_options.append("Heuristic / Synthetic Pipeline")

    backend_choice = st.sidebar.radio("Vision Pipeline Engine", engine_options, index=0)
    engine_code = "v3" if "Advanced v3" in backend_choice else ("v1" if "Legacy v1" in backend_choice else "heuristic")

    cpu_optimized = st.sidebar.checkbox(
        "Cloud Run / CPU Fast Mode (640px, TTA off)",
        value=True,
        help="Runs YOLOv11m at 640px without Test-Time Augmentation for ~3x faster CPU latency.",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Evidence Source")
    source_options = []
    if photos:
        source_options.append(f"Live Claim Evidence ({len(photos)} photos)")
    source_options.extend(["Custom Photo Upload", "Interactive Synthetic Preset"])
    input_mode = st.sidebar.radio("Input Source", source_options, index=0)

    selected_photo_idx = 0
    uploaded_file = None
    preset_name = "Medium PDR Dent"

    if input_mode.startswith("Live Claim Evidence"):
        photo_labels = [f"Evidence Photo #{i+1} ({p.get('category', 'photo')})" for i, p in enumerate(photos)]
        selected_photo_idx = st.sidebar.selectbox(
            "Select Claim Photo",
            range(len(photos)),
            format_func=lambda i: photo_labels[i],
        )
        default_narrative = (
            claim_obj.get("description")
            or "Policyholder submitted vehicle damage claim for adjuster review."
        )
    elif input_mode == "Custom Photo Upload":
        uploaded_file = st.sidebar.file_uploader("Upload inspection photo", type=["jpg", "jpeg", "png"])
        default_narrative = claim_obj.get("description") or "Reversed into a concrete bollard in an underground parking garage."
    else:
        preset_name = st.sidebar.selectbox("Damage Preset", list(PRESETS.keys()))
        st.sidebar.caption(f"_{PRESETS[preset_name]['blurb']}_")
        default_narrative = PRESETS[preset_name]["narrative"]

    user_narrative = st.sidebar.text_area(
        "Policyholder Incident Statement",
        value=default_narrative,
        height=90,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎨 DSINE & Overlay Controls")
    normal_display_mode = st.sidebar.selectbox(
        "DSINE Surface Normal Style",
        ["Inverted B&W", "Standard Color", "Negative Color"],
        index=0,
    )
    show_vector_needles = st.sidebar.checkbox("Overlay Sampled DSINE Vector Needles", value=True)
    show_yolo_boxes = st.sidebar.checkbox("Overlay YOLOv11m BBoxes on SAM2 Mask", value=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🚘 Material & Scale Calibration")
    panel_type = st.sidebar.selectbox(
        "Panel Material Multiplier",
        ["Standard Steel (1.0x)", "Aluminum Fender (1.5x)", "Plastic Bumper (0.8x)", "Composite Hood (1.3x)"],
    )
    multiplier = float(panel_type.split("(")[1].replace("x)", ""))
    real_mm = st.sidebar.slider("Reference Plate Width (mm)", 300, 700, DEFAULT_REF_MM, step=10)

    # ---- Execute Pipeline on Selected Source ----
    v2_report = None
    raw_bytes_for_hash = b""

    if input_mode.startswith("Live Claim Evidence") and photos:
        photo_url = photos[selected_photo_idx]["url"]
        decoded = download_image_from_url(photo_url)
        if decoded is None:
            st.warning("Could not download live claim photo from signed URL; showing synthetic reference scan.")
            bgr_img, depth_map, normal_map, mask, mm_per_px = build_scenario(preset_name, IMG_SIZE, real_mm)
            metrics = compute_metrics(depth_map, normal_map, mask, mm_per_px)
            backend_mode = "Synthetic Fallback (URL Unreachable)"
            raw_bytes_for_hash = bgr_img.tobytes()
            scenario_label = f"{claim_display_id}_photo_{selected_photo_idx+1}"
        else:
            _, enc = cv2.imencode(".jpg", decoded)
            raw_bytes_for_hash = enc.tobytes()
            imgsz = 640 if cpu_optimized else 1280
            with st.spinner(f"Running {backend_choice} on Claim Photo #{selected_photo_idx+1}..."):
                bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report, backend_mode = (
                    execute_cached_pipeline(
                        raw_bytes_for_hash,
                        engine_mode=engine_code,
                        real_mm=float(real_mm),
                        imgsz=imgsz,
                        use_tta=not cpu_optimized,
                    )
                )
            scenario_label = f"{claim_display_id}_photo_{selected_photo_idx+1}"

    elif input_mode == "Custom Photo Upload":
        if uploaded_file is None:
            st.info("👈 Upload a vehicle inspection photo in the sidebar or switch to Live Claim Evidence / Synthetic Preset.")
            st.stop()
        raw_bytes_for_hash = uploaded_file.read()
        imgsz = 640 if cpu_optimized else 1280
        with st.spinner(f"Running {backend_choice} on {uploaded_file.name}..."):
            bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report, backend_mode = (
                execute_cached_pipeline(
                    raw_bytes_for_hash,
                    engine_mode=engine_code,
                    real_mm=float(real_mm),
                    imgsz=imgsz,
                    use_tta=not cpu_optimized,
                )
            )
        scenario_label = uploaded_file.name

    else:
        bgr_img, depth_map, normal_map, mask, mm_per_px = build_scenario(preset_name, IMG_SIZE, real_mm)
        metrics = compute_metrics(depth_map, normal_map, mask, mm_per_px)
        backend_mode = "Interactive Synthetic Preset"
        raw_bytes_for_hash = bgr_img.tobytes()
        scenario_label = preset_name

    # ---- Compute Derived Visuals & Guardrail Telemetry ----
    quality_conf, quality_status, glare_pct, blur_var = check_photo_quality(bgr_img)
    img_hash = hashlib.sha256(raw_bytes_for_hash).hexdigest()[:12].upper()
    glare_reduced = apply_clahe_glare_reduction(bgr_img)
    mask_overlay_img = overlay_mask_and_boxes(bgr_img, mask, v2_report=v2_report, show_boxes=show_yolo_boxes)
    normal_rgb = normal_to_rgb(normal_map, mode=normal_display_mode, draw_vectors=show_vector_needles, mask=mask)
    delta_depth = compute_relative_depth(depth_map, mask)
    decision = approval_engine(metrics["max_depth_mm"], metrics["angle_deg"], multiplier)

    # Calibration details
    calib_info = (v2_report or {}).get("calibration", {}).get("depth_metric", {})
    calib_tier = (calib_info.get("tier") or calib_info.get("method") or "tier_1_plate").replace("_", " ").upper()
    calib_conf = (calib_info.get("confidence") or "high").upper()
    focal_px = calib_info.get("focal_length_px")

    # Fraud details (from live backend / Supabase `claim_fraud_analyses`)
    fraud_score = fraud_analysis.get("fraud_score")
    if fraud_score is None:
        fraud_score = claim_obj.get("fraud_score")
    fraud_risk_level = (
        fraud_analysis.get("risk_level")
        or claim_obj.get("risk_level")
        or ("HIGH RISK" if (fraud_score or 0) >= 67 else ("MEDIUM RISK" if (fraud_score or 0) >= 34 else "LOW RISK"))
    )
    fraud_score_display = f"{int(fraud_score)} / 100" if fraud_score is not None else "0 / 100"
    fraud_color = "#F87171" if "HIGH" in str(fraud_risk_level).upper() else ("#FBBF24" if "MED" in str(fraud_risk_level).upper() else "#4ADE80")

    # Cost estimate details
    est_min = ai_analysis.get("estimated_cost_min")
    est_max = ai_analysis.get("estimated_cost_max")
    if est_min and est_max:
        cost_kpi_val = f"₹{int(float(est_min)):,}–₹{int(float(est_max)):,}"
        cost_kpi_sub = f"Rule Benchmark: ₹{decision['cost']:,}"
    else:
        cost_kpi_val = f"₹{decision['cost']:,}"
        cost_kpi_sub = f"{decision['status']} (Tier {decision['tier']})"

    # ---- 6-Card High-Density Adjuster KPI Strip ----
    st.markdown(
        f"""
        <div class="cp-kpi-grid">
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Max Dent Depth (ΔZ)</div>
                <div class="cp-kpi-value">{metrics['max_depth_mm']} mm</div>
                <div class="cp-kpi-sub">95th pct local basin relief</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Damaged Surface Area</div>
                <div class="cp-kpi-value">{metrics['area_cm2']} cm²</div>
                <div class="cp-kpi-sub">SAM2 mask: {int(mask.sum()):,} px</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">DSINE Crease Angle</div>
                <div class="cp-kpi-value">{metrics['angle_deg']}°</div>
                <div class="cp-kpi-sub">{decision['action']}</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Scale Calibration</div>
                <div class="cp-kpi-value">{mm_per_px:.3f} mm/px</div>
                <div class="cp-kpi-sub">{calib_tier} ({calib_conf})</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Repair Estimate (INR)</div>
                <div class="cp-kpi-value" style="color:#4ADE80;">{cost_kpi_val}</div>
                <div class="cp-kpi-sub">{cost_kpi_sub}</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Fraud Risk Telemetry</div>
                <div class="cp-kpi-value" style="color:{fraud_color};">{fraud_score_display}</div>
                <div class="cp-kpi-sub">{fraud_risk_level} · Quality {quality_conf}%</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 4 Main Adjuster Workspace Tabs ----
    tab_vision, tab_instances, tab_fraud, tab_export = st.tabs([
        "🧊 2D/3D Vision & DSINE Telemetry",
        "📊 Per-Instance Analytics & Calibration Graphs",
        "🛡️ Fraud, EXIF & Gemini Cross-Modal Audit",
        "🧾 Deliverables & Official Certificate",
    ])

    # =========================================================================
    # TAB 1: 2D/3D VISION & DSINE TELEMETRY
    # =========================================================================
    with tab_vision:
        r1c1, r1c2 = st.columns(2, gap="large")

        with r1c1:
            with st.container(border=True):
                st.markdown("#### ① Input RGB + CLAHE Specular Glare Suppression")
                st.caption(
                    f"Photo Quality: **{quality_conf}% ({quality_status})** · Specular Glare (>240 V): **{glare_pct}%** · Laplacian Focus: **{blur_var}**"
                )
                img_a, img_b = st.columns(2)
                img_a.image(cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB), caption="Raw Evidence Input", use_container_width=True)
                img_b.image(cv2.cvtColor(glare_reduced, cv2.COLOR_BGR2RGB), caption="CLAHE L-Channel Normalized", use_container_width=True)
                st.plotly_chart(plot_glare_histogram_plotly(bgr_img, glare_reduced), use_container_width=True)

        with r1c2:
            with st.container(border=True):
                st.markdown("#### ② SAM2.1 + YOLOv11m Damage Segmentation")
                num_inst = len((v2_report or {}).get("damage_instances") or [])
                st.caption(
                    f"Segmented Area: **{int(mask.sum()):,} px ({metrics['area_cm2']} cm²)** · Detected Instances: **{num_inst}** · Engine: **{backend_mode}**"
                )
                st.image(
                    cv2.cvtColor(mask_overlay_img, cv2.COLOR_BGR2RGB),
                    caption="SAM2 pixel-accurate mask contour + YOLOv11m per-class thresholded detections",
                    use_container_width=True,
                )

        r2c1, r2c2 = st.columns(2, gap="large")

        with r2c1:
            with st.container(border=True):
                st.markdown("#### ③ Relative Damage Deformation (ΔZ Millimeter Relief)")
                st.caption(
                    f"Peak Indentation: **{metrics['max_depth_mm']} mm** · Scale: **{mm_per_px:.4f} mm/px** · Calibration: **{calib_tier}**"
                )
                dt1, dt2, dt3 = st.tabs([
                    "2D Heatmap (ΔZ mm)",
                    "Interactive 3D Surface Mesh",
                    "Dent Basin Cross-Section Graph",
                ])
                with dt1:
                    st.plotly_chart(plot_depth_heatmap(delta_depth), use_container_width=True)
                with dt2:
                    st.plotly_chart(plot_3d_mesh(depth_map, delta_depth), use_container_width=True)
                with dt3:
                    st.plotly_chart(plot_depth_cross_section(delta_depth, mask, mm_per_px), use_container_width=True)

        with r2c2:
            with st.container(border=True):
                nc1, nc2 = st.columns([2, 1])
                with nc1:
                    st.markdown("#### ④ DSINE — Surface Normal Vectors & Crease Map")
                    st.caption(
                        f"Peak Angular Shift: **{metrics['angle_deg']}°** · Vector Field: **{'Real Sampled (nx, ny)' if show_vector_needles else 'Hidden'}**"
                    )
                with nc2:
                    inline_norm_mode = st.selectbox(
                        "DSINE Mode",
                        ["Inverted B&W", "Standard Color", "Negative Color"],
                        index=["Inverted B&W", "Standard Color", "Negative Color"].index(normal_display_mode),
                        key="agent_inline_norm_mode",
                        label_visibility="collapsed",
                    )
                norm_img = normal_to_rgb(normal_map, mode=inline_norm_mode, draw_vectors=show_vector_needles, mask=mask)
                st.image(
                    norm_img,
                    caption=f"DSINE Surface Orientation ({inline_norm_mode}) · Emerald needles show local normal deflection inside damage mask",
                    use_container_width=True,
                )

    # =========================================================================
    # TAB 2: PER-INSTANCE ANALYTICS & CALIBRATION GRAPHS
    # =========================================================================
    with tab_instances:
        if v2_report:
            with st.container(border=True):
                st.markdown("#### 📏 3-Tier Metric Depth Calibration Telemetry")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calibration Tier", calib_tier)
                c2.metric("Confidence Level", calib_conf)
                c3.metric("Calibrated Scale", f"{mm_per_px:.4f} mm/px")
                c4.metric("Camera Focal Length", f"{focal_px:.1f} px" if focal_px else "Assumed 60° HFOV")
                if calib_info.get("note"):
                    st.caption(f"ℹ️ {calib_info['note']}")

            g_col1, g_col2 = st.columns(2, gap="large")
            with g_col1:
                with st.container(border=True):
                    inst_fig = plot_instance_telemetry_chart(v2_report)
                    if inst_fig:
                        st.plotly_chart(inst_fig, use_container_width=True)
                    else:
                        st.info("No individual YOLO bounding boxes met threshold; used full-panel salient contour.")

            with g_col2:
                with st.container(border=True):
                    time_fig = plot_stage_timing_chart(v2_report)
                    if time_fig:
                        st.plotly_chart(time_fig, use_container_width=True)
                    else:
                        st.info("Stage timing telemetry not available.")

            instances = v2_report.get("damage_instances") or []
            if instances:
                with st.container(border=True):
                    st.markdown("#### 🔬 Per-Instance Damage Telemetry Table")
                    rows = []
                    for inst in instances:
                        rows.append({
                            "Instance #": inst.get("instance_id"),
                            "Damage Class": inst.get("class_name"),
                            "YOLO Conf": f"{inst.get('confidence', 0)*100:.1f}%",
                            "SAM2 IoU": inst.get("mask_iou_score"),
                            "Mask Area (px)": inst.get("area_px"),
                            "Area (cm²)": inst.get("area_cm2"),
                            "Max Depth ΔZ (mm)": inst.get("max_depth_mm"),
                            "DSINE Crease (°)": inst.get("crease_angle_deg"),
                            "Crease Status": inst.get("crease_status"),
                            "BBox [x1, y1, x2, y2]": [round(x, 1) for x in (inst.get("bbox_xyxy") or [])],
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Switch the Vision Pipeline Engine to **Advanced v3** in the sidebar to view per-instance SAM2/DSINE telemetry and stage latency graphs.")

    # =========================================================================
    # TAB 3: FRAUD, EXIF & GEMINI CROSS-MODAL AUDIT
    # =========================================================================
    with tab_fraud:
        f_col1, f_col2 = st.columns([1, 1], gap="large")

        with f_col1:
            with st.container(border=True):
                st.markdown("#### 🛡️ Forensic & Fraud Assessment (`claim_fraud_analyses`)")
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:0.85rem 1rem; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid rgba(255,255,255,0.10); margin-bottom:1rem;">
                        <div>
                            <div style="font-size:0.75rem; color:#9BA3AF; text-transform:uppercase; font-weight:600;">Composite Fraud Score</div>
                            <div class="cp-mono" style="font-size:1.65rem; font-weight:700; color:{fraud_color};">{fraud_score_display}</div>
                        </div>
                        <span class="cp-badge" style="background:{fraud_color}22; color:{fraud_color}; border:1px solid {fraud_color}55; font-size:0.85rem; padding:0.35rem 0.85rem;">
                            {fraud_risk_level}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                indicators = fraud_analysis.get("indicators") or []
                if indicators:
                    for ind in indicators:
                        passed = bool(ind.get("passed", True))
                        badge_txt = "VERIFIED" if passed else "SUSPICIOUS FLAG"
                        b_col = "#4ADE80" if passed else "#F87171"
                        msg = ind.get("message") or ind.get("name") or "Check completed"
                        st.markdown(
                            f"""
                            <div style="padding:0.65rem 0.85rem; margin-bottom:0.5rem; border-radius:10px; background:rgba(14,14,20,0.65); border:1px solid rgba(255,255,255,0.08);">
                                <span class="cp-mono" style="font-size:0.72rem; font-weight:700; color:{b_col};">[{badge_txt}]</span>
                                <span style="font-size:0.85rem; color:#E5E7EB; margin-left:0.5rem;">{msg}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption(
                        f"Digital Fingerprint (SHA-256): `{img_hash}` · Photo Quality: `{quality_conf}% ({quality_status})` · Specular Glare: `{glare_pct}%`"
                    )
                    if not claim_id:
                        st.info("Open this workbench from an active claim in the Agent Portal to load live Supabase EXIF, pHash duplicate, and ELA tampering indicators.")

        with f_col2:
            with st.container(border=True):
                st.markdown("#### 🤖 Gemini 2.5 Flash — Narrative vs. 3D Telemetry Audit")
                st.caption(
                    "Cross-examines the policyholder's written incident statement against measured 3D dent depth (ΔZ) and DSINE crease angle."
                )
                run_gemini_btn = st.button("⚡ Run Gemini Cross-Modal Consistency Audit")
                gemini_narrative = st.session_state.get(f"gemini_audit_{scenario_label}")

                if run_gemini_btn:
                    with st.spinner("Auditing incident statement against 3D sensor telemetry via Gemini 2.5 Flash..."):
                        gemini_narrative = generate_gemini_inr_estimate(
                            bgr_img, metrics, decision, panel_type, user_narrative
                        )
                        st.session_state[f"gemini_audit_{scenario_label}"] = gemini_narrative

                if gemini_narrative:
                    st.markdown(gemini_narrative)
                else:
                    st.markdown(
                        f"""
                        **Rule-Engine Baseline Pre-Check:**
                        - **Statement:** *"{user_narrative}"*
                        - **Measured Physical Relief:** `{metrics['max_depth_mm']} mm` depth across `{metrics['area_cm2']} cm²` with `{metrics['angle_deg']}°` surface normal crease.
                        - **Triage Recommendation:** **{decision['status']}** — `{decision['action']}` (Benchmark: **₹{decision['cost']:,} INR** on `{panel_type}`).
                        *(Click the button above to run the live Gemini 2.5 Flash consistency audit if `GEMINI_API_KEY` is set in your environment.)*
                        """
                    )

    # =========================================================================
    # TAB 4: DELIVERABLES & OFFICIAL CERTIFICATE
    # =========================================================================
    with tab_export:
        payload = build_export_payload(
            scenario_label=scenario_label,
            metrics=metrics,
            decision=decision,
            mm_per_px=mm_per_px,
            backend_mode=backend_mode,
            claim_id=claim_display_id,
            panel_type=panel_type,
            quality_conf=quality_conf,
            img_hash=img_hash,
            user_narrative=user_narrative,
            gemini_narrative=st.session_state.get(f"gemini_audit_{scenario_label}"),
            v2_report=v2_report,
            fraud_analysis=fraud_analysis,
        )

        col_cert, col_json = st.columns([1, 1], gap="large")
        with col_cert:
            with st.container(border=True):
                st.markdown("#### 📜 Official ClaimPilot 3D Telemetry Certificate")
                st.markdown(
                    f"""
                    > **CLAIMPILOT AI — SENIOR ADJUSTER TELEMETRY CERTIFICATE**  
                    > **Claim Reference:** `{claim_display_id}` · **Vehicle:** `{vehicle_name}`  
                    > **Timestamp:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`  
                    > **Triage Status:** **{decision['status']}** · **Benchmark Estimate:** **₹{decision['cost']:,} INR**  
                    >  
                    > **Policyholder Statement:**  
                    > *"{user_narrative}"*  
                    >  
                    > **3D Deformation & DSINE Telemetry:**  
                    > - **Max Dent Depth (ΔZ):** `{metrics['max_depth_mm']} mm`  
                    > - **DSINE Surface Crease Angle:** `{metrics['angle_deg']}°`  
                    > - **SAM2 Damaged Surface Area:** `{metrics['area_cm2']} cm² ({int(mask.sum()):,} px)`  
                    > - **Calibration Tier:** `{calib_tier}` (`{mm_per_px:.4f} mm/px`)  
                    >  
                    > **Forensic Guardrails:**  
                    > - **SHA-256 Fingerprint:** `{img_hash}` · **Photo Quality:** `{quality_conf}% ({quality_status})`  
                    > - **Fraud Risk Assessment:** `{fraud_risk_level}` (`{fraud_score_display}`)  
                    > - **Recommended Repair Action:** `{decision['action']}` on `{panel_type}`
                    """
                )

        with col_json:
            with st.container(border=True):
                st.markdown("#### 📦 Structured Telemetry Payload (JSON)")
                payload_str = json.dumps(payload, indent=2, default=str)
                st.download_button(
                    "⬇️ Download Adjuster Telemetry (.json)",
                    data=payload_str,
                    file_name=f"{claim_display_id}_telemetry.json",
                    mime="application/json",
                )
                st.code(payload_str, language="json")


if __name__ == "__main__":
    run_agent_extendview(set_page_cfg=True)
