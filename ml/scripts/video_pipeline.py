"""
T4.3 - Video Mode end-to-end pipeline: RT-DETR detection + COLMAP/mesh
reconstruction (already completed by T3.2-T4.1, reused from their saved
state/outputs) + 3D measurement (T4.2), combined into one callable function
producing a single JSON result - the Video Mode equivalent of Photo Mode's
photo_pipeline.analyze_photo().

SCOPE NOTE: T3.2 (frame extraction), T3.3 (SfM), T3.4 (dense point cloud),
and T4.1 (mesh) are each expensive, multi-minute Colab stages with their own
already-solved, non-trivial failure modes (parallax-shift tuning, mapper
threshold relaxation, dense-stereo CUDA-wheel limitations, Poisson density
trimming) - re-deriving and re-running all of that logic inside a single
function call to run_video_mode_pipeline() is possible but is a separate
larger task's worth of work (and the pre-reconstructed state is already
checkpointed on Drive from those notebooks). So, matching ClaimPilot's
established Drive-checkpoint pattern throughout this project, this function
REUSES T3.3's sparse model and T4.1's mesh via their state JSON files rather
than re-running SfM/dense/mesh reconstruction from a raw video each call.
What IS newly unified here, matching T4.3's roadmap description ("Combine
RT-DETR + COLMAP + ... 3D measurement into single pipeline, output JSON"):
running RT-DETR detection across the reconstructed frames, raycasting into
the mesh, and measuring each instance - all as ONE function call with one
JSON output, instead of separate manually-run notebook cells (T4.2).

RESILIENCE: per-instance measurement is wrapped in try/except (same pattern
as photo_pipeline.py's per-stage resilience) so one bad instance doesn't
crash the whole video's result - it degrades to null measurements + an
error note in that instance's "stage_errors", exactly like Photo Mode.
"""

import json
import pathlib
import time

import numpy as np


def _locate_rtdetr_weights(project_root):
    project_root = pathlib.Path(project_root)
    candidates = list(project_root.glob("**/cardd_finetune_v2/**/best.pt"))
    if not candidates:
        candidates = list(project_root.glob("**/weights/best.pt"))
    if not candidates:
        raise RuntimeError(
            f"Could not locate RT-DETR best.pt under {project_root}. "
            "Pass rtdetr_weights_path explicitly."
        )
    return candidates[0]


def _load_state(state_dir, name):
    path = pathlib.Path(state_dir) / f"{name}.json"
    if not path.exists():
        raise RuntimeError(
            f"Required state file {path} not found - run the {name} notebook first."
        )
    with open(path) as f:
        return json.load(f)


def _pose_cam_to_world(image):
    cam_from_world = image.cam_from_world()
    R_cw = cam_from_world.rotation.matrix()
    t_cw = np.asarray(cam_from_world.translation)
    R_wc = R_cw.T
    t_wc = -R_wc @ t_cw
    pose = np.eye(4)
    pose[:3, :3] = R_wc
    pose[:3, 3] = t_wc
    return pose


def run_video_mode_pipeline(
    video_name,
    project_root,
    rtdetr_weights_path=None,
    pixel_stride=3,
    device="cuda",
    ocr_reader=None,
    metric_depth_processor=None,
    metric_depth_model=None,
):
    """End-to-end Video Mode analysis for an already-reconstructed video
    (T3.2-T4.1 must have completed and saved their state - see SCOPE NOTE).

    ocr_reader / metric_depth_processor / metric_depth_model: optional,
    pre-loaded Tier 2/3 calibration fallbacks (see scale_calibration.py). If
    not passed, calibration still runs Tier 1 (plate) and Tier 2b (generic
    wheel diameter, no OCR needed) - only Tier 2a (exact tire-code OCR) and
    Tier 3 (metric depth prior) are skipped, degrading gracefully rather than
    failing to import. Pass these in (see T4_3 notebook) to get the full
    never-null calibration chain.

    Returns the result dict (same dict that's written to
    outputs/measurements/<video_name>_pipeline_result.json), in the same
    schema family as Photo Mode's analyze_photo() output.
    """
    import cv2
    import pycolmap
    import open3d as o3d
    from ultralytics import RTDETR

    import sys
    project_root = pathlib.Path(project_root)
    scripts_dir = project_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import mesh_measurement
    import scale_calibration

    state_dir = project_root / "state"
    outputs_dir = project_root / "outputs"
    measurements_dir = outputs_dir / "measurements"
    measurements_dir.mkdir(parents=True, exist_ok=True)

    stage_errors = {}
    t_start = time.time()
    timing = {}

    # --- Load upstream state (T3.3 sparse model, T4.1 mesh) ---
    t3_3_state = _load_state(state_dir, "t3_3_sfm")
    t4_1_state = _load_state(state_dir, "t4_1_mesh")
    if not t3_3_state.get("t3_3_sfm"):
        raise RuntimeError("T3.3 did not complete successfully for this video.")
    if not t4_1_state.get("t4_1_mesh"):
        raise RuntimeError("T4.1 did not complete successfully for this video.")

    sfm_stats = t3_3_state["sfm_stats"]
    sparse_model_dir = pathlib.Path(sfm_stats["best_model_dir"])
    mesh_obj_path = pathlib.Path(t4_1_state["obj_path"])
    image_dir = outputs_dir / "video" / "frames" / video_name / "parallax_synthetic"

    t0 = time.time()
    reconstruction = pycolmap.Reconstruction(str(sparse_model_dir))
    timing["load_reconstruction"] = time.time() - t0

    t0 = time.time()
    mesh = o3d.io.read_triangle_mesh(str(mesh_obj_path))
    scene = mesh_measurement.build_raycasting_scene(mesh)
    timing["load_mesh"] = time.time() - t0

    # --- Detection across all registered frames ---
    t0 = time.time()
    per_frame_detections = {}
    try:
        weights_path = rtdetr_weights_path or _locate_rtdetr_weights(project_root)
        detector = RTDETR(str(weights_path))
        for image_id, image in reconstruction.images.items():
            img_path = image_dir / image.name
            if not img_path.exists():
                continue
            results = detector.predict(str(img_path), device=device, verbose=False)
            r = results[0]
            instances = []
            for box in r.boxes:
                instances.append(
                    {
                        "bbox_xyxy": box.xyxy[0].tolist(),
                        "confidence": float(box.conf[0]),
                        "class_id": int(box.cls[0]),
                        "class_name": detector.names[int(box.cls[0])],
                    }
                )
            per_frame_detections[image.name] = instances
    except Exception as e:
        stage_errors["detection"] = str(e)
        per_frame_detections = {}
    timing["detection"] = time.time() - t0

    # --- Pick reference frame (highest-confidence single detection) ---
    best_frame_name, best_conf, best_instances = None, -1.0, []
    for frame_name, instances in per_frame_detections.items():
        if not instances:
            continue
        top_conf = max(inst["confidence"] for inst in instances)
        if top_conf > best_conf:
            best_conf = top_conf
            best_frame_name = frame_name
            best_instances = instances

    if best_frame_name is None:
        result = {
            "video_name": video_name,
            "processed_at": None,
            "reference_frame": None,
            "models": {
                "detection": "RT-DETR-L (ClaimPilot fine-tuned, T3.1v2)",
                "reconstruction": "COLMAP SfM (T3.3) + dense (T3.4) + Poisson mesh (T4.1)",
            },
            "calibration": {"status": "skipped_no_detections", "mm_per_unit": None},
            "damage_instances": [],
            "summary": {"num_instances": 0, "classes_detected": [], "total_damage_area_cm2": None},
            "stage_errors": stage_errors or {"detection": "no damage detected in any frame"},
            "timing_sec": {**timing, "total": time.time() - t_start},
        }
        _write_result(measurements_dir, video_name, result)
        return result

    # --- Scale calibration (Tier 1 plate -> Tier 2 wheel/tire -> Tier 3 metric
    # depth prior; see scale_calibration.py - this is the never-null chain, not
    # plate-or-null) ---
    t0 = time.time()
    try:
        calibration = scale_calibration.calibrate_scale(
            scene, reconstruction, image_dir,
            plate_calibrate_fn=mesh_measurement.calibrate_scale_from_plate,
            ocr_reader=ocr_reader,
            metric_depth_processor=metric_depth_processor,
            metric_depth_model=metric_depth_model,
            device=device,
        )
    except Exception as e:
        stage_errors["calibration"] = str(e)
        calibration = {"status": "failed", "mm_per_unit": None}
    timing["calibration"] = time.time() - t0

    # --- Reference frame pose/camera ---
    ref_image = None
    for image_id, image in reconstruction.images.items():
        if image.name == best_frame_name:
            ref_image = image
            break
    ref_camera = reconstruction.cameras[ref_image.camera_id]
    ref_pose = _pose_cam_to_world(ref_image)

    ref_img_bgr = cv2.imread(str(image_dir / best_frame_name))
    image_shape = ref_img_bgr.shape
    mm_per_unit = calibration.get("mm_per_unit")

    # --- Per-instance measurement (resilient: one bad instance != pipeline failure) ---
    t0 = time.time()
    damage_instances = []
    for i, inst in enumerate(best_instances):
        instance_errors = {}
        measurement = None
        try:
            measurement = mesh_measurement.measure_damage_instance_3d(
                scene, ref_camera, ref_pose, inst["bbox_xyxy"], image_shape,
                mm_per_unit, pixel_stride=pixel_stride,
            )
            if measurement["status"] != "success":
                instance_errors["measurement"] = measurement.get("reason", "unknown failure")
        except Exception as e:
            instance_errors["measurement"] = str(e)
            measurement = {}

        damage_instances.append(
            {
                "instance_id": i,
                "class_name": inst["class_name"],
                "confidence": inst["confidence"],
                "bbox_xyxy": inst["bbox_xyxy"],
                "depth_mm": measurement.get("depth_mm"),
                "area_cm2": measurement.get("area_cm2"),
                "volume_cm3": measurement.get("volume_cm3"),
                "crease_angle_deg": measurement.get("crease_angle_deg"),
                "stage_errors": instance_errors,
            }
        )
    timing["measurement"] = time.time() - t0
    timing["total"] = time.time() - t_start

    total_area = None
    if calibration.get("status") == "calibrated":
        areas = [d["area_cm2"] for d in damage_instances if d["area_cm2"] is not None]
        total_area = sum(areas) if areas else None

    result = {
        "video_name": video_name,
        "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reference_frame": best_frame_name,
        "image_size": [image_shape[1], image_shape[0]],
        "models": {
            "detection": "RT-DETR-L (ClaimPilot fine-tuned, T3.1v2)",
            "reconstruction": "COLMAP SfM (T3.3) + dense point cloud (T3.4) + Poisson mesh (T4.1)",
        },
        "calibration": calibration,
        "damage_instances": damage_instances,
        "summary": {
            "num_instances": len(damage_instances),
            "classes_detected": sorted(set(d["class_name"] for d in damage_instances)),
            "total_damage_area_cm2": total_area,
        },
        "stage_errors": stage_errors,
        "timing_sec": timing,
    }
    _write_result(measurements_dir, video_name, result)
    return result


def _write_result(measurements_dir, video_name, result):
    out_path = pathlib.Path(measurements_dir) / f"{video_name}_pipeline_result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    result["_output_path"] = str(out_path)
