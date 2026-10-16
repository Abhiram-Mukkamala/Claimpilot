from app.services.cost_estimator import (
    DUPLICATE_NOTE,
    ESTIMATE_BASIS,
    LOW_CONFIDENCE_NOTE,
    UNKNOWN_CLASS_NOTE,
    UNCALIBRATED_NOTE,
    estimate_damage_costs,
)


def _detection(class_name, confidence, bbox, image_size=(1000, 1000)):
    return {
        "id": f"{class_name}-{confidence}-{bbox[0]}",
        "part": class_name,
        "confidence": confidence,
        "_estimator_class_name": class_name,
        "_estimator_bbox_xyxy": bbox,
        "_estimator_image_size": image_size,
    }


def test_large_crack_costs_more_than_small_scratch_at_identical_confidence():
    result = estimate_damage_costs([
        _detection("crack", 0.75, (0, 0, 500, 500)),
        _detection("scratch", 0.75, (0, 0, 100, 100)),
    ])

    crack, scratch = result["detected_damages"]
    assert crack["severity"] == "Severe"
    assert scratch["severity"] == "Minor"
    assert crack["estimated_cost"] > scratch["estimated_cost"]
    assert result["estimate_basis"] == ESTIMATE_BASIS


def test_confidence_changes_do_not_change_price():
    lower_confidence = estimate_damage_costs([
        _detection("dent", 0.50, (0, 0, 300, 300)),
    ])
    higher_confidence = estimate_damage_costs([
        _detection("dent", 0.95, (0, 0, 300, 300)),
    ])

    low_item = lower_confidence["detected_damages"][0]
    high_item = higher_confidence["detected_damages"][0]
    assert low_item["estimated_cost"] == high_item["estimated_cost"]
    assert low_item["estimated_cost_min"] == high_item["estimated_cost_min"]
    assert low_item["estimated_cost_max"] == high_item["estimated_cost_max"]
    assert lower_confidence["estimated_cost_min"] == higher_confidence["estimated_cost_min"]
    assert lower_confidence["estimated_cost_max"] == higher_confidence["estimated_cost_max"]


def test_heavily_overlapping_same_class_boxes_are_counted_once():
    result = estimate_damage_costs([
        _detection("dent", 0.80, (100, 100, 500, 500)),
        _detection("dent", 0.95, (110, 110, 510, 510)),
    ])

    first, duplicate = result["detected_damages"]
    assert first["estimated_cost"] > 0
    assert duplicate["estimated_cost"] == 0
    assert duplicate["estimate_note"] == DUPLICATE_NOTE
    assert result["estimated_cost_min"] == first["estimated_cost_min"]
    assert result["estimated_cost_max"] == first["estimated_cost_max"]


def test_unknown_class_is_excluded_with_a_flagged_note():
    result = estimate_damage_costs([
        _detection("unknown panel damage", 0.90, (0, 0, 300, 300)),
    ])

    item = result["detected_damages"][0]
    assert item["estimated_cost"] == 0
    assert item["estimated_cost_min"] == 0
    assert item["estimated_cost_max"] == 0
    assert item["estimate_note"] == UNKNOWN_CLASS_NOTE
    assert result["estimated_cost_min"] == result["estimated_cost_max"] == 0


def test_low_confidence_detection_is_excluded_from_cost():
    result = estimate_damage_costs([
        _detection("scratch", 0.20, (0, 0, 300, 300)),
    ])

    item = result["detected_damages"][0]
    assert item["estimated_cost"] == 0
    assert item["estimated_cost_min"] == 0
    assert item["estimated_cost_max"] == 0
    assert item["estimate_note"] == LOW_CONFIDENCE_NOTE
    assert result["estimated_cost_min"] == result["estimated_cost_max"] == 0


def test_moderate_table_rates_are_marked_uncalibrated():
    result = estimate_damage_costs([
        _detection("glass_shatter", 0.9, (0, 0, 250, 200)),
    ])

    item = result["detected_damages"][0]
    assert item["severity"] == "Moderate"
    assert item["estimated_cost"] > 0
    assert item["estimate_note"] == UNCALIBRATED_NOTE
