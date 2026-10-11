
"""
Depth-based synthetic parallax video generator.

T3.2's original create_synthetic_video() only applied pixel jitter (+/-20px) and
mild scale (0.97-1.03) to a static image. That has NO real 3D structure: every
pixel moves by (approximately) the same global transform, so COLMAP's two-view
geometry / triangulation has nothing to work with - there's no parallax
(near objects should appear to move more than far ones under camera translation,
and a pure affine jitter can't produce that). This is the most likely reason
T3.3's incremental_mapping returned ~0 registered 3D points even after relaxing
mapper thresholds.

This module instead uses a monocular depth map (from T2.1 - depth_estimation.py)
to do depth-dependent horizontal view synthesis: for a simulated lateral camera
sweep, pixels at small depth (near camera) are shifted further than pixels at
large depth (far from camera), which is the actual signature of parallax under
camera translation. This is still synthetic (single real viewpoint, monocular
depth, occlusion holes filled by border replication rather than true
disocclusion inpainting), but it gives COLMAP genuine per-pixel disparity
instead of none, so feature matches across frames can actually be triangulated.

Convention: `depth_map` values are assumed "disparity-like" (LARGER = NEARER),
which matches Depth Anything V2's typical raw output. If your depth model uses
the opposite convention (larger = farther), pass invert_depth=True.
"""

import pathlib

import cv2
import numpy as np


def create_parallax_synthetic_video(
    image_path,
    depth_map,
    out_dir,
    n_frames=15,
    max_shift_frac=0.05,
    invert_depth=False,
):
    """Generate a sequence of frames simulating a lateral camera sweep, using
    per-pixel depth to create real parallax (near objects shift more than far ones).

    Args:
        image_path: path to the single real source image.
        depth_map: 2D numpy array (any resolution; will be resized to match image),
            disparity-like convention (larger = nearer) unless invert_depth=True.
        out_dir: directory to write frame_000.jpg, frame_001.jpg, ...
        n_frames: number of synthetic frames to generate.
        max_shift_frac: max horizontal shift for the nearest pixels, as a
            fraction of image width, at the sweep's extremes.
        invert_depth: set True if your depth map uses larger=farther instead.

    Returns:
        list of output frame paths, in order along the simulated camera sweep.
    """
    image_path = pathlib.Path(image_path)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    h, w = img.shape[:2]

    d = cv2.resize(depth_map.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    if invert_depth:
        d = d.max() - d
    d_min, d_max = float(d.min()), float(d.max())
    if d_max - d_min < 1e-6:
        d_norm = np.zeros_like(d)
    else:
        d_norm = (d - d_min) / (d_max - d_min)

    max_shift_px = max_shift_frac * w
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    camera_offsets = np.linspace(-1.0, 1.0, n_frames)
    out_paths = []
    for i, t in enumerate(camera_offsets):
        shift = t * max_shift_px * d_norm
        map_x = (xs + shift).astype(np.float32)
        map_y = ys.astype(np.float32)
        warped = cv2.remap(
            img, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        out_path = out_dir / f"frame_{i:03d}.jpg"
        cv2.imwrite(str(out_path), warped)
        out_paths.append(out_path)

    return {
        "frame_paths": out_paths,
        "depth_range": (d_min, d_max),
        "max_shift_px": max_shift_px,
        "degenerate_depth": bool(d_max - d_min < 1e-6),
    }
