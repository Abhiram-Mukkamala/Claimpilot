"""
ClaimPilot vision pipeline orchestrator for backend integration.

Ties together SAM2 segmentation, DSINE surface normals, and Depth Anything V2
metric depth into a single callable stage that extends ai_runner.py's existing
YOLO/RT-DETR damage detection pipeline.

All stages are experimental and optional. If any model is unavailable or a
stage fails, the pipeline degrades gracefully: existing damage dicts are
returned with null vision fields, and the normal claim-processing flow is
never broken.

Usage from ai_runner.py:

    from app.services.vision import VisionPipeline

    vision = VisionPipeline(device=device)
    seg_result = vision.run(
        image_path=local_photo_path,
        detections=detected_damages_for_this_image,
    )
    # seg_result["masks"] -> list of (mask_bool, iou_score) or []
    # seg_result["normals"] -> (H, W, 3) float32 array or None
    # seg_result["depth_map"] -> (H, W) float32 mm array or None
    # seg_result["stage_errors"] -> dict of stage -> error message
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
            detections: List of damage dicts from YOLO/RT-DETR, each with
                        "bbox_xyxy" and optionally "confidence".
            plate_bbox: Optional manual (x, y, w, h) plate override for calibration.
            plate_width_mm: Real-world plate width in mm for calibration.

        Returns:
            dict with keys:
                "masks": list of (mask_bool, iou_score) or []
                "normals": (H, W, 3) float32 array or None
                "depth_map": (H, W) float32 mm array or None
                "focal_length_px": float or None
                "calibration": dict with status/method/confidence
                "stage_errors": dict of stage_name -> error message
                "instances": list of per-instance vision dicts
        """
        stage_errors: Dict[str, str] = {}
        result: Dict[str, Any] = {
            "masks": [],
            "normals": None,
            "depth_map": None,
            "focal_length_px": None,
            "calibration": {"status": "skipped", "method": None, "confidence": None},
            "stage_errors": stage_errors,
            "instances": [],
        }

        pil_image = None
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

        # --- Stage 3: Depth + metric calibration ---
        depth_map = None
        focal_length_px = None
        calibration = {"status": "skipped", "method": None, "confidence": None}
        if self.enable_depth:
            try:
                proc, model = _lazy_depth(self.device)
                relative_depth = estimate_relative_depth_safe(proc, model, image_path, self.device)
                if relative_depth is not None:
                    from .depth_estimation import calibrate_metric_depth_tiered, estimate_focal_length_px as _efl
                    depth_map, calibration = calibrate_metric_depth_tiered(
                        relative_depth, image_path,
                        plate_bbox=plate_bbox,
                        plate_width_mm=plate_width_mm,
                        metric_depth_processor=None,
                        metric_depth_model=None,
                        device=self.device,
                    )
                    focal_length_px, _ = _efl(image_path, img_w)
                    if calibration.get("method") == "metric_depth_prior":
                        focal_length_px, _ = _efl(image_path, img_w)
                    result["depth_map"] = depth_map
                    result["focal_length_px"] = focal_length_px
                    result["calibration"] = calibration
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
                "stage_errors": {},
            }

            if i < len(masks):
                mask_bool, iou_score = masks[i]
                instance["mask_iou_score"] = iou_score
                pixel_count = int(mask_bool.sum())
                instance["area_px"] = pixel_count

                # Area from depth map (preferred) or flat-plane fallback
                area_cm2 = None
                if depth_map is not None and focal_length_px:
                    from .segmentation import compute_mask_area_from_depth
                    pc, ac = compute_mask_area_from_depth(mask_bool, depth_map, focal_length_px)
                    area_cm2 = ac
                else:
                    try:
                        from .segmentation import compute_pixel_to_mm, compute_mask_area
                        mm_per_pixel, _ = compute_pixel_to_mm(
                            image_path, img_w, plate_bbox=plate_bbox,
                            plate_width_mm=plate_width_mm,
                        )
                        pc, ac = compute_mask_area(mask_bool, mm_per_pixel)
                        area_cm2 = ac
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


def estimate_relative_depth_safe(processor, model, image_path, device):
    from .depth_estimation import estimate_relative_depth
    return estimate_relative_depth(processor, model, image_path, device=device)
