# Reusable monocular depth estimation + metric calibration for ClaimPilot.
# Used by T2.1, by the end-to-end pipeline (T2.4/photo_pipeline.py), and by
# run_local_pipeline.py.
#
# CALIBRATION CHAIN (never-null): a license plate alone leaves most real
# claims uncalibrated (plate damaged, dirty, unphotographed, or at an
# un-matchable angle for the Haar cascade - see module docstring further
# down for the fallback design). calibrate_metric_depth_tiered() tries, in
# order:
#   Tier 1 - license plate (existing calibrate_metric_depth() logic)
#   Tier 2 - wheel / tire: Hough-circle wheel detection, then either an
#            exact tire-sidewall size code read via OCR (ISO 4000 formula -
#            exact, no lookup table) or a generic passenger-tire diameter if
#            the code can't be read. Wheels are visible in nearly every
#            vehicle photo and (unlike the plate) are almost never the
#            claimed damage.
#   Tier 3 - Depth-Anything-V2's METRIC-finetuned checkpoint, used directly
#            as the depth source (no reference object needed at all) - the
#            true last resort, always available once the model is loaded.
# Each tier mirrors the implementation already validated in
# scale_calibration.py (Video Mode's 3D equivalent of this chain) -
# detect_wheel_circles / parse_tire_code / tire_code_to_diameter_mm /
# read_tire_code_near_circle are imported from there rather than
# duplicated, since that logic is pure 2D/OpenCV and has no mesh
# dependency.
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
    # Distinct checkpoint from load_depth_model() above: this one is fine-tuned to
    # output ABSOLUTE depth directly (trained on real metric depth datasets, e.g.
    # Virtual-KITTI for the outdoor variant), not a relative depth map. Same
    # transformers API family. UNIT CAVEAT: the model card doesn't explicitly state
    # output units; Virtual-KITTI ground truth is in meters, so this module treats
    # raw output as meters and converts to mm - an inference from the training
    # dataset's convention, not a confirmed spec. This is why Tier 3 (below) is
    # flagged "low" confidence, not "high".
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id)
    model.to(device).eval()
    return processor, model


def estimate_relative_depth(processor, model, image_path, device="cuda"):
    # Returns a (H, W) float32 numpy array, upsampled to the original image size.
    # Values are relative depth in an unspecified, uncalibrated unit -- NOT millimeters.
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
    # Tier 3's raw estimate: (H, W) float32 array of ABSOLUTE depth in millimeters
    # (see UNIT CAVEAT in load_metric_depth_model), no reference object required.
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
    # for the largest detected region, or None if nothing was found (or if the detector
    # itself is unavailable). This is a coarse detector tuned for frontal/rear plate
    # photos -- expect a low hit rate on angled or close-up shots. Use the manual bbox
    # override in calibrate_metric_depth() when it misses.
    #
    # Wrapped defensively: environments with multiple opencv-* pip packages installed
    # (e.g. opencv-python alongside opencv-python-headless, which can happen when a
    # library like fiftyone pulls in a different variant than an earlier install) can end
    # up with a broken cv2 module missing attributes like CascadeClassifier. Plate
    # detection is a best-effort convenience, not the core deliverable of this module --
    # a broken cascade classifier should degrade to "no plate detected", not crash the
    # whole depth-estimation pipeline.
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
                  "calibration will be skipped for auto-detection; manual plate_bbox still works. "
                  "To fix: pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python "
                  "opencv-contrib-python-headless, then pip install opencv-python-headless, then "
                  "restart the runtime.")
            detect_license_plate._warned = True
        return None

    if len(plates) == 0:
        return None
    # Largest detected region by area is the most likely true positive
    x, y, w, h = max(plates, key=lambda b: b[2] * b[3])
    return int(x), int(y), int(w), int(h)


def estimate_focal_length_px(image_path, image_width_px, assumed_hfov_deg=60.0):
    # Prefer EXIF FocalLengthIn35mmFilm when available: that tag is defined relative to
    # the 36mm-wide full-frame sensor, so focal_length_px = image_width_px * (f35 / 36).
    # Falls back to an assumed horizontal field-of-view otherwise.
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
    # as a single calibration reference. Scale-only calibration (see module docstring in
    # the notebook for why this is a documented simplification, not a full affine fit).
    #
    # plate_bbox: (x, y, w, h) in pixels. If None, runs the Haar-cascade auto-detector.
    #
    # Returns: (metric_depth_map_or_None, calibration_info_dict)
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


def _calibrate_metric_depth_from_wheel(relative_depth_map, image_path, image_bgr,
                                        focal_length_px, ocr_reader=None, patch_radius=3):
    # Tier 2: same scale-fit math as calibrate_metric_depth() above, but using a
    # detected wheel's pixel diameter (instead of the plate's pixel width) as the
    # known-size reference.
    import scale_calibration  # Hough-circle + tire-code logic, validated in that module

    h_img, w_img = relative_depth_map.shape
    circles = scale_calibration.detect_wheel_circles(image_bgr)
    if not circles:
        return None, {"status": "skipped_no_wheel_detected"}

    for x, y, r in circles:
        diameter_mm = scale_calibration.GENERIC_TIRE_DIAMETER_MM
        method = "wheel_generic_diameter"
        confidence = "low"
        if ocr_reader is not None:
            parsed, _ = scale_calibration.read_tire_code_near_circle(image_bgr, (x, y, r), ocr_reader)
            if parsed is not None:
                diameter_mm = parsed["diameter_mm"]
                method = "wheel_tire_code_ocr"
                confidence = "medium"

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

        return metric_depth_map, {
            "status": "calibrated",
            "method": method,
            "confidence": confidence,
            "wheel_bbox_px": [float(x - r), float(y - r), float(2 * r), float(2 * r)],
            "assumed_diameter_mm": diameter_mm,
            "focal_length_px": float(focal_length_px),
            "wheel_distance_mm": float(wheel_distance_mm),
            "scale_factor": float(scale),
        }

    return None, {"status": "failed_wheel_depth_lookup"}


def calibrate_metric_depth_tiered(relative_depth_map, image_path, plate_bbox=None,
                                   plate_width_mm=520.0, assumed_hfov_deg=60.0,
                                   ocr_reader=None, metric_depth_processor=None,
                                   metric_depth_model=None, device="cuda"):
    """Never-null metric depth calibration: Tier 1 (plate) -> Tier 2 (wheel/tire)
    -> Tier 3 (metric depth model prior, used directly - no reference object
    needed). Returns (metric_depth_map_or_None, calibration_info); only returns
    None if every tier fails (expected to be rare - Tier 3 succeeds whenever the
    model is loaded and the image is readable, regardless of scene content).

    Tiers 2/3 are skipped gracefully (not an error) if their optional
    dependencies (ocr_reader / metric_depth_processor+model) aren't passed in,
    so this function degrades to a Tier-1-only chain rather than failing to
    import when called without them (e.g. from run_local_pipeline.py without
    the extra models loaded).
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

    # --- Tier 3: metric depth model prior (true last resort) ---
    if metric_depth_processor is not None and metric_depth_model is not None:
        try:
            metric_depth_map = estimate_metric_depth_mm(
                metric_depth_processor, metric_depth_model, image_path, device=device,
            )
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
