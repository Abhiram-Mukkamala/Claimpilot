import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from ultralytics import YOLO, RTDETR
from app.core.config import settings
from app.db.supabase import db
from app.services.evidence_storage import canonical_evidence_path
from app.services.cost_estimator import estimate_damage_costs
from app.services.fraud_analysis_service import PhashColumnMissingError, analyze_fraud

# Optional vision pipeline (SAM2 + DSINE + depth). Loaded lazily; the
# existing YOLO/RT-DETR pipeline works without it. Import is wrapped so a
# missing vision dependency never breaks module import.
try:
    from app.services.vision.vision_pipeline import (
        extract_vision_summary_for_db,
        run_vision_pipeline,
    )
    _VISION_AVAILABLE = True
except Exception:  # ImportError, missing torch/transformers, etc.
    run_vision_pipeline = None  # type: ignore[assignment]
    extract_vision_summary_for_db = None  # type: ignore[assignment]
    _VISION_AVAILABLE = False

logger = logging.getLogger("claimpilot.ai_runner")

# Vision device: default to CPU. Override via VISION_DEVICE env var if CUDA is available.
_VISION_DEVICE = os.getenv("VISION_DEVICE", "cpu")
# Set VISION_PIPELINE_ENABLED=false to skip the vision stage entirely.
_VISION_ENABLED = os.getenv("VISION_PIPELINE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_WEIGHTS_PATH = BASE_DIR / "models" / "weights" / "best.pt"
YOLO_FALLBACK_WEIGHTS_PATH = BASE_DIR / "models" / "weights" / "yolov11m.pt"
RTDETR_FALLBACK_WEIGHTS_PATH = BASE_DIR / "models" / "weights" / "rt-detr.pt"

_yolo_model = None
_rtdetr_model = None

def get_models():
    global _yolo_model, _rtdetr_model

    configured_weights = os.getenv("MODEL_WEIGHTS_PATH", "").strip()
    configured_path = Path(configured_weights).expanduser() if configured_weights else None
    if configured_path and not configured_path.is_absolute():
        configured_path = BASE_DIR.parent / configured_path

    yolo_candidates = [
        configured_path,
        DEFAULT_MODEL_WEIGHTS_PATH,
        YOLO_FALLBACK_WEIGHTS_PATH,
    ]
    seen_paths = set()
    if _yolo_model is None:
        for weights_path in yolo_candidates:
            if weights_path is None or weights_path in seen_paths:
                continue
            seen_paths.add(weights_path)
            if not weights_path.is_file():
                continue
            try:
                logger.info("Loading YOLO model weights from %s", weights_path)
                _yolo_model = YOLO(str(weights_path))
                break
            except Exception as exc:
                logger.warning("Could not load YOLO weights (%s)", type(exc).__name__)

    if _rtdetr_model is None and RTDETR_FALLBACK_WEIGHTS_PATH.is_file():
        try:
            logger.info("Loading RT-DETR model weights from %s", RTDETR_FALLBACK_WEIGHTS_PATH)
            _rtdetr_model = RTDETR(str(RTDETR_FALLBACK_WEIGHTS_PATH))
        except Exception as exc:
            logger.warning("Could not load RT-DETR weights (%s)", type(exc).__name__)

    return _yolo_model, _rtdetr_model


async def _save_analysis(payload: Dict[str, Any]) -> None:
    claim_id = payload["claim_id"]
    try:
        existing = await db.select(
            "claim_ai_analysis",
            params={"claim_id": f"eq.{claim_id}"},
            single=True,
        )
        if existing:
            await db.update(
                "claim_ai_analysis",
                filters={"claim_id": f"eq.{claim_id}"},
                data=payload,
            )
        else:
            await db.insert("claim_ai_analysis", payload)
    except Exception as exc:
        logger.error("Could not save AI analysis for claim %s (%s)", claim_id, type(exc).__name__)


async def _mark_analysis_failed(claim_id: str, message: str) -> Dict[str, Any]:
    failure_payload = {
        "claim_id": claim_id,
        "analysis_status": "failed",
        "error_message": message[:240],
        "detected_damages": [],
    }
    await _save_analysis(failure_payload)
    try:
        await db.update(
            "claims",
            filters={"id": f"eq.{claim_id}"},
            data={"status": "flagged"},
        )
    except Exception as exc:
        logger.error("Could not flag claim %s for manual review (%s)", claim_id, type(exc).__name__)
    return failure_payload


async def _save_fraud_analysis(
    claim_id: str,
    *,
    result: Dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    payload = {
        "claim_id": claim_id,
        "analysis_status": "completed" if result is not None else "failed",
        "error_message": error_message[:240] if error_message else None,
        "score": result.get("score") if result else None,
        "risk_level": result.get("riskLevel") if result else None,
        "indicators": result.get("indicators", []) if result else [],
        "analysis": result,
    }
    try:
        existing = await db.select(
            "claim_fraud_analyses",
            params={"claim_id": f"eq.{claim_id}"},
            single=True,
        )
        if existing:
            await db.update(
                "claim_fraud_analyses",
                filters={"claim_id": f"eq.{claim_id}"},
                data=payload,
            )
        else:
            await db.insert("claim_fraud_analyses", payload)
    except Exception as exc:
        logger.error("Could not save fraud analysis for claim %s (%s)", claim_id, type(exc).__name__)


async def trigger_ai_assessment(claim_id: str, background: bool = True) -> Dict[str, Any]:
    logger.info(f"[AI PIPELINE TRIGGERED] Starting vision adjudication for Claim: {claim_id}")

    claim = await db.select(
        "claims",
        params={"select": "id,user_id,description,created_at", "id": f"eq.{claim_id}"},
        single=True,
    )
    owner_id = str((claim or {}).get("user_id") or "")
    if not owner_id:
        logger.warning("Skipping AI analysis for claim %s: claim owner is unavailable", claim_id)
        return {"claim_id": claim_id, "status": "skipped", "reason": "claim_owner_unavailable"}

    # Evidence registration is the trigger. Do not start analysis for a new
    # claim until at least one damage photo has been cataloged.
    evidence_list = await db.select(
        "claim_evidence", params={"claim_id": f"eq.{claim_id}"}
    ) or []
    photo_evidence = []
    for evidence in evidence_list:
        if evidence.get("category") not in {"photo", "damage_photo"}:
            continue
        stored_path = evidence.get("storage_path")
        if not isinstance(stored_path, str) or stored_path.strip().lower() in {"", "none", "null"}:
            stored_path = evidence.get("file_url")
        try:
            path = canonical_evidence_path(
                stored_path or "",
                category="photo",
                owner_id=owner_id,
            )
        except Exception:
            logger.warning("Skipping malformed evidence path for claim %s", claim_id)
            continue
        photo_evidence.append((evidence, path))
    if not photo_evidence:
        logger.info("Skipping AI analysis for claim %s: no damage photo evidence", claim_id)
        return {"claim_id": claim_id, "status": "skipped", "reason": "no_photo_evidence"}

    # This conditional update is the database-backed idempotency guard. Only
    # one upload-triggered task can move a new claim out of pending_review.
    claimed = await db.update(
        "claims",
        filters={"id": f"eq.{claim_id}", "status": "eq.pending_review"},
        data={"status": "under_review"},
    )
    if not claimed:
        logger.info("Skipping duplicate AI analysis trigger for claim %s", claim_id)
        return {"claim_id": claim_id, "status": "skipped", "reason": "already_started"}

    detected_damages: List[Dict[str, Any]] = []
    fraud_images = []
    yolo_model, rtdetr_model = get_models()
    inference_failure_message = (
        "No damage detection model weights are available."
        if not yolo_model and not rtdetr_model
        else "Damage detection failed for all uploaded photos."
    )

    downloaded_count = 0
    successful_inferences = 0
    vision_results: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, (evidence, storage_path) in enumerate(photo_evidence[:10]):
            try:
                local_photo_path = os.path.join(tmp_dir, f"evidence_{idx}.jpg")
                image_bytes = await db.download_storage_object(
                    settings.SUPABASE_STORAGE_BUCKET,
                    storage_path,
                )
                with open(local_photo_path, "wb") as out_file:
                    out_file.write(image_bytes)
                downloaded_count += 1
                fraud_images.append({
                    "evidence_id": evidence.get("id"),
                    "image_bytes": image_bytes,
                })
            except Exception as exc:
                # Do not log the URL; storage URLs can contain signed tokens.
                logger.warning("Could not download claim evidence (%s)", type(exc).__name__)
                continue

            image_damage_count = len(detected_damages)
            image_inference_succeeded = False
            if yolo_model:
                try:
                    results = yolo_model.predict(local_photo_path, conf=0.25)
                    for result in results:
                        img_h, img_w = result.orig_shape
                        for box_index, box in enumerate(result.boxes):
                            class_id = int(box.cls[0])
                            label = (
                                yolo_model.names[class_id]
                                if hasattr(yolo_model, "names")
                                else f"Class {class_id}"
                            )
                            confidence = float(box.conf[0])
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            detected_damages.append({
                                "id": f"dmg_yolo_{idx + 1}_{box_index + 1}",
                                "type": label.replace("_", " ").title(),
                                "part": label,
                                "damage_type": "Detected Fracture/Dent",
                                "severity": "Severe" if confidence > 0.8 else (
                                    "Moderate" if confidence > 0.5 else "Minor"
                                ),
                                "confidence": round(confidence, 2),
                                "location": f"Panel Area {box_index + 1}",
                                "repair_action": "Tinkering & Paint",
                                "estimated_cost": round(confidence * 5000, 2),
                                "_estimator_class_name": label,
                                "_estimator_bbox_xyxy": [x1, y1, x2, y2],
                                "_estimator_image_size": [img_w, img_h],
                                "boundingBox": {
                                    "x": round((x1 / img_w) * 100, 2),
                                    "y": round((y1 / img_h) * 100, 2),
                                    "width": round(((x2 - x1) / img_w) * 100, 2),
                                    "height": round(((y2 - y1) / img_h) * 100, 2),
                                },
                            })
                    image_inference_succeeded = True
                except Exception as exc:
                    logger.warning("YOLO inference failed for claim evidence (%s)", type(exc).__name__)

            if rtdetr_model and (
                not image_inference_succeeded
                or len(detected_damages) == image_damage_count
            ):
                try:
                    results = rtdetr_model.predict(local_photo_path, conf=0.30)
                    for result in results:
                        img_h, img_w = result.orig_shape
                        for box_index, box in enumerate(result.boxes):
                            confidence = float(box.conf[0])
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            detected_damages.append({
                                "id": f"dmg_rtdetr_{idx + 1}_{box_index + 1}",
                                "type": "Structural Panel Damage",
                                "part": "Structural Panel",
                                "damage_type": "Surface Deformation",
                                "severity": "Severe" if confidence > 0.8 else "Moderate",
                                "confidence": round(confidence, 2),
                                "location": f"Panel Area {box_index + 1}",
                                "repair_action": "Replacement",
                                "estimated_cost": round(confidence * 7500, 2),
                                "_estimator_class_name": "Structural Panel Damage",
                                "_estimator_bbox_xyxy": [x1, y1, x2, y2],
                                "_estimator_image_size": [img_w, img_h],
                                "boundingBox": {
                                    "x": round((x1 / img_w) * 100, 2),
                                    "y": round((y1 / img_h) * 100, 2),
                                    "width": round(((x2 - x1) / img_w) * 100, 2),
                                    "height": round(((y2 - y1) / img_h) * 100, 2),
                                },
                            })
                    image_inference_succeeded = True
                except Exception as exc:
                    logger.warning("RT-DETR inference failed for claim evidence (%s)", type(exc).__name__)

            if image_inference_succeeded:
                successful_inferences += 1

            # --- Optional vision pipeline: SAM2 segmentation + DSINE normals + depth ---
            # Runs per image after detection. Degrades gracefully if vision models
            # are unavailable or any stage fails; never breaks the claim flow.
            image_damages = detected_damages[image_damage_count:]
            if image_inference_succeeded and image_damages and _VISION_AVAILABLE and _VISION_ENABLED:
                try:
                    # Vision pipeline expects bbox_xyxy in absolute pixels;
                    # ai_runner stores them under _estimator_bbox_xyxy.
                    vision_detections = []
                    for dmg in image_damages:
                        vd = dict(dmg)
                        vd["bbox_xyxy"] = dmg.get("_estimator_bbox_xyxy", [0, 0, 0, 0])
                        vd["class_name"] = dmg.get("_estimator_class_name", "unknown")
                        vision_detections.append(vd)
                    vision_result = run_vision_pipeline(
                        local_photo_path,
                        vision_detections,
                        device=_VISION_DEVICE,
                        plate_bbox=None,  # auto-detect via Haar cascade
                        plate_width_mm=520.0,
                    )
                    vision_results.append(vision_result)
                    # Merge JSON-safe per-instance measurements back into the damage dicts.
                    for dmg, inst in zip(image_damages, vision_result.get("instances", [])):
                        for key in (
                            "mask_iou_score", "area_px", "area_cm2", "crease_angle_deg",
                            "crease_status", "max_depth_mm", "max_indentation_mm",
                        ):
                            dmg[key] = inst.get(key)
                        if inst.get("stage_errors"):
                            dmg.setdefault("vision_stage_errors", {}).update(inst["stage_errors"])
                except Exception as exc:
                    logger.warning("Vision pipeline failed for claim evidence (%s)", type(exc).__name__)

    if downloaded_count == 0:
        return await _mark_analysis_failed(
            claim_id,
            "Unable to download uploaded damage photos.",
        )
    # Geometry and a seeded cost table provide an indicative estimate only.
    # The estimator removes its internal geometry fields before persistence.
    cost_estimate = estimate_damage_costs(
        detected_damages,
        min_confidence=settings.COST_ESTIMATOR_MIN_CONFIDENCE,
        minor_max_area_ratio=settings.COST_SEVERITY_MINOR_MAX_AREA_RATIO,
        moderate_max_area_ratio=settings.COST_SEVERITY_MODERATE_MAX_AREA_RATIO,
        duplicate_iou_threshold=settings.COST_DUPLICATE_IOU_THRESHOLD,
    )
    detected_damages = cost_estimate["detected_damages"]
    estimated_min = cost_estimate["estimated_cost_min"]
    estimated_max = cost_estimate["estimated_cost_max"]
    estimate_basis = cost_estimate["estimate_basis"]
    primary_image_url = photo_evidence[0][1]

    # Aggregate vision results across all processed images. The summary is a
    # flat JSON-safe dict; it never contains numpy arrays.
    vision_db_fields: Dict[str, Any] = {}
    if _VISION_AVAILABLE and vision_results:
        try:
            vision_db_fields = extract_vision_summary_for_db(vision_results) or {}
        except Exception as exc:
            logger.warning("Could not summarize vision results (%s)", type(exc).__name__)
            vision_db_fields = {}
    crease_angle = vision_db_fields.get("crease_angle_deg")

    analysis_payload = {
        "claim_id": claim_id,
        "analysis_status": "completed",
        "error_message": None,
        "detected_damages": detected_damages,
        "estimated_cost_min": estimated_min,
        "estimated_cost_max": estimated_max,
        "estimate_basis": estimate_basis,
        # claim_ai_analysis has clahe_image_url but no image_url column.
        "clahe_image_url": primary_image_url,
        "segmentation_masks": {
            "mask_count": vision_db_fields.get("mask_count") or len(detected_damages),
            "polygon_density": vision_db_fields.get("mean_mask_iou"),
            "primary_impact_zone": None,
            "vision_available": _VISION_AVAILABLE and _VISION_ENABLED,
        },
        # NOT NULL INTEGER column (default 0): never send None.
        "surface_area_px": int(vision_db_fields.get("surface_area_px") or 0),
        # claim_ai_analysis has NO top-level vision_calibration column, so the
        # calibration and indentation live inside this JSONB document.
        "relative_deformation_z": {
            "crease_angle_deg": crease_angle,
            "crease_angle_count": vision_db_fields.get("crease_angle_count", 0),
            "method": "dsine_surface_normals" if crease_angle is not None else None,
            "max_indentation_mm": vision_db_fields.get("max_indentation_mm"),
            "max_depth_mm": vision_db_fields.get("max_depth_mm"),
            "area_cm2": vision_db_fields.get("area_cm2"),
            "vision_calibration": vision_db_fields.get("vision_calibration"),
        },
        "dsine_vectors": {
            "available": crease_angle is not None,
            "mean_crease_angle_deg": crease_angle,
        },
        "fraud_flags": []
    }

    fraud_payload = None
    try:
        fraud_result = await analyze_fraud(
            claim_id=claim_id,
            claimant_id=(claim or {}).get("user_id"),
            description=(claim or {}).get("description") or "",
            submitted_at=(claim or {}).get("created_at"),
            damages=detected_damages,
            evidence_images=fraud_images,
        )
        fraud_payload = fraud_result.model_dump(mode="json")
        await _save_fraud_analysis(claim_id, result=fraud_payload)
        analysis_payload["fraud_analysis"] = fraud_payload
        analysis_payload["fraud_analysis_error"] = None
        analysis_payload["fraud_flags"] = [
            indicator["message"]
            for indicator in fraud_payload["indicators"]
            if not indicator["passed"]
        ]
    except PhashColumnMissingError as fraud_err:
        logger.error("Fraud analysis unavailable for claim %s: %s", claim_id, fraud_err)
        await _save_fraud_analysis(claim_id, error_message=str(fraud_err))
        analysis_payload["fraud_analysis_error"] = str(fraud_err)
        analysis_payload["fraud_flags"] = []
        analysis_payload["fraud_analysis"] = None
    except Exception as fraud_err:
        logger.error("Fraud analysis failed for claim %s (%s)", claim_id, type(fraud_err).__name__)
        await _save_fraud_analysis(
            claim_id,
            error_message="Fraud analysis could not be completed.",
        )
        analysis_payload["fraud_analysis_error"] = "Fraud analysis could not be completed."
        analysis_payload["fraud_flags"] = []
        analysis_payload["fraud_analysis"] = None

    if successful_inferences == 0:
        return await _mark_analysis_failed(
            claim_id,
            inference_failure_message,
        )

    await _save_analysis(analysis_payload)
    claim_update = {"status": "under_review"}
    if fraud_payload is not None:
        claim_update.update({
            "fraud_score": fraud_payload["score"],
            "risk_level": fraud_payload["riskLevel"],
        })
    try:
        await db.update("claims", filters={"id": f"eq.{claim_id}"}, data=claim_update)
    except Exception as exc:
        logger.error("Could not finish claim update for %s (%s)", claim_id, type(exc).__name__)
    logger.info("[AI PIPELINE COMPLETED] Claim %s assessed successfully", claim_id)
    return analysis_payload
