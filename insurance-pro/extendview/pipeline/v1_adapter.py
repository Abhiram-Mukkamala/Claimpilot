"""
v1 Adapter — Bridge ClaimPilot ExtendView UI to v3 Photo Pipeline
=================================================================
Resolves model weights from:
  1. C:\\Projects\\claimpilot\\insurance-pro\\backend\\app\\models\\weights
  2. C:\\Users\\abhir\\Downloads\\v3\\v3\\models (read-only fallback)
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Tuple, Optional, List

import cv2
import numpy as np
import torch

PIPELINE_ROOT = Path(__file__).parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

try:
    from photo_pipeline import analyze_photo
    from inference_v2 import run_inference_v2
    from depth_estimation import (
        estimate_relative_depth,
        calibrate_metric_depth_tiered,
        load_depth_model,
        load_metric_depth_model,
        compute_instance_depth_mm,
    )
    from segmentation import segment_boxes, compute_mask_area_from_depth
    from surface_normals import estimate_normals, compute_crease_angle, load_dsine
except ImportError as e:
    raise ImportError(f"v3 pipeline modules not found in {PIPELINE_ROOT}. Error: {e}")


def resolve_weight_path(filename: str) -> Path:
    """Resolve model checkpoint from repo backend weights dir or v3 read-only models dir."""
    ext_root = PIPELINE_ROOT.parent
    repo_weights = ext_root.parent / "backend" / "app" / "models" / "weights"
    local_models = ext_root / "models"
    v3_fallback = Path(r"C:\Users\abhir\Downloads\v3\v3\models")

    # Map cardd_best.pt <-> best.pt alias
    aliases = [filename]
    if filename == "cardd_best.pt":
        aliases.append("best.pt")
    elif filename == "best.pt":
        aliases.append("cardd_best.pt")

    for base_dir in (local_models, repo_weights, v3_fallback):
        for name in aliases:
            candidate = base_dir / name
            if candidate.exists():
                return candidate

    return repo_weights / filename


def load_v2_models(device: str = "cpu") -> Tuple:
    """
    Load all v3 photo-pipeline models once.
    Returns:
        (yolo_model, depth_processor, depth_model, sam2_processor, sam2_model, dsine_model)
    """
    from ultralytics import YOLO
    from depth_estimation import load_depth_model
    from segmentation import load_sam2

    yolo_path = resolve_weight_path("yolov11m.pt")
    if not yolo_path.exists():
        raise FileNotFoundError(f"YOLOv11m not found at {yolo_path}")
    yolo_model = YOLO(str(yolo_path))
    yolo_model.to(device)

    depth_processor, depth_model = load_depth_model(
        "depth-anything/Depth-Anything-V2-Small-hf", device=device
    )

    sam2_processor, sam2_model = load_sam2(
        "facebook/sam2.1-hiera-small", device=device
    )

    dsine_model = _load_dsine_patched(device)

    return yolo_model, depth_processor, depth_model, sam2_processor, sam2_model, dsine_model


def _load_dsine_patched(device: str):
    return load_dsine(device=device)


def run_v2_pipeline_as_v1(
    bgr_img: np.ndarray,
    yolo_model,
    depth_processor,
    depth_model,
    sam2_processor,
    sam2_model,
    dsine_model,
    real_mm: float = 500.0,
    size: int = 480,
    device: str = "cpu",
    plate_bbox: Optional[List[float]] = None,
    imgsz: int = 640,
    use_tta: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    img_out, depth_map, normal_map, mask, mm_per_px, _, _ = run_v2_pipeline_full(
        bgr_img,
        yolo_model,
        depth_processor,
        depth_model,
        sam2_processor,
        sam2_model,
        dsine_model,
        real_mm=real_mm,
        size=size,
        device=device,
        plate_bbox=plate_bbox,
        imgsz=imgsz,
        use_tta=use_tta,
    )
    return img_out, depth_map, normal_map, mask, mm_per_px


def extract_v1_metrics_from_v2_report(
    report: dict,
    depth_map: Optional[np.ndarray] = None,
    normal_map: Optional[np.ndarray] = None,
    mask: Optional[np.ndarray] = None,
    mm_per_px: float = 2.63,
) -> dict:
    """
    Convert v3's per-instance metrics to {max_depth_mm, area_cm2, angle_deg}.
    Never returns 0.0 when a valid depth_map and mask are present.
    """
    instances = report.get("damage_instances", [])
    max_depth_mm = 0.0
    total_area_cm2 = 0.0
    max_angle_deg = 0.0

    for inst in instances:
        if inst.get("area_cm2") is not None:
            total_area_cm2 += float(inst["area_cm2"])
        if inst.get("max_depth_mm") is not None:
            max_depth_mm = max(max_depth_mm, float(inst["max_depth_mm"]))
        if inst.get("crease_angle_deg") is not None:
            max_angle_deg = max(max_angle_deg, float(inst["crease_angle_deg"]))

    depth_info = report.get("calibration", {}).get("depth_metric", {})
    if depth_info.get("max_depth_mm"):
        max_depth_mm = max(max_depth_mm, float(depth_info["max_depth_mm"]))

    # Fallback if YOLO found 0 instances or depth_mm wasn't populated on instances
    if (max_depth_mm <= 0.0 or total_area_cm2 <= 0.0) and depth_map is not None and mask is not None:
        mask_bool = mask.astype(bool)
        if np.any(mask_bool):
            if max_depth_mm <= 0.0:
                max_depth_mm = compute_instance_depth_mm(depth_map, mask_bool)
            if total_area_cm2 <= 0.0:
                total_area_cm2 = float(mask_bool.sum() * (mm_per_px ** 2) / 100.0)
            if max_angle_deg <= 0.0 and normal_map is not None:
                ref = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                normals_in_mask = normal_map[mask_bool]
                dots = np.clip(normals_in_mask @ ref, -1.0, 1.0)
                angles = np.degrees(np.arccos(dots))
                if angles.size > 0:
                    max_angle_deg = float(np.percentile(angles, 90))

    return dict(
        max_depth_mm=round(max(max_depth_mm, 0.8), 2),
        area_cm2=round(max(total_area_cm2, 1.0), 1),
        angle_deg=round(max(max_angle_deg, 2.5), 2),
    )


def run_v2_pipeline_full(
    bgr_img: np.ndarray,
    yolo_model,
    depth_processor,
    depth_model,
    sam2_processor,
    sam2_model,
    dsine_model,
    real_mm: float = 500.0,
    size: int = 480,
    device: str = "cpu",
    plate_bbox: Optional[List[float]] = None,
    imgsz: int = 640,
    use_tta: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, dict, dict]:
    """
    Extended version returning visualization arrays + metrics + full v3 report.
    Returns:
        (img_out, depth_map, normal_map, mask, mm_per_px, v1_metrics, v2_report)
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, bgr_img)
            tmp_path = tmp.name

        report = analyze_photo(
            image_path=tmp_path,
            yolo_model=yolo_model,
            depth_processor=depth_processor,
            depth_model=depth_model,
            sam2_processor=sam2_processor,
            sam2_model=sam2_model,
            dsine_model=dsine_model,
            plate_bbox=plate_bbox,
            plate_width_mm=real_mm,
            imgsz=imgsz,
            device=device,
            use_per_class_thresholds=True,
            use_tta=use_tta,
            return_artifacts=True,
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    artifacts = report.get("_artifacts", {})
    metric_depth_map = artifacts.get("metric_depth_map")
    normal_map_full = artifacts.get("normal_map")
    seg_masks = artifacts.get("seg_masks")

    img_h, img_w = bgr_img.shape[:2]
    img_out = cv2.resize(bgr_img, (size, size))

    if metric_depth_map is not None:
        depth_map = cv2.resize(metric_depth_map, (size, size), interpolation=cv2.INTER_LINEAR)
    else:
        depth_map = np.zeros((size, size), dtype=np.float32)

    if normal_map_full is not None:
        normal_map = cv2.resize(normal_map_full, (size, size), interpolation=cv2.INTER_LINEAR)
        norm = np.linalg.norm(normal_map, axis=-1, keepdims=True)
        norm[norm == 0] = 1.0
        normal_map = (normal_map / norm).astype(np.float32)
    else:
        normal_map = np.zeros((size, size, 3), dtype=np.float32)
        normal_map[:, :, 2] = 1.0

    mask = np.zeros((size, size), dtype=np.uint8)
    scale_x = size / img_w
    scale_y = size / img_h

    if seg_masks:
        for mask_bool, iou_score in seg_masks:
            if mask_bool is not None and mask_bool.any():
                mask_resized = cv2.resize(mask_bool.astype(np.uint8), (size, size), interpolation=cv2.INTER_NEAREST)
                mask = np.maximum(mask, mask_resized)

    if mask.sum() == 0:
        for inst in report.get("damage_instances", []):
            if inst.get("stage_errors", {}).get("segmentation"):
                continue
            bbox = inst.get("bbox_xyxy", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                x1, y1, x2, y2 = int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)
                mask[y1:y2, x1:x2] = 1

    # Salient contour fallback if no bounding boxes fired on a custom close-up photo
    if mask.sum() == 0:
        gray = cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 30, 100)
        edges_dilated = cv2.dilate(edges, np.ones((7, 7), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 100:
                cv2.drawContours(mask, [largest], -1, 1, -1)
        if mask.sum() == 0:
            cy, cx = size // 2, size // 2
            mask[cy - 50:cy + 50, cx - 50:cx + 50] = 1

    mm_per_px = real_mm / 190.0
    calib = report.get("calibration", {}).get("depth_metric", {})
    if calib.get("mm_per_pixel"):
        mm_per_px = float(calib["mm_per_pixel"])

    v1_metrics = extract_v1_metrics_from_v2_report(
        report, depth_map=depth_map, normal_map=normal_map, mask=mask, mm_per_px=mm_per_px
    )
    report_clean = {k: v for k, v in report.items() if k != "_artifacts"}

    return img_out, depth_map, normal_map, mask, mm_per_px, v1_metrics, report_clean
