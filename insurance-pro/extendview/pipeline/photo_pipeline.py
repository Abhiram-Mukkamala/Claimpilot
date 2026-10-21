# End-to-end ClaimPilot photo-mode pipeline: YOLOv11m + Depth Anything V2 + SAM2 + DSINE.
import time
import datetime
import numpy as np
from PIL import Image


def analyze_photo(image_path, yolo_model, depth_processor, depth_model,
                   sam2_processor, sam2_model, dsine_model,
                   plate_bbox=None, plate_width_mm=520.0,
                   conf=0.25, iou=0.35, imgsz=640, ring_width_px=15,
                   device="cuda",
                   ocr_reader=None, metric_depth_processor=None, metric_depth_model=None,
                   use_per_class_thresholds=True, use_tta=False,
                   return_artifacts=False):
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
            "segmentation": "SAM2.1 Hiera Small",
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
        if use_per_class_thresholds:
            try:
                import inference_v2
                detections = inference_v2.run_inference_v2(
                    yolo_model, image_path,
                    iou=iou, imgsz=imgsz, tta=use_tta, device=device,
                )
            except ImportError:
                import inference
                detections = inference.run_inference(yolo_model, image_path, conf=conf, iou=iou, imgsz=imgsz)
        else:
            import inference
            detections = inference.run_inference(yolo_model, image_path, conf=conf, iou=iou, imgsz=imgsz)
    except Exception as e:
        detection_error = str(e)
    timing["detection"] = time.time() - t0

    # --- Depth + metric calibration (runs even if detections == 0 so 3D mesh is always available) ---
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

    focal_length_px = metric_depth_info.get("focal_length_px")
    if focal_length_px is None:
        try:
            focal_length_px, _ = depth_estimation.estimate_focal_length_px(image_path, img_w)
        except Exception:
            focal_length_px = None

    t0 = time.time()
    normals_error = None
    normal_map = None
    try:
        normal_map = surface_normals.estimate_normals(dsine_model, image_path)
    except Exception as e:
        normals_error = str(e)
    timing["normals"] = time.time() - t0

    if detection_error or not detections:
        result["summary"] = {
            "num_instances": 0,
            "classes_detected": [],
            "total_damage_area_cm2": 0.0,
            "max_depth_mm": 0.0,
        }
        if detection_error:
            result["summary"]["detection_error"] = detection_error
        timing["total"] = time.time() - t_start
        result["timing_sec"] = timing
        if return_artifacts:
            result["_artifacts"] = {
                "metric_depth_map": metric_depth_map,
                "relative_depth_map": relative_depth,
                "normal_map": normal_map,
                "seg_masks": None,
            }
        return result

    boxes_xyxy = [d["bbox_xyxy"] for d in detections]

    t0 = time.time()
    segmentation_error = None
    seg_results = []
    try:
        seg_results = segmentation.segment_boxes(sam2_processor, sam2_model, pil_image, boxes_xyxy, device=device)
    except Exception as e:
        segmentation_error = str(e)
    timing["segmentation"] = time.time() - t0

    damage_instances = []
    classes_detected = set()
    total_area_cm2 = 0.0
    any_area_cm2 = False
    scene_max_depth_mm = 0.0

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
            "max_depth_mm": None,
            "crease_angle_deg": None,
            "crease_status": "not_computed",
        }
        classes_detected.add(det["class_name"])

        if segmentation_error:
            stage_errors["segmentation"] = segmentation_error
        elif i < len(seg_results):
            mask_bool, iou_score = seg_results[i]
            instance["mask_iou_score"] = round(float(iou_score), 3) if iou_score is not None else None

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

            # Compute per-instance physical indentation depth (mm)
            if metric_depth_map is not None:
                inst_depth_mm = depth_estimation.compute_instance_depth_mm(
                    metric_depth_map, mask_bool, ring_width_px=ring_width_px
                )
                instance["max_depth_mm"] = inst_depth_mm
                scene_max_depth_mm = max(scene_max_depth_mm, inst_depth_mm)

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

    # Record scene max depth in calibration summary so extract_v1_metrics_from_v2_report finds it
    result["calibration"]["depth_metric"]["max_depth_mm"] = round(scene_max_depth_mm, 2)

    result["damage_instances"] = damage_instances
    result["summary"] = {
        "num_instances": len(damage_instances),
        "classes_detected": sorted(classes_detected),
        "total_damage_area_cm2": round(total_area_cm2, 2) if any_area_cm2 else None,
        "max_depth_mm": round(scene_max_depth_mm, 2),
    }
    if detection_error:
        result["summary"]["detection_error"] = detection_error

    timing["total"] = time.time() - t_start
    result["timing_sec"] = timing

    if return_artifacts:
        result["_artifacts"] = {
            "metric_depth_map": metric_depth_map,
            "relative_depth_map": relative_depth,
            "normal_map": normal_map,
            "seg_masks": seg_results if seg_results else None,
        }

    return result
