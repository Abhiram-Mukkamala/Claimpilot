# Reusable monocular depth estimation + metric calibration for ClaimPilot.
# Used by the photo-mode pipeline and by ai_runner.py vision integration.
# Ported from ml/scripts/depth_estimation.py for backend integration.
#
# CALIBRATION CHAIN (simplified for backend integration):
#   Tier 1 - license plate (high confidence when plate is visible)
#   Tier 3 - Depth-Anything-V2 metric-finetuned checkpoint (low confidence,
#            no reference object needed, true last resort)
#
# Tier 2 (wheel/tire via scale_calibration) is intentionally omitted here
# because scale_calibration.py depends on mesh_measurement.py and COLMAP
# reconstruction state, which are experimental and kept modular in ml/scripts/.
import math
import numpy as np
import torch
import cv2
from PIL import Image, ExifTags


PLATE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"


def load_depth_model(model_id="depth-anything/Depth-Anything-V2-Base-hf", device="cuda"):
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def load_metric_depth_model(model_id="depth-anything/Depth-Anything-V2-Metric-Outdoor-Base-hf", device="cuda"):
    # Distinct checkpoint from load_depth_model(): this one is fine-tuned to
    # output ABSOLUTE depth directly, not a relative depth map.
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def estimate_relative_depth(processor, model, image_path, device="cuda"):
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


def estimate_metric_depth_mm(processor, model, image_path, device="cuda"):
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
    # for the largest detected region, or None if nothing was found.
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
                                   metric_depth_processor=None, metric_depth_model=None,
                                   device="cuda"):
    """Never-null metric depth calibration: Tier 1 (plate) -> Tier 3 (metric depth
    model prior). Tier 2 (wheel/tire) is omitted because it requires scale_calibration.py
    and mesh_measurement.py which depend on COLMAP reconstruction state.

    Returns (metric_depth_map_or_None, calibration_info). Only returns None if every
    tier fails.
    """
    # --- Tier 1: plate ---
    metric_depth_map, calib_info = calibrate_metric_depth(
        relative_depth_map, image_path, plate_bbox=plate_bbox,
        plate_width_mm=plate_width_mm, assumed_hfov_deg=assumed_hfov_deg,
    )
    if calib_info.get("status") == "calibrated":
        return metric_depth_map, calib_info

    # --- Tier 3: metric depth model prior ---
    if metric_depth_processor is not None and metric_depth_model is not None:
        try:
            metric_depth_map = estimate_metric_depth_mm(
                metric_depth_processor, metric_depth_model, image_path, device=device,
            )
            focal_length_px, focal_method = estimate_focal_length_px(image_path, relative_depth_map.shape[1], assumed_hfov_deg)
            return metric_depth_map, {
                "status": "calibrated",
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
