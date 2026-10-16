# Reusable YOLOv11m inference helpers for ClaimPilot.
# Used directly by this notebook (T1.4) and by the end-to-end pipeline (T2.4).
from ultralytics import YOLO


def load_model(model_path, device=0):
    # Load a YOLO model onto the given device (int GPU index, or 'cpu').
    model = YOLO(model_path)
    model.to(device)
    return model


def run_inference(model, image_path, conf=0.25, iou=0.45, imgsz=640):
    # Run detection on a single image.
    #
    # Returns a list of dicts: {class_id, class_name, confidence, bbox_xyxy}
    # where bbox_xyxy is [x1, y1, x2, y2] in absolute pixel coordinates.
    results = model.predict(source=image_path, conf=conf, iou=iou, imgsz=imgsz, verbose=False)
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


def draw_detections(image_path, detections, out_path, box_color=(0, 255, 0)):
    # Draw predicted boxes + label + confidence onto the image and save to out_path.
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
