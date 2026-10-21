"""
ClaimPilot AI — Customer Extended 3D & Surface Inspection View (customer_app.py)
================================================================================
Dedicated Streamlit application for Policyholders / Customers.
Linked from React's `ClaimAnalysis.tsx` (/customer/claims/:id).

Displays:
  - Interactive 3D Surface Deformation Mesh & 2D Millimeter Heatmap (ΔZ)
  - Dent Basin Cross-Section Profile (mm)
  - Raw vs. CLAHE Glare-Reduced Evidence Photo
  - SAM2 Precision Damage Boundary Contour
  - DSINE 3D Surface Curvature & Crease Map
  - Customer-facing Repair Estimate & Settlement Summary

Strictly hides:
  - Internal Fraud Risk Scores, pHash duplicate flags, EXIF audit flags
  - Internal Adjuster Rule Engine overrides & raw telemetry JSON payloads

Run standalone on Port 8501:
    streamlit run customer_app.py --server.port 8501
"""

import importlib
import cv2
import numpy as np
import streamlit as st

import extendview_core
importlib.reload(extendview_core)

from extendview_core import (
    DEFAULT_REF_MM,
    IMG_SIZE,
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
    fetch_recent_claims_list,
    inject_claimpilot_theme,
    load_all_models,
    normal_to_rgb,
    overlay_mask_and_boxes,
    plot_3d_mesh,
    plot_depth_cross_section,
    plot_depth_heatmap,
    render_topbar,
)


def run_customer_extendview(set_page_cfg: bool = True):
    qp = st.query_params
    is_embedded = str(qp.get("embed") or "").lower() in ("true", "1", "yes")
    claim_id = qp.get("claim_id") or qp.get("id") or ""
    token = qp.get("token") or ""

    if set_page_cfg:
        st.set_page_config(
            page_title="ClaimPilot AI | 3D Damage Inspection",
            layout="wide",
            page_icon="🛡️",
            initial_sidebar_state="collapsed",
        )

    inject_claimpilot_theme(is_embedded=is_embedded)
    load_all_models()

    # ---- Sidebar (Collapsed by Default for Clean Customer Experience) ----
    st.sidebar.markdown("### 🛡️ Inspection Controls")

    recent_claims = fetch_recent_claims_list(limit=15)
    if not claim_id and recent_claims:
        claim_options = [str(c.get("id")) for c in recent_claims]
        claim_labels = {}
        for c in recent_claims:
            cid = str(c.get("id"))
            cnum = c.get("claim_number") or cid[:8]
            veh = c.get("vehicle_name") or "Insured Vehicle"
            claim_labels[cid] = f"{cnum} — {veh}"
        selected_cid = st.sidebar.selectbox(
            "Select Active Claim",
            claim_options,
            index=0,
            format_func=lambda x: claim_labels.get(x, x),
        )
        if selected_cid:
            claim_id = selected_cid

    live_bundle = None
    if claim_id:
        with st.spinner("Loading your claim evidence and 3D telemetry..."):
            live_bundle = fetch_live_claim_bundle(claim_id, token=token, role="customer")

    claim_obj = (live_bundle or {}).get("claim") or {}
    ai_analysis = (live_bundle or {}).get("ai_analysis") or {}
    photos = (live_bundle or {}).get("photos") or []

    claim_display_id = claim_obj.get("claim_number") or claim_obj.get("id") or (claim_id if claim_id else "DEMO-INSPECTION")
    vehicle_name = claim_obj.get("vehicle_name") or claim_obj.get("vehicle") or "Insured Vehicle"
    raw_status = (claim_obj.get("status") or "Under Review").replace("_", " ").title()
    back_path = f"/customer/claims/{claim_id}" if claim_id else "/customer"

    render_topbar(
        role_label="3D Extended Inspection",
        claim_id=claim_id,
        claim_display_id=claim_display_id,
        vehicle_name=vehicle_name,
        status_text=raw_status,
        back_path=back_path,
        is_embedded=is_embedded,
    )

    normal_display_mode = st.sidebar.selectbox(
        "Surface Curvature View Style",
        ["Inverted B&W", "Standard Color", "Negative Color"],
        index=0,
        help="Switch how the 3D surface curvature map highlights panel dents and creases.",
    )
    show_vectors = st.sidebar.checkbox("Show 3D Surface Orientation Vectors", value=True)
    cpu_fast = st.sidebar.checkbox("Fast Inspection Mode (640px)", value=True)

    # ---- Resolve Evidence Image Source ----
    selected_bgr = None
    selected_photo_label = ""

    if photos:
        if len(photos) > 1:
            photo_labels = [f"Evidence Photo #{i+1}" for i in range(len(photos))]
            chosen_idx = st.selectbox(
                "Select Uploaded Claim Evidence Photo",
                range(len(photos)),
                format_func=lambda idx: photo_labels[idx],
            )
        else:
            chosen_idx = 0
        photo_item = photos[chosen_idx]
        selected_bgr = download_image_from_url(
            photo_item.get("url", ""),
            storage_path=photo_item.get("storage_path", ""),
        )
        selected_photo_label = f"Evidence Photo #{chosen_idx + 1}"

    # Fallback if opened without a claim_id or if image URL could not be reached
    if selected_bgr is None:
        with st.expander("📸 Switch Sample 3D Scan or Upload a Custom Photo", expanded=False):
            col_u1, col_u2 = st.columns([1, 2])
            with col_u1:
                preset_choice = st.selectbox("Preview 3D Damage Scan", list(PRESETS.keys()))
            with col_u2:
                uploaded = st.file_uploader(
                    "Or upload a vehicle damage photo (JPG / PNG)",
                    type=["jpg", "jpeg", "png"],
                )

        if uploaded is not None:
            raw_bytes = uploaded.read()
            imgsz = 640 if cpu_fast else 1280
            with st.spinner("Running 3D Depth Anything V2 + SAM2 + DSINE Surface Scan..."):
                bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report, backend_mode = (
                    execute_cached_pipeline(raw_bytes, engine_mode="v3", real_mm=DEFAULT_REF_MM, imgsz=imgsz, use_tta=not cpu_fast)
                )
        else:
            bgr_img, depth_map, normal_map, mask, mm_per_px = build_scenario(preset_choice, IMG_SIZE, DEFAULT_REF_MM)
            metrics = compute_metrics(depth_map, normal_map, mask, mm_per_px)
            v2_report = None
            backend_mode = "Interactive 3D Scan Preview"
    else:
        _, enc = cv2.imencode(".jpg", selected_bgr)
        raw_bytes = enc.tobytes()
        imgsz = 640 if cpu_fast else 1280
        with st.spinner(f"Generating 3D Depth & Surface Normal Maps for {selected_photo_label}..."):
            bgr_img, depth_map, normal_map, mask, mm_per_px, metrics, v2_report, backend_mode = (
                execute_cached_pipeline(raw_bytes, engine_mode="v3", real_mm=DEFAULT_REF_MM, imgsz=imgsz, use_tta=not cpu_fast)
            )

    # Merge with stored backend AI analysis metrics when available
    stored_rel_z = ai_analysis.get("relative_deformation_z") or {}
    if isinstance(stored_rel_z, dict) and stored_rel_z.get("max_indentation_mm"):
        stored_depth = float(stored_rel_z["max_indentation_mm"])
        if stored_depth > 0 and metrics["max_depth_mm"] <= 1.0:
            metrics["max_depth_mm"] = round(stored_depth, 2)

    decision = approval_engine(metrics["max_depth_mm"], metrics["angle_deg"], 1.0)
    est_min = ai_analysis.get("estimated_cost_min")
    est_max = ai_analysis.get("estimated_cost_max")
    approved_amt = claim_obj.get("approved_amount")

    if est_min and est_max:
        cost_display = f"₹{int(float(est_min)):,} – ₹{int(float(est_max)):,}"
        cost_sub = "AI Estimated Repair Range"
    else:
        low_est = int(decision["cost"] * 0.85)
        high_est = int(decision["cost"] * 1.15)
        cost_display = f"₹{low_est:,} – ₹{high_est:,}"
        cost_sub = "Indicative Repair Benchmark"

    if approved_amt:
        cost_display = f"₹{int(float(approved_amt)):,}"
        cost_sub = "Approved Settlement Payout"

    quality_conf, quality_status, glare_pct, _ = check_photo_quality(bgr_img)
    glare_reduced = apply_clahe_glare_reduction(bgr_img)
    mask_overlay_img = overlay_mask_and_boxes(bgr_img, mask, v2_report=v2_report, show_boxes=True)
    normal_rgb = normal_to_rgb(normal_map, mode=normal_display_mode, draw_vectors=show_vectors, mask=mask)
    delta_depth = compute_relative_depth(depth_map, mask)

    # ---- Customer High-Density Summary Strip ----
    st.markdown(
        f"""
        <div class="cp-kpi-grid">
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">{cost_sub}</div>
                <div class="cp-kpi-value" style="color:#4ADE80;">{cost_display}</div>
                <div class="cp-kpi-sub">Subject to policy terms & adjuster verification</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Peak Dent Depth (ΔZ)</div>
                <div class="cp-kpi-value">{metrics['max_depth_mm']} mm</div>
                <div class="cp-kpi-sub">3D monocular depth indentation</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Affected Surface Area</div>
                <div class="cp-kpi-value">{metrics['area_cm2']} cm²</div>
                <div class="cp-kpi-sub">SAM2 pixel-accurate boundary</div>
            </div>
            <div class="cp-kpi-card">
                <div class="cp-kpi-label">Surface Crease Angle</div>
                <div class="cp-kpi-value">{metrics['angle_deg']}°</div>
                <div class="cp-kpi-sub">Recommended: {decision['action']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Main 2x2 Crystal Glass Visual Grid ----
    row1_col1, row1_col2 = st.columns(2, gap="large")

    with row1_col1:
        with st.container(border=True):
            st.markdown("#### ① Evidence Photo & Glare Suppression (CLAHE)")
            st.caption(
                f"Photo Quality: **{quality_conf}% ({quality_status})** · Specular Glare Reduced: **{glare_pct}%**"
            )
            sub_a, sub_b = st.columns(2)
            sub_a.image(
                cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB),
                caption="Original Uploaded Photo",
                use_container_width=True,
            )
            sub_b.image(
                cv2.cvtColor(glare_reduced, cv2.COLOR_BGR2RGB),
                caption="CLAHE Glare-Normalized",
                use_container_width=True,
            )

    with row1_col2:
        with st.container(border=True):
            st.markdown("#### ② AI Damage Boundary Segmentation (SAM2)")
            detected_classes = []
            if v2_report and v2_report.get("summary", {}).get("classes_detected"):
                detected_classes = v2_report["summary"]["classes_detected"]
            elif ai_analysis.get("detected_damages"):
                detected_classes = list({
                    d.get("type") or d.get("class") or "Damage"
                    for d in ai_analysis["detected_damages"]
                    if isinstance(d, dict)
                })
            classes_txt = ", ".join(c.title() for c in detected_classes) if detected_classes else "Surface Deformation"
            st.caption(f"Detected Regions: **{classes_txt}** · Segmented Pixels: **{int(mask.sum()):,} px**")
            st.image(
                cv2.cvtColor(mask_overlay_img, cv2.COLOR_BGR2RGB),
                caption="Emerald contour marks exact damage boundary isolated by SAM2",
                use_container_width=True,
            )

    row2_col1, row2_col2 = st.columns(2, gap="large")

    with row2_col1:
        with st.container(border=True):
            st.markdown("#### ③ 3D Damage Deformation & Depth Map (ΔZ)")
            st.caption("Drag to rotate the 3D surface mesh or hover to inspect millimeter depth across the dent.")
            v_tab1, v_tab2, v_tab3 = st.tabs([
                "Interactive 3D Surface Mesh",
                "2D Depth Heatmap (ΔZ)",
                "Dent Cross-Section Profile",
            ])
            with v_tab1:
                st.plotly_chart(plot_3d_mesh(depth_map, delta_depth), use_container_width=True)
            with v_tab2:
                st.plotly_chart(plot_depth_heatmap(delta_depth), use_container_width=True)
            with v_tab3:
                st.plotly_chart(plot_depth_cross_section(delta_depth, mask, mm_per_px), use_container_width=True)

    with row2_col2:
        with st.container(border=True):
            hdr_c1, hdr_c2 = st.columns([2, 1])
            with hdr_c1:
                st.markdown("#### ④ DSINE — 3D Surface Curvature & Normals")
                st.caption("Highlights panel folds, sharp creases, and sheet-metal curvature changes.")
            with hdr_c2:
                inline_mode = st.selectbox(
                    "View Style",
                    ["Inverted B&W", "Standard Color", "Negative Color"],
                    index=["Inverted B&W", "Standard Color", "Negative Color"].index(normal_display_mode),
                    key="cust_inline_normal_mode",
                    label_visibility="collapsed",
                )
            normal_rgb_inline = normal_to_rgb(normal_map, mode=inline_mode, draw_vectors=show_vectors, mask=mask)
            st.image(
                normal_rgb_inline,
                caption=f"DSINE Surface Orientation ({inline_mode}) · Green arrows indicate local surface tilt",
                use_container_width=True,
            )

    # ---- Plain-English Customer Assessment Summary ----
    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 📋 What This 3D Scan Means for Your Claim")
        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.markdown(
                f"""
                - **Measured Panel Indentation ({metrics['max_depth_mm']} mm):** Our monocular 3D depth engine compares the recessed damage basin against the surrounding undamaged sheet metal.
                - **Surface Curvature Shift ({metrics['angle_deg']}°):** DSINE surface normal analysis measures whether the metal has a smooth elastic depression or a sharp structural crease.
                - **Recommended Repair Approach:** **{decision['action']}** covering approximately **{metrics['area_cm2']} cm²**.
                """
            )
        with c_right:
            st.markdown(
                f"""
                <div style="background:rgba(5,150,105,0.10); border:1px solid rgba(5,150,105,0.35); border-radius:14px; padding:1rem; text-align:center;">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:#9BA3AF; font-weight:600;">{cost_sub}</div>
                    <div class="cp-mono" style="font-size:1.45rem; font-weight:700; color:#4ADE80; margin:0.35rem 0;">{cost_display}</div>
                    <a href="{back_path}" target="_self" class="cp-back-btn" style="margin-top:0.4rem;">Return to Claim Portal</a>
                </div>
                """,
                unsafe_allow_html=True,
            )


main = run_customer_extendview

if __name__ == "__main__":
    run_customer_extendview(set_page_cfg=True)
