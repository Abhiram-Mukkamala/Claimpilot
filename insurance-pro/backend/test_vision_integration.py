"""Offline integration tests for the ported v3 vision pipeline.

No model weights are downloaded: heavy stages (SAM2, DSINE, Depth Anything) are
replaced with deterministic stubs, while the real scale calibration, indentation
measurement, aggregation and ai_runner payload-building code is exercised.

Run:  python -m pytest test_vision_integration.py
"""
import asyncio
import importlib
import importlib.util
import inspect
import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
from PIL import Image, ImageDraw

BACKEND = Path(__file__).resolve().parent
for _name, _value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}.items():
    os.environ[_name] = _value

if "jose" not in sys.modules and importlib.util.find_spec("jose") is None:
    _jose = ModuleType("jose")

    class _JWTError(Exception):
        pass

    _jose.jwt = object()
    _jose.JWTError = _JWTError
    sys.modules.setdefault("jose", _jose)

# Avoid app.services' eager model/email imports (same approach as tests/test_ai_runner.py).
_services = ModuleType("app.services")
_services.__path__ = [str(BACKEND / "app" / "services")]
sys.modules.setdefault("app.services", _services)

from app.services.vision import depth_estimation as de  # noqa: E402
from app.services.vision import inference as inf  # noqa: E402
from app.services.vision import scale_calibration as sc  # noqa: E402
from app.services.vision import surface_normals as sn  # noqa: E402
from app.services.vision import vision_pipeline as vp  # noqa: E402


# --------------------------------------------------------------------------- helpers
def _photo(tmp_path, size=(160, 120)):
    path = tmp_path / "photo.jpg"
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle((40, 30, 100, 80), fill="gray")
    image.save(path, format="JPEG")
    return str(path)


def _dented_depth(shape=(120, 160), base=2000.0, dent=25.0):
    depth = np.full(shape, base, dtype=np.float32)
    mask = np.zeros(shape, dtype=bool)
    mask[40:80, 60:100] = True
    depth[mask] += dent
    return depth, mask


# --------------------------------------------------------------------------- scale_calibration
def test_scale_calibration_exports_and_tire_math():
    assert len({sc.TIER_1_PLATE, sc.TIER_2_WHEEL, sc.TIER_3_FALLBACK}) == 3
    parsed = sc.parse_tire_code("Tyre 205 / 55 R16 91V")
    assert parsed["rim_diameter_in"] == 16
    assert parsed["diameter_mm"] == pytest.approx(16 * 25.4 + 2 * 205 * 0.55)
    assert sc.parse_tire_code("999/10R99") is None  # outside sanity bounds
    assert sc.parse_tire_code("no code here") is None


def test_camera_intrinsics_and_read_tire_code_without_ocr(tmp_path):
    k = sc.estimate_camera_intrinsics(_photo(tmp_path), 160, 120)
    assert k["fx"] == pytest.approx(160 / (2 * np.tan(np.radians(30))))
    assert k["cx"] == 80 and k["cy"] == 60
    assert k["method"].startswith("assumed_hfov")
    assert sc.read_tire_code(np.zeros((50, 50, 3), np.uint8), ocr_reader=None) is None


def test_wheel_calibration_runs_without_colmap(monkeypatch):
    # Tier 2 must not import pycolmap/open3d/mesh_measurement.
    rel = np.full((200, 300), 2.0, dtype=np.float32)
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    monkeypatch.setattr(sc, "detect_wheel_circles", lambda _img: [(150.0, 100.0, 40.0)])
    depth, info = sc.calibrate_from_wheel(rel, image, focal_length_px=250.0)
    assert info["status"] == "calibrated"
    assert info["tier"] == sc.TIER_2_WHEEL
    assert info["method"] == "wheel_generic_diameter" and info["confidence"] == "low"
    expected_distance = sc.GENERIC_TIRE_DIAMETER_MM * 250.0 / 80.0
    assert depth[100, 150] == pytest.approx(expected_distance)
    for banned in ("pycolmap", "open3d", "mesh_measurement"):
        assert banned not in sys.modules

    monkeypatch.setattr(sc, "detect_wheel_circles", lambda _img: [])
    assert sc.calibrate_from_wheel(rel, image, 250.0)[0] is None


# --------------------------------------------------------------------------- depth / indentation
def test_max_indentation_is_nonzero_and_clamped():
    depth, mask = _dented_depth(dent=25.0)
    peak = de.compute_max_indentation_mm(depth, mask)
    assert peak == pytest.approx(25.0, abs=0.5)

    huge, mask = _dented_depth(dent=900.0)
    assert de.compute_max_indentation_mm(huge, mask) == 150.0
    assert de.compute_max_indentation_mm(None, mask) is None
    assert de.compute_max_indentation_mm(depth, np.zeros_like(mask)) is None


def test_run_depth_estimation_writes_both_keys(monkeypatch, tmp_path):
    depth, mask = _dented_depth(dent=18.0)
    monkeypatch.setattr(de, "estimate_relative_depth", lambda *a, **k: depth)
    monkeypatch.setattr(
        de, "calibrate_metric_depth_tiered",
        lambda rel, *a, **k: (rel, {"status": "calibrated", "method": "plate", "confidence": "high"}),
    )
    out = de.run_depth_estimation(_photo(tmp_path), None, None, masks=[(mask, 0.9)])
    assert out["status"] == "ok"
    assert out["max_depth_mm"] == pytest.approx(18.0, abs=0.5)
    assert out["max_indentation_mm"] == out["max_depth_mm"]
    assert out["max_depth_mm"] > 0.0
    inst = out["instances"][0]
    assert inst["max_depth_mm"] == inst["max_indentation_mm"] > 0.0


# --------------------------------------------------------------------------- surface normals / inference
def test_crease_angle_between_tilted_patch_and_ring():
    normals = np.zeros((60, 60, 3), dtype=np.float32)
    normals[..., 2] = 1.0
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    tilt = np.radians(30)
    normals[mask] = [np.sin(tilt), 0.0, np.cos(tilt)]
    res = sn.compute_crease_angle(normals, mask)
    assert res["status"] == "computed"
    assert res["crease_angle_deg"] == pytest.approx(30.0, abs=0.5)


def test_dsine_loader_patches_hardcoded_cuda(monkeypatch, tmp_path):
    hub = tmp_path / "hub"
    repo = hub / "hugoycj_DSINE-hub_main"
    repo.mkdir(parents=True)
    src = repo / "model.py"
    src.write_text('d = torch.device("cuda")\nx = t.to(0)\n', encoding="utf-8")

    class FakeModel:
        def __init__(self):
            self.device = None

        def to(self, device):
            self.device = device
            return self

    monkeypatch.setattr(sn.torch.hub, "get_dir", lambda: str(hub))
    monkeypatch.setattr(sn.torch.hub, "load", lambda *a, **k: FakeModel())
    model = sn.load_dsine(device="cpu")
    patched = src.read_text(encoding="utf-8")
    assert model.device == "cpu"
    assert 'torch.device("cuda")' not in patched
    assert ".to(0)" not in patched
    assert "is_available()" in patched


def test_inference_defaults_are_cpu_friendly():
    params = inspect.signature(inf.run_inference).parameters
    assert params["imgsz"].default == 640
    assert params["use_tta"].default is False
    assert inspect.signature(inf.load_model).parameters["device"].default == "cpu"


def test_package_exports_resolve_lazily():
    pkg = importlib.import_module("app.services.vision")
    for name in ("VisionPipeline", "run_vision_pipeline", "extract_vision_summary_for_db",
                 "calibrate_from_wheel", "run_depth_estimation", "load_yolo_model"):
        assert callable(getattr(pkg, name)), name
    assert pkg.TIER_2_WHEEL == sc.TIER_2_WHEEL


# --------------------------------------------------------------------------- pipeline + DB summary
def _stub_stages(monkeypatch, depth, mask):
    monkeypatch.setattr(vp, "_lazy_sam2", lambda device: (None, None))
    monkeypatch.setattr(vp, "segment_boxes_safe", lambda *a, **k: [(mask, 0.93)])
    monkeypatch.setattr(vp, "_lazy_dsine", lambda device: None)

    def fake_normals(_model, _path):
        normals = np.zeros(mask.shape + (3,), dtype=np.float32)
        normals[..., 2] = 1.0
        tilt = np.radians(20)
        normals[mask] = [np.sin(tilt), 0.0, np.cos(tilt)]
        return normals

    monkeypatch.setattr(vp, "estimate_normals_safe", fake_normals)
    monkeypatch.setattr(vp, "_lazy_depth", lambda device: (None, None))
    monkeypatch.setattr(de, "estimate_relative_depth", lambda *a, **k: depth)
    monkeypatch.setattr(
        de, "calibrate_metric_depth_tiered",
        lambda rel, *a, **k: (rel, {"status": "calibrated", "method": "plate", "confidence": "high"}),
    )


def test_vision_pipeline_all_stages_and_summary(monkeypatch, tmp_path):
    depth, mask = _dented_depth(dent=22.0)
    _stub_stages(monkeypatch, depth, mask)
    det = [{"class_name": "dent", "confidence": 0.8, "bbox_xyxy": [60, 40, 100, 80]}]

    result = vp.run_vision_pipeline(_photo(tmp_path), det, device="cpu", pipeline=vp.VisionPipeline())
    assert result["stage_errors"] == {}
    inst = result["instances"][0]
    assert inst["area_px"] == int(mask.sum())
    assert inst["area_cm2"] and inst["area_cm2"] > 0
    assert inst["crease_angle_deg"] == pytest.approx(20.0, abs=1.0)
    assert inst["max_depth_mm"] == inst["max_indentation_mm"] == pytest.approx(22.0, abs=0.5)

    summary = vp.extract_vision_summary_for_db([result])
    assert summary["surface_area_px"] == int(mask.sum())
    assert summary["max_indentation_mm"] > 0
    assert summary["vision_calibration"]["status"] == "calibrated"
    json.dumps(summary)  # DB-safe: no numpy arrays / non-serializable values


def test_summary_is_safe_for_empty_and_failed_runs():
    empty = vp.extract_vision_summary_for_db([])
    assert empty["surface_area_px"] == 0 and empty["vision_calibration"] is None
    failed = vp.run_vision_pipeline("does-not-exist.jpg", [], pipeline=vp.VisionPipeline())
    assert "image_load" in failed["stage_errors"]
    assert vp.extract_vision_summary_for_db(failed)["mask_count"] == 0


# --------------------------------------------------------------------------- ai_runner payload shape
CLAIM_AI_ANALYSIS_COLUMNS = {
    "id", "claim_id", "detected_damages", "estimated_cost_min", "estimated_cost_max",
    "clahe_image_url", "segmentation_masks", "surface_area_px", "relative_deformation_z",
    "dsine_vectors", "fraud_flags", "fraud_analysis", "analysis_status", "error_message",
    "fraud_analysis_error", "created_at",
    # Added by migrations beyond the core schema and already written by the runner:
    "estimate_basis",
}


def _load_ai_runner():
    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = lambda *a, **k: None
    fake_ultralytics.RTDETR = lambda *a, **k: None
    fake_db = ModuleType("app.db.supabase")
    fake_db.db = object()
    saved = {n: sys.modules.get(n) for n in ("ultralytics", "app.db.supabase")}
    sys.modules["ultralytics"], sys.modules["app.db.supabase"] = fake_ultralytics, fake_db
    try:
        return importlib.import_module("app.services.ai_runner")
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class _FakeDb:
    def __init__(self):
        self.claim = {"id": "c1", "user_id": "u1", "description": "dent", "status": "pending_review",
                      "created_at": datetime.now(UTC).isoformat()}
        self.analysis = None

    async def select(self, table, params=None, single=False):
        if table == "claims":
            return self.claim
        if table == "claim_evidence":
            return [{"id": "e1", "category": "photo", "storage_path": "evidence/photo/u1/p.png",
                     "file_url": "evidence/photo/u1/p.png"}]
        return None

    async def update(self, table, filters, data):
        if table == "claims":
            self.claim.update(data)
            return [self.claim]
        self.analysis.update(data)
        return [self.analysis]

    async def insert(self, table, data):
        if table == "claim_ai_analysis":
            self.analysis = dict(data)
        return data

    async def download_storage_object(self, bucket, path):
        image = Image.new("RGB", (64, 64), "white")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


def test_ai_runner_payload_matches_claim_ai_analysis_schema(monkeypatch):
    ai_runner = _load_ai_runner()
    fake_db = _FakeDb()

    class Coords:
        def tolist(self):
            return [8, 8, 40, 40]

    class Box:
        cls, conf, xyxy = [0], [0.8], [Coords()]

    class Pred:
        orig_shape, boxes = (64, 64), [Box()]

    class Model:
        names = {0: "dent"}

        def predict(self, _p, **_k):
            return [Pred()]

    seen = {}

    def fake_vision(path, detections, **kwargs):
        seen["detections"] = detections
        return {
            "calibration": {"status": "calibrated", "method": "wheel_generic_diameter", "confidence": "low"},
            "max_depth_mm": 12.5, "max_indentation_mm": 12.5, "stage_errors": {},
            "instances": [{"area_px": 900, "area_cm2": 31.5, "mask_iou_score": 0.9,
                           "crease_angle_deg": 14.0, "crease_status": "computed",
                           "max_depth_mm": 12.5, "max_indentation_mm": 12.5, "stage_errors": {}}],
        }

    async def fake_fraud(**_kwargs):
        raise RuntimeError("fraud is out of scope for this test")

    monkeypatch.setattr(ai_runner, "db", fake_db)
    monkeypatch.setattr(ai_runner, "get_models", lambda: (Model(), None))
    monkeypatch.setattr(ai_runner, "run_vision_pipeline", fake_vision)
    monkeypatch.setattr(ai_runner, "analyze_fraud", fake_fraud)
    monkeypatch.setattr(ai_runner, "_VISION_AVAILABLE", True)
    monkeypatch.setattr(ai_runner, "_VISION_ENABLED", True)

    payload = asyncio.run(ai_runner.trigger_ai_assessment("c1"))

    assert seen["detections"][0]["bbox_xyxy"] == [8, 8, 40, 40]
    assert "vision_calibration" not in payload  # no such column on claim_ai_analysis
    assert set(payload) <= CLAIM_AI_ANALYSIS_COLUMNS
    assert set(fake_db.analysis) <= CLAIM_AI_ANALYSIS_COLUMNS

    z = payload["relative_deformation_z"]
    assert z["vision_calibration"]["method"] == "wheel_generic_diameter"
    assert z["max_indentation_mm"] == 12.5
    assert z["crease_angle_deg"] == 14.0
    assert payload["surface_area_px"] == 900 and isinstance(payload["surface_area_px"], int)
    assert payload["dsine_vectors"]["available"] is True
    assert payload["segmentation_masks"]["mask_count"] == 1
    json.dumps(payload)


def test_ai_runner_payload_without_vision_has_not_null_safe_values(monkeypatch):
    ai_runner = _load_ai_runner()
    monkeypatch.setattr(ai_runner, "_VISION_ENABLED", False)
    assert ai_runner.run_vision_pipeline is not None  # importable without loading any model
    # NOT NULL columns must never receive None when vision is skipped.
    summary = vp.extract_vision_summary_for_db([])
    assert int(summary["surface_area_px"] or 0) == 0
