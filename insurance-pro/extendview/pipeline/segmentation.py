# Reusable SAM2 box-prompted segmentation + pixel-to-mm area calibration for ClaimPilot.
import numpy as np
import torch


def load_sam2(model_id="facebook/sam2.1-hiera-small", device="cuda"):
    from transformers import Sam2Model, Sam2Processor
    processor = Sam2Processor.from_pretrained(model_id)
    model = Sam2Model.from_pretrained(model_id).to(device)
    model.eval()
    return processor, model


def segment_boxes(processor, model, image, boxes_xyxy, device="cuda"):
    # image: PIL.Image (RGB). boxes_xyxy: list of [x1, y1, x2, y2] in pixel coords.
    # Returns a list of (mask_bool_hw, iou_score) tuples, one per box, in the same order.
    if len(boxes_xyxy) == 0:
        return []

    input_boxes = [[list(map(float, b)) for b in boxes_xyxy]]
    inputs = processor(images=image, input_boxes=input_boxes, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model(**inputs, multimask_output=False)

    masks = processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"])[0]
    scores = outputs.iou_scores.squeeze().detach().cpu().numpy()
    scores = np.atleast_1d(scores)

    results = []
    for i in range(masks.shape[0]):
        mask_bool = masks[i, 0].numpy().astype(bool)
        score = float(scores[i]) if i < len(scores) else None
        results.append((mask_bool, score))
    return results


def compute_pixel_to_mm(image_path, image_width_px, plate_bbox=None,
                         plate_width_mm=520.0, assumed_hfov_deg=60.0):
    from depth_estimation import detect_license_plate

    if plate_bbox is None:
        plate_bbox = detect_license_plate(image_path)
        detection_method = "auto_haar_cascade"
    else:
        detection_method = "manual_override"

    if plate_bbox is None:
        return None, {"status": "skipped_no_plate_detected", "detection_method": "auto_haar_cascade"}

    x, y, w, h = plate_bbox
    if w <= 0:
        return None, {"status": "invalid_plate_bbox", "detection_method": detection_method}

    mm_per_pixel = plate_width_mm / w
    calibration_info = {
        "status": "calibrated",
        "detection_method": detection_method,
        "plate_bbox_xywh": [int(x), int(y), int(w), int(h)],
        "plate_width_mm": plate_width_mm,
        "mm_per_pixel": mm_per_pixel,
    }
    return mm_per_pixel, calibration_info


def compute_mask_area_from_depth(mask_bool, metric_depth_map_mm, focal_length_px):
    """Per-instance area from calibrated metric depth map and camera focal length."""
    pixel_count = int(mask_bool.sum())
    if metric_depth_map_mm is None or focal_length_px is None or focal_length_px <= 0:
        return pixel_count, None
    if pixel_count == 0:
        return pixel_count, 0.0

    depths_at_mask = metric_depth_map_mm[mask_bool]
    valid = np.isfinite(depths_at_mask) & (depths_at_mask > 0)
    if not np.any(valid):
        return pixel_count, None

    mm_per_pixel_at_each = depths_at_mask[valid] / focal_length_px
    area_mm2 = float(np.sum(mm_per_pixel_at_each ** 2))
    if valid.sum() < pixel_count:
        mean_mm2_per_px = area_mm2 / valid.sum()
        area_mm2 += mean_mm2_per_px * (pixel_count - valid.sum())
    area_cm2 = round(area_mm2 / 100.0, 2)
    return pixel_count, area_cm2


def compute_mask_area(mask_bool, mm_per_pixel=None):
    pixel_count = int(mask_bool.sum())
    if mm_per_pixel is None:
        return pixel_count, None
    area_mm2 = pixel_count * (mm_per_pixel ** 2)
    area_cm2 = round(area_mm2 / 100.0, 2)
    return pixel_count, area_cm2
