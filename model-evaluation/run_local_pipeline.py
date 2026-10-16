#!/usr/bin/env python3
"""
ClaimPilot -- Local Photo Mode Pipeline Runner

Runs the full YOLOv11m + Depth Anything V2 + SAM2 + DSINE pipeline (built in
T1.3/T1.4, T2.1, T2.2, T2.3, T2.4) on your own photos, outside Colab.

--------------------------------------------------------------------------
SETUP
--------------------------------------------------------------------------
1. From Google Drive, copy this folder structure to your local machine:

     ClaimPilot/
       scripts/
         checkpoint_utils.py
         inference.py
         depth_estimation.py
         segmentation.py
         surface_normals.py
         photo_pipeline.py
       models/
         yolov11m/
           best.pt

   Easiest way: open drive.google.com, select the ClaimPilot/scripts and
   ClaimPilot/models/yolov11m folders, right-click > Download (this zips them
   for you), then unzip locally preserving that structure. (If you use the
   Google Drive desktop app, the files are already on your local disk under
   your Drive mount point -- just point --project-root at that path instead
   of copying anything.)

2. Create a clean environment and install dependencies:

     python -m venv claimpilot-local
     # Windows: claimpilot-local\\Scripts\\activate
     # Linux/Mac: source claimpilot-local/bin/activate

     # RTX 50-series (Blackwell) GPUs need CUDA 12.8+ wheels -- install torch
     # FIRST, separately, from the cu128 index:
     pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
     # (On an older, non-Blackwell NVIDIA GPU, skip the above and just let the
     # requirements.txt below install a normal torch build instead.)

     pip install -r requirements.txt

3. Put your own test photos in a folder, e.g. ./my_photos/

4. Run:

     python run_local_pipeline.py --images ./my_photos --project-root ./ClaimPilot --output ./local_results

--------------------------------------------------------------------------
VRAM NOTE (12GB card)
--------------------------------------------------------------------------
Colab's T4 has 16GB; this laptop's RTX 5070 has 12GB. Defaults below use the
smaller Depth Anything V2 and SAM2 checkpoints to leave headroom. If you have
room to spare, pass --depth-model ".../Depth-Anything-V2-Base-hf" and
--sam2-model "facebook/sam2.1-hiera-base-plus" to match what was used on Colab.
"""
import argparse
import json
import os
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Run ClaimPilot's photo-mode pipeline locally.")
    parser.add_argument("--images", required=True,
                         help="Path to a single image file or a folder of images")
    parser.add_argument("--project-root", default="./ClaimPilot",
                         help="Local ClaimPilot folder (must contain scripts/ and models/yolov11m/best.pt)")
    parser.add_argument("--output", default="./local_results",
                         help="Where to write per-image JSON results")
    parser.add_argument("--plate-width-mm", type=float, default=520.0,
                         help="Real-world license plate width used for metric calibration")
    parser.add_argument("--depth-model", default="depth-anything/Depth-Anything-V2-Small-hf",
                         help="Smaller variant by default for a 12GB card; use '...-Base-hf' with more headroom")
    parser.add_argument("--sam2-model", default="facebook/sam2.1-hiera-small",
                         help="Smaller variant by default for a 12GB card; use 'hiera-base-plus' with more headroom")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO detection confidence threshold")
    parser.add_argument("--enable-tire-ocr", action="store_true",
                         help="Load easyocr for Tier 2a exact tire-code reading (slower first run, "
                              "downloads an OCR model). Without this flag, Tier 2 still runs but uses "
                              "a generic tire diameter instead of reading the sidewall code.")
    parser.add_argument("--enable-metric-depth-fallback", action="store_true",
                         help="Load Depth-Anything-V2's metric-finetuned checkpoint as Tier 3 (true "
                              "last resort, used only if neither a plate nor a wheel calibrates the "
                              "scale). Off by default to save VRAM/download time on a 12GB card; "
                              "turn on if your photos often lack both a visible plate and a visible "
                              "wheel -- without it, calibration can still return null on those photos.")
    args = parser.parse_args()

    scripts_dir = os.path.join(args.project_root, "scripts")
    if not os.path.isdir(scripts_dir):
        sys.exit(f"ERROR: {scripts_dir} not found. Check --project-root points at your local ClaimPilot copy.")
    sys.path.insert(0, scripts_dir)

    import torch
    import inference
    import depth_estimation
    import segmentation
    import surface_normals
    import photo_pipeline
    from ultralytics import YOLO

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"GPU : {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    else:
        print("WARNING: no CUDA GPU detected -- this will be slow on CPU.")

    yolo_path = os.path.join(args.project_root, "models", "yolov11m", "best.pt")
    if not os.path.exists(yolo_path):
        sys.exit(f"ERROR: YOLO model not found at {yolo_path} -- did you copy it from Drive?")

    print("\nLoading models (first run downloads Depth Anything V2 / SAM2 / DSINE weights "
          "to your local Hugging Face / Torch Hub cache -- one-time cost)...")

    yolo_model = YOLO(yolo_path)
    yolo_model.to(device)
    print("  YOLOv11m loaded")

    depth_processor, depth_model = depth_estimation.load_depth_model(args.depth_model, device=device)
    print(f"  {args.depth_model} loaded")

    sam2_processor, sam2_model = segmentation.load_sam2(args.sam2_model, device=device)
    print(f"  {args.sam2_model} loaded")

    # Optional never-null calibration fallbacks (Tier 2a: tire-code OCR, Tier 3: metric
    # depth prior) -- see depth_estimation.calibrate_metric_depth_tiered(). Both are
    # off by default here to keep the local runner's footprint small; Tier 1 (plate)
    # and Tier 2b (generic wheel diameter, no OCR needed) always run regardless.
    ocr_reader = None
    if args.enable_tire_ocr:
        try:
            import easyocr
            ocr_reader = easyocr.Reader(["en"], gpu=(device == "cuda"))
            print("  easyocr loaded (Tier 2a: exact tire-code reading enabled)")
        except Exception as e:
            print(f"  WARNING: easyocr failed to load ({e}) -- Tier 2 will use generic tire diameter only")

    metric_depth_processor, metric_depth_model = None, None
    if args.enable_metric_depth_fallback:
        try:
            metric_depth_processor, metric_depth_model = depth_estimation.load_metric_depth_model(device=device)
            print("  Depth-Anything-V2 metric checkpoint loaded (Tier 3: metric depth prior enabled)")
        except Exception as e:
            print(f"  WARNING: metric depth model failed to load ({e}) -- calibration will stop at Tier 2")

    # hugoycj/DSINE-hub hardcodes torch.device("cuda") in more than one file within the
    # cloned repo -- patching only hubconf.py fixed model *loading* but not necessarily
    # the actual inference call (infer_cv2), which likely lives in a separate module file
    # and has its own hardcoded reference. Scan and patch every .py file in the cached
    # repo directory, not just hubconf.py. Rather than monkey-patch torch.device globally
    # (which broke isinstance() checks deep inside torch's own checkpoint-loading code --
    # a real bug in an earlier version of this fix), this is a small, surgical, idempotent
    # text replacement applied file-by-file.
    import glob

    def _find_dsine_repo_dir():
        hub_dir = torch.hub.get_dir()
        matches = glob.glob(os.path.join(hub_dir, "hugoycj_DSINE-hub_*"))
        return matches[0] if matches else None

    def _patch_dsine_repo_for_cpu():
        repo_dir = _find_dsine_repo_dir()
        if repo_dir is None:
            return False
        any_changed = False
        replacements = [
            ('torch.device("cuda")', 'torch.device("cuda" if torch.cuda.is_available() else "cpu")'),
            ("torch.device('cuda')", "torch.device('cuda' if torch.cuda.is_available() else 'cpu')"),
        ]
        for py_path in glob.glob(os.path.join(repo_dir, "**", "*.py"), recursive=True):
            with open(py_path, "r", encoding="utf-8") as f:
                content = f.read()
            patched = content
            for old, new in replacements:
                patched = patched.replace(old, new)
            if patched != content:
                with open(py_path, "w", encoding="utf-8") as f:
                    f.write(patched)
                print(f"  [patch] Fixed hardcoded CUDA device in {py_path}")
                any_changed = True
        return any_changed

    _patch_dsine_repo_for_cpu()  # handles the case where it's already cached from a prior run
    try:
        dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
    except Exception as e:
        # First-ever run: the repo wasn't cached yet when we tried to patch it above, so
        # this attempt downloaded it fresh (unpatched) and hit the same crash. Patch the
        # now-cached files and retry once.
        print(f"  [patch] DSINE load failed ({e}); patching newly-downloaded repo files and retrying...")
        if _patch_dsine_repo_for_cpu():
            dsine_model = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
        else:
            raise
    if hasattr(dsine_model, "to"):
        dsine_model = dsine_model.to(device)
    elif hasattr(dsine_model, "model") and hasattr(dsine_model.model, "to"):
        dsine_model.model = dsine_model.model.to(device)
    print("  DSINE loaded")

    if device == "cuda":
        print(f"\nGPU memory allocated: {torch.cuda.memory_allocated() / (1024**3):.2f} GB "
              f"/ {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB total")

    if os.path.isdir(args.images):
        image_paths = [
            os.path.join(args.images, f) for f in sorted(os.listdir(args.images))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        if not image_paths:
            sys.exit(f"ERROR: no .jpg/.jpeg/.png files found in {args.images}")
    elif os.path.isfile(args.images):
        image_paths = [args.images]
    else:
        sys.exit(f"ERROR: {args.images} is not a file or directory")

    os.makedirs(args.output, exist_ok=True)
    print(f"\nProcessing {len(image_paths)} image(s)...\n")

    all_results = {}
    for image_path in image_paths:
        stem = os.path.splitext(os.path.basename(image_path))[0]
        t0 = time.time()
        try:
            report = photo_pipeline.analyze_photo(
                image_path, yolo_model, depth_processor, depth_model,
                sam2_processor, sam2_model, dsine_model,
                plate_width_mm=args.plate_width_mm, conf=args.conf, device=device,
                ocr_reader=ocr_reader, metric_depth_processor=metric_depth_processor,
                metric_depth_model=metric_depth_model,
            )
        except Exception as e:
            print(f"{stem:20s}  FAILED: {e}")
            continue

        out_path = os.path.join(args.output, f"{stem}.json")
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)
        all_results[stem] = report

        summary = report["summary"]
        elapsed = time.time() - t0
        print(f"{stem:20s}  {elapsed:5.2f}s  "
              f"instances={summary['num_instances']}  classes={summary['classes_detected']}  "
              f"total_area_cm2={summary['total_damage_area_cm2']}")

    print(f"\n✅ Done. {len(all_results)}/{len(image_paths)} succeeded. Results in {args.output}/")


if __name__ == "__main__":
    main()
