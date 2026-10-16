
"""
T3.3 - Structure-from-Motion pipeline using pycolmap.

IMPORTANT (API version note):
pycolmap's own README/docs (as of the versions indexed by PyPI/colmap.github.io at
the time this was written) show feature extraction called as:

    sift_options = pycolmap.SiftExtractionOptions()
    pycolmap.extract_features(database_path, image_dir, sift_options=sift_options)

However, the pycolmap build actually installed via `pip install pycolmap-cuda12`
on Colab (late 2025 / 2026 wheels) exposes a DIFFERENT signature. The real
TypeError raised at runtime revealed the true signature:

    extract_features(database_path, image_path, image_names=[],
                      camera_mode=CameraMode.AUTO, reader_options=ImageReaderOptions(),
                      extraction_options=FeatureExtractionOptions(),
                      device=Device.auto, cancellation_token=None) -> None

i.e. the kwarg is `extraction_options` (not `sift_options`) and the class is
`pycolmap.FeatureExtractionOptions` (not `pycolmap.SiftExtractionOptions`).
This module uses the verified, error-message-confirmed API, and sets
`max_num_features` defensively via hasattr() checks since the exact attribute
path on the renamed class isn't independently documented anywhere we could
verify - if neither location exists, pycolmap's own default is left in place
rather than guessing a third time.
"""

import json
import pathlib

import pycolmap


def _set_max_num_features(extraction_options, max_num_features):
    """Best-effort, defensive assignment of max_num_features.

    Tries the flat attribute first (most likely location based on the
    error message's printed repr, which showed max_num_features as a
    top-level field of the options object). Falls back to a nested
    `.sift.max_num_features` in case the installed version structures
    it that way instead. If neither exists, leaves pycolmap's built-in
    default untouched rather than raising or silently doing nothing
    unexplained.
    """
    if hasattr(extraction_options, "max_num_features"):
        extraction_options.max_num_features = max_num_features
        return "max_num_features"
    if hasattr(extraction_options, "sift") and hasattr(
        extraction_options.sift, "max_num_features"
    ):
        extraction_options.sift.max_num_features = max_num_features
        return "sift.max_num_features"
    return None


def _compute_mean_track_length(reconstruction):
    if reconstruction.num_points3D() == 0:
        return 0.0
    total_track_len = 0
    for point3D in reconstruction.points3D.values():
        total_track_len += point3D.track.length()
    return total_track_len / reconstruction.num_points3D()


def _compute_mean_reprojection_error(reconstruction):
    if reconstruction.num_points3D() == 0:
        return float("nan")
    errors = [point3D.error for point3D in reconstruction.points3D.values()]
    return sum(errors) / len(errors)


def run_sfm(image_dir, output_dir, max_num_features=8192):
    """Run COLMAP feature extraction -> matching -> incremental SfM.

    Args:
        image_dir: directory of input frames (e.g. motion-based extracted frames from T3.2).
        output_dir: directory to write database.db and sparse/ reconstruction into.
        max_num_features: cap on SIFT features per image.

    Returns:
        dict of summary stats, also written to output_dir/sfm_report.json.
    """
    image_dir = pathlib.Path(image_dir)
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir = output_dir / "sparse"
    sparse_dir.mkdir(exist_ok=True)
    database_path = output_dir / "database.db"

    if database_path.exists():
        database_path.unlink()

    # --- Step 1: Feature extraction (SIFT) ---
    # Verified against the actual installed pycolmap's error-message signature:
    # extraction_options=pycolmap.FeatureExtractionOptions(), not sift_options=.
    extraction_options = pycolmap.FeatureExtractionOptions()
    applied_via = _set_max_num_features(extraction_options, max_num_features)

    pycolmap.extract_features(
        database_path,
        image_dir,
        extraction_options=extraction_options,
    )

    # --- Step 2: Exhaustive matching ---
    pycolmap.match_exhaustive(database_path)

    # --- Step 3: Incremental Structure-from-Motion ---
    maps = pycolmap.incremental_mapping(database_path, image_dir, sparse_dir)

    if not maps:
        stats = {
            "status": "failed",
            "reason": "incremental_mapping produced no reconstruction",
            "max_num_features_requested": max_num_features,
            "max_num_features_applied_via": applied_via,
        }
        with open(output_dir / "sfm_report.json", "w") as f:
            json.dump(stats, f, indent=2)
        return stats

    # pycolmap.incremental_mapping returns a dict {model_id: Reconstruction};
    # pick the model with the most registered images as the "best" one.
    best_model_id = max(maps, key=lambda k: maps[k].num_reg_images())
    reconstruction = maps[best_model_id]

    best_model_dir = sparse_dir / str(best_model_id)
    best_model_dir.mkdir(exist_ok=True)
    reconstruction.write(str(best_model_dir))

    num_input_images = len(
        [p for p in image_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )
    num_registered = reconstruction.num_reg_images()
    registration_rate = num_registered / num_input_images if num_input_images else 0.0

    stats = {
        "status": "success",
        "num_input_images": num_input_images,
        "num_registered_images": num_registered,
        "registration_rate": registration_rate,
        "num_points3D": reconstruction.num_points3D(),
        "mean_track_length": _compute_mean_track_length(reconstruction),
        "mean_reprojection_error_px": _compute_mean_reprojection_error(reconstruction),
        "best_model_id": int(best_model_id),
        "best_model_dir": str(best_model_dir),
        "max_num_features_requested": max_num_features,
        "max_num_features_applied_via": applied_via,
    }

    with open(output_dir / "sfm_report.json", "w") as f:
        json.dump(stats, f, indent=2)

    return stats

