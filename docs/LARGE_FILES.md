# Large Files Report

## Tracked Files Over 50 MB

| File | Size (bytes) | Size (human-readable) | Status |
|---|---|---|---|
| `insurance-pro/backend/app/models/weights/rt-detr.pt` | 66,248,189 | 63,248,189 bytes | Tracked, should use Git LFS |
| `insurance-pro/backend/app/models/weights/yolov11m.pt` | 40,511,404 | 40,511,404 bytes | Tracked, should use Git LFS |

## All .pt/.pth/.onnx Files

| File | Size (bytes) | Size (human-readable) | Tracked |
|---|---|---|---|
| `insurance-pro/backend/app/models/weights/rt-detr.pt` | 66,248,189 | 66,248,189 bytes | Yes |
| `insurance-pro/backend/app/models/weights/yolov11m.pt` | 40,511,404 | 40,511,404 bytes | Yes |

**Total model weights: 106,759,593 bytes (106.8 MB)**

## Git LFS Recommendation

Both weight files (`rt-detr.pt` and `yolov11m.pt`) exceed 50 MB and are currently tracked in Git, which will bloat the repository size and slow down clones.

**Recommended actions:**

1. **Install Git LFS** on all developer machines:
   ```bash
   git lfs install
   ```

2. **Track weight files with LFS:**
   ```bash
   git lfs track "*.pt"
   git lfs track "*.pth"
   git lfs track "*.onnx"
   ```

3. **Migrate existing files:**
   ```bash
   git add .gitattributes
   git add insurance-pro/backend/app/models/weights/*.pt
   git commit -m "Migrate weight files to Git LFS"
   git lfs push --all
   ```

4. **Update `.gitattributes`:**
   ```gitattributes
   # ML model weights
   *.pt filter=lfs diff=lfs merge=lfs -text
   *.pth filter=lfs diff=lfs merge=lfs -text
   *.onnx filter=lfs diff=lfs merge=lfs -text
   ```

5. **Consider `.gitignore` alternative:** If Git LFS is not desired, add weight files to `.gitignore` and use a separate download mechanism (e.g., cloud storage, package manager, or CI artifact).

**Note:** Total size of model weights: ~107 MB. Without LFS, each clone will download this data, significantly increasing repository size and clone time.
