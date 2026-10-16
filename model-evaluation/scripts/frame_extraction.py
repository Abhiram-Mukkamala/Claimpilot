# Reusable frame extraction for ClaimPilot video mode.
# Used by this notebook (T3.2) and by the video pipeline (T4.3).
import os
import cv2
import numpy as np


def get_video_info(video_path):
    # Returns basic metadata about a video file.
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = total_frames / fps if fps > 0 else 0
    cap.release()
    return {
        "total_frames": total_frames,
        "fps": fps,
        "width": width,
        "height": height,
        "duration_sec": duration_sec,
    }


def extract_uniform(video_path, out_dir, n_frames=15):
    # Extract n_frames evenly spaced frames from the video.
    # Returns a list of dicts: {frame_index, timestamp_sec, out_path}.
    info = get_video_info(video_path)
    total = info["total_frames"]

    indices = [int(round(i * (total - 1) / max(n_frames - 1, 1)))
               for i in range(n_frames)]
    indices = sorted(set(indices))

    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    results = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        fname = f"frame_{idx:06d}.jpg"
        out_path = os.path.join(out_dir, fname)
        cv2.imwrite(out_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        results.append({
            "frame_index": idx,
            "timestamp_sec": idx / info["fps"] if info["fps"] > 0 else 0,
            "out_path": out_path,
            "strategy": "uniform",
        })

    cap.release()
    return results


def extract_motion_based(video_path, out_dir, target_frames=15,
                          min_frames=10, max_frames=20,
                          motion_threshold_percentile=70):
    # Extract keyframes based on optical flow magnitude between consecutive frames.
    # Frames where the camera has moved significantly are preferred -- near-duplicate
    # frames from slow pans or pauses are skipped. This produces better input for COLMAP
    # than uniform sampling when the camera speed is uneven.
    #
    # motion_threshold_percentile: inter-frame flow magnitudes below this percentile are
    # considered "not enough motion" and those frames are skipped. Tuning this up means
    # fewer (but more distinct) keyframes; tuning it down means more frames.
    info = get_video_info(video_path)
    cap = cv2.VideoCapture(video_path)

    prev_gray = None
    flow_scores = []
    frame_idx = 0

    # Pass 1: compute inter-frame motion score for every frame
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
            )
            magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            flow_scores.append((frame_idx, float(magnitude.mean())))
        prev_gray = gray
        frame_idx += 1
    cap.release()

    if not flow_scores:
        # Very short video or single frame -- fall back to uniform
        return extract_uniform(video_path, out_dir, n_frames=target_frames)

    # Pass 2: select frames greedily by motion score until we reach target count
    threshold = np.percentile([s for _, s in flow_scores], motion_threshold_percentile)
    candidate_indices = [idx for idx, score in flow_scores if score >= threshold]

    # Trim or pad to [min_frames, max_frames] range
    step = max(1, len(candidate_indices) // target_frames)
    selected = candidate_indices[::step]
    selected = selected[:max_frames]
    if len(selected) < min_frames:
        # Not enough motion-distinct frames -- top up with uniform samples
        uniform_indices = [int(round(i * (frame_idx - 1) / max(target_frames - 1, 1)))
                           for i in range(target_frames)]
        combined = sorted(set(selected + uniform_indices))[:max_frames]
        selected = combined

    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    results = []

    for idx in sorted(selected):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        fname = f"frame_{idx:06d}.jpg"
        out_path = os.path.join(out_dir, fname)
        cv2.imwrite(out_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        score = next((s for i, s in flow_scores if i == idx), None)
        results.append({
            "frame_index": idx,
            "timestamp_sec": idx / info["fps"] if info["fps"] > 0 else 0,
            "motion_score": score,
            "out_path": out_path,
            "strategy": "motion_based",
        })

    cap.release()
    return results


def create_synthetic_video(image_paths, out_path, fps=15, jitter_px=20, scale_range=(0.97, 1.03)):
    # Create a synthetic walkround video from a list of still images by applying
    # small random camera jitter (translation + rotation + scale) to each frame.
    # Used when no real video is available, so T3.2/T3.3 can be tested end-to-end.
    import random
    random.seed(42)
    if not image_paths:
        raise ValueError("image_paths is empty -- provide at least one source image.")
    ref = cv2.imread(image_paths[0])
    h, w = ref.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    for img_path in image_paths:
        img = cv2.imread(img_path)
        if img is None:
            continue
        # Repeat each source image for a few frames with varying jitter
        for _ in range(fps // len(image_paths) + 3):
            dx = random.uniform(-jitter_px, jitter_px)
            dy = random.uniform(-jitter_px, jitter_px)
            angle = random.uniform(-2, 2)
            scale = random.uniform(*scale_range)
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
            M[0, 2] += dx
            M[1, 2] += dy
            jittered = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
            writer.write(jittered)
    writer.release()
    return out_path
