# Reusable monocular depth estimation + metric calibration for ClaimPilot.
# Used by the photo-mode pipeline and by ai_runner.py vision integration.
# Ported from the v3 pipeline/depth_estimation.py.
#
# CALIBRATION CHAIN (never-null):
#   Tier 1 - license plate (high confidence when a plate is visible)
#   Tier 2 - wheel / tire (2D Hough circle + optional tire-code OCR; implemented
#            in scale_calibration.py with no COLMAP / open3d dependency)
#   Tier 3 - Depth-Anything-V2 metric-finetuned checkpoint (low confidence,
#            no reference object needed, true last resort)
import math
import numpy as np
import torch
import cv2
from PIL import Image, ExifTags

from . import scale_calibration

PLATE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"

# Realistic automotive dent depth range, in millimetres.
MIN_INDENTATION_MM = 0.0
MAX_INDENTATION_MM = 150.0


def load_depth_model(model_id="depth-anything/Depth-Anything-V2-Base-hf", device="cpu"):
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def load_metric_depth_model(model_id="depth-anything/Depth-Anything-V2-Metric-Outdoor-Base-hf", device="cpu"):
    # Distinct checkpoint from load_depth_model(): fine-tuned to output ABSOLUTE
    # depth directly. UNIT CAVEAT: output is treated as meters (inferred from the
    # Virtual-KITTI training convention) and converted to mm, which is why Tier 3
    # is flagged "low" confidence.
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def estimate_relative_depth(processor, model, image_path, device="cpu"):
    # Returns a (H, W) float32 numpy array, upsampled to the original image size.
    # Values are relative depth in an unspecified, uncalibrated unit.
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth

    prediction = torch.nn.functional.interpolate(
        predicted_depth.unsqueeze(1),
        size=image.size[::-1],  # (H, W) from PIL's (W, H)
        mode="bicubic",
        align_corners=False,
    )
    return prediction.squeeze().cpu().numpy().astype(np.float32)


def estimate_metric_depth_mm(processor, model, image_path, device="cpu"):
    # Tier 3's raw estimate: (H, W) float32 array of ABSOLUTE depth in millimeters.
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth

    prediction = torch.nn.functional.interpolate(
        predicted_depth.unsqueeze(1),
        size=image.size[::-1],
        mode="bicubic",
        align_corners=False,
    )
    depth_m = prediction.squeeze().cpu().numpy().astype(np.float32)
    return depth_m * 1000.0  # meters -> mm


def detect_license_plate(image_path, cascade_path=PLATE_CASCADE_PATH,
                          scale_factor=1.05, min_neighbors=4):
    # Best-effort plate detection via OpenCV Haar cascade. Returns (x, y, w, h) in pixels
    # for the largest detected region, or None if nothing was found or the detector
    # itself is unavailable (e.g. conflicting opencv-* packages).
    try:
        cascade = cv2.CascadeClassifier(cascade_path)
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        plates = cascade.detectMultiScale(gray, scaleFactor=scale_factor, minNeighbors=min_neighbors)
    except AttributeError as e:
        if not getattr(detect_license_plate, "_warned", False):
            print(f"[depth_estimation] plate detector unavailable ({e}). This usually means "
                  "multiple opencv-* pip packages are installed and conflicting. Metric "
                  "calibration will be skipped for auto-detection; manual plate_bbox still works.")
            detect_license_plate._warned = True
        return None

    if len(plates) == 0:
        return None
    x, y, w, h = max(plates, key=lambda b: b[2] * b[3])
    return int(x), int(y), int(w), int(h)


def estimate_focal_length_px(image_path, image_width_px, assumed_hfov_deg=60.0):
    # Prefer EXIF FocalLengthIn35mmFilm when available.
    try:
        img = Image.open(image_path)
        exif_raw = img._getexif()
        if exif_raw:
            tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
            f35 = tag_map.get("FocalLengthIn35mmFilm")
            if f35:
                return image_width_px * (float(f35) / 36.0), "exif_35mm_equivalent"
    except Exception:
        pass

    hfov_rad = math.radians(assumed_hfov_deg)
    focal_px = image_width_px / (2 * math.tan(hfov_rad / 2))
    return focal_px, f"assumed_hfov_{assumed_hfov_deg}deg"


def calibrate_metric_depth(relative_depth_map, image_path, plate_bbox=None,
                            plate_width_mm=520.0, assumed_hfov_deg=60.0, patch_radius=3):
    # Convert a relative depth map to metric (mm) using a license plate of known width
    # as a single calibration reference. Scale-only calibration.
    h_img, w_img = relative_depth_map.shape

    if plate_bbox is None:
        plate_bbox = detect_license_plate(image_path)
        detection_method = "auto_haar_cascade"
    else:
        detection_method = "manual_override"

    if plate_bbox is None:
        return None, {"status": "skipped_no_plate_detected", "detection_method": "auto_haar_cascade"}

    x, y, w, h = plate_bbox
    if w <= 0:
        return None, {"status": "invalid_plate_bbox", "detection_method": detection_method}

    focal_length_px, focal_method = estimate_focal_length_px(image_path, w_img, assumed_hfov_deg)
    plate_distance_mm = (plate_width_mm * focal_length_px) / w

    cx, cy = x + w // 2, y + h // 2
    y0, y1 = max(cy - patch_radius, 0), min(cy + patch_radius + 1, h_img)
    x0, x1 = max(cx - patch_radius, 0), min(cx + patch_radius + 1, w_img)
    relative_value_at_plate = float(np.median(relative_depth_map[y0:y1, x0:x1]))

    if relative_value_at_plate <= 0:
        return None, {"status": "invalid_relative_depth_at_plate", "detection_method": detection_method}

    scale = plate_distance_mm / relative_value_at_plate
    metric_depth_map = relative_depth_map * scale

    calibration_info = {
        "status": "calibrated",
        "tier": scale_calibration.TIER_1_PLATE,
        "method": "plate",
        "confidence": "high",
        "detection_method": detection_method,
        "plate_bbox_xywh": [int(x), int(y), int(w), int(h)],
        "plate_width_mm": plate_width_mm,
        "focal_length_px": float(focal_length_px),
        "focal_length_method": focal_method,
        "plate_distance_mm": float(plate_distance_mm),
        "scale_factor": float(scale),
    }
    return metric_depth_map, calibration_info


def calibrate_metric_depth_tiered(relative_depth_map, image_path, plate_bbox=None,
                                   plate_width_mm=520.0, assumed_hfov_deg=60.0,
                                   ocr_reader=None, metric_depth_processor=None,
                                   metric_depth_model=None, device="cpu"):
    """Never-null metric depth calibration: Tier 1 (plate) -> Tier 2 (wheel/tire)
    -> Tier 3 (metric depth model prior, used directly - no reference object).

    Tiers 2 (OCR part) and 3 degrade gracefully when ocr_reader /
    metric_depth_processor+model are not supplied. Returns
    (metric_depth_map_or_None, calibration_info); None only if every tier fails.
    """
    # --- Tier 1: plate ---
    metric_depth_map, calib_info = calibrate_metric_depth(
        relative_depth_map, image_path, plate_bbox=plate_bbox,
        plate_width_mm=plate_width_mm, assumed_hfov_deg=assumed_hfov_deg,
    )
    if calib_info.get("status") == "calibrated":
        return metric_depth_map, calib_info

    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return None, {"status": "skipped_image_unreadable"}
    h_img, w_img = relative_depth_map.shape
    focal_length_px, focal_method = estimate_focal_length_px(image_path, w_img, assumed_hfov_deg)

    # --- Tier 2: wheel / tire (pure 2D, no COLMAP) ---
    try:
        metric_depth_map, wheel_info = scale_calibration.calibrate_from_wheel(
            relative_depth_map, image_bgr, focal_length_px, ocr_reader=ocr_reader,
        )
    except Exception as e:
        metric_depth_map, wheel_info = None, {"status": "failed_wheel_calibration", "error": type(e).__name__}
    if wheel_info.get("status") == "calibrated":
        wheel_info["focal_length_method"] = focal_method
        return metric_depth_map, wheel_info

    # --- Tier 3: metric depth model prior (true last resort) ---
    if metric_depth_processor is not None and metric_depth_model is not None:
        try:
            metric_depth_map = estimate_metric_depth_mm(
                metric_depth_processor, metric_depth_model, image_path, device=device,
            )
            return metric_depth_map, {
                "status": "calibrated",
                "tier": scale_calibration.TIER_3_FALLBACK,
                "method": "metric_depth_prior",
                "confidence": "low",
                "focal_length_px": float(focal_length_px),
                "focal_length_method": focal_method,
                "note": (
                    "Model-estimated absolute depth (Depth-Anything-V2 metric checkpoint), "
                    "not a measured reference object. Treat as order-of-magnitude, not precise."
                ),
            }
        except Exception as e:
            return None, {"status": "failed", "method": "metric_depth_prior", "error": str(e)}

    return None, {"status": "skipped_no_reference_found"}


def compute_max_indentation_mm(metric_depth_map_mm, mask_bool, ring_width_px=15,
                                peak_percentile=98.0):
    """Peak indentation (mm) of a damage mask relative to the surrounding
    undamaged ring.

    The ring is a band just outside the mask (dilated mask minus mask). Its
    median metric depth is the local undeformed panel reference; the indentation
    is how far depth inside the mask deviates from it. A high percentile of the
    absolute deviation (rather than the raw max) keeps single noisy pixels from
    dominating. The result is clamped to the realistic automotive range
    [0.0, 150.0] mm.

    Returns a float, or None when depth/mask/ring data is unavailable.
    """
    if metric_depth_map_mm is None or mask_bool is None:
        return None
    mask_bool = np.asarray(mask_bool, dtype=bool)
    if mask_bool.shape != metric_depth_map_mm.shape or not mask_bool.any():
        return None

    kernel = np.ones((ring_width_px, ring_width_px), np.uint8)
    dilated = cv2.dilate(mask_bool.astype(np.uint8), kernel, iterations=1).astype(bool)
    ring = dilated & ~mask_bool

    ring_depths = metric_depth_map_mm[ring]
    ring_depths = ring_depths[np.isfinite(ring_depths) & (ring_depths > 0)]
    mask_depths = metric_depth_map_mm[mask_bool]
    mask_depths = mask_depths[np.isfinite(mask_depths) & (mask_depths > 0)]
    if ring_depths.size == 0 or mask_depths.size == 0:
        return None

    ring_median = float(np.median(ring_depths))
    deviation = np.abs(mask_depths - ring_median)
    peak = float(np.percentile(deviation, peak_percentile))
    return float(np.clip(peak, MIN_INDENTATION_MM, MAX_INDENTATION_MM))


def run_depth_estimation(image_path, processor, model, masks=None, plate_bbox=None,
                          plate_width_mm=520.0, assumed_hfov_deg=60.0, ocr_reader=None,
                          metric_depth_processor=None, metric_depth_model=None,
                          device="cpu", relative_depth=None):
    """Run depth estimation + tiered metric calibration and per-instance
    indentation measurement.

    Args:
        masks: optional list of (mask_bool, iou_score) (or bare mask arrays), one
            per damage instance, as returned by segmentation.segment_boxes().

    Returns a dict:
        status: "ok" | "uncalibrated" | "failed"
        depth_map: (H, W) float32 mm array or None
        relative_depth: (H, W) float32 array or None
        focal_length_px, calibration
        instances: [{"instance_id", "max_depth_mm", "max_indentation_mm"}]
        max_depth_mm / max_indentation_mm: peak across instances (same value,
            both keys always written so consumers never see a missing key). They
            are None only when depth estimation did not succeed.
    """
    result = {
        "status": "failed",
        "depth_map": None,
        "relative_depth": None,
        "focal_length_px": None,
        "calibration": {"status": "skipped", "method": None, "confidence": None},
        "instances": [],
        "max_depth_mm": None,
        "max_indentation_mm": None,
    }

    if relative_depth is None:
        relative_depth = estimate_relative_depth(processor, model, image_path, device=device)
    result["relative_depth"] = relative_depth
    if relative_depth is None:
        return result

    h_img, w_img = relative_depth.shape
    focal_length_px, _ = estimate_focal_length_px(image_path, w_img, assumed_hfov_deg)
    result["focal_length_px"] = focal_length_px

    depth_map, calibration = calibrate_metric_depth_tiered(
        relative_depth, image_path, plate_bbox=plate_bbox, plate_width_mm=plate_width_mm,
        assumed_hfov_deg=assumed_hfov_deg, ocr_reader=ocr_reader,
        metric_depth_processor=metric_depth_processor,
        metric_depth_model=metric_depth_model, device=device,
    )
    result["calibration"] = calibration
    result["depth_map"] = depth_map
    if depth_map is None:
        result["status"] = "uncalibrated"
        return result

    result["status"] = "ok"
    peaks = []
    for i, entry in enumerate(masks or []):
        mask_bool = entry[0] if isinstance(entry, (tuple, list)) else entry
        indentation = compute_max_indentation_mm(depth_map, mask_bool)
        result["instances"].append({
            "instance_id": i,
            "max_depth_mm": indentation,
            "max_indentation_mm": indentation,
        })
        if indentation is not None:
            peaks.append(indentation)

    if peaks:
        peak = float(max(peaks))
        result["max_depth_mm"] = peak
        result["max_indentation_mm"] = peak
    return result
