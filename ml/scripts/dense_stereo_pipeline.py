
"""
T3.4 - Dense Multi-View Stereo using pycolmap's native dense reconstruction
(undistort_images -> patch_match_stereo -> stereo_fusion), replacing the
OpenMVS from-source build approach.

IMPORTANT (API version note, same situation as sfm_pipeline.py's T3.3 fix):
pycolmap's dense-reconstruction functions (undistort_images, patch_match_stereo,
stereo_fusion) are NOT reliably documented on pypi.org or colmap.github.io's
pycolmap API reference page at the time this was written - the reference page
only documents Database/Reconstruction/Camera/FeatureExtractor-style classes,
not these pipeline functions. Rather than guess a signature from COLMAP's C++
CLI docs (which don't necessarily match the Python bindings 1:1, as we learned
the hard way with extract_features / sift_options in T3.3), this module:

  1. Introspects the actually-installed pycolmap build at runtime via
     `help()` / `inspect.signature()` and prints what it finds, BEFORE
     attempting any call, so a real signature mismatch shows up as a clear
     printed diagnostic instead of a buried stack trace.
  2. Tries a small set of plausible call styles per function (most-likely
     COLMAP convention first), catching TypeError specifically and moving to
     the next candidate, and only raises once every candidate has been tried
     - with the full list of attempted signatures and the last real error
     message included, so a genuine mismatch is immediately actionable
     (same defensive pattern as sfm_pipeline.py's _set_max_num_features).
"""

import inspect
import json
import pathlib


def print_api_signatures():
    """Print whatever introspectable signature/docstring info is available
    for the three dense-reconstruction functions, on the actually-installed
    pycolmap build. Run this BEFORE run_dense_stereo() so any mismatch
    between what this module assumes and what's really installed is visible
    up front rather than discovered via a TypeError deep in a try/except.
    """
    import pycolmap

    for name in ("undistort_images", "patch_match_stereo", "stereo_fusion"):
        fn = getattr(pycolmap, name, None)
        print(f"--- pycolmap.{name} ---")
        if fn is None:
            print("  NOT FOUND on this pycolmap build.")
            continue
        try:
            print(" ", inspect.signature(fn))
        except (TypeError, ValueError):
            doc = (fn.__doc__ or "").strip().splitlines()
            print("  (signature not introspectable; docstring first lines:)")
            for line in doc[:5]:
                print("   ", line)
        print()


def _try_calls(fn_name, fn, candidates):
    """Try each candidate (args, kwargs) pair against fn in order.
    Returns (success, result_or_None, attempts_log).
    Only TypeError (wrong signature) moves on to the next candidate;
    any other exception (real runtime failure, e.g. CUDA error) is raised
    immediately since retrying with a different signature won't fix it.
    """
    attempts_log = []
    for args, kwargs in candidates:
        try:
            result = fn(*args, **kwargs)
            attempts_log.append((args, kwargs, "OK"))
            return True, result, attempts_log
        except TypeError as e:
            attempts_log.append((args, kwargs, f"TypeError: {e}"))
            continue
    return False, None, attempts_log


def _raise_with_log(fn_name, attempts_log):
    lines = [f"Could not find a working call signature for pycolmap.{fn_name}."]
    lines.append("Attempted signatures (in order):")
    for args, kwargs, status in attempts_log:
        lines.append(f"  args={args}, kwargs={list(kwargs.keys())} -> {status}")
    lines.append(
        "Run print_api_signatures() and inspect the printed signature/docstring "
        "above, then add a matching candidate to dense_stereo_pipeline.py."
    )
    raise RuntimeError("\n".join(lines))


def run_dense_stereo(image_dir, sparse_model_dir, output_dir, max_image_size=1600):
    """Run undistort_images -> patch_match_stereo -> stereo_fusion.

    Args:
        image_dir: directory of the original (distorted) input frames used
            for T3.3's SfM (e.g. the parallax-synthetic frames).
        sparse_model_dir: T3.3's best_model_dir (contains cameras.bin/
            images.bin/points3D.bin).
        output_dir: directory to write the undistorted workspace,
            per-view depth maps, and the final fused dense point cloud into.
        max_image_size: cap on undistorted image dimension, passed through
            if the installed API supports it; ignored otherwise.

    Returns:
        dict of summary stats, also written to output_dir/dense_report.json.
    """
    import pycolmap

    image_dir = pathlib.Path(image_dir)
    sparse_model_dir = pathlib.Path(sparse_model_dir)
    output_dir = pathlib.Path(output_dir)
    workspace_dir = output_dir / "dense_workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    fused_ply = output_dir / "dense_fused.ply"

    # --- Step 0: print real signatures so any mismatch is visible up front ---
    print_api_signatures()

    # --- Step 1: undistort images into the dense workspace ---
    undistort_candidates = [
        (
            (),
            dict(
                output_path=str(workspace_dir),
                input_path=str(sparse_model_dir),
                image_path=str(image_dir),
            ),
        ),
        (
            (),
            dict(
                output_path=str(workspace_dir),
                input_path=str(sparse_model_dir),
                image_path=str(image_dir),
                max_image_size=max_image_size,
            ),
        ),
        (
            (str(image_dir), str(sparse_model_dir), str(workspace_dir)),
            {},
        ),
    ]
    ok, _, log = _try_calls(
        "undistort_images", pycolmap.undistort_images, undistort_candidates
    )
    if not ok:
        _raise_with_log("undistort_images", log)

    # --- Step 2: PatchMatch stereo (per-view depth + normal maps, CUDA) ---
    pms_candidates = [
        ((), dict(workspace_path=str(workspace_dir))),
        ((str(workspace_dir),), {}),
    ]
    ok, _, log = _try_calls(
        "patch_match_stereo", pycolmap.patch_match_stereo, pms_candidates
    )
    if not ok:
        _raise_with_log("patch_match_stereo", log)

    # --- Step 3: Stereo fusion (merge per-view depth maps into one point cloud) ---
    fusion_candidates = [
        ((), dict(workspace_path=str(workspace_dir), output_path=str(fused_ply))),
        ((str(workspace_dir), str(fused_ply)), {}),
    ]
    ok, _, log = _try_calls(
        "stereo_fusion", pycolmap.stereo_fusion, fusion_candidates
    )
    if not ok:
        _raise_with_log("stereo_fusion", log)

    if not fused_ply.exists():
        stats = {
            "status": "failed",
            "reason": "stereo_fusion reported success but no .ply was written",
        }
        with open(output_dir / "dense_report.json", "w") as f:
            json.dump(stats, f, indent=2)
        return stats

    num_dense_points = _count_ply_vertices(fused_ply)

    stats = {
        "status": "success",
        "fused_ply_path": str(fused_ply),
        "num_dense_points": num_dense_points,
        "max_image_size": max_image_size,
    }
    with open(output_dir / "dense_report.json", "w") as f:
        json.dump(stats, f, indent=2)
    return stats


def _count_ply_vertices(ply_path):
    with open(ply_path, "rb") as f:
        header = []
        while True:
            line = f.readline().decode("ascii", errors="ignore").strip()
            header.append(line)
            if line == "end_header":
                break
    for line in header:
        if line.startswith("element vertex"):
            return int(line.split()[-1])
    return 0

