# Model weights

Both model-weight blobs are present in the release snapshot:

- `rt-detr.pt` — SHA `17733554692bcd44570ab2347a21d73d82591f42`
- `yolov11m.pt` — SHA `578f718b04478638652668ba4411aa717405bb9b`

They were referenced from Git objects already available in the destination repository's `claimpilotayaan` branch. The files were not re-uploaded by the migration script. After cloning, verify that both files are present at this directory before running inference.
