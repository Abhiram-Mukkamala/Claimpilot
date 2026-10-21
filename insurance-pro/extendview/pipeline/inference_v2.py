"""
Improved inference helpers for ClaimPilot — accuracy improvements for dent, scratch, crack.

Three orthogonal techniques applied together:
  1. Per-class confidence thresholds:
       crack   -> conf=0.40
       scratch -> conf=0.35
       dent    -> conf=0.15
       others  -> conf=0.25
  2. Configurable resolution (imgsz=640 for CPU speed, 1280 for high-res GPU/recall)
  3. Optional Test-Time Augmentation (TTA)
  4. Lower NMS IoU threshold (0.35) so co-located dent+scratch on the same panel survive.
"""

from ultralytics import YOLO

DEFAULT_CLASS_THRESHOLDS = {
    "crack":   0.40,
    "scratch": 0.35,
    "dent":    0.15,
}

DEFAULT_IMGSZ = 640
DEFAULT_IOU_NMS = 0.35


def run_inference_v2(
    model,
    image_path,
    class_thresholds=None,
    global_conf=0.10,
    iou=DEFAULT_IOU_NMS,
    imgsz=DEFAULT_IMGSZ,
    tta=False,
    device=None,
):
    """Run detection with per-class confidence thresholds, configurable resolution, and TTA."""
    if class_thresholds is None:
        class_thresholds = DEFAULT_CLASS_THRESHOLDS

    predict_kwargs = dict(
        source=image_path,
        conf=global_conf,
        iou=iou,
        imgsz=imgsz,
        augment=tta,
        verbose=False,
    )
    if device is not None:
        predict_kwargs["device"] = device

    results = model.predict(**predict_kwargs)
    r = results[0]
    names = r.names

    detections = []
    for box in r.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        class_name = names[cls_id]
        threshold = class_thresholds.get(class_name, 0.25)
        if conf < threshold:
            continue
        detections.append({
            "class_id":   cls_id,
            "class_name": class_name,
            "confidence": conf,
            "bbox_xyxy":  [float(v) for v in box.xyxy[0].tolist()],
        })

    return detections


def run_inference_multiscale(
    model,
    image_path,
    scales=(640, 1280),
    class_thresholds=None,
    global_conf=0.10,
    merge_iou=0.50,
    tta=False,
    device=None,
):
    """Multi-scale ensemble: run inference at each resolution in `scales`, merge with NMS."""
    if class_thresholds is None:
        class_thresholds = DEFAULT_CLASS_THRESHOLDS

    all_preds = []
    for imgsz in scales:
        predict_kwargs = dict(
            source=image_path, conf=global_conf, iou=DEFAULT_IOU_NMS,
            imgsz=imgsz, augment=tta, verbose=False,
        )
        if device is not None:
            predict_kwargs["device"] = device
        results = model.predict(**predict_kwargs)
        r = results[0]
        names = r.names
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = names[cls_id]
            threshold = class_thresholds.get(class_name, 0.25)
            if conf < threshold:
                continue
            all_preds.append((conf, cls_id, class_name, [float(v) for v in box.xyxy[0].tolist()]))

    if not all_preds:
        return []

    def _box_iou(a, b):
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    all_preds.sort(key=lambda x: -x[0])
    kept = []
    suppressed = set()
    for i, (conf_i, cls_i, name_i, box_i) in enumerate(all_preds):
        if i in suppressed:
            continue
        kept.append((conf_i, cls_i, name_i, box_i))
        for j in range(i + 1, len(all_preds)):
            if j in suppressed:
                continue
            conf_j, cls_j, name_j, box_j = all_preds[j]
            if cls_j != cls_i:
                continue
            if _box_iou(box_i, box_j) >= merge_iou:
                suppressed.add(j)

    return [
        {"class_id": cls_id, "class_name": class_name, "confidence": conf, "bbox_xyxy": bbox}
        for conf, cls_id, class_name, bbox in kept
    ]


def draw_detections(image_path, detections, out_path, box_color=(0, 255, 0)):
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    for det in detections:
        x1, y1, x2, y2 = (int(round(v)) for v in det["bbox_xyxy"])
        label = f"{det['class_name']} {det['confidence']:.2f}"
        cv2.rectangle(img, (x1, y1), (x2, y2), box_color, 2)
        text_y = max(y1 - 8, 12)
        cv2.putText(img, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1, cv2.LINE_AA)

    cv2.imwrite(out_path, img)
    return out_path
