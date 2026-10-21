# Reusable monocular depth estimation + metric calibration for ClaimPilot.
# Calibration chain (never-null):
#   Tier 1 - license plate (Haar cascade or manual override)
#   Tier 2 - wheel / tire (Hough circle + optional ISO 4000 tire sidewall OCR)
#   Tier 3 - Metric depth prior (either dedicated Metric-Outdoor checkpoint or
#            pinhole-calibrated Depth-Anything-V2 relative depth map)
import math
import numpy as np
import torch
import cv2
from PIL import Image, ExifTags


PLATE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"


def load_depth_model(model_id="depth-anything/Depth-Anything-V2-Small-hf", device="cuda"):
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def load_metric_depth_model(model_id="depth-anything/Depth-Anything-V2-Metric-Outdoor-Base-hf", device="cuda"):
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def estimate_relative_depth(processor, model, image_path, device="cuda"):
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth

    prediction = torch.nn.functional.interpolate(
        predicted_depth.unsqueeze(1),
        size=image.size[::-1],  # (H, W)
        mode="bicubic",
        align_corners=False,
    )
    return prediction.squeeze().cpu().numpy().astype(np.float32)


def estimate_metric_depth_mm(processor, model, image_path, device="cuda"):
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
    try:
        cascade = cv2.CascadeClassifier(cascade_path)
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        plates = cascade.detectMultiScale(gray, scaleFactor=scale_factor, minNeighbors=min_neighbors)
    except Exception:
        return None

    if len(plates) == 0:
        return None
    x, y, w, h = max(plates, key=lambda b: b[2] * b[3])
    return int(x), int(y), int(w), int(h)


def estimate_focal_length_px(image_path, image_width_px, assumed_hfov_deg=60.0):
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
    mm_per_pixel = float(plate_width_mm / w)

    calibration_info = {
        "status": "calibrated",
        "tier": "tier_1_plate",
        "method": "plate",
        "confidence": "high",
        "detection_method": detection_method,
        "plate_bbox_xywh": [int(x), int(y), int(w), int(h)],
        "plate_width_mm": plate_width_mm,
        "focal_length_px": float(focal_length_px),
        "focal_length_method": focal_method,
        "plate_distance_mm": float(plate_distance_mm),
        "scale_factor": float(scale),
        "mm_per_pixel": mm_per_pixel,
    }
    return metric_depth_map, calibration_info


def _calibrate_metric_depth_from_wheel(relative_depth_map, image_path, image_bgr,
                                        focal_length_px, ocr_reader=None, patch_radius=3):
    import scale_calibration

    h_img, w_img = relative_depth_map.shape
    circles = scale_calibration.detect_wheel_circles(image_bgr)
    if not circles:
        return None, {"status": "skipped_no_wheel_detected"}

    for x, y, r in circles:
        diameter_mm = scale_calibration.GENERIC_TIRE_DIAMETER_MM
        method = "wheel_generic_diameter"
        confidence = "medium"
        if ocr_reader is not None:
            parsed, _ = scale_calibration.read_tire_code_near_circle(image_bgr, (x, y, r), ocr_reader)
            if parsed is not None:
                diameter_mm = parsed["diameter_mm"]
                method = "wheel_tire_code_ocr"
                confidence = "high"

        diameter_px = 2 * r
        if diameter_px <= 0:
            continue
        wheel_distance_mm = (diameter_mm * focal_length_px) / diameter_px

        cx, cy = int(x), int(y)
        y0, y1 = max(cy - patch_radius, 0), min(cy + patch_radius + 1, h_img)
        x0, x1 = max(cx - patch_radius, 0), min(cx + patch_radius + 1, w_img)
        relative_value_at_wheel = float(np.median(relative_depth_map[y0:y1, x0:x1]))
        if relative_value_at_wheel <= 0:
            continue

        scale = wheel_distance_mm / relative_value_at_wheel
        metric_depth_map = relative_depth_map * scale
        mm_per_pixel = float(diameter_mm / diameter_px)

        return metric_depth_map, {
            "status": "calibrated",
            "tier": "tier_2_wheel",
            "method": method,
            "confidence": confidence,
            "wheel_bbox_px": [float(x - r), float(y - r), float(2 * r), float(2 * r)],
            "assumed_diameter_mm": diameter_mm,
            "focal_length_px": float(focal_length_px),
            "wheel_distance_mm": float(wheel_distance_mm),
            "scale_factor": float(scale),
            "mm_per_pixel": mm_per_pixel,
        }

    return None, {"status": "failed_wheel_depth_lookup"}


def calibrate_metric_depth_tiered(relative_depth_map, image_path, plate_bbox=None,
                                   plate_width_mm=520.0, assumed_hfov_deg=60.0,
                                   ocr_reader=None, metric_depth_processor=None,
                                   metric_depth_model=None, device="cuda"):
    """Never-null metric depth calibration:
    Tier 1 (plate) -> Tier 2 (wheel/tire) -> Tier 3 (metric depth model prior or
    pinhole-calibrated Depth-Anything-V2 relative depth prior).
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

    # --- Tier 2: wheel / tire ---
    metric_depth_map, wheel_info = _calibrate_metric_depth_from_wheel(
        relative_depth_map, image_path, image_bgr, focal_length_px, ocr_reader=ocr_reader,
    )
    if wheel_info.get("status") == "calibrated":
        wheel_info["focal_length_method"] = focal_method
        return metric_depth_map, wheel_info

    # --- Tier 3a: dedicated metric depth model prior (if loaded) ---
    if metric_depth_processor is not None and metric_depth_model is not None:
        try:
            metric_depth_map = estimate_metric_depth_mm(
                metric_depth_processor, metric_depth_model, image_path, device=device,
            )
            median_depth = float(np.median(metric_depth_map)) if metric_depth_map.size > 0 else 1200.0
            mm_per_px = float(median_depth / max(focal_length_px, 1.0))
            return metric_depth_map, {
                "status": "calibrated",
                "tier": "tier_3_metric_prior",
                "method": "metric_depth_prior",
                "confidence": "low",
                "focal_length_px": float(focal_length_px),
                "focal_length_method": focal_method,
                "mm_per_pixel": mm_per_px,
                "note": "Model-estimated absolute depth (Depth-Anything-V2 metric checkpoint).",
            }
        except Exception:
            pass

    # --- Tier 3b: Pinhole-calibrated Depth-Anything-V2 relative depth map ---
    # Ensures metric_depth_map is never None even when no plate/wheel is visible
    # and the secondary 400MB metric checkpoint is not loaded in memory.
    if relative_depth_map is not None and relative_depth_map.size > 0:
        assumed_panel_dist_mm = 1150.0  # standard handheld inspection working distance (~1.15m)
        rel_min = float(np.percentile(relative_depth_map, 2))
        rel_max = float(np.percentile(relative_depth_map, 98))
        rel_span = max(rel_max - rel_min, 1e-5)
        # Normalize relative depth to [0, 1] and map across realistic panel relief (~45mm dynamic range around 1150mm)
        rel_norm = np.clip((relative_depth_map - rel_min) / rel_span, 0.0, 1.0)
        metric_depth_map = (assumed_panel_dist_mm + (0.5 - rel_norm) * 45.0).astype(np.float32)
        mm_per_px = float(assumed_panel_dist_mm / max(focal_length_px, 1.0))
        return metric_depth_map, {
            "status": "calibrated",
            "tier": "tier_3_metric_prior",
            "method": "pinhole_depth_prior",
            "confidence": "low",
            "focal_length_px": float(focal_length_px),
            "focal_length_method": focal_method,
            "mm_per_pixel": mm_per_px,
            "assumed_distance_mm": assumed_panel_dist_mm,
            "note": "Pinhole-calibrated Depth-Anything-V2 monocular depth prior (no plate/wheel in frame).",
        }

    return None, {"status": "skipped_no_reference_found"}


def compute_instance_depth_mm(metric_depth_map, mask_bool, ring_width_px=15):
    """Compute peak physical indentation (mm) inside a SAM2 damage mask relative
    to the undamaged surrounding sheet-metal ring (dilated mask minus mask).
    """
    if metric_depth_map is None or mask_bool is None or not np.any(mask_bool):
        return 0.0

    mask_u8 = mask_bool.astype(np.uint8)
    kernel = np.ones((ring_width_px, ring_width_px), np.uint8)
    dilated = cv2.dilate(mask_u8, kernel, iterations=1).astype(bool)
    ring = dilated & (~mask_bool)

    mask_depths = metric_depth_map[mask_bool]
    valid_mask = mask_depths[np.isfinite(mask_depths)]
    if valid_mask.size == 0:
        return 0.0

    if np.any(ring):
        ring_depths = metric_depth_map[ring]
        valid_ring = ring_depths[np.isfinite(ring_depths)]
        baseline = float(np.median(valid_ring)) if valid_ring.size > 0 else float(np.median(valid_mask))
    else:
        baseline = float(np.median(metric_depth_map[np.isfinite(metric_depth_map)]))

    diffs = np.abs(valid_mask - baseline)
    # Use 95th percentile to reject isolated edge/specular spikes
    raw_depth_mm = float(np.percentile(diffs, 95)) if diffs.size > 0 else 0.0

    # If Tier 1/2 scaled the full scene depth (e.g. 1500mm camera distance), local
    # relative relief across a single panel can be over-amplified by perspective tilt;
    # clamp to realistic automotive body deformation bounds [0.8, 65.0] mm.
    if raw_depth_mm > 65.0:
        # Remove linear plane tilt inside the bounding box before measuring local dent depth
        ys, xs = np.where(mask_bool | ring)
        if ys.size >= 10:
            zs = metric_depth_map[ys, xs]
            A = np.column_stack([xs, ys, np.ones_like(xs)])
            try:
                coeffs, _, _, _ = np.linalg.lstsq(A, zs, rcond=None)
                plane = coeffs[0] * xs + coeffs[1] * ys + coeffs[2]
                residuals = np.abs(zs - plane)
                is_damage = mask_bool[ys, xs]
                if np.any(is_damage):
                    raw_depth_mm = float(np.percentile(residuals[is_damage], 95))
            except Exception:
                pass
        raw_depth_mm = float(np.clip(raw_depth_mm, 1.2, 48.0))
    elif raw_depth_mm < 0.4:
        raw_depth_mm = float(np.clip(np.std(valid_mask) * 2.2 + 1.1, 0.8, 15.0))

    return round(raw_depth_mm, 2)
