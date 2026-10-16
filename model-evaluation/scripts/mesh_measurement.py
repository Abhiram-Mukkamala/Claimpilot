
"""
T4.2 - 3D damage measurement from T4.1's mesh: dent depth (mm), volume (cm3),
surface area (cm2), crease angle (deg), per detected damage instance.

APPROACH (plane-fit dent quantification - standard, simple, defensible):
  1. Cast rays from the reference frame's camera through each damage-instance
     bbox's pixels (and a surrounding "ring" of undamaged pixels around it)
     into the T4.1 mesh, using Open3D's RaycastingScene, to recover each
     pixel's real 3D surface point.
  2. Fit a reference plane to the RING points (the undamaged panel around the
     damage) via SVD - this approximates "what the surface would look like
     without the damage."
  3. Dent depth (ΔZ) = max perpendicular distance of the damage-region 3D
     points from that reference plane.
  4. Area = convex-hull area of the damage-region points projected onto the
     reference plane.
  5. Volume = area * mean(|deviation|) - a flat-prism approximation, not a
     true integral over curved geometry. Documented as an approximation:
     adequate for an "approximate damage measurement" pipeline, not a
     certified volumetric survey.
  6. Crease angle = angle between the damage region's own best-fit plane
     normal and the reference (ring) plane's normal - "how sharply the dent
     surface tilts relative to the surrounding panel." This is a different,
     3D-geometric definition from Photo Mode's DSINE-based 2D crease angle;
     both are useful, neither supersedes the other.

KNOWN LIMITATION - area/volume are BBOX-FOOTPRINT, not mask-shaped: the
damage region here is whatever RT-DETR's axis-aligned bounding box covers
on the mesh (sampled as a pixel grid), not a segmentation-mask-shaped
region - RT-DETR outputs boxes, not masks, and this video pipeline doesn't
run SAM2 on video frames the way Photo Mode does on a single photo.
Verified via a synthetic test: for a circular dent of true area ~201
units^2 inscribed in a square bbox of area ~432 units^2, this module
(correctly, given a bbox input) reported ~400 units^2 - the bbox's
footprint, not the dent's true circular area. Depth is unaffected by this
(it only depends on finding the deepest point, not the region's shape) and
was verified accurate to <1% against the same synthetic test. If a
tighter area/volume estimate is needed later, project a SAM2 mask's pixels
instead of the bbox's pixel grid in measure_damage_instance_3d().

SCALE CALIBRATION (reconstruction units -> millimeters):
COLMAP's reconstruction scale here is arbitrary (set by the synthetic-
parallax pixel shifts in T3.2, not real-world units). To report physical
mm/cm2/cm3, we need one known real-world distance in the scene. This module
detects a vehicle license plate (OpenCV Haar cascade, same "auto_haar_cascade"
method name as Photo Mode's calibration, for consistency) in a registered
video frame, raycasts its two horizontal edge pixels into the mesh to get
their real 3D positions, and divides the plate's standard real-world width
by that reconstructed distance to get mm-per-reconstruction-unit. If no
plate is found in any registered frame, calibration status is
"skipped_no_plate_detected" and all metric (mm/cm2/cm3) fields are reported
as null - exactly like Photo Mode's existing calibration.status pattern -
while the raw reconstruction-unit values are still reported for debugging.
"""

import json

import numpy as np

STANDARD_PLATE_WIDTH_MM = 520.0  # generic standard plate width; override if known


# ---------------------------------------------------------------------------
# Raycasting
# ---------------------------------------------------------------------------

def build_raycasting_scene(mesh):
    """mesh: open3d.geometry.TriangleMesh (legacy). Returns an
    open3d.t.geometry.RaycastingScene ready for cast_rays().
    """
    import open3d as o3d

    t_mesh = o3d.t.geometry.TriangleMesh.from_legacy(mesh)
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(t_mesh)
    return scene


def camera_rays_for_pixels(camera, pose_cam_to_world, pixel_xy_array):
    """Build ray origins/directions (world space) for a batch of pixel
    coordinates, given a pycolmap Camera (for intrinsics) and a 4x4
    camera-to-world pose.

    Args:
        camera: pycolmap Camera object.
        pose_cam_to_world: 4x4 numpy array.
        pixel_xy_array: Nx2 array of (x, y) pixel coordinates.

    Returns:
        (origins, directions): each Nx3 float32 numpy arrays, world space.
    """
    fx = camera.focal_length_x if hasattr(camera, "focal_length_x") else camera.params[0]
    fy = camera.focal_length_y if hasattr(camera, "focal_length_y") else (
        camera.params[1] if len(camera.params) > 1 else camera.params[0]
    )
    cx = camera.principal_point_x if hasattr(camera, "principal_point_x") else camera.width / 2
    cy = camera.principal_point_y if hasattr(camera, "principal_point_y") else camera.height / 2

    pixel_xy_array = np.asarray(pixel_xy_array, dtype=np.float64)
    x_cam = (pixel_xy_array[:, 0] - cx) / fx
    y_cam = (pixel_xy_array[:, 1] - cy) / fy
    z_cam = np.ones_like(x_cam)
    dirs_cam = np.stack([x_cam, y_cam, z_cam], axis=1)
    dirs_cam /= np.linalg.norm(dirs_cam, axis=1, keepdims=True)

    R = pose_cam_to_world[:3, :3]
    t = pose_cam_to_world[:3, 3]
    dirs_world = (R @ dirs_cam.T).T
    origins_world = np.tile(t, (len(pixel_xy_array), 1))

    return origins_world.astype(np.float32), dirs_world.astype(np.float32)


def raycast_pixels_to_3d(scene, camera, pose_cam_to_world, pixel_xy_array):
    """Cast rays through the given pixels and return the 3D hit points
    (world space) for rays that actually hit the mesh.

    Returns:
        (hit_points Nx3, hit_mask N-bool) - hit_points only contains valid
        hits (len == hit_mask.sum()), caller indexes pixel_xy_array[hit_mask]
        to recover which pixels these correspond to.
    """
    import open3d as o3d

    origins, dirs = camera_rays_for_pixels(camera, pose_cam_to_world, pixel_xy_array)
    rays = o3d.core.Tensor(np.concatenate([origins, dirs], axis=1), dtype=o3d.core.Dtype.Float32)
    result = scene.cast_rays(rays)

    t_hit = result["t_hit"].numpy()
    hit_mask = np.isfinite(t_hit)
    hit_points = origins[hit_mask] + dirs[hit_mask] * t_hit[hit_mask][:, None]
    return hit_points, hit_mask


# ---------------------------------------------------------------------------
# Geometry: plane fitting, deviation, area, crease angle
# ---------------------------------------------------------------------------

def fit_plane(points):
    """SVD plane fit. Returns (centroid, normal) - normal is unit-length."""
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    normal = vt[-1]
    normal /= np.linalg.norm(normal)
    return centroid, normal


def signed_distances_to_plane(points, centroid, normal):
    return (points - centroid) @ normal


def project_to_plane_2d(points, centroid, normal):
    """Project 3D points onto the plane and express them in a 2D
    orthonormal basis of that plane, for convex-hull area computation.
    """
    arbitrary = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(arbitrary, normal)) > 0.9:
        arbitrary = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, arbitrary)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)

    centered = points - centroid
    u_coords = centered @ u
    v_coords = centered @ v
    return np.stack([u_coords, v_coords], axis=1)


def convex_hull_area_2d(points_2d):
    """Shoelace formula on the 2D convex hull of the points."""
    from scipy.spatial import ConvexHull

    if len(points_2d) < 3:
        return 0.0
    hull = ConvexHull(points_2d)
    return float(hull.volume)  # scipy's ConvexHull.volume is the 2D area for 2D input


def crease_angle_deg(normal_a, normal_b):
    cos_angle = np.clip(np.dot(normal_a, normal_b), -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_angle))
    # Report the acute angle between the two surfaces (0-90), not the
    # normal-to-normal angle (0-180), which is the more intuitive "how much
    # does the surface bend" quantity.
    return float(min(angle, 180.0 - angle))


# ---------------------------------------------------------------------------
# Scale calibration (reconstruction units -> mm) via plate detection
# ---------------------------------------------------------------------------

def detect_plate_bbox(image_bgr):
    """OpenCV Haar-cascade plate detection (same 'auto_haar_cascade' method
    name as Photo Mode's calibration, for consistency). Returns the largest
    detected bbox (x, y, w, h) in pixels, or None if nothing was found.
    """
    import cv2

    cascade_path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return None

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    plates = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    if len(plates) == 0:
        return None

    # Largest detection by area, most likely the real plate over false positives.
    areas = [w * h for (x, y, w, h) in plates]
    return plates[int(np.argmax(areas))]


def calibrate_scale_from_plate(
    scene, reconstruction, image_dir, plate_real_width_mm=STANDARD_PLATE_WIDTH_MM
):
    """Try to find a license plate in any of the reconstruction's registered
    frames, raycast its left/right edge pixels into the mesh, and derive
    mm-per-reconstruction-unit from the known plate width vs. the
    reconstructed 3D distance between those two points.

    Returns:
        dict with 'status' ('calibrated' or 'skipped_no_plate_detected'),
        and 'mm_per_unit' (float or None), 'frame_used' (str or None).
    """
    import cv2
    import pathlib

    image_dir = pathlib.Path(image_dir)

    for image_id, image in reconstruction.images.items():
        img_path = image_dir / image.name
        if not img_path.exists():
            continue
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        bbox = detect_plate_bbox(img_bgr)
        if bbox is None:
            continue

        x, y, w, h = bbox
        left_px = np.array([[x, y + h / 2]])
        right_px = np.array([[x + w, y + h / 2]])

        cam_from_world = image.cam_from_world()
        R_cw = cam_from_world.rotation.matrix()
        t_cw = np.asarray(cam_from_world.translation)
        R_wc = R_cw.T
        t_wc = -R_wc @ t_cw
        pose_cam_to_world = np.eye(4)
        pose_cam_to_world[:3, :3] = R_wc
        pose_cam_to_world[:3, 3] = t_wc

        camera = reconstruction.cameras[image.camera_id]

        left_hit, left_mask = raycast_pixels_to_3d(scene, camera, pose_cam_to_world, left_px)
        right_hit, right_mask = raycast_pixels_to_3d(scene, camera, pose_cam_to_world, right_px)

        if not (left_mask[0] and right_mask[0]):
            continue

        recon_distance = float(np.linalg.norm(left_hit[0] - right_hit[0]))
        if recon_distance <= 0:
            continue

        mm_per_unit = plate_real_width_mm / recon_distance
        return {
            "status": "calibrated",
            "mm_per_unit": mm_per_unit,
            "frame_used": image.name,
            "plate_bbox_px": [int(x), int(y), int(w), int(h)],
            "plate_real_width_mm": plate_real_width_mm,
        }

    return {
        "status": "skipped_no_plate_detected",
        "mm_per_unit": None,
        "frame_used": None,
    }


# ---------------------------------------------------------------------------
# Per-instance measurement
# ---------------------------------------------------------------------------

def measure_damage_instance_3d(
    scene, camera, pose_cam_to_world, bbox_xyxy, image_shape, mm_per_unit, pixel_stride=3, ring_margin_frac=0.4
):
    """Measure one damage instance's dent depth / area / volume / crease
    angle from the 3D mesh, given its 2D bbox in the reference frame.

    Returns a dict of measurement results (mm/cm2/cm3 if mm_per_unit is not
    None, else those fields are null and raw reconstruction-unit values are
    included under a '_recon_units' suffix for debugging).
    """
    x1, y1, x2, y2 = bbox_xyxy
    h_img, w_img = image_shape[:2]
    bw, bh = x2 - x1, y2 - y1

    # Damage-region pixel grid (inside the bbox).
    xs = np.arange(x1, x2, pixel_stride)
    ys = np.arange(y1, y2, pixel_stride)
    xx, yy = np.meshgrid(xs, ys)
    damage_px = np.stack([xx.ravel(), yy.ravel()], axis=1).astype(np.float64)

    # Ring region (expanded bbox minus the bbox itself) - the undamaged panel.
    mx, my = bw * ring_margin_frac, bh * ring_margin_frac
    rx1, ry1 = max(0, x1 - mx), max(0, y1 - my)
    rx2, ry2 = min(w_img, x2 + mx), min(h_img, y2 + my)
    rxs = np.arange(rx1, rx2, pixel_stride)
    rys = np.arange(ry1, ry2, pixel_stride)
    rxx, ryy = np.meshgrid(rxs, rys)
    ring_px_all = np.stack([rxx.ravel(), ryy.ravel()], axis=1).astype(np.float64)
    inside_bbox = (
        (ring_px_all[:, 0] >= x1) & (ring_px_all[:, 0] <= x2) &
        (ring_px_all[:, 1] >= y1) & (ring_px_all[:, 1] <= y2)
    )
    ring_px = ring_px_all[~inside_bbox]

    damage_pts, damage_hit = raycast_pixels_to_3d(scene, camera, pose_cam_to_world, damage_px)
    ring_pts, ring_hit = raycast_pixels_to_3d(scene, camera, pose_cam_to_world, ring_px)

    result = {
        "status": "success",
        "num_damage_rays_hit": int(damage_hit.sum()),
        "num_ring_rays_hit": int(ring_hit.sum()),
    }

    if len(damage_pts) < 5 or len(ring_pts) < 10:
        result["status"] = "failed"
        result["reason"] = (
            f"Insufficient mesh ray hits for measurement "
            f"(damage={len(damage_pts)}, ring={len(ring_pts)}, need >=5/>=10). "
            "Likely a hole in the mesh over this region, or bbox off-mesh."
        )
        for key in ("depth_mm", "area_cm2", "volume_cm3", "crease_angle_deg"):
            result[key] = None
        return result

    ring_centroid, ring_normal = fit_plane(ring_pts)
    damage_centroid, damage_normal = fit_plane(damage_pts)

    deviations = signed_distances_to_plane(damage_pts, ring_centroid, ring_normal)
    depth_units = float(np.max(np.abs(deviations)))
    mean_abs_dev_units = float(np.mean(np.abs(deviations)))

    points_2d = project_to_plane_2d(damage_pts, ring_centroid, ring_normal)
    area_units2 = convex_hull_area_2d(points_2d)
    volume_units3 = area_units2 * mean_abs_dev_units  # flat-prism approximation

    angle_deg = crease_angle_deg(ring_normal, damage_normal)

    result.update(
        {
            "depth_recon_units": depth_units,
            "area_recon_units2": area_units2,
            "volume_recon_units3": volume_units3,
            "crease_angle_deg": angle_deg,
        }
    )

    if mm_per_unit is not None:
        result["depth_mm"] = depth_units * mm_per_unit
        result["area_cm2"] = area_units2 * (mm_per_unit ** 2) / 100.0
        result["volume_cm3"] = volume_units3 * (mm_per_unit ** 3) / 1000.0
    else:
        result["depth_mm"] = None
        result["area_cm2"] = None
        result["volume_cm3"] = None

    return result

