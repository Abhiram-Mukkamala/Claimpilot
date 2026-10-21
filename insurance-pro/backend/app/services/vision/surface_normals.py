# Reusable DSINE surface-normal estimation + crease-angle calculation for ClaimPilot.
# Used by the photo-mode pipeline and by ai_runner.py vision integration.
# Ported from the v3 pipeline/surface_normals.py, with the CPU-safe DSINE loader
# from v3 pipeline/v1_adapter.py (_load_dsine_patched).
import glob
import os

import numpy as np
import cv2
import torch


def _load_dsine_patched(device: str):
    """Load DSINE with runtime patch for hardcoded CUDA device."""

    def _find_dsine_repo_dir():
        hub_dir = torch.hub.get_dir()
        matches = glob.glob(os.path.join(hub_dir, "hugoycj_DSINE-hub_*"))
        return matches[0] if matches else None

    def _patch_dsine_repo_for_cpu():
        repo_dir = _find_dsine_repo_dir()
        if repo_dir is None:
            return False
        any_changed = False
        replacements = [
            ('torch.device("cuda")', 'torch.device("cuda" if torch.cuda.is_available() else "cpu")'),
            ("torch.device('cuda')", "torch.device('cuda' if torch.cuda.is_available() else 'cpu')"),
            # Hardcoded GPU index 0 crashes on CPU-only machines.
            (".to(0)", '.to("cuda" if __import__("torch").cuda.is_available() else "cpu")'),
        ]
        for py_path in glob.glob(os.path.join(repo_dir, "**", "*.py"), recursive=True):
            try:
                with open(py_path, "r", encoding="utf-8") as f:
                    content = f.read()
                patched = content
                for old, new in replacements:
                    patched = patched.replace(old, new)
                if patched != content:
                    with open(py_path, "w", encoding="utf-8") as f:
                        f.write(patched)
                    any_changed = True
            except Exception:
                pass
        return any_changed

    _patch_dsine_repo_for_cpu()  # patch if already cached
    try:
        dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
    except Exception:
        # First run: repo wasn't cached, patch after download and retry
        if _patch_dsine_repo_for_cpu():
            dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
        else:
            raise

    if hasattr(dsine_model, "to"):
        dsine_model = dsine_model.to(device)
    elif hasattr(dsine_model, "model") and hasattr(dsine_model.model, "to"):
        dsine_model.model = dsine_model.model.to(device)

    return dsine_model


def load_dsine(device="cpu"):
    return _load_dsine_patched(device)


def estimate_normals(model, image_path):
    # Returns a (H, W, 3) float32 array of unit surface normal vectors in DSINE's
    # right-handed, outward-pointing convention (X=right, Y=down, Z=front), values in
    # [-1, 1] -- NOT remapped to a displayable [0, 255] range. Use colorize_normals()
    # for visualization.
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    with torch.inference_mode():
        raw = model.infer_cv2(image_bgr)[0]

    normal = raw.detach().cpu().numpy().astype(np.float32)
    if normal.shape[0] == 3 and normal.shape[-1] != 3:
        normal = normal.transpose(1, 2, 0)  # (3, H, W) -> (H, W, 3)
    return normal


def colorize_normals(normal_map):
    # Standard normal-map visualization: map [-1, 1] -> [0, 255] per channel.
    display = ((normal_map + 1.0) / 2.0 * 255).astype(np.uint8)
    return display


def compute_crease_angle(normal_map, mask_bool, ring_width_px=15):
    # Crease angle: the angle (degrees) between the mean surface normal inside a damage
    # mask and the mean surface normal of the surrounding undamaged panel (a ring just
    # outside the mask). 0 degrees means the damage region is coplanar with its
    # surroundings; larger angles indicate sharper deformation.
    #
    # Returns a dict with status, crease_angle_deg (or None), and the two mean normals
    # for transparency/debugging.
    mask_u8 = mask_bool.astype(np.uint8)
    kernel = np.ones((ring_width_px, ring_width_px), np.uint8)
    dilated = cv2.dilate(mask_u8, kernel, iterations=1).astype(bool)
    ring = dilated & (~mask_bool)

    if mask_bool.sum() == 0:
        return {"status": "empty_damage_mask", "crease_angle_deg": None}
    if ring.sum() == 0:
        return {"status": "no_surrounding_context", "crease_angle_deg": None}

    damage_normals = normal_map[mask_bool]
    ring_normals = normal_map[ring]

    mean_damage_normal = damage_normals.mean(axis=0)
    mean_ring_normal = ring_normals.mean(axis=0)

    # Re-normalize the mean vectors (averaging unit vectors doesn't preserve unit length)
    mean_damage_normal = mean_damage_normal / (np.linalg.norm(mean_damage_normal) + 1e-8)
    mean_ring_normal = mean_ring_normal / (np.linalg.norm(mean_ring_normal) + 1e-8)

    dot = float(np.clip(np.dot(mean_damage_normal, mean_ring_normal), -1.0, 1.0))
    angle_deg = float(np.degrees(np.arccos(dot)))

    return {
        "status": "computed",
        "crease_angle_deg": angle_deg,
        "mean_damage_normal": mean_damage_normal.tolist(),
        "mean_ring_normal": mean_ring_normal.tolist(),
        "damage_pixel_count": int(mask_bool.sum()),
        "ring_pixel_count": int(ring.sum()),
    }
