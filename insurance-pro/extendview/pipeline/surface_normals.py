# Reusable DSINE surface-normal estimation + crease-angle calculation for ClaimPilot.
import os
import glob
import numpy as np
import cv2
import torch


def load_dsine(device="cuda"):
    """Load DSINE with runtime patch for hardcoded CUDA device so CPU works cleanly."""
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

    _patch_dsine_repo_for_cpu()
    try:
        dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
    except Exception:
        if _patch_dsine_repo_for_cpu():
            dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
        else:
            raise

    if hasattr(dsine_model, "to"):
        dsine_model = dsine_model.to(device)
    elif hasattr(dsine_model, "model") and hasattr(dsine_model.model, "to"):
        dsine_model.model = dsine_model.model.to(device)

    return dsine_model


def estimate_normals(model, image_path):
    # Returns a (H, W, 3) float32 array of unit surface normal vectors in [-1, 1].
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
    display = ((normal_map + 1.0) / 2.0 * 255).astype(np.uint8)
    return display


def compute_crease_angle(normal_map, mask_bool, ring_width_px=15):
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

    mean_damage_normal = mean_damage_normal / (np.linalg.norm(mean_damage_normal) + 1e-8)
    mean_ring_normal = mean_ring_normal / (np.linalg.norm(mean_ring_normal) + 1e-8)

    dot = float(np.clip(np.dot(mean_damage_normal, mean_ring_normal), -1.0, 1.0))
    angle_deg = float(np.degrees(np.arccos(dot)))

    # Also compute 95th percentile local angular deviation inside the mask for sharp creases
    dots_local = np.clip(damage_normals @ mean_ring_normal, -1.0, 1.0)
    angles_local = np.degrees(np.arccos(dots_local))
    p95_angle = float(np.percentile(angles_local, 90)) if angles_local.size > 0 else angle_deg
    effective_angle = round(max(angle_deg, p95_angle * 0.65), 2)

    return {
        "status": "computed",
        "crease_angle_deg": effective_angle,
        "mean_angle_deg": round(angle_deg, 2),
        "p90_angle_deg": round(p95_angle, 2),
        "mean_damage_normal": mean_damage_normal.tolist(),
        "mean_ring_normal": mean_ring_normal.tolist(),
        "damage_pixel_count": int(mask_bool.sum()),
        "ring_pixel_count": int(ring.sum()),
    }
