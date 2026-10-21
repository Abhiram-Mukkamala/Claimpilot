"""
ClaimPilot vision pipeline orchestrator for backend integration.

Ties together SAM2 segmentation, DSINE surface normals, and Depth Anything V2
metric depth (tiered plate -> wheel -> metric prior calibration) into a single
callable stage that extends ai_runner.py's YOLO/RT-DETR damage detection.

All stages are optional. If a model is unavailable or a stage fails, the
pipeline degrades gracefully: instances are returned with null vision fields
and the normal claim-processing flow is never broken.

Entry points:
    run_vision_pipeline(image_path, detections, ...) -> per-image result dict
    extract_vision_summary_for_db(results)           -> flat, JSON-safe summary
        used by ai_runner.py to build the claim_ai_analysis payload.
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger("claimpilot.vision_pipeline")

# Lazy-loaded model singletons
_sam2_processor = None
_sam2_model = None
_dsine_model = None
_depth_processor = None
_depth_model = None
_metric_depth_processor = None
_metric_depth_model = None
_default_pipeline: Optional["VisionPipeline"] = None


def _lazy_sam2(device: str):
    global _sam2_processor, _sam2_model
    if _sam2_model is None:
        from .segmentation import load_sam2
        _sam2_processor, _sam2_model = load_sam2(device=device)
    return _sam2_processor, _sam2_model


def _lazy_dsine(device: str):
    global _dsine_model
    if _dsine_model is None:
        from .surface_normals import load_dsine
        _dsine_model = load_dsine(device=device)
    return _dsine_model


def _lazy_depth(device: str):
    global _depth_processor, _depth_model
    if _depth_processor is None:
        from .depth_estimation import load_depth_model
        _depth_processor, _depth_model = load_depth_model(device=device)
    return _depth_processor, _depth_model


def _lazy_metric_depth(device: str):
    global _metric_depth_processor, _metric_depth_model
    if _metric_depth_processor is None:
        from .depth_estimation import load_metric_depth_model
        _metric_depth_processor, _metric_depth_model = load_metric_depth_model(device=device)
    return _metric_depth_processor, _metric_depth_model


class VisionPipeline:
    """
    Orchestrates SAM2 segmentation + DSINE normals + depth calibration
    for a single damage photo, producing per-instance vision measurements.
    """

    def __init__(self, device: str = "cpu", enable_depth: bool = True,
                 enable_metric_depth_prior: bool = False):
        self.device = device
        self.enable_depth = enable_depth
        self.enable_metric_depth_prior = enable_metric_depth_prior

    def run(self, image_path: str, detections: List[Dict[str, Any]],
            plate_bbox: Optional[Tuple[int, int, int, int]] = None,
            plate_width_mm: float = 520.0) -> Dict[str, Any]:
        """
        Run the full vision pipeline on a single image for a list of detections.

        Args:
            image_path: Path to the local image file.
            detections: Damage dicts from YOLO/RT-DETR, each with "bbox_xyxy"
                        and optionally "confidence" / "class_name".
            plate_bbox: Optional manual (x, y, w, h) plate override for calibration.
            plate_width_mm: Real-world plate width in mm for calibration.

        Returns:
            dict with keys: masks, normals, depth_map, focal_length_px,
            calibration, max_depth_mm, max_indentation_mm, stage_errors,
            instances (per-instance vision dicts, including max_depth_mm and
            max_indentation_mm).
        """
        stage_errors: Dict[str, str] = {}
        result: Dict[str, Any] = {
            "masks": [],
            "normals": None,
            "depth_map": None,
            "focal_length_px": None,
            "calibration": {"status": "skipped", "method": None, "confidence": None},
            "max_depth_mm": None,
            "max_indentation_mm": None,
            "stage_errors": stage_errors,
            "instances": [],
        }

        try:
            pil_image = Image.open(image_path).convert("RGB")
        except Exception as e:
            stage_errors["image_load"] = str(e)
            return result

        img_w, img_h = pil_image.size
        boxes_xyxy = [d.get("bbox_xyxy", [0, 0, 0, 0]) for d in detections]

        # --- Stage 1: SAM2 segmentation ---
        masks: List[Tuple[np.ndarray, Optional[float]]] = []
        try:
            processor, model = _lazy_sam2(self.device)
            masks = segment_boxes_safe(processor, model, pil_image, boxes_xyxy, self.device)
        except Exception as e:
            stage_errors["segmentation"] = str(e)
            logger.warning("SAM2 segmentation failed: %s", type(e).__name__)

        # --- Stage 2: DSINE surface normals ---
        normal_map = None
        try:
            dsine_model = _lazy_dsine(self.device)
            normal_map = estimate_normals_safe(dsine_model, image_path)
            result["normals"] = normal_map
        except Exception as e:
            stage_errors["normals"] = str(e)
            logger.warning("DSINE surface normals failed: %s", type(e).__name__)

        # --- Stage 3: Depth + tiered metric calibration + indentation ---
        depth_map = None
        focal_length_px = None
        depth_instances: Dict[int, Dict[str, Any]] = {}
        if self.enable_depth:
            try:
                from .depth_estimation import run_depth_estimation
                proc, model = _lazy_depth(self.device)
                metric_proc = metric_model = None
                if self.enable_metric_depth_prior:
                    try:
                        metric_proc, metric_model = _lazy_metric_depth(self.device)
                    except Exception as e:
                        stage_errors["metric_depth_prior"] = str(e)
                depth_out = run_depth_estimation(
                    image_path, proc, model, masks=masks,
                    plate_bbox=plate_bbox, plate_width_mm=plate_width_mm,
                    metric_depth_processor=metric_proc, metric_depth_model=metric_model,
                    device=self.device,
                )
                depth_map = depth_out["depth_map"]
                focal_length_px = depth_out["focal_length_px"]
                result["depth_map"] = depth_map
                result["focal_length_px"] = focal_length_px
                result["calibration"] = depth_out["calibration"]
                result["max_depth_mm"] = depth_out["max_depth_mm"]
                result["max_indentation_mm"] = depth_out["max_indentation_mm"]
                depth_instances = {i["instance_id"]: i for i in depth_out["instances"]}
            except Exception as e:
                stage_errors["depth"] = str(e)
                logger.warning("Depth estimation/calibration failed: %s", type(e).__name__)

        # --- Stage 4: Per-instance vision measurements ---
        for i, det in enumerate(detections):
            instance = {
                "instance_id": i,
                "class_name": det.get("class_name", "unknown"),
                "confidence": det.get("confidence"),
                "bbox_xyxy": det.get("bbox_xyxy"),
                "mask_iou_score": None,
                "area_px": None,
                "area_cm2": None,
                "crease_angle_deg": None,
                "crease_status": "not_computed",
                "max_depth_mm": None,
                "max_indentation_mm": None,
                "stage_errors": {},
            }

            depth_inst = depth_instances.get(i)
            if depth_inst:
                instance["max_depth_mm"] = depth_inst.get("max_depth_mm")
                instance["max_indentation_mm"] = depth_inst.get("max_indentation_mm")

            if i < len(masks):
                mask_bool, iou_score = masks[i]
                instance["mask_iou_score"] = iou_score
                instance["area_px"] = int(mask_bool.sum())

                # Area from depth map (preferred) or flat-plane fallback
                area_cm2 = None
                if depth_map is not None and focal_length_px:
                    from .segmentation import compute_mask_area_from_depth
                    _, area_cm2 = compute_mask_area_from_depth(mask_bool, depth_map, focal_length_px)
                else:
                    try:
                        from .segmentation import compute_pixel_to_mm, compute_mask_area
                        mm_per_pixel, _ = compute_pixel_to_mm(
                            image_path, img_w, plate_bbox=plate_bbox,
                            plate_width_mm=plate_width_mm,
                        )
                        _, area_cm2 = compute_mask_area(mask_bool, mm_per_pixel)
                    except Exception as e:
                        instance["stage_errors"]["area"] = str(e)
                instance["area_cm2"] = area_cm2

                # Crease angle from DSINE normals
                if normal_map is not None:
                    from .surface_normals import compute_crease_angle
                    try:
                        crease_info = compute_crease_angle(normal_map, mask_bool)
                        instance["crease_angle_deg"] = crease_info.get("crease_angle_deg")
                        instance["crease_status"] = crease_info.get("status")
                    except Exception as e:
                        instance["stage_errors"]["crease_angle"] = str(e)
                        instance["crease_status"] = "stage_error"

            result["instances"].append(instance)

        result["masks"] = masks
        return result


def segment_boxes_safe(processor, model, image, boxes_xyxy, device):
    from .segmentation import segment_boxes
    return segment_boxes(processor, model, image, boxes_xyxy, device=device)


def estimate_normals_safe(model, image_path):
    from .surface_normals import estimate_normals
    return estimate_normals(model, image_path)


def get_vision_pipeline(device: str = "cpu") -> "VisionPipeline":
    """Shared VisionPipeline instance (model weights are cached module-wide)."""
    global _default_pipeline
    if _default_pipeline is None or _default_pipeline.device != device:
        _default_pipeline = VisionPipeline(device=device)
    return _default_pipeline


def run_vision_pipeline(image_path: str, detections: List[Dict[str, Any]],
                        device: str = "cpu",
                        plate_bbox: Optional[Tuple[int, int, int, int]] = None,
                        plate_width_mm: float = 520.0,
                        pipeline: Optional[VisionPipeline] = None) -> Dict[str, Any]:
    """Run the vision pipeline for one image. Never raises: any unexpected
    failure is returned as a result with ``stage_errors["pipeline"]`` set."""
    try:
        pipe = pipeline or get_vision_pipeline(device)
        return pipe.run(
            image_path=image_path, detections=detections,
            plate_bbox=plate_bbox, plate_width_mm=plate_width_mm,
        )
    except Exception as e:
        logger.warning("Vision pipeline failed (%s)", type(e).__name__)
        return {
            "masks": [], "normals": None, "depth_map": None, "focal_length_px": None,
            "calibration": {"status": "failed", "method": None, "confidence": None},
            "max_depth_mm": None, "max_indentation_mm": None,
            "stage_errors": {"pipeline": str(e)}, "instances": [],
        }


def _round(value: Optional[float], digits: int) -> Optional[float]:
    return round(float(value), digits) if value is not None else None


def extract_vision_summary_for_db(
    results: Union[Dict[str, Any], Iterable[Dict[str, Any]], None],
) -> Dict[str, Any]:
    """Aggregate one or more per-image vision results into a flat, JSON-safe
    summary for the ``claim_ai_analysis`` row.

    ``claim_ai_analysis`` has NO top-level ``vision_calibration`` column, so the
    caller must embed ``vision_calibration`` / ``max_indentation_mm`` inside the
    ``relative_deformation_z`` JSONB rather than writing them as columns.

    Keys: mask_count, mean_mask_iou, surface_area_px (int, 0 if unknown),
    area_cm2, crease_angle_deg, crease_angle_count, max_depth_mm,
    max_indentation_mm, vision_calibration, stage_errors.
    """
    if results is None:
        results = []
    elif isinstance(results, dict):
        results = [results]

    total_area_px = 0
    total_area_cm2 = 0.0
    any_area_cm2 = False
    ious: List[float] = []
    creases: List[float] = []
    mask_count = 0
    peaks: List[float] = []
    calibration = None
    stage_errors: Dict[str, str] = {}

    for res in results:
        if not res:
            continue
        for stage, message in (res.get("stage_errors") or {}).items():
            stage_errors.setdefault(stage, str(message)[:200])
        if calibration is None and (res.get("calibration") or {}).get("status") == "calibrated":
            calibration = res["calibration"]
        if res.get("max_indentation_mm") is not None:
            peaks.append(float(res["max_indentation_mm"]))
        for inst in res.get("instances", []):
            if inst.get("area_px") is not None:
                total_area_px += int(inst["area_px"])
            if inst.get("area_cm2") is not None:
                total_area_cm2 += float(inst["area_cm2"])
                any_area_cm2 = True
            if inst.get("mask_iou_score") is not None:
                mask_count += 1
                ious.append(float(inst["mask_iou_score"]))
            if inst.get("crease_angle_deg") is not None:
                creases.append(float(inst["crease_angle_deg"]))
            if inst.get("max_indentation_mm") is not None:
                peaks.append(float(inst["max_indentation_mm"]))

    peak = max(peaks) if peaks else None
    return {
        "mask_count": mask_count,
        "mean_mask_iou": _round(sum(ious) / len(ious), 4) if ious else None,
        "surface_area_px": int(total_area_px),
        "area_cm2": _round(total_area_cm2, 2) if any_area_cm2 else None,
        "crease_angle_deg": _round(sum(creases) / len(creases), 2) if creases else None,
        "crease_angle_count": len(creases),
        "max_depth_mm": _round(peak, 2),
        "max_indentation_mm": _round(peak, 2),
        "vision_calibration": calibration,
        "stage_errors": stage_errors,
    }
