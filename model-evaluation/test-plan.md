# Model Evaluation Test Plan

This is a **planned test matrix**, not a claim that these tests have already passed. The runner and photo/video pipeline scripts were imported from the original `models` branch.

| Case | Input / stage | Expected evidence to capture |
|---|---|---|
| EVAL-PHOTO-01 | Single clear damaged-vehicle photo | Detection classes, confidences, bounding boxes, per-stage errors, elapsed time |
| EVAL-PHOTO-02 | Multiple damage regions in one photo | Instance count, class list, area and severity/geometry outputs, duplicate detection behavior where available |
| EVAL-PHOTO-03 | Photo without visible damage | Empty or low-confidence detections; no fabricated damage measurement |
| EVAL-CAL-01 | Photo with a visible license plate | Calibration method, confidence, and whether metric values are null or calibrated |
| EVAL-CAL-02 | Photo without plate but with visible wheel/tire | Fallback calibration method, confidence, limitations, metric outputs |
| EVAL-VIDEO-01 | Short walkaround video | Extracted keyframes, per-frame detections, timestamps and per-stage error records |
| EVAL-VIDEO-02 | Video with motion blur / poor lighting | Stage failures and warnings recorded explicitly; no silently fabricated measurements |
| EVAL-3D-01 | Video with enough visual parallax | SfM/depth-fusion/mesh artifacts, measurement outputs, and reconstruction warnings |
| EVAL-REPRO-01 | Re-run the same fixed input with the same checkpoints | Compare JSON outputs, model/checkpoint hashes, dependency versions, and timing variance |

## Required record for each executed run

- Run ID and UTC timestamp
- Input sample IDs (not private customer photos unless authorized)
- Dataset split and exact sample count
- Checkpoint SHA-256 hashes
- Python/package versions and device details
- Raw machine-generated metrics and per-stage errors
- Reviewer and disposition of unexpected results

**Pass/fail scores have not been recorded here** because a run was not executed as part of this port.
