"""ClaimPilot vision pipeline modules (ported from ml/scripts/).

This package provides optional, GPU-dependent computer vision stages that
extend the existing claim adjudication pipeline in ai_runner.py:

- SAM2 box-prompted segmentation (segmentation.py)
- DSINE surface-normal estimation + crease angle (surface_normals.py)
- Depth Anything V2 monocular depth + metric calibration (depth_estimation.py)
- YOLO inference helpers (inference.py)

All stages are experimental and optional. The existing YOLO/RT-DETR damage
detection pipeline continues to work without any of these modules. Vision
stages are loaded lazily and degrade gracefully when models or GPU are
unavailable.

Experimental components (COLMAP SfM, dense reconstruction, mesh measurement,
video mode) remain in ml/scripts/ and are NOT ported here. They require
precomputed reconstruction state and are kept modular so they cannot break
the normal photo-mode claim-processing flow.
"""

from .segmentation import load_sam2, segment_boxes, compute_mask_area, compute_mask_area_from_depth, compute_pixel_to_mm
from .surface_normals import load_dsine, estimate_normals, colorize_normals, compute_crease_angle
from .depth_estimation import (
    load_depth_model,
    load_metric_depth_model,
    estimate_relative_depth,
    estimate_metric_depth_mm,
    detect_license_plate,
    estimate_focal_length_px,
    calibrate_metric_depth,
    calibrate_metric_depth_tiered,
)
from .inference import load_model as load_yolo_model, run_inference as run_yolo_inference

__all__ = [
    "load_sam2",
    "segment_boxes",
    "compute_mask_area",
    "compute_mask_area_from_depth",
    "compute_pixel_to_mm",
    "load_dsine",
    "estimate_normals",
    "colorize_normals",
    "compute_crease_angle",
    "load_depth_model",
    "load_metric_depth_model",
    "estimate_relative_depth",
    "estimate_metric_depth_mm",
    "detect_license_plate",
    "estimate_focal_length_px",
    "calibrate_metric_depth",
    "calibrate_metric_depth_tiered",
    "load_yolo_model",
    "run_yolo_inference",
]
