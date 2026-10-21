"""ClaimPilot vision pipeline modules (ported from the v3 pipeline).

This package provides optional computer vision stages that extend the claim
adjudication pipeline in ai_runner.py:

- SAM2 box-prompted segmentation (segmentation.py)
- DSINE surface-normal estimation + crease angle, CPU-safe loader (surface_normals.py)
- Depth Anything V2 monocular depth + tiered metric calibration + peak
  indentation in mm (depth_estimation.py)
- 2D wheel/tire/plate scale calibration helpers (scale_calibration.py)
- YOLO inference helpers (inference.py)
- Frame-to-frame tracking for video mode (temporal_consistency.py)
- Orchestration: VisionPipeline, run_vision_pipeline,
  extract_vision_summary_for_db (vision_pipeline.py)

Names are exported lazily (PEP 562) so that importing this package does not
import torch / transformers / ultralytics until a stage is actually used.
Vision stages degrade gracefully when models or GPU are unavailable.

COLMAP SfM, dense reconstruction, mesh measurement and video mode remain in
the v3 project and are NOT ported here.
"""

import importlib

_EXPORTS = {
    "load_sam2": "segmentation",
    "segment_boxes": "segmentation",
    "compute_mask_area": "segmentation",
    "compute_mask_area_from_depth": "segmentation",
    "compute_pixel_to_mm": "segmentation",
    "load_dsine": "surface_normals",
    "estimate_normals": "surface_normals",
    "colorize_normals": "surface_normals",
    "compute_crease_angle": "surface_normals",
    "load_depth_model": "depth_estimation",
    "load_metric_depth_model": "depth_estimation",
    "estimate_relative_depth": "depth_estimation",
    "estimate_metric_depth_mm": "depth_estimation",
    "detect_license_plate": "depth_estimation",
    "estimate_focal_length_px": "depth_estimation",
    "calibrate_metric_depth": "depth_estimation",
    "calibrate_metric_depth_tiered": "depth_estimation",
    "compute_max_indentation_mm": "depth_estimation",
    "run_depth_estimation": "depth_estimation",
    "calibrate_from_wheel": "scale_calibration",
    "detect_wheel_rim_circle": "scale_calibration",
    "read_tire_code": "scale_calibration",
    "parse_tire_code": "scale_calibration",
    "estimate_camera_intrinsics": "scale_calibration",
    "TIER_1_PLATE": "scale_calibration",
    "TIER_2_WHEEL": "scale_calibration",
    "TIER_3_FALLBACK": "scale_calibration",
    "TemporalTracker": "temporal_consistency",
    "VisionPipeline": "vision_pipeline",
    "run_vision_pipeline": "vision_pipeline",
    "extract_vision_summary_for_db": "vision_pipeline",
}
_ALIASES = {
    "load_yolo_model": ("inference", "load_model"),
    "run_yolo_inference": ("inference", "run_inference"),
}

__all__ = sorted(set(_EXPORTS) | set(_ALIASES))


def __getattr__(name):
    if name in _EXPORTS:
        module = importlib.import_module(f".{_EXPORTS[name]}", __name__)
        return getattr(module, name)
    if name in _ALIASES:
        module_name, attr = _ALIASES[name]
        module = importlib.import_module(f".{module_name}", __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
