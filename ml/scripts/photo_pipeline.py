# End-to-end ClaimPilot photo-mode pipeline: YOLOv11m + Depth Anything V2 + SAM2 + DSINE.
# Combines T1.3/T1.4, T2.1, T2.2, and T2.3 into one structured JSON-producing function.
#
# CALIBRATION: uses depth_estimation.calibrate_metric_depth_tiered() (plate -> wheel/tire
# -> metric-depth-model prior) instead of a plate-only calibration, so a damaged/missing/
# unphotographed plate no longer means a null result - see depth_estimation.py's module
# docstring for the full 3-tier design (mirrors scale_calibration.py, Video Mode's 3D
# equivalent of this same chain). Per-instance area now comes from
# segmentation.compute_mask_area_from_depth(), which derives area from the calibrated
# metric depth AT EACH INSTANCE's own pixels (via the pinhole relation) rather than
# assuming every instance sits at the same distance as the plate - an accuracy
# improvement that falls out of the null-elimination work, not just a side effect of it.
import os
import time
import datetime
import numpy as np
from PIL import Image


def analyze_photo(image_path, yolo_model, depth_processor, depth_model,
                   sam2_processor, sam2_model, dsine_model,
                   plate_bbox=None, plate_width_mm=520.0,
                   conf=0.25, iou=0.45, imgsz=640, ring_width_px=15,
                   device="cuda",
                   ocr_reader=None, metric_depth_processor=None, metric_depth_model=None):
    # Run the full photo-mode pipeline on a single image and return a schema-conformant
    # dict (see the notebook markdown for the full JSON schema). Every stage is wrapped
    # so a single stage's failure does not lose the other stages' results for this image.
    #
    # IMPORTANT: pass the SAME device string here that the models were actually loaded
    # onto (e.g. "cpu" on a machine with no CUDA GPU). This is not auto-detected -- an
    # earlier version of this function hardcoded "cuda" internally regardless of what
    # device was passed to load_depth_model()/load_sam2(), which crashed the depth and
    # segmentation stages outright on any CPU-only machine even when the models
    # themselves were correctly loaded onto CPU.
    #
    # ocr_reader / metric_depth_processor / metric_depth_model: optional Tier 2/3
    # calibration fallbacks (see depth_estimation.calibrate_metric_depth_tiered). If
    # omitted, calibration still runs Tier 1 (plate) and Tier 2b (generic wheel
    # diameter) - only exact tire-code OCR and the metric-depth-prior last resort are
    # skipped, degrading gracefully rather than failing to import.
    import cv2
    import inference
    import depth_estimation
    import segmentation
    import surface_normals

    timing = {}
    t_start = time.time()

    pil_image = Image.open(image_path).convert("RGB")
    img_w, img_h = pil_image.size

    result = {
        "image_path": image_path,
        "image_size": [img_w, img_h],
        "processed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "models": {
            "detection": "YOLOv11m (ClaimPilot fine-tuned)",
            "depth": "Depth Anything V2",
            "segmentation": "SAM2",
            "normals": "DSINE",
        },
        "calibration": {},
        "damage_instances": [],
        "summary": {},
        "timing_sec": {},
    }

    t0 = time.time()
    detection_error = None
    detections = []
    try:
        detections = inference.run_inference(yolo_model, image_path, conf=conf, iou=iou, imgsz=imgsz)
    except Exception as e:
        detection_error = str(e)
    timing["detection"] = time.time() - t0

    if detection_error or not detections:
        result["summary"] = {
            "num_instances": 0,
            "classes_detected": [],
            "total_damage_area_cm2": None,
        }
        if detection_error:
            result["summary"]["detection_error"] = detection_error
        result["timing_sec"] = {**timing, "total": time.time() - t_start}
        return result

    boxes_xyxy = [d["bbox_xyxy"] for d in detections]

    # --- Depth + metric calibration (never-null: plate -> wheel/tire -> metric-depth
    # prior; see depth_estimation.calibrate_metric_depth_tiered) ---
    t0 = time.time()
    depth_error = None
    relative_depth = None
    metric_depth_map = None
    metric_depth_info = {"status": "skipped_stage_error"}
    try:
        relative_depth = depth_estimation.estimate_relative_depth(depth_processor, depth_model, image_path, device=device)
        metric_depth_map, metric_depth_info = depth_estimation.calibrate_metric_depth_tiered(
            relative_depth, image_path, plate_bbox=plate_bbox, plate_width_mm=plate_width_mm,
            ocr_reader=ocr_reader, metric_depth_processor=metric_depth_processor,
            metric_depth_model=metric_depth_model, device=device,
        )
    except Exception as e:
        depth_error = str(e)
        metric_depth_info = {"status": "stage_error", "error": depth_error}
    timing["depth"] = time.time() - t0
    result["calibration"]["depth_metric"] = metric_depth_info

    # Focal length for the per-instance area calibration below (same tiered-calibration
    # focal estimate used internally by depth_estimation - EXIF when available, else an
    # assumed horizontal FOV; never null).
    focal_length_px = metric_depth_info.get("focal_length_px")
    if focal_length_px is None:
        try:
            focal_length_px, _ = depth_estimation.estimate_focal_length_px(image_path, img_w)
        except Exception:
            focal_length_px = None

    t0 = time.time()
    segmentation_error = None
    seg_results = []
    try:
        seg_results = segmentation.segment_boxes(sam2_processor, sam2_model, pil_image, boxes_xyxy, device=device)
    except Exception as e:
        segmentation_error = str(e)
    timing["segmentation"] = time.time() - t0

    t0 = time.time()
    normals_error = None
    normal_map = None
    try:
        normal_map = surface_normals.estimate_normals(dsine_model, image_path)
    except Exception as e:
        normals_error = str(e)
    timing["normals"] = time.time() - t0

    damage_instances = []
    classes_detected = set()
    total_area_cm2 = 0.0
    any_area_cm2 = False

    for i, det in enumerate(detections):
        stage_errors = {}
        instance = {
            "instance_id": i,
            "class_name": det["class_name"],
            "confidence": det["confidence"],
            "bbox_xyxy": det["bbox_xyxy"],
            "mask_iou_score": None,
            "area_px": None,
            "area_cm2": None,
            "crease_angle_deg": None,
            "crease_status": "not_computed",
        }
        classes_detected.add(det["class_name"])

        if segmentation_error:
            stage_errors["segmentation"] = segmentation_error
        elif i < len(seg_results):
            mask_bool, iou_score = seg_results[i]
            instance["mask_iou_score"] = iou_score

            # Prefer per-instance depth-based area (accurate regardless of which
            # calibration tier fired, and works even with no reference object visible
            # at all once Tier 3 has filled in metric_depth_map). Falls back to the
            # legacy flat-plane plate calibration only if depth calibration failed
            # outright (every tier failed, or the depth stage itself errored).
            if metric_depth_map is not None and focal_length_px:
                pixel_count, area_cm2 = segmentation.compute_mask_area_from_depth(
                    mask_bool, metric_depth_map, focal_length_px
                )
            else:
                try:
                    mm_per_pixel, _ = segmentation.compute_pixel_to_mm(
                        image_path, img_w, plate_bbox=plate_bbox, plate_width_mm=plate_width_mm
                    )
                except Exception:
                    mm_per_pixel = None
                pixel_count, area_cm2 = segmentation.compute_mask_area(mask_bool, mm_per_pixel)

            instance["area_px"] = pixel_count
            instance["area_cm2"] = area_cm2
            if area_cm2 is not None:
                total_area_cm2 += area_cm2
                any_area_cm2 = True

            if normals_error:
                stage_errors["normals"] = normals_error
            elif normal_map is not None:
                try:
                    crease_info = surface_normals.compute_crease_angle(normal_map, mask_bool, ring_width_px=ring_width_px)
                    instance["crease_angle_deg"] = crease_info.get("crease_angle_deg")
                    instance["crease_status"] = crease_info.get("status")
                except Exception as e:
                    stage_errors["crease_angle"] = str(e)
                    instance["crease_status"] = "stage_error"

        instance["stage_errors"] = stage_errors
        damage_instances.append(instance)

    result["damage_instances"] = damage_instances
    result["summary"] = {
        "num_instances": len(damage_instances),
        "classes_detected": sorted(classes_detected),
        "total_damage_area_cm2": total_area_cm2 if any_area_cm2 else None,
    }
    if detection_error:
        result["summary"]["detection_error"] = detection_error

    timing["total"] = time.time() - t_start
    result["timing_sec"] = timing
    return result
