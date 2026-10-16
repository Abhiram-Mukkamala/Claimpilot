> **Ported evaluation workspace.** This folder was copied from the original `models` branch (source commit `4c4f8eadc380a1a6458bf0a2905c9ffedb214251`). The scores documented below are inherited from that branch and were **not recomputed** during the port. Model checkpoints and test datasets are intentionally not committed here.

# ClaimPilot — Automated Motor Insurance Claim Processing

ClaimPilot is an AI-powered pipeline for processing motor insurance claims.
It takes a **photo** or a **video walkaround** of a damaged vehicle and produces
a structured JSON report with damage classification and physical measurements
(area, depth, volume, crease angle) — without requiring a human adjuster for
initial triage.

## Architecture

```
Input (Photo or Video)
        │
        ▼
┌───────────────────────────────────────────────┐
│              PHOTO MODE PIPELINE               │
│                                                 │
│  ┌─────────────┐   ┌───────────────────────┐   │
│  │  YOLOv11m   │   │   Depth Anything V2   │   │
│  │  (T1.3)     │   │   (T2.1)              │   │
│  │  6 damage   │   │  Relative depth map   │   │
│  │  classes    │   │  + metric calibration │   │
│  │  mAP50:65%  │   │  via license plate    │   │
│  └──────┬──────┘   └───────────────────────┘   │
│         ▼                                      │
│  ┌─────────────┐   ┌───────────────────────┐   │
│  │    SAM2     │   │        DSINE          │   │
│  │  (T2.2)     │   │        (T2.3)         │   │
│  │  Box-prompt │   │  Surface normal maps  │   │
│  │  masks,     │   │  + crease angle (θ°)  │   │
│  │  area       │   │                       │   │
│  └──────┬──────┘   └──────────┬────────────┘   │
│         └──────────┬──────────┘                │
│                     ▼                           │
│         photo_pipeline.analyze_photo() (T2.4)   │
└────────────────────│───────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────────┐
│             VIDEO MODE PIPELINE                │
│                                                 │
│  ┌─────────────┐   ┌───────────────────────┐   │
│  │   RT-DETR   │   │  Frame Extraction     │   │
│  │   (T3.1v2)  │   │  (T3.2)               │   │
│  │  mAP50:69%  │   │  Motion-based keyframes│  │
│  │             │   │  + synthetic parallax │   │
│  └─────────────┘   └───────────────────────┘   │
│                                                 │
│  ┌─────────────┐   ┌───────────────────────┐   │
│  │   COLMAP    │   │  Dense Point Cloud    │   │
│  │   SfM       │──▶│  (T3.4)               │   │
│  │   (T3.3)    │   │  Open3D depth-fusion  │   │
│  │  Camera     │   │  (monocular depth +   │   │
│  │  poses +    │   │  recovered poses —    │   │
│  │  sparse pts │   │  see Limitations)      │   │
│  └─────────────┘   └──────────┬────────────┘   │
│                                ▼                │
│                     ┌───────────────────────┐   │
│                     │  Mesh Reconstruction  │   │
│                     │  (T4.1)               │   │
│                     │  Poisson surface →    │   │
│                     │  watertight-ish OBJ   │   │
│                     └──────────┬────────────┘   │
│                                ▼                │
│                     ┌───────────────────────┐   │
│                     │  3D Measurement       │   │
│                     │  (T4.2)               │   │
│                     │  Raycast + plane-fit  │   │
│                     │  depth/area/volume/   │   │
│                     │  crease angle         │   │
│                     └──────────┬────────────┘   │
│                                ▼                │
│              video_pipeline.run_video_          │
│              mode_pipeline()  (T4.3)            │
└─────────────────────────────────────────────────┘
          
```

---

## Damage Classes

| Class | Description |
|-------|-------------|
| `crack` | Surface cracks in panels or glass |
| `dent` | Deformation/denting of body panels |
| `glass shatter` | Shattered or broken glass |
| `lamp broken` | Damaged head/tail lamps |
| `scratch` | Paint scratches |
| `tire flat` | Flat or damaged tyres |

---

## Detection Models

| Model | Architecture | mAP50 | mAP50-95 | Use case |
|-------|-------------|-------|----------|----------|
| YOLOv11m (T1.3) | CNN-based, Ultralytics | 64.8% | 50.4% | Photo mode |
| RT-DETR-L (T3.1v2) | Transformer-based, Ultralytics | **69.1%** | 46.7% | Video mode |

Both fine-tuned on **CarDD** (2,816 images, 6 damage classes) using the same frozen
train/val/test split (70/20/10). RT-DETR-L's production weights are from the **v2**
training run (`cardd_finetune_v2`) — the original run (`T3_1_Finetune_RTDETR.ipynb`)
was undertrained due to early-stopping `patience` and is kept only for reference;
**always use the v2 run's `best.pt`.**

---

## Photo Mode Pipeline Output (JSON schema)

`scripts/photo_pipeline.py → analyze_photo()` returns:

```json
{
  "image_path": "path/to/image.jpg",
  "image_size": [1146, 859],
  "processed_at": "2026-09-07T21:32:20",
  "models": {
    "detection": "YOLOv11m (ClaimPilot fine-tuned)",
    "depth": "Depth Anything V2",
    "segmentation": "SAM2",
    "normals": "DSINE"
  },
  "calibration": {
    "depth_metric": {
      "status": "calibrated",
      "method": "plate | wheel_tire_code_ocr | wheel_generic_diameter | metric_depth_prior",
      "confidence": "high | medium | low"
    }
  },
  "damage_instances": [
    {
      "instance_id": 0,
      "class_name": "dent",
      "confidence": 0.83,
      "bbox_xyxy": [0, 0, 1009, 767],
      "mask_iou_score": 0.91,
      "area_px": 4213,
      "area_cm2": 38.7,
      "crease_angle_deg": 12.4,
      "crease_status": "computed",
      "stage_errors": {}
    }
  ],
  "summary": {
    "num_instances": 1,
    "classes_detected": ["dent"],
    "total_damage_area_cm2": 38.7
  },
  "timing_sec": { "detection": 0.22, "depth": 0.79, "segmentation": 3.04, "normals": 14.1, "total": 18.6 }
}
```

- `area_cm2` / `depth_metric` are calibrated via a 3-tier never-null fallback chain
  (plate → wheel/tire → metric depth model prior — see Known Limitations #4 below), so
  they're `null` now only if every tier fails outright (e.g. the depth stage itself
  errors); `area_px` is always reported regardless.
- `stage_errors` is `{}` when all four models succeed — one stage failing degrades that
  field to `null` with an error note rather than crashing the whole result.

---

## Video Mode Pipeline Output (JSON schema)

`scripts/video_pipeline.py → run_video_mode_pipeline()` returns (and writes to
`outputs/measurements/<video_name>_pipeline_result.json`):

```json
{
  "video_name": "damage_walkround",
  "processed_at": "2026-10-08T21:58:05",
  "reference_frame": "frame_002.jpg",
  "image_size": [1000, 751],
  "models": {
    "detection": "RT-DETR-L (ClaimPilot fine-tuned, T3.1v2)",
    "reconstruction": "COLMAP SfM (T3.3) + dense point cloud (T3.4) + Poisson mesh (T4.1)"
  },
  "calibration": {
    "status": "calibrated",
    "method": "plate | tire_code_ocr | wheel_generic_diameter | metric_depth_prior",
    "confidence": "high | medium | low",
    "mm_per_unit": 0.847,
    "frame_used": "frame_002.jpg"
  },
  "damage_instances": [
    {
      "instance_id": 0,
      "class_name": "scratch",
      "confidence": 0.79,
      "bbox_xyxy": [543.0, 522.4, 752.5, 751.4],
      "depth_mm": 3.1,
      "area_cm2": 142.6,
      "volume_cm3": 4.4,
      "crease_angle_deg": 14.08,
      "stage_errors": {}
    }
  ],
  "summary": {
    "num_instances": 5,
    "classes_detected": ["lamp broken", "scratch"],
    "total_damage_area_cm2": 612.3
  },
  "stage_errors": {},
  "timing_sec": { "detection": 4.2, "calibration": 0.9, "measurement": 1.1, "total": 6.5 }
}
```

- Same never-null calibration chain as Photo Mode (see `scripts/scale_calibration.py`):
  Tier 1 plate → Tier 2 wheel/tire (exact sidewall code via OCR, or a generic tire
  diameter) → Tier 3 metric depth model prior. `depth_mm`/`area_cm2`/`volume_cm3` are
  `null` now only if every tier fails on every registered frame (expected to be rare -
  previously the common case under plate-only calibration). `calibration.confidence`
  tells you how much to trust the result: `high` (plate) down to `low` (metric depth
  prior - a learned estimate, treat as order-of-magnitude). `crease_angle_deg` (a **3D**
  surface-tilt measurement, different from Photo Mode's 2D DSINE-based crease angle —
  see Limitations) doesn't need calibration and is always reported.
- `stage_errors` (top-level) covers pipeline-wide failures (e.g. detector weights not
  found); each instance's own `stage_errors` covers per-instance measurement failures
  (e.g. a bbox over a hole in the mesh) — one bad instance never crashes the others.

---

## ⚠️ Known Limitations (read before trusting the numbers)

Video Mode's 3D reconstruction took a longer path than planned — worth understanding
before using its output for anything beyond a demo:

1. **Dense point cloud is NOT true multi-view stereo.** OpenMVS (the originally planned
   tool) requires a from-source C++ build with a long, fragile dependency chain and was
   abandoned. `pycolmap`'s own native dense stereo (`patch_match_stereo`) was tried next
   but its PyPI wheels — even `pycolmap-cuda12` — don't ship a CUDA-built dense module
   (`mvs.cc:51: requires CUDA or HIP`, even on a T4). **T3.4 falls back to fusing
   per-frame Depth Anything V2 monocular depth** (independently calibrated per view against
   COLMAP's sparse points, then back-projected and voxel-downsampled). This is NOT
   geometrically multi-view-consistent — visualizing it shows repeated "ghost" surface
   layers rather than one clean surface, because each video frame came from synthetic
   parallax of a single photo (see `parallax_synthesis.py`), so the monocular depth model
   produces nearly identical depth per frame from slightly different poses.
2. **The Poisson mesh (T4.1) is usually not strictly watertight.** This is a known Open3D/
   Poisson characteristic (self-intersecting slivers) that occurs even on clean synthetic
   test geometry, not specific to this noisy input. Edge/vertex-manifold checks are more
   reliable quality signals than `is_watertight()` here.
3. **Video Mode's `area_cm2`/`volume_cm3` are bbox-footprint, not mask-shaped.** RT-DETR
   outputs boxes, not masks (SAM2 isn't run on video frames), so these fields measure the
   rectangular bbox's footprint on the mesh — verified in testing to overstate a circular
   dent's true area by roughly 2x. `depth_mm` is accurate (validated to <1% error against
   synthetic ground truth) since it only depends on finding the deepest point, not the
   region's shape.
4. **Scale calibration is now a 3-tier never-null fallback chain, not plate-or-null.**
   A license plate alone leaves most real claims uncalibrated — the plate is often
   damaged, dirty, unphotographed, or at an angle the Haar cascade can't match, which is
   exactly when calibration matters most. `scripts/scale_calibration.py` (Video Mode) and
   `depth_estimation.calibrate_metric_depth_tiered()` (Photo Mode) now try, in order:
   **Tier 1 — plate** (highest confidence, ~520mm standard width); **Tier 2 — wheel/tire**
   (wheels are visible in nearly every vehicle photo and almost never the claimed damage;
   reads the exact tire sidewall size code, e.g. "205/55R16", via OCR and the ISO 4000
   formula when legible, else falls back to a generic ~660mm passenger-tire diameter);
   **Tier 3 — Depth-Anything-V2's metric-finetuned checkpoint**, used as a monocular
   absolute-depth prior with no reference object needed at all — the true last resort,
   flagged `confidence: "low"` since it's a learned estimate, not a measurement. Each
   result reports which tier fired (`calibration.method`) and how much to trust it
   (`calibration.confidence`), so `status: "skipped_no_reference_found"` is now expected
   to be rare rather than the common case. All three tiers were validated against
   synthetic ground truth (tire-code parsing against known reference diameters, Hough
   wheel detection against a synthetic circle image, and the median-ratio depth-prior fit
   recovering a known scale factor to <1% error) before being wired in.
5. **Video Mode measures one reference frame per damage instance** (the frame with the
   highest-confidence detection), not a cross-frame-verified measurement. Good enough for
   this project's approximate-measurement goal; a future improvement would measure across
   multiple frames and reconcile.

None of this blocks a demo — Photo Mode's measurements are solid, and Video Mode's
`depth_mm` and `crease_angle_deg` are reliable; just don't present Video Mode's
`area_cm2`/`volume_cm3` as precise, and expect `calibration.status` to be
`skipped_no_plate_detected` unless your walkaround video frames the plate.

---

## Repository Structure

```
ClaimPilot/
├── scripts/                           # Reusable Python modules (import these)
│   ├── checkpoint_utils.py            # Training checkpoint save/resume helpers
│   ├── inference.py                   # YOLOv11m detection 
│   ├── depth_estimation.py            # Depth Anything V2 + metric calibration 
│   ├── segmentation.py                # SAM2 box-prompted segmentation + area 
│   ├── surface_normals.py             # DSINE surface normals + crease angle 
│   ├── photo_pipeline.py              # End-to-end Photo Mode pipeline 
│   ├── temporal_consistency.py        # Frame-to-frame tracker for video mode 
│   ├── parallax_synthesis.py          # Synthetic-parallax frame generation 
│   ├── sfm_pipeline.py                # COLMAP Structure-from-Motion wrapper 
│   ├── dense_stereo_pipeline.py       # pycolmap native dense stereo attemp
│   ├── open3d_depth_fusion.py         # Dense point cloud fallback — ACTIVE PATH 
│   ├── mesh_reconstruction.py         # Poisson surface reconstruction → OBJ 
│   ├── mesh_measurement.py            # Raycasting + plane-fit 3D measurement 
│   ├── scale_calibration.py           # Never-null 3-tier scale calibration: plate →
│   │                                   wheel/tire → metric depth prior
│   └── video_pipeline.py              # End-to-end Video Mode pipeline 
│
├── models/
│   ├── yolov11m/best.pt               # Fine-tuned YOLOv11m weights (38MB) ← from Drive
│   └── rtdetr/best.pt                 # Fine-tuned RT-DETR-L weights, v2 run (66MB) ← from Drive
│
├── run_local_pipeline.py              # Local CLI runner for Photo Mode (CPU or GPU)
├── requirements.txt
└── README.md
```


## Quick Start — Photo Mode (runs locally, CPU or GPU)

###  Clone and install

```bash
git clone https://github.com/your-org/claimpilot.git
cd claimpilot

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# NVIDIA RTX 50-series (Blackwell, e.g. RTX 5070) — install torch from cu128 FIRST:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

pip install -r requirements.txt
```

###  Run inference on your own photos

```bash
python run_local_pipeline.py --images ./my_photos --project-root . --output ./results
```

Add `--enable-tire-ocr` and/or `--enable-metric-depth-fallback` to turn on Tier 2a (exact
tire-code OCR) and Tier 3 (metric depth model) of the never-null calibration chain — both
are off by default to keep the local runner's footprint small on a 12GB card; Tier 1
(plate) and Tier 2b (generic wheel diameter) always run regardless:

```bash
python run_local_pipeline.py --images ./my_photos --project-root . --output ./results \
    --enable-tire-ocr --enable-metric-depth-fallback
```

Or call the pipeline directly in Python:

```python
import sys
sys.path.insert(0, "scripts")

import torch
from ultralytics import YOLO
from photo_pipeline import analyze_photo
import depth_estimation, segmentation, surface_normals

device = "cuda" if torch.cuda.is_available() else "cpu"
yolo   = YOLO("models/yolov11m/best.pt").to(device)
d_proc, d_model = depth_estimation.load_depth_model(device=device)
s_proc, s_model = segmentation.load_sam2(device=device)
dsine  = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)

result = analyze_photo("path/to/car_damage.jpg", yolo, d_proc, d_model, s_proc, s_model, dsine, device=device)
import json; print(json.dumps(result, indent=2))
```

## Physical Measurements

| Measurement | Photo Mode source | Video Mode source | Notes |
|---|---|---|---|
| Damage area (px) | SAM2 mask | — | Photo Mode only; always available |
| Damage area (cm²) | Per-pixel depth-based (pinhole projection from calibrated depth map) | Bbox footprint on mesh + tiered calibration | Video Mode overstates vs. true shape — see Limitations |
| Depth (mm) | Tiered-calibrated metric depth map (not per-instance ΔZ) | Raycast + plane-fit ΔZ | Video Mode's `depth_mm` is validated <1% error |
| Volume (cm³) | — | Flat-prism approximation | Video Mode only |
| Crease angle (θ°) | DSINE surface normals (2D) | Plane-normal angle (3D) | Different definitions — both meaningful, not directly comparable |

**Calibration method (both modes):** a 3-tier never-null fallback chain — see Known
Limitations #4 above. Tier 1 is a standard license plate (~520mm wide), auto-detected via
an OpenCV Haar cascade; Tier 2 is a detected wheel/tire (exact sidewall size code via OCR,
or a generic diameter); Tier 3 is Depth-Anything-V2's metric-finetuned checkpoint, used
directly with no reference object needed. Photo Mode's area calibration additionally
derives `mm_per_pixel` **per instance** from that instance's own calibrated depth (via the
pinhole relation `mm_per_px = depth_mm / focal_length_px`) rather than assuming every
instance sits at the same distance as the plate — more accurate than the single global
scale factor used previously, and a free side effect of the depth map now always being
populated. Metric fields are `null` only if every tier fails; pixel/reconstruction-unit
values are always reported regardless.

---

## Temporal Consistency (Video Mode)

`scripts/temporal_consistency.py` provides a `TemporalTracker` class that:

- Matches RT-DETR detections across consecutive frames by IoU (same class required)
- Smooths bounding box coordinates and confidence via exponential moving average (`ema_alpha=0.6`)
- Suppresses single-frame false positives via a stability filter (`min_hits=2`)
- Drops tracks that disappear for too long (`max_misses=3`)

```python
from temporal_consistency import TemporalTracker

tracker = TemporalTracker(iou_threshold=0.3, ema_alpha=0.6, min_hits=2, max_misses=3)
for frame in video_frames:
    detections = run_rtdetr(frame)
    stable = tracker.update(detections)
```

---

## Dataset

**CarDD** (Car Damage Detection) — 2,816 images, 6 damage classes.

- Source: Wang et al., *CarDD: A New Dataset for Vision-Based Car Damage Detection*, IEEE TITS, 2024.
- License: non-commercial research / educational use only.
- Loaded via `fiftyone` from the HuggingFace mirror (`harpreetsahota/CarDD`).
- Frozen train/val/test split (70/20/10) stored in `state/split_manifest.json`.

## Citation

```bibtex
@article{wang2024cardd,
  title   = {CarDD: A New Dataset for Vision-Based Car Damage Detection},
  author  = {Wang, Xinkuang and Li, Wenjing and Wu, Zhongcheng},
  journal = {IEEE Transactions on Intelligent Transportation Systems},
  volume  = {24},
  number  = {7},
  pages   = {7202--7214},
  year    = {2024}
}
```
