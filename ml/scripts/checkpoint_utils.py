# Reusable checkpoint save/resume helper for ClaimPilot training notebooks.
# Writes to Google Drive so progress survives Colab disconnects / usage-limit lockouts.
import os
import glob
import time
import torch


def save_checkpoint(model, optimizer, epoch, extra=None, checkpoint_dir=None,
                     task_name="task", keep_last=3):
    # Save a training checkpoint to Drive and prune old ones.
    #
    # Args:
    #   model: a torch.nn.Module (or any object with .state_dict())
    #   optimizer: a torch.optim.Optimizer (or any object with .state_dict()), or None
    #   epoch: int, the epoch/step index just completed
    #   extra: optional dict of extra fields to store (e.g. {"best_map": 0.61})
    #   checkpoint_dir: directory to write into (typically PROJECT_ROOT/models/checkpoints)
    #   task_name: short id used in the filename, e.g. "yolov11m_cardd"
    #   keep_last: how many recent checkpoints to retain (older ones are deleted)
    os.makedirs(checkpoint_dir, exist_ok=True)
    payload = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
        "extra": extra or {},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ckpt_path = os.path.join(checkpoint_dir, f"{task_name}_epoch{epoch:04d}.pt")
    torch.save(payload, ckpt_path)

    # Also write/overwrite a stable "latest" pointer for easy resume
    latest_path = os.path.join(checkpoint_dir, f"{task_name}_latest.pt")
    torch.save(payload, latest_path)

    # Prune old numbered checkpoints beyond keep_last (latest.pt is always kept)
    numbered = sorted(glob.glob(os.path.join(checkpoint_dir, f"{task_name}_epoch*.pt")))
    for old_ckpt in numbered[:-keep_last]:
        os.remove(old_ckpt)

    print(f"[checkpoint] saved epoch {epoch} -> {ckpt_path}")
    return ckpt_path


def find_latest_checkpoint(checkpoint_dir, task_name="task"):
    # Return the path to the most recent checkpoint for this task, or None.
    latest_path = os.path.join(checkpoint_dir, f"{task_name}_latest.pt")
    if os.path.exists(latest_path):
        return latest_path
    numbered = sorted(glob.glob(os.path.join(checkpoint_dir, f"{task_name}_epoch*.pt")))
    return numbered[-1] if numbered else None


def load_checkpoint(model, optimizer=None, checkpoint_dir=None, task_name="task",
                     map_location="cuda"):
    # Load the latest checkpoint for this task, if one exists.
    #
    # Returns: (start_epoch, extra_dict). start_epoch is 0 and extra_dict is {} if
    # nothing was found, so callers can unconditionally do:
    #     start_epoch, extra = load_checkpoint(...)
    #     for epoch in range(start_epoch, num_epochs): ...
    ckpt_path = find_latest_checkpoint(checkpoint_dir, task_name)
    if ckpt_path is None:
        print(f"[checkpoint] no existing checkpoint for '{task_name}' -- starting fresh")
        return 0, {}

    payload = torch.load(ckpt_path, map_location=map_location)
    model.load_state_dict(payload["model_state_dict"])
    if optimizer is not None and payload.get("optimizer_state_dict") is not None:
        optimizer.load_state_dict(payload["optimizer_state_dict"])

    start_epoch = payload["epoch"] + 1
    print(f"[checkpoint] resumed '{task_name}' from {ckpt_path} -- continuing at epoch {start_epoch}")
    return start_epoch, payload.get("extra", {})
