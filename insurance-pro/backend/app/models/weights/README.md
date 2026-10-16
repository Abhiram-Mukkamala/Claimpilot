# Required model weights not included in this snapshot

This folder's model binaries were omitted because the connected migration interface cannot transfer binary Git blobs.

Restore these exact files from the source release-candidate branch before running AI inference:

- `rt-detr.pt`: https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/rt-detr.pt
- `yolov11m.pt`: https://raw.githubusercontent.com/shreyasshah707/ClaimPilot/test/e2e-demo-smoke/insurance-pro/backend/app/models/weights/yolov11m.pt

Do not consider AI inference validated until the weights are restored and the corresponding tests are run.
