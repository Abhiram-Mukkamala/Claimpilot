# Reusable YOLOv11m inference helpers for ClaimPilot.
# Ported from ml/scripts/inference.py for backend integration.
#
# Defaults are tuned for fast CPU execution: imgsz=640 and test-time
# augmentation (TTA) disabled.


def load_model(model_path, device="cpu"):
    # Load a YOLO model onto the given device (int GPU index, or 'cpu').
    from ultralytics import YOLO

    model = YOLO(model_path)
    model.to(device)
    return model


def run_inference(model, image_path, conf=0.25, iou=0.45, imgsz=640, use_tta=False):
    # Run detection on a single image.
    #
    # Returns a list of dicts: {class_id, class_name, confidence, bbox_xyxy}
    # where bbox_xyxy is [x1, y1, x2, y2] in absolute pixel coordinates.
    results = model.predict(
        source=image_path, conf=conf, iou=iou, imgsz=imgsz,
        augment=use_tta, verbose=False,
    )
    r = results[0]
    names = r.names
    detections = []
    for box in r.boxes:
        cls_id = int(box.cls[0])
        detections.append({
            "class_id": cls_id,
            "class_name": names[cls_id],
            "confidence": float(box.conf[0]),
            "bbox_xyxy": [float(v) for v in box.xyxy[0].tolist()],
        })
    return detections
