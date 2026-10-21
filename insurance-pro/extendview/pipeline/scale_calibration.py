"""
Scale calibration: 2D wheel / tire Hough-circle & ISO 4000 tire-code helpers
plus 3D mesh calibration fallbacks for ClaimPilot.
"""

import re
import numpy as np

TIRE_CODE_REGEX = re.compile(r"(\d{3})\s*/\s*(\d{2})\s*R\s*(\d{2})", re.IGNORECASE)
GENERIC_TIRE_DIAMETER_MM = 660.0  # typical passenger-car overall tire diameter


def tire_code_to_diameter_mm(section_width_mm, aspect_ratio_pct, rim_diameter_in):
    """ISO 4000 tire sizing formula: overall diameter = rim diameter + 2 x sidewall height."""
    sidewall_height_mm = section_width_mm * (aspect_ratio_pct / 100.0)
    return rim_diameter_in * 25.4 + 2 * sidewall_height_mm


def parse_tire_code(text):
    """Parse a tire size code like '205/55R16' out of an OCR text string."""
    match = TIRE_CODE_REGEX.search(text.replace(" ", ""))
    if not match:
        return None
    width, ratio, rim = (int(g) for g in match.groups())
    if not (115 <= width <= 335 and 25 <= ratio <= 85 and 12 <= rim <= 24):
        return None
    return {
        "section_width_mm": width,
        "aspect_ratio_pct": ratio,
        "rim_diameter_in": rim,
        "diameter_mm": tire_code_to_diameter_mm(width, ratio, rim),
    }


def detect_wheel_circles(image_bgr, min_radius_frac=0.04, max_radius_frac=0.25):
    """Hough circle transform to locate candidate wheels in 2D vehicle photos."""
    import cv2

    h, w = image_bgr.shape[:2]
    min_dim = min(h, w)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(10.0, min_dim * 0.2),
        param1=100,
        param2=40,
        minRadius=max(5, int(min_dim * min_radius_frac)),
        maxRadius=max(10, int(min_dim * max_radius_frac)),
    )
    if circles is None:
        return []
    circles = circles[0]
    circles = sorted(circles, key=lambda c: -c[2])  # largest radius first
    return [(float(x), float(y), float(r)) for x, y, r in circles]


def read_tire_code_near_circle(image_bgr, circle, ocr_reader):
    """Crop around a detected wheel circle and OCR it for a tire size code."""
    x, y, r = circle
    h, w = image_bgr.shape[:2]
    x0, y0 = max(0, int(x - r)), max(0, int(y - r))
    x1, y1 = min(w, int(x + r)), min(h, int(y + r))
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return None, 0.0

    results = ocr_reader.readtext(crop)
    for _, text, conf in results:
        parsed = parse_tire_code(text)
        if parsed is not None:
            return parsed, float(conf)
    return None, 0.0
