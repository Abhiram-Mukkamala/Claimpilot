"""Tests for the optional vision pipeline integration.

These tests verify that:
1. The vision package exists with the expected module structure.
2. When vision dependencies are available, VisionPipeline exposes the
   expected run() interface.
3. All existing ai_runner tests continue to pass (covered by test_ai_runner.py).
"""

import os

import pytest


def test_vision_package_structure():
    """The vision package exists with expected submodules."""
    # tests/ is one level below backend/, so backend dir is parent of tests dir
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vision_dir = os.path.join(backend_dir, "app", "services", "vision")
    assert os.path.isdir(vision_dir), f"Vision package not found at {vision_dir}"

    expected_files = ["__init__.py", "segmentation.py", "surface_normals.py",
                      "depth_estimation.py", "inference.py", "temporal_consistency.py",
                      "vision_pipeline.py"]
    for fname in expected_files:
        fpath = os.path.join(vision_dir, fname)
        assert os.path.isfile(fpath), f"Missing vision module: {fname}"


def test_vision_pipeline_has_run_interface():
    """VisionPipeline.run() has the expected signature."""
    try:
        from app.services.vision import VisionPipeline
    except ImportError:
        pytest.skip("Vision dependencies (torch/transformers/cv2/numpy) not installed")

    import inspect
    sig = inspect.signature(VisionPipeline.run)
    params = list(sig.parameters.keys())
    assert "image_path" in params
    assert "detections" in params


def test_vision_pipeline_device_default_cpu():
    """VisionPipeline defaults to CPU device."""
    try:
        from app.services.vision import VisionPipeline
    except ImportError:
        pytest.skip("Vision dependencies not installed")

    vp = VisionPipeline()
    assert vp.device == "cpu"


def test_ai_runner_vision_available_flag():
    """ai_runner exposes _VISION_AVAILABLE flag reflecting ML dependency presence."""
    import app.services.ai_runner as ai_runner
    # Flag is a boolean (True if torch/transformers available, False otherwise)
    assert isinstance(ai_runner._VISION_AVAILABLE, bool)
    # Core pipeline is callable regardless
    assert callable(ai_runner.trigger_ai_assessment)
    assert callable(ai_runner.get_models)
    assert callable(ai_runner._get_vision_pipeline)