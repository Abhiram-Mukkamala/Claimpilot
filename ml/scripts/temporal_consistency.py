# Reusable frame-to-frame detection tracker/smoother for ClaimPilot video mode.
# Used by this notebook (T3.1) and by later video-pipeline tasks (T3.2+, T4.3).


def _iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class TemporalTracker:
    def __init__(self, iou_threshold=0.3, ema_alpha=0.6, min_hits=2, max_misses=3):
        self.iou_threshold = iou_threshold
        self.ema_alpha = ema_alpha
        self.min_hits = min_hits
        self.max_misses = max_misses
        self.tracks = []
        self._next_id = 0

    def update(self, detections):
        unmatched = list(range(len(detections)))

        for track in self.tracks:
            best_iou, best_j = 0.0, -1
            for j in unmatched:
                if detections[j]["class_name"] != track["class_name"]:
                    continue
                iou = _iou(track["bbox"], detections[j]["bbox_xyxy"])
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_iou >= self.iou_threshold:
                det = detections[best_j]
                a = self.ema_alpha
                track["bbox"] = [a * n + (1 - a) * o for n, o in zip(det["bbox_xyxy"], track["bbox"])]
                track["confidence"] = a * det["confidence"] + (1 - a) * track["confidence"]
                track["hits"] += 1
                track["misses"] = 0
                unmatched.remove(best_j)
            else:
                track["misses"] += 1

        self.tracks = [t for t in self.tracks if t["misses"] <= self.max_misses]

        for j in unmatched:
            det = detections[j]
            self.tracks.append({
                "id": self._next_id,
                "bbox": list(det["bbox_xyxy"]),
                "confidence": det["confidence"],
                "class_name": det["class_name"],
                "hits": 1,
                "misses": 0,
            })
            self._next_id += 1

        return [
            {
                "track_id": t["id"],
                "class_name": t["class_name"],
                "confidence": t["confidence"],
                "bbox_xyxy": list(t["bbox"]),
            }
            for t in self.tracks if t["hits"] >= self.min_hits
        ]
