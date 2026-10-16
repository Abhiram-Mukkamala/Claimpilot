# Model Evaluation Scores — Imported Baseline

**Source:** original `shreyasshah707/ClaimPilot` branch `models`, commit `4c4f8eadc380a1a6458bf0a2905c9ffedb214251`.

**Provenance warning:** these are the scores documented in the source branch's README. They were not rerun during this migration and have not been independently verified as part of the October 2026 release checks. Do not present them as fresh benchmark results.

| Model | Reported role | Reported mAP50 | Reported mAP50–95 | Dataset notes from source |
|---|---|---:|---:|---|
| YOLOv11m (T1.3) | Photo-mode detector | 64.8% | 50.4% | CarDD; source README reports 2,816 images and a frozen 70/20/10 train/validation/test split |
| RT-DETR-L (T3.1v2) | Video-mode detector | 69.1% | 46.7% | Source README says it uses the v2 `cardd_finetune_v2` run; original T3.1 run retained only as reference |

## Damage classes reported

`crack`, `dent`, `glass shatter`, `lamp broken`, `scratch`, and `tire flat`.

## What was not transferred

Model checkpoints and test datasets are not present in this branch. The source runner expects local checkpoint/data paths and can download some model dependencies at runtime. Keep datasets and locally produced result files out of Git unless they are approved, small, and non-sensitive.

## Release use

Use these values as historical reference only. Before using them in a public demo or an insurer-facing claim, rerun evaluation against the intended fixed test split, record the exact checkpoint hashes and dependency versions, and save machine-generated metrics/logs alongside the run metadata.
