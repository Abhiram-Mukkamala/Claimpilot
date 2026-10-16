# Reusable DSINE surface-normal estimation + crease-angle calculation for ClaimPilot.
# Used by this notebook (T2.3) and by the end-to-end pipeline (T2.4).
import numpy as np
import cv2
import torch


def load_dsine(device="cuda"):
    model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
    return model.to(device)


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
