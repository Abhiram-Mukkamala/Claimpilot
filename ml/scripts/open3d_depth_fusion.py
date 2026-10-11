"""
T3.4 FALLBACK - Dense point cloud via Open3D depth-map fusion.

Used because pycolmap's PyPI wheels (including pycolmap-cuda12) only
CUDA-accelerate SIFT feature extraction/matching, NOT patch_match_stereo -
that function needs COLMAP's dense MVS module compiled with the CUDA
toolkit from source, which the pip wheel doesn't ship (confirmed by the
runtime error "[mvs.cc:51] Dense stereo reconstruction requires CUDA or
HIP, neither of which is available on your system" even on a T4 GPU).
Building that from source is the same class of fragile multi-dependency
build OpenMVS required, so this fallback avoids it entirely:

  - Depth Anything V2 (already used in photo_pipeline.py) for a per-frame
    monocular depth map of each of T3.3's registered images.
  - T3.3's recovered camera poses (pycolmap Reconstruction) - no new pose
    estimation needed.
  - Open3D's ScalableTSDFVolume to fuse those posed depth maps into one
    dense point cloud.

Monocular relative depth is not metric, so each view's depth map is rescaled
to COLMAP's reconstruction scale using that image's own sparse 3D points
(matching 2D keypoints to the relative-depth value at the same pixel, fitting
a single scale+shift per image via least squares) before fusion.

IMPORTANT scale fix: COLMAP's reconstruction scale here is NOT metric - it's
whatever scale fell out of the synthetic-parallax pixel shifts used in T3.2/
T3.3, which could be anywhere from ~0.01 to ~100+ in arbitrary units. The
first version of this module hardcoded metric-scene TSDF parameters
(voxel_length=0.01, sdf_trunc=0.04, depth_trunc=20.0, i.e. tuned for a
real-world room in meters) which silently discarded every fused point when
the reconstruction's actual scale didn't match those assumptions - fusion
"succeeded" but wrote an empty point cloud with no error. This version
computes the scene's real extent from the sparse point cloud itself
(compute_scene_scale) and derives TSDF parameters proportional to it,
and prints per-view depth-range diagnostics so a repeat of this failure
mode is visible immediately instead of silently producing 0 points.
"""

import numpy as np


def _fit_scale_shift(relative_depth_at_points, colmap_depth_at_points):
    """Fit colmap_depth ~= a * relative_depth + b via least squares.
    Returns (a, b). Falls back to (1.0, 0.0) if there aren't enough points
    or the fit is degenerate.
    """
    rel = np.asarray(relative_depth_at_points, dtype=np.float64)
    col = np.asarray(colmap_depth_at_points, dtype=np.float64)
    if len(rel) < 5:
        return 1.0, 0.0
    A = np.stack([rel, np.ones_like(rel)], axis=1)
    result, *_ = np.linalg.lstsq(A, col, rcond=None)
    a, b = result
    if not np.isfinite(a) or a <= 0:
        return 1.0, 0.0
    return float(a), float(b)


def rescale_relative_depth(relative_depth_map, image_points_2d, colmap_depths):
    """Rescale a relative depth map to COLMAP's reconstruction scale using
    that image's own sparse-point correspondences.

    Args:
        relative_depth_map: HxW array of relative depth values.
        image_points_2d: list of (x, y) pixel coords of this image's
            registered sparse 3D points.
        colmap_depths: matching list of each point's depth in the camera's
            coordinate frame (distance along the camera's viewing axis).

    Returns:
        (rescaled_depth_map, (a, b), num_fit_points) - the rescaled HxW
        array, the fitted scale/shift, and how many correspondences the fit
        used (0 means the original unscaled map was returned - a sign this
        view's depth is unreliable).
    """
    if len(image_points_2d) == 0:
        return relative_depth_map, (1.0, 0.0), 0

    rel_vals = []
    col_vals = []
    for (x, y), d in zip(image_points_2d, colmap_depths):
        yi, xi = int(round(y)), int(round(x))
        if 0 <= yi < relative_depth_map.shape[0] and 0 <= xi < relative_depth_map.shape[1]:
            rel_vals.append(relative_depth_map[yi, xi])
            col_vals.append(d)

    if len(rel_vals) < 5:
        return relative_depth_map, (1.0, 0.0), len(rel_vals)

    a, b = _fit_scale_shift(rel_vals, col_vals)
    return relative_depth_map * a + b, (a, b), len(rel_vals)


def compute_scene_scale(reconstruction):
    """Compute the sparse point cloud's bounding-box diagonal, used as the
    scene's characteristic scale (in COLMAP's arbitrary reconstruction
    units) so TSDF fusion parameters can be derived proportionally instead
    of assuming real-world meters.

    Returns:
        dict with 'diagonal', 'min', 'max' (numpy arrays), or None if the
        reconstruction has no points.
    """
    if reconstruction.num_points3D() == 0:
        return None
    xyz = np.array([p.xyz for p in reconstruction.points3D.values()])
    pmin = xyz.min(axis=0)
    pmax = xyz.max(axis=0)
    diagonal = float(np.linalg.norm(pmax - pmin))
    return {"diagonal": diagonal, "min": pmin, "max": pmax}


def suggest_tsdf_params(scene_scale):
    """Derive voxel_length / sdf_trunc / depth_trunc proportional to the
    scene's real extent (compute_scene_scale's 'diagonal'), instead of
    hardcoded metric-scene defaults that silently zero out fusion when the
    reconstruction isn't in meters.
    """
    diagonal = scene_scale["diagonal"] if scene_scale else 1.0
    if not np.isfinite(diagonal) or diagonal <= 0:
        diagonal = 1.0
    voxel_length = diagonal / 256.0
    sdf_trunc = voxel_length * 5.0
    depth_trunc = diagonal * 3.0
    return {
        "voxel_length": voxel_length,
        "sdf_trunc": sdf_trunc,
        "depth_trunc": depth_trunc,
    }


def fuse_posed_depth_maps(
    rgbd_list, intrinsics, voxel_length=0.01, sdf_trunc=0.04, depth_scale=1.0, depth_trunc=20.0,
    verbose=True,
):
    """Fuse a list of (color, depth, camera_to_world_pose) into one dense
    point cloud using Open3D's TSDF volume.

    Args:
        rgbd_list: list of dicts, each with keys 'color' (HxWx3 uint8),
            'depth' (HxW float32, rescaled to reconstruction units),
            'pose' (4x4 camera-to-world extrinsic matrix).
        intrinsics: open3d.camera.PinholeCameraIntrinsic for all views.
        voxel_length, sdf_trunc, depth_trunc: TSDF fusion parameters -
            use suggest_tsdf_params(compute_scene_scale(reconstruction))
            rather than hardcoding these, since COLMAP's reconstruction
            scale here is arbitrary, not metric.
        depth_scale: divisor Open3D applies to raw depth values; kept at
            1.0 since our depth is already in reconstruction units.
        verbose: print per-view depth-range diagnostics, so an empty
            result is immediately explainable instead of a silent 0.

    Returns:
        open3d.geometry.PointCloud (extracted from the fused TSDF volume).
    """
    import open3d as o3d

    if verbose:
        print(
            f"TSDF params: voxel_length={voxel_length:.6g}, "
            f"sdf_trunc={sdf_trunc:.6g}, depth_trunc={depth_trunc:.6g}"
        )

    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_length,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
    )

    for i, item in enumerate(rgbd_list):
        depth = item["depth"].astype(np.float32)
        # Clip non-finite / non-positive depth to 0 (Open3D treats 0 as invalid).
        depth = np.where(np.isfinite(depth) & (depth > 0), depth, 0.0).astype(np.float32)

        if verbose:
            valid = depth[depth > 0]
            in_range = valid[valid < depth_trunc]
            print(
                f"  view {i}: depth valid={valid.size}/{depth.size}, "
                f"range=[{valid.min() if valid.size else float('nan'):.4g}, "
                f"{valid.max() if valid.size else float('nan'):.4g}], "
                f"within depth_trunc={in_range.size}"
            )

        color_o3d = o3d.geometry.Image(np.ascontiguousarray(item["color"]))
        depth_o3d = o3d.geometry.Image(np.ascontiguousarray(depth))
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d,
            depth_o3d,
            depth_scale=depth_scale,
            depth_trunc=depth_trunc,
            convert_rgb_to_intensity=False,
        )
        # Open3D wants world-to-camera (extrinsic); invert the camera-to-world pose.
        extrinsic = np.linalg.inv(item["pose"])
        volume.integrate(rgbd, intrinsics, extrinsic)

    pcd = volume.extract_point_cloud()
    if verbose:
        print(f"Fused point cloud: {len(pcd.points)} points")
    return pcd

