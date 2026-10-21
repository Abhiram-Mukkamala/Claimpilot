"""
2D scale calibration helpers for the ClaimPilot photo vision pipeline.

Ported from the v3 ``pipeline/scale_calibration.py`` module. Only the pure
2D / OpenCV pieces are kept here, so Tier 2 (wheel / tire) calibration works
without ``pycolmap``, ``open3d`` or any COLMAP reconstruction state. The
3D-only orchestration from v3 (mesh raycasting, COLMAP images) is intentionally
not ported; if it is ever needed it must be imported lazily inside the function
that uses it.

Calibration tiers (highest confidence first):

TIER 1 - License plate (~520 mm standard width).
TIER 2 - Wheel / tire.
         2a. Tire sidewall size code (e.g. "205/55R16") read via OCR. ISO 4000
             gives the exact overall tire diameter by formula.
         2b. If a wheel is found but no code can be read, fall back to a
             generic passenger-tire diameter (~660 mm), flagged low confidence.
TIER 3 - Metric monocular depth prior (Depth-Anything-V2 metric checkpoint).
         Lowest confidence, no reference object needed.

Every calibration result carries ``status``, ``method`` and ``confidence`` so
consumers can see HOW a measurement was calibrated.
"""

import math
import re

import numpy as np

# Tier identifiers used in calibration dicts ("tier" key).
TIER_1_PLATE = "tier_1_plate"
TIER_2_WHEEL = "tier_2_wheel"
TIER_3_FALLBACK = "tier_3_metric_depth_prior"

TIRE_CODE_REGEX = re.compile(r"(\d{3})\s*/\s*(\d{2})\s*R\s*(\d{2})", re.IGNORECASE)
GENERIC_TIRE_DIAMETER_MM = 660.0  # typical passenger-car overall tire diameter


def tire_code_to_diameter_mm(section_width_mm, aspect_ratio_pct, rim_diameter_in):
    """ISO 4000 tire sizing formula: overall diameter = rim diameter +
    2 x sidewall height, where sidewall height = section width x aspect ratio.
    """
    sidewall_height_mm = section_width_mm * (aspect_ratio_pct / 100.0)
    return rim_diameter_in * 25.4 + 2 * sidewall_height_mm


def parse_tire_code(text):
    """Parse a tire size code like '205/55R16' out of an OCR text string.
    Returns a dict with the parsed components and computed diameter, or
    None if the text doesn't contain a recognizable code.
    """
    if not text:
        return None
    match = TIRE_CODE_REGEX.search(text.replace(" ", ""))
    if not match:
        return None
    width, ratio, rim = (int(g) for g in match.groups())
    # Sanity bounds - reject OCR noise that matches the regex shape but isn't a
    # plausible passenger-vehicle tire size.
    if not (115 <= width <= 335 and 25 <= ratio <= 85 and 12 <= rim <= 24):
        return None
    return {
        "section_width_mm": width,
        "aspect_ratio_pct": ratio,
        "rim_diameter_in": rim,
        "diameter_mm": tire_code_to_diameter_mm(width, ratio, rim),
    }


def detect_wheel_circles(image_bgr, min_radius_frac=0.04, max_radius_frac=0.25):
    """Hough circle transform to locate candidate wheels. Generic, untrained.
    Returns a list of (x, y, r) in pixels, largest first, or [] if none found.
    """
    import cv2

    h, w = image_bgr.shape[:2]
    min_dim = min(h, w)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_dim * 0.2,
        param1=100,
        param2=40,
        minRadius=int(min_dim * min_radius_frac),
        maxRadius=int(min_dim * max_radius_frac),
    )
    if circles is None:
        return []
    circles = sorted(circles[0], key=lambda c: -c[2])  # largest radius first
    return [(float(x), float(y), float(r)) for x, y, r in circles]


def detect_wheel_rim_circle(image_bgr, min_radius_frac=0.04, max_radius_frac=0.25):
    """Return the single most likely wheel circle as (x, y, r), or None."""
    circles = detect_wheel_circles(
        image_bgr, min_radius_frac=min_radius_frac, max_radius_frac=max_radius_frac
    )
    return circles[0] if circles else None


def read_tire_code_near_circle(image_bgr, circle, ocr_reader):
    """Crop around a detected wheel circle and OCR it for a tire size code.
    ocr_reader: an easyocr.Reader instance (passed in so it is loaded once).
    Returns (parsed_code_dict_or_None, ocr_confidence).
    """
    x, y, r = circle
    h, w = image_bgr.shape[:2]
    x0, y0 = max(0, int(x - r)), max(0, int(y - r))
    x1, y1 = min(w, int(x + r)), min(h, int(y + r))
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return None, 0.0

    for _, text, conf in ocr_reader.readtext(crop):
        parsed = parse_tire_code(text)
        if parsed is not None:
            return parsed, float(conf)
    return None, 0.0


def read_tire_code(image_bgr, circle=None, ocr_reader=None):
    """Read a tire size code from a photo.

    OCR is optional: when ``ocr_reader`` is None (easyocr not installed) this
    returns None and callers fall back to the generic tire diameter (Tier 2b).
    If ``circle`` is None the best wheel circle is detected first.
    Returns the parsed code dict (see ``parse_tire_code``) or None.
    """
    if ocr_reader is None:
        return None
    if circle is None:
        circle = detect_wheel_rim_circle(image_bgr)
        if circle is None:
            return None
    try:
        parsed, _ = read_tire_code_near_circle(image_bgr, circle, ocr_reader)
    except Exception:
        return None
    return parsed


def estimate_camera_intrinsics(image_path, image_width_px, image_height_px=None,
                               assumed_hfov_deg=60.0):
    """Estimate pinhole intrinsics for a photo.

    Prefers EXIF ``FocalLengthIn35mmFilm`` (defined relative to the 36 mm wide
    full-frame sensor: f_px = width_px * f35 / 36); otherwise assumes a
    horizontal field of view. Returns a dict with ``fx``, ``fy``, ``cx``,
    ``cy`` and ``method``.
    """
    focal_px, method = None, None
    try:
        from PIL import ExifTags, Image

        img = Image.open(image_path)
        exif_raw = img._getexif()
        if exif_raw:
            tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
            f35 = tag_map.get("FocalLengthIn35mmFilm")
            if f35:
                focal_px = image_width_px * (float(f35) / 36.0)
                method = "exif_35mm_equivalent"
    except Exception:
        pass

    if not focal_px or focal_px <= 0:
        hfov_rad = math.radians(assumed_hfov_deg)
        focal_px = image_width_px / (2 * math.tan(hfov_rad / 2))
        method = f"assumed_hfov_{assumed_hfov_deg}deg"

    height = image_height_px if image_height_px else image_width_px
    return {
        "fx": float(focal_px),
        "fy": float(focal_px),
        "cx": image_width_px / 2.0,
        "cy": height / 2.0,
        "method": method,
    }


def calibrate_from_wheel(relative_depth_map, image_bgr, focal_length_px,
                         ocr_reader=None, patch_radius=3):
    """Tier 2: convert a relative depth map to metric millimetres using a
    detected wheel as the known-size reference (2a: tire code via OCR when a
    reader is supplied, 2b: generic tire diameter otherwise).

    Pure 2D - needs no COLMAP / mesh state. Returns
    (metric_depth_map_or_None, calibration_info).
    """
    h_img, w_img = relative_depth_map.shape
    circles = detect_wheel_circles(image_bgr)
    if not circles:
        return None, {"status": "skipped_no_wheel_detected"}

    for x, y, r in circles:  # largest first, fall through on invalid depth
        diameter_mm = GENERIC_TIRE_DIAMETER_MM
        method = "wheel_generic_diameter"
        confidence = "low"
        if ocr_reader is not None:
            parsed = read_tire_code(image_bgr, (x, y, r), ocr_reader)
            if parsed is not None:
                diameter_mm = parsed["diameter_mm"]
                method = "wheel_tire_code_ocr"
                confidence = "medium"

        diameter_px = 2 * r
        if diameter_px <= 0 or not focal_length_px:
            continue
        wheel_distance_mm = (diameter_mm * focal_length_px) / diameter_px

        cx, cy = int(x), int(y)
        y0, y1 = max(cy - patch_radius, 0), min(cy + patch_radius + 1, h_img)
        x0, x1 = max(cx - patch_radius, 0), min(cx + patch_radius + 1, w_img)
        if y1 <= y0 or x1 <= x0:
            continue
        relative_value_at_wheel = float(np.median(relative_depth_map[y0:y1, x0:x1]))
        if relative_value_at_wheel <= 0:
            continue

        scale = wheel_distance_mm / relative_value_at_wheel
        return relative_depth_map * scale, {
            "status": "calibrated",
            "tier": TIER_2_WHEEL,
            "method": method,
            "confidence": confidence,
            "wheel_bbox_px": [float(x - r), float(y - r), float(2 * r), float(2 * r)],
            "assumed_diameter_mm": float(diameter_mm),
            "focal_length_px": float(focal_length_px),
            "wheel_distance_mm": float(wheel_distance_mm),
            "scale_factor": float(scale),
        }

    return None, {"status": "failed_wheel_depth_lookup"}
