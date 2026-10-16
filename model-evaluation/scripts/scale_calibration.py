"""
Scale calibration: converts T3.3's arbitrary COLMAP reconstruction units to
real-world millimeters, with a priority-ordered fallback chain so a null
result is no longer possible (previously: plate-or-null, a single point of
failure that fails exactly when it matters most - a damaged or unphotographed
plate on 99% of real claims).

TIER 1 - License plate (highest confidence, ~520mm standard width).
         Fails when the plate is damaged, dirty, unphotographed, or at an
         angle the Haar cascade can't match.

TIER 2 - Wheel / tire. Wheels are visible in nearly every vehicle photo and
         are almost never the claimed damage (unlike the plate, which the
         claim might specifically be about). Two confidence levels within
         this tier:
           2a. Tire sidewall size code (e.g. "205/55R16") read via OCR -
               ISO 4000 tire sizing is a worldwide standard: the code alone
               gives the EXACT real-world overall tire diameter by formula,
               no lookup table needed. This is a real, productized computer-
               vision technique (tire sidewall OCR), not a novel idea - see
               module docstring note below.
           2b. If a wheel is located (Hough circle transform) but its code
               can't be read, fall back to a generic average passenger-tire
               diameter (~660mm) - lower confidence, explicitly flagged as
               such, but still a real number instead of null.

TIER 3 - Metric monocular depth model prior (Depth-Anything-V2's metric-
         finetuned checkpoint, NOT the relative checkpoint used elsewhere in
         this project). This is the true last resort and is why null should
         now be essentially unreachable: instead of needing an object of
         KNOWN real-world size in the scene, this tier trusts a model that
         estimates ABSOLUTE depth directly (trained on real metric depth
         datasets, e.g. KITTI), and fits COLMAP's reconstruction-unit depth
         against it at several sparse points to recover a scale factor - the
         same scale-fit idea already used in open3d_depth_fusion.py, just
         with a metric depth source instead of a relative one. This is
         explicitly the lowest-confidence tier: a monocular metric depth
         estimate is a learned prior about typical scene geometry, not a
         measurement, and should be treated as order-of-magnitude, not
         precise. It is still strictly better than null for a field
         ("skip this measurement entirely") that previously meant "we have
         no answer" for the majority of real claim photos.

Every tier returns a result with a 'status' and 'confidence' field so
downstream consumers can see HOW a measurement was calibrated, not just
whether it was - 'calibrated_via_plate' carries far more trust than
'calibrated_via_metric_depth_prior', and both are distinguishable from the
true-failure case 'skipped_no_reference_found' (expected to be rare now).
"""

import re

import numpy as np

# ---------------------------------------------------------------------------
# Tier 2: wheel / tire
# ---------------------------------------------------------------------------

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
    match = TIRE_CODE_REGEX.search(text.replace(" ", ""))
    if not match:
        return None
    width, ratio, rim = (int(g) for g in match.groups())
    # Sanity bounds - reject OCR noise that happens to match the regex shape
    # but isn't a plausible passenger-vehicle tire size.
    if not (115 <= width <= 335 and 25 <= ratio <= 85 and 12 <= rim <= 24):
        return None
    return {
        "section_width_mm": width,
        "aspect_ratio_pct": ratio,
        "rim_diameter_in": rim,
        "diameter_mm": tire_code_to_diameter_mm(width, ratio, rim),
    }


def detect_wheel_circles(image_bgr, min_radius_frac=0.04, max_radius_frac=0.25):
    """Hough circle transform to locate candidate wheels. Generic, untrained -
    no model needed, works on the classical observation that a wheel/tire
    projects as a roughly circular dark region. Returns a list of (x, y, r)
    in pixels, largest first, or an empty list if none found.
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
    circles = circles[0]
    circles = sorted(circles, key=lambda c: -c[2])  # largest radius first
    return [(float(x), float(y), float(r)) for x, y, r in circles]


def read_tire_code_near_circle(image_bgr, circle, ocr_reader):
    """Crop around a detected wheel circle and OCR it for a tire size code.
    ocr_reader: an easyocr.Reader instance (passed in so it's loaded once,
    not per-call - model loading is the expensive part).
    Returns (parsed_code_dict_or_None, ocr_confidence).
    """
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


def calibrate_scale_from_wheel(scene, camera, pose_cam_to_world, image_bgr, ocr_reader=None):
    """Tier 2: locate a wheel, try to read its exact tire code (2a), fall
    back to a generic tire diameter if the code can't be read (2b). Either
    way, raycast the wheel's top/bottom pixels into the mesh to get the
    reconstruction-unit distance, then divide the (known or assumed)
    real-world diameter by it.
    """
    import mesh_measurement  # reuses raycast_pixels_to_3d from T4.2

    circles = detect_wheel_circles(image_bgr)
    if not circles:
        return {"status": "skipped_no_wheel_detected", "mm_per_unit": None, "confidence": None}

    for x, y, r in circles:  # try largest first, fall through on raycast miss
        diameter_mm = GENERIC_TIRE_DIAMETER_MM
        method = "generic_tire_diameter"
        confidence = "low"

        if ocr_reader is not None:
            parsed, ocr_conf = read_tire_code_near_circle(image_bgr, (x, y, r), ocr_reader)
            if parsed is not None:
                diameter_mm = parsed["diameter_mm"]
                method = "tire_code_ocr"
                confidence = "medium"

        top_px = np.array([[x, y - r]])
        bottom_px = np.array([[x, y + r]])
        top_hit, top_mask = mesh_measurement.raycast_pixels_to_3d(
            scene, camera, pose_cam_to_world, top_px
        )
        bottom_hit, bottom_mask = mesh_measurement.raycast_pixels_to_3d(
            scene, camera, pose_cam_to_world, bottom_px
        )
        if not (len(top_mask) and top_mask[0] and len(bottom_mask) and bottom_mask[0]):
            continue  # this circle's top/bottom missed the mesh; try the next one

        recon_distance = float(np.linalg.norm(top_hit[0] - bottom_hit[0]))
        if recon_distance <= 0:
            continue

        return {
            "status": "calibrated",
            "method": method,
            "confidence": confidence,
            "mm_per_unit": diameter_mm / recon_distance,
            "wheel_bbox_px": [float(x - r), float(y - r), float(2 * r), float(2 * r)],
            "assumed_diameter_mm": diameter_mm,
        }

    return {"status": "failed_wheel_raycast", "mm_per_unit": None, "confidence": None}


# ---------------------------------------------------------------------------
# Tier 3: metric depth model prior (true last resort - should always succeed)
# ---------------------------------------------------------------------------

_METRIC_DEPTH_MODEL_ID = "depth-anything/Depth-Anything-V2-Metric-Outdoor-Base-hf"


def load_metric_depth_model(model_id=_METRIC_DEPTH_MODEL_ID, device="cuda"):
    """Loads Depth-Anything-V2's METRIC-finetuned checkpoint (NOT the
    relative-depth checkpoint used elsewhere in this project for
    photo_pipeline.py / T3.4's dense fallback - a different model, trained
    to output absolute depth). Same transformers API family
    (AutoImageProcessor / AutoModelForDepthEstimation) as the relative model,
    confirmed against the model card rather than assumed.

    UNIT CAVEAT: the model card does not explicitly state output units.
    Virtual-KITTI (its outdoor fine-tuning dataset) ground truth is in
    meters, so this module treats raw output as meters and converts to mm
    - but this is inference from the training dataset's convention, not a
    confirmed spec, consistent with how this tier is the lowest-confidence
    one in the chain.
    """
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id).to(device)
    model.eval()
    return processor, model


def estimate_metric_depth_map(processor, model, image_pil, device="cuda"):
    """Returns an HxW numpy array of estimated depth in millimeters (see
    UNIT CAVEAT in load_metric_depth_model)."""
    import torch
    import torch.nn.functional as F

    inputs = processor(images=image_pil, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    predicted = outputs.predicted_depth  # (1, h', w') per the model card

    resized = F.interpolate(
        predicted.unsqueeze(1),
        size=image_pil.size[::-1],
        mode="bicubic",
        align_corners=False,
    )
    depth_m = resized.squeeze().detach().cpu().numpy()
    return depth_m * 1000.0  # meters -> mm


def calibrate_scale_from_metric_depth_prior(
    scene, camera, pose_cam_to_world, image_bgr, processor, model, device="cuda",
    num_sample_points=200,
):
    """Tier 3: fit reconstruction-units -> mm using a metric depth model's
    own absolute depth estimate as the 'known' reference, instead of an
    object of known real-world size. Samples random mesh-hit pixels, compares
    the model's metric depth at each to COLMAP's camera-space depth (in
    reconstruction units) at the same pixel, and takes the MEDIAN ratio
    (robust to individual outlier pixels, and correctly zero-intercept since
    both quantities measure the same physical distance in different units -
    unlike T3.4's relative-depth fit, which needed a shift term because
    relative depth is affine-, not just scale-, ambiguous).
    """
    import cv2
    from PIL import Image
    import mesh_measurement

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image_pil = Image.fromarray(image_rgb)
    metric_depth_mm_map = estimate_metric_depth_map(processor, model, image_pil, device=device)

    h, w = image_bgr.shape[:2]
    rng = np.random.default_rng(0)
    sample_x = rng.integers(0, w, size=num_sample_points)
    sample_y = rng.integers(0, h, size=num_sample_points)
    pixel_xy = np.stack([sample_x, sample_y], axis=1).astype(np.float64)

    hit_points, hit_mask = mesh_measurement.raycast_pixels_to_3d(
        scene, camera, pose_cam_to_world, pixel_xy
    )
    if hit_mask.sum() < 10:
        return {
            "status": "failed_insufficient_mesh_hits",
            "mm_per_unit": None,
            "confidence": None,
        }

    hit_pixels = pixel_xy[hit_mask]
    cam_origin = pose_cam_to_world[:3, 3]
    recon_depth_units = np.linalg.norm(hit_points - cam_origin, axis=1)

    model_depth_mm = metric_depth_mm_map[
        hit_pixels[:, 1].astype(int), hit_pixels[:, 0].astype(int)
    ]

    valid = (recon_depth_units > 1e-6) & np.isfinite(model_depth_mm) & (model_depth_mm > 0)
    if valid.sum() < 10:
        return {
            "status": "failed_insufficient_valid_samples",
            "mm_per_unit": None,
            "confidence": None,
        }

    ratios = model_depth_mm[valid] / recon_depth_units[valid]
    mm_per_unit = float(np.median(ratios))
    spread = float(np.std(ratios) / (np.median(ratios) + 1e-9))

    return {
        "status": "calibrated",
        "method": "metric_depth_prior",
        "confidence": "low",
        "mm_per_unit": mm_per_unit,
        "num_samples_used": int(valid.sum()),
        "relative_spread": spread,  # high spread = model's prior disagrees with itself across the scene; treat mm_per_unit with extra caution if this is large (e.g. > 0.5)
        "note": (
            "Model-estimated absolute scale (Depth-Anything-V2 metric checkpoint), "
            "not a measured reference object. Treat as order-of-magnitude, not precise."
        ),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def calibrate_scale(
    scene,
    reconstruction,
    image_dir,
    plate_calibrate_fn,
    ocr_reader=None,
    metric_depth_processor=None,
    metric_depth_model=None,
    device="cuda",
):
    """Tries Tier 1 (plate) -> Tier 2 (wheel/tire) -> Tier 3 (metric depth
    prior) in order against every registered frame, returning the first
    success. Only returns a null mm_per_unit if every tier fails on every
    frame - expected to be rare now that Tier 3 exists, versus the previous
    plate-or-null design where it was the common case.

    Args:
        plate_calibrate_fn: mesh_measurement.calibrate_scale_from_plate
            (passed in rather than imported, to avoid a circular import -
            this module is meant to be called FROM mesh_measurement-adjacent
            code, not the other way around).
        ocr_reader: optional easyocr.Reader - Tier 2a (exact tire code) is
            skipped (falls through to 2b, generic diameter) if not provided.
        metric_depth_processor/model: optional, from load_metric_depth_model()
            - Tier 3 is skipped entirely if not provided (so this module
            degrades gracefully to a Tier-1/2-only chain if the metric model
            isn't loaded, rather than failing to import).
    """
    import pathlib
    import cv2

    import mesh_measurement

    image_dir = pathlib.Path(image_dir)

    # --- Tier 1: plate (existing implementation, tried across all frames) ---
    result = plate_calibrate_fn(scene, reconstruction, image_dir)
    if result.get("status") == "calibrated":
        result.setdefault("confidence", "high")
        result.setdefault("method", "plate")
        return result

    # --- Tier 2: wheel / tire (tried across all frames) ---
    for image_id, image in reconstruction.images.items():
        img_path = image_dir / image.name
        if not img_path.exists():
            continue
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        camera = reconstruction.cameras[image.camera_id]
        # Build the pose inline (avoids depending on an internal helper name
        # that might not exist in every mesh_measurement.py version).
        cam_from_world = image.cam_from_world()
        R_cw = cam_from_world.rotation.matrix()
        t_cw = np.asarray(cam_from_world.translation)
        R_wc = R_cw.T
        t_wc = -R_wc @ t_cw
        pose_cam_to_world = np.eye(4)
        pose_cam_to_world[:3, :3] = R_wc
        pose_cam_to_world[:3, 3] = t_wc

        wheel_result = calibrate_scale_from_wheel(
            scene, camera, pose_cam_to_world, img_bgr, ocr_reader=ocr_reader
        )
        if wheel_result.get("status") == "calibrated":
            wheel_result["frame_used"] = image.name
            return wheel_result

    # --- Tier 3: metric depth prior (true last resort) ---
    if metric_depth_processor is not None and metric_depth_model is not None:
        for image_id, image in reconstruction.images.items():
            img_path = image_dir / image.name
            if not img_path.exists():
                continue
            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                continue

            camera = reconstruction.cameras[image.camera_id]
            cam_from_world = image.cam_from_world()
            R_cw = cam_from_world.rotation.matrix()
            t_cw = np.asarray(cam_from_world.translation)
            R_wc = R_cw.T
            t_wc = -R_wc @ t_cw
            pose_cam_to_world = np.eye(4)
            pose_cam_to_world[:3, :3] = R_wc
            pose_cam_to_world[:3, 3] = t_wc

            try:
                depth_result = calibrate_scale_from_metric_depth_prior(
                    scene, camera, pose_cam_to_world, img_bgr,
                    metric_depth_processor, metric_depth_model, device=device,
                )
            except Exception as e:
                depth_result = {"status": "failed", "reason": str(e)}

            if depth_result.get("status") == "calibrated":
                depth_result["frame_used"] = image.name
                return depth_result

    return {
        "status": "skipped_no_reference_found",
        "mm_per_unit": None,
        "confidence": None,
    }
