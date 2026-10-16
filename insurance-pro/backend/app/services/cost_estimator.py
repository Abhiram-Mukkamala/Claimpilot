"""Deterministic, indicative repair-cost estimates from detection geometry."""

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


ESTIMATE_BASIS = "indicative, from a seeded cost table, uncalibrated"
UNCALIBRATED_NOTE = "UNCALIBRATED, needs garage or insurer data"
LOW_CONFIDENCE_NOTE = "low confidence, excluded"
UNKNOWN_CLASS_NOTE = "unknown damage class, excluded from estimate"
DUPLICATE_NOTE = "overlapping duplicate, excluded from total"
INVALID_GEOMETRY_NOTE = "invalid geometry, excluded from estimate"
TABLE_PATH = Path(__file__).resolve().parents[1] / "data" / "cost_table.json"


@lru_cache(maxsize=1)
def load_cost_table() -> dict[str, Any]:
    with TABLE_PATH.open(encoding="utf-8") as table_file:
        return json.load(table_file)


def _normalize_class(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").strip().casefold().split())


def _geometry(detection: dict[str, Any]) -> tuple[float | None, tuple[float, float, float, float] | None]:
    try:
        x1, y1, x2, y2 = (float(value) for value in detection["_estimator_bbox_xyxy"])
        image_width, image_height = (float(value) for value in detection["_estimator_image_size"])
    except (KeyError, TypeError, ValueError):
        return None, None

    values = (x1, y1, x2, y2, image_width, image_height)
    if not all(math.isfinite(value) for value in values) or image_width <= 0 or image_height <= 0:
        return None, None

    left = min(max(x1, 0.0), image_width)
    top = min(max(y1, 0.0), image_height)
    right = min(max(x2, 0.0), image_width)
    bottom = min(max(y2, 0.0), image_height)
    width = max(0.0, right - left)
    height = max(0.0, bottom - top)
    ratio = (width * height) / (image_width * image_height)
    return ratio, (left, top, right, bottom)


def _intersection_over_union(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def estimate_damage_costs(
    detections: list[dict[str, Any]],
    *,
    min_confidence: float = 0.30,
    minor_max_area_ratio: float = 0.02,
    moderate_max_area_ratio: float = 0.08,
    duplicate_iou_threshold: float = 0.80,
    cost_table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply table rates and geometry severity while retaining every detection."""
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")
    if not 0.0 < minor_max_area_ratio < moderate_max_area_ratio <= 1.0:
        raise ValueError("severity area thresholds must satisfy 0 < minor < moderate <= 1")
    if not 0.0 <= duplicate_iou_threshold <= 1.0:
        raise ValueError("duplicate_iou_threshold must be between 0 and 1")

    table = cost_table if cost_table is not None else load_cost_table()
    rows: list[dict[str, Any]] = []
    for source_detection in detections:
        item = {
            key: value
            for key, value in source_detection.items()
            if not key.startswith("_estimator_")
        }
        class_name = source_detection.get("_estimator_class_name", source_detection.get("part"))
        class_key = _normalize_class(class_name)
        try:
            confidence = float(source_detection.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        area_ratio, bbox = _geometry(source_detection)

        if area_ratio is None:
            severity_key = None
            severity_label = "Not available"
        elif area_ratio < minor_max_area_ratio:
            severity_key = "minor"
            severity_label = "Minor"
        elif area_ratio <= moderate_max_area_ratio:
            severity_key = "moderate"
            severity_label = "Moderate"
        else:
            severity_key = "severe"
            severity_label = "Severe"

        item["severity"] = severity_label
        item["area_ratio"] = round(area_ratio, 6) if area_ratio is not None else None
        item["estimated_cost_min"] = 0.0
        item["estimated_cost_max"] = 0.0
        item["estimated_cost"] = 0.0
        notes: list[str] = []
        table_entry = table.get(class_key)
        severity_entry = table_entry.get(severity_key) if table_entry and severity_key else None
        excluded = False

        if confidence < min_confidence:
            notes.append(LOW_CONFIDENCE_NOTE)
            excluded = True
        elif area_ratio is None or bbox is None:
            notes.append(INVALID_GEOMETRY_NOTE)
            excluded = True
        elif not table_entry:
            notes.append(UNKNOWN_CLASS_NOTE)
            excluded = True
        elif not severity_entry:
            notes.append(UNKNOWN_CLASS_NOTE)
            excluded = True
        else:
            minimum = float(severity_entry["min"])
            maximum = float(severity_entry["max"])
            item["estimated_cost_min"] = round(minimum, 2)
            item["estimated_cost_max"] = round(maximum, 2)
            item["estimated_cost"] = round((minimum + maximum) / 2, 2)
            note = severity_entry.get("note")
            if note:
                notes.append(str(note))

        item["estimate_note"] = "; ".join(notes) if notes else None
        rows.append({
            "item": item,
            "class_key": class_key,
            "bbox": bbox,
            "area_ratio": area_ratio,
            "excluded": excluded,
        })

    # Keep the largest box as the representative for an overlapping same-class
    # group. Confidence affects inclusion only and never affects ordering/price.
    candidates = [index for index, row in enumerate(rows) if not row["excluded"]]
    candidates.sort(key=lambda index: (-(rows[index]["area_ratio"] or 0.0), index))
    representatives: list[int] = []
    for index in candidates:
        row = rows[index]
        duplicate = any(
            rows[representative]["class_key"] == row["class_key"]
            and _intersection_over_union(rows[representative]["bbox"], row["bbox"])
            > duplicate_iou_threshold
            for representative in representatives
        )
        if duplicate:
            row["excluded"] = True
            item = row["item"]
            item["estimated_cost_min"] = 0.0
            item["estimated_cost_max"] = 0.0
            item["estimated_cost"] = 0.0
            item["estimate_note"] = "; ".join(
                filter(None, [item.get("estimate_note"), DUPLICATE_NOTE])
            )
        else:
            representatives.append(index)

    priced_detections = [row["item"] for row in rows]
    estimated_min = round(sum(item["estimated_cost_min"] for item in priced_detections), 2)
    estimated_max = round(sum(item["estimated_cost_max"] for item in priced_detections), 2)
    return {
        "detected_damages": priced_detections,
        "estimated_cost_min": estimated_min,
        "estimated_cost_max": estimated_max,
        "estimate_basis": ESTIMATE_BASIS,
    }
