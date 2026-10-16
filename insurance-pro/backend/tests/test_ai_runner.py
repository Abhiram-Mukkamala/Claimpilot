import asyncio
import importlib
import importlib.util
import io
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import Image, ImageDraw


BACKEND = Path(__file__).resolve().parents[1]
for name, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}.items():
    os.environ[name] = value

# app.core imports security at package load time. Install an inert test stub
# only when python-jose is genuinely absent, and never replace a real module.
if "jose" not in sys.modules and importlib.util.find_spec("jose") is None:
    jose_stub = ModuleType("jose")

    class JWTError(Exception):
        pass

    jose_stub.jwt = object()
    jose_stub.JWTError = JWTError
    sys.modules.setdefault("jose", jose_stub)

# Keep app.services imports isolated from its eager model/email imports.
services_package = ModuleType("app.services")
services_package.__path__ = [str(BACKEND / "app" / "services")]
sys.modules.setdefault("app.services", services_package)


def _load_runner_without_optional_runtime_dependencies():
    """Import ai_runner against inert model/database modules; tests inject fakes."""
    original_modules = {}
    absent = object()
    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = lambda *_args, **_kwargs: None
    fake_ultralytics.RTDETR = lambda *_args, **_kwargs: None
    fake_database = ModuleType("app.db.supabase")
    fake_database.db = object()

    for name, module in {
        "ultralytics": fake_ultralytics,
        "app.db.supabase": fake_database,
    }.items():
        original_modules[name] = sys.modules.get(name, absent)
        sys.modules[name] = module
    try:
        return importlib.import_module("app.services.ai_runner")
    finally:
        for name, module in original_modules.items():
            if module is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


ai_runner = _load_runner_without_optional_runtime_dependencies()
from app.services import fraud_analysis_service as fraud_service


def _image_bytes():
    image = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(image).rectangle((12, 12, 40, 40), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class PipelineDatabase:
    def __init__(self, *, with_photo=True, phash_missing=False):
        self.claim_id = "claim-123"
        self.claim = {
            "id": self.claim_id,
            "user_id": "user-123",
            "description": "minor scratch while parking",
            "created_at": datetime.now(UTC).isoformat(),
            "status": "pending_review",
        }
        self.evidence = []
        if with_photo:
            self.evidence.append({
                "id": "evidence-123",
                "claim_id": self.claim_id,
                "category": "photo",
                "file_url": "evidence/photo/user-123/photo.png",
                "storage_path": "evidence/photo/user-123/photo.png",
                "phash": None,
            })
        self.claims = [self.claim]
        self.ai_analysis = None
        self.fraud_analysis = None
        self.phash_missing = phash_missing
        self.downloaded_paths = []

    async def select(self, table, params=None, single=False):
        params = params or {}
        if table == "claim_evidence":
            if self.phash_missing and "phash" in params:
                return {
                    "code": "42703",
                    "message": "column claim_evidence.phash does not exist",
                }
            claim_filter = params.get("claim_id", "")
            if claim_filter.startswith("neq."):
                excluded_id = claim_filter.removeprefix("neq.")
                rows = [
                    {"claim_id": row["claim_id"], "phash": row.get("phash")}
                    for row in self.evidence
                    if row["claim_id"] != excluded_id and row.get("phash")
                ]
            elif claim_filter.startswith("eq."):
                claim_id = claim_filter.removeprefix("eq.")
                rows = [row for row in self.evidence if row["claim_id"] == claim_id]
            else:
                rows = list(self.evidence)
            offset = int(params.get("offset", "0"))
            limit = int(params.get("limit", str(len(rows))))
            return rows[offset:offset + limit]

        if table == "claims":
            if "user_id" in params:
                user_id = params["user_id"].removeprefix("eq.")
                return [
                    {"id": row["id"], "created_at": row["created_at"]}
                    for row in self.claims
                    if row.get("user_id") == user_id
                ]
            claim_id = params.get("id", "").removeprefix("eq.")
            return next((row for row in self.claims if row["id"] == claim_id), None)

        if table == "claim_ai_analysis":
            return self.ai_analysis
        if table == "claim_fraud_analyses":
            return self.fraud_analysis
        raise AssertionError(f"Unexpected table select: {table}")

    async def download_storage_object(self, bucket, file_path):
        self.downloaded_paths.append((bucket, file_path))
        return _image_bytes()

    async def create_signed_read_url(self, bucket, file_path, expires_in=300):
        return {"signed_url": f"https://unit-test.invalid/private/{file_path}?expires={expires_in}"}

    async def update(self, table, filters, data):
        if table == "claims":
            claim_id = filters.get("id", "").removeprefix("eq.")
            claim = next((row for row in self.claims if row["id"] == claim_id), None)
            if not claim:
                return []
            expected_status = filters.get("status")
            if expected_status and claim.get("status") != expected_status.removeprefix("eq."):
                return []
            claim.update(data)
            return [claim]

        if table == "claim_evidence":
            evidence_id = filters.get("id", "").removeprefix("eq.")
            evidence = next((row for row in self.evidence if row["id"] == evidence_id), None)
            if not evidence:
                return []
            evidence.update(data)
            return [evidence]

        if table == "claim_ai_analysis":
            self.ai_analysis.update(data)
            return [self.ai_analysis]
        if table == "claim_fraud_analyses":
            self.fraud_analysis.update(data)
            return [self.fraud_analysis]
        raise AssertionError(f"Unexpected table update: {table}")

    async def insert(self, table, data):
        if table == "claim_ai_analysis":
            self.ai_analysis = dict(data)
            return self.ai_analysis
        if table == "claim_fraud_analyses":
            self.fraud_analysis = dict(data)
            return self.fraud_analysis
        raise AssertionError(f"Unexpected table insert: {table}")


class EmptyPrediction:
    orig_shape = (64, 64)
    boxes = []


class EmptyDetectionModel:
    def predict(self, _path, **_kwargs):
        return [EmptyPrediction()]


@pytest.fixture
def runtime(monkeypatch):
    database = PipelineDatabase()
    real_analyzer = ai_runner.analyze_fraud

    async def analyze_with_fake_database(**kwargs):
        return await real_analyzer(**kwargs, db_client=database)

    monkeypatch.setattr(ai_runner, "db", database)
    monkeypatch.setattr(ai_runner, "analyze_fraud", analyze_with_fake_database)
    monkeypatch.setattr(ai_runner, "get_models", lambda: (EmptyDetectionModel(), None))
    return database


def test_runner_waits_for_damage_photo_evidence(runtime, monkeypatch):
    runtime.evidence.clear()
    model_calls = []
    monkeypatch.setattr(ai_runner, "get_models", lambda: model_calls.append(True))

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    assert result["status"] == "skipped"
    assert result["reason"] == "no_photo_evidence"
    assert runtime.claim["status"] == "pending_review"
    assert model_calls == []


def test_inference_failure_is_saved_and_claim_moves_to_manual_review(runtime, monkeypatch):
    class BrokenModel:
        def predict(self, *_args, **_kwargs):
            raise RuntimeError("private detail must not be persisted")

    monkeypatch.setattr(ai_runner, "get_models", lambda: (BrokenModel(), None))

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    assert result["analysis_status"] == "failed"
    assert result["error_message"] == "Damage detection failed for all uploaded photos."
    assert "private detail" not in result["error_message"]
    assert runtime.ai_analysis["analysis_status"] == "failed"
    assert runtime.claim["status"] == "manual_review"
    assert runtime.evidence[0]["phash"]
    assert runtime.fraud_analysis["analysis_status"] == "completed"
    assert runtime.downloaded_paths == [
        (ai_runner.settings.SUPABASE_STORAGE_BUCKET, "evidence/photo/user-123/photo.png")
    ]


def test_missing_model_weights_still_runs_fraud_hashing(runtime, monkeypatch):
    monkeypatch.setattr(ai_runner, "get_models", lambda: (None, None))

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    assert result["analysis_status"] == "failed"
    assert result["error_message"] == "No damage detection model weights are available."
    assert runtime.claim["status"] == "manual_review"
    assert runtime.evidence[0]["phash"]
    assert runtime.fraud_analysis["analysis_status"] == "completed"


def test_upload_analysis_hashes_compares_persists_and_runs_once(runtime, monkeypatch):
    image_hash = fraud_service.compute_image_phash(_image_bytes())
    runtime.evidence.append({
        "id": "prior-evidence",
        "claim_id": "prior-claim",
        "category": "photo",
        "file_url": "evidence/photo/user-123/prior.png",
        "storage_path": "evidence/photo/user-123/prior.png",
        "phash": image_hash,
    })
    model_calls = []
    monkeypatch.setattr(
        ai_runner,
        "get_models",
        lambda: (model_calls.append(True) or EmptyDetectionModel(), None),
    )

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))
    repeated = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    current_evidence = next(row for row in runtime.evidence if row["id"] == "evidence-123")
    assert result["analysis_status"] == "completed"
    assert result["detected_damages"] == []
    assert current_evidence["phash"] == image_hash
    assert result["fraud_analysis"]["indicators"][0]["passed"] is False
    assert runtime.fraud_analysis["analysis_status"] == "completed"
    assert runtime.fraud_analysis["score"] == result["fraud_analysis"]["score"]
    assert repeated["reason"] == "already_started"
    assert len(model_calls) == 1


def test_runner_uses_geometry_estimator_and_persists_basis_without_internal_fields(runtime, monkeypatch):
    class FakeCoordinates:
        def tolist(self):
            return [0, 0, 500, 500]

    class FakeBox:
        cls = [0]
        conf = [0.75]
        xyxy = [FakeCoordinates()]

    class FakePrediction:
        orig_shape = (1000, 1000)
        boxes = [FakeBox()]

    class CrackModel:
        names = {0: "crack"}

        def predict(self, _path, **_kwargs):
            return [FakePrediction()]

    monkeypatch.setattr(ai_runner, "get_models", lambda: (CrackModel(), None))

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    damage = result["detected_damages"][0]
    assert result["estimate_basis"] == "indicative, from a seeded cost table, uncalibrated"
    assert damage["severity"] == "Severe"
    assert damage["estimated_cost_min"] == 15000
    assert damage["estimated_cost_max"] == 30000
    assert damage["estimated_cost"] == 22500
    assert result["estimated_cost_min"] == 15000
    assert result["estimated_cost_max"] == 30000
    assert not any(key.startswith("_estimator_") for key in damage)
    assert runtime.ai_analysis["estimate_basis"] == result["estimate_basis"]
    # The current schema intentionally has clahe_image_url, not image_url.
    assert "image_url" not in runtime.ai_analysis


def test_evidence_catalog_failure_and_retry_do_not_duplicate_analysis(runtime, monkeypatch):
    from fastapi import BackgroundTasks, HTTPException

    from app.schemas.claim import ClaimEvidenceCreate

    # Load only this route module with a fake DB import, avoiding the app router
    # package's unrelated Supabase client startup during this isolated test.
    fake_database_module = ModuleType("app.db.supabase")
    fake_database_module.db = object()
    absent = object()
    original_database_module = sys.modules.get("app.db.supabase", absent)
    sys.modules["app.db.supabase"] = fake_database_module
    try:
        storage_spec = importlib.util.spec_from_file_location(
            "_claimpilot_storage_route_test",
            BACKEND / "app" / "api" / "v1" / "storage.py",
        )
        storage = importlib.util.module_from_spec(storage_spec)
        storage_spec.loader.exec_module(storage)
    finally:
        if original_database_module is absent:
            sys.modules.pop("app.db.supabase", None)
        else:
            sys.modules["app.db.supabase"] = original_database_module

    runtime.evidence.clear()
    monkeypatch.setattr(storage, "db", runtime)
    failed_photo_two_once = False
    persisted_analysis_rows = {"claim_ai_analysis": 0, "claim_fraud_analyses": 0}
    original_insert = runtime.insert

    async def insert_with_photo_two_failure(table, data):
        nonlocal failed_photo_two_once
        if table == "claim_evidence":
            if data["file_url"].endswith("photo-2.png") and not failed_photo_two_once:
                failed_photo_two_once = True
                raise RuntimeError("simulated catalog write failure")
            row = {**data, "id": f"evidence-{len(runtime.evidence) + 1}"}
            runtime.evidence.append(row)
            return [row]
        if table in persisted_analysis_rows:
            persisted_analysis_rows[table] += 1
        return await original_insert(table, data)

    monkeypatch.setattr(runtime, "insert", insert_with_photo_two_failure)
    inference_calls = []

    class CountingModel:
        def predict(self, *_args, **_kwargs):
            inference_calls.append(True)
            return [EmptyPrediction()]

    monkeypatch.setattr(ai_runner, "get_models", lambda: (CountingModel(), None))
    user = {"user_id": "user-123", "role": "customer"}

    async def catalog(file_name, tasks):
        return await storage.catalog_evidence(
            ClaimEvidenceCreate(
                claim_id=runtime.claim_id,
                file_url=(
                    "https://unit-test.invalid/storage/v1/object/public/claim-evidence/"
                    f"evidence/photo/user-123/{file_name}"
                ),
                storage_path=f"evidence/photo/user-123/{file_name}",
                file_type="image/png",
                category="photo",
            ),
            tasks,
            SimpleNamespace(state=SimpleNamespace()),
            user,
        )

    first_upload_tasks = BackgroundTasks()
    first_result = asyncio.run(catalog("photo-1.png", first_upload_tasks))
    assert first_result["message"] == "Evidence cataloged successfully"
    asyncio.run(first_upload_tasks())

    failed_retry_tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        asyncio.run(catalog("photo-2.png", failed_retry_tasks))
    assert error.value.status_code == 500
    assert not failed_retry_tasks.tasks
    assert len(runtime.evidence) == 1

    retry_tasks = BackgroundTasks()
    retry_result = asyncio.run(catalog("photo-2.png", retry_tasks))
    assert retry_result["message"] == "Evidence cataloged successfully"
    assert len(runtime.evidence) == 2
    asyncio.run(retry_tasks())

    assert len(inference_calls) == 1
    assert persisted_analysis_rows == {"claim_ai_analysis": 1, "claim_fraud_analyses": 1}
    assert runtime.ai_analysis["claim_id"] == runtime.claim_id
    assert runtime.fraud_analysis["claim_id"] == runtime.claim_id
    assert runtime.claim["status"] == "under_review"


def test_missing_phash_column_is_recorded_with_migration_guidance(runtime):
    runtime.phash_missing = True

    result = asyncio.run(ai_runner.trigger_ai_assessment(runtime.claim_id))

    expected_error = "claim_evidence.phash is missing; apply migration_v3_phash.sql in the Supabase SQL editor."
    assert result["analysis_status"] == "completed"
    assert result["fraud_analysis"] is None
    assert result["fraud_analysis_error"] == expected_error
    assert runtime.fraud_analysis["analysis_status"] == "failed"
    assert runtime.fraud_analysis["error_message"] == expected_error


def test_model_weights_use_configured_default_and_fallback_paths(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    weights_dir = app_dir / "models" / "weights"
    weights_dir.mkdir(parents=True)
    default_weights = weights_dir / "best.pt"
    yolo_fallback = weights_dir / "yolov11m.pt"
    rtdetr_fallback = weights_dir / "rt-detr.pt"
    configured_weights = tmp_path / "custom.pt"
    for weights_path in (default_weights, yolo_fallback, rtdetr_fallback, configured_weights):
        weights_path.write_bytes(b"fake model file")

    loaded_yolo = []
    loaded_rtdetr = []
    monkeypatch.setattr(ai_runner, "BASE_DIR", app_dir)
    monkeypatch.setattr(ai_runner, "DEFAULT_MODEL_WEIGHTS_PATH", default_weights)
    monkeypatch.setattr(ai_runner, "YOLO_FALLBACK_WEIGHTS_PATH", yolo_fallback)
    monkeypatch.setattr(ai_runner, "RTDETR_FALLBACK_WEIGHTS_PATH", rtdetr_fallback)
    monkeypatch.setattr(ai_runner, "YOLO", lambda path: loaded_yolo.append(path) or object())
    monkeypatch.setattr(ai_runner, "RTDETR", lambda path: loaded_rtdetr.append(path) or object())
    monkeypatch.setattr(ai_runner, "_yolo_model", None)
    monkeypatch.setattr(ai_runner, "_rtdetr_model", None)

    monkeypatch.delenv("MODEL_WEIGHTS_PATH", raising=False)
    ai_runner.get_models()
    assert loaded_yolo == [str(default_weights)]
    assert loaded_rtdetr == [str(rtdetr_fallback)]

    loaded_yolo.clear()
    loaded_rtdetr.clear()
    monkeypatch.setattr(ai_runner, "_yolo_model", None)
    monkeypatch.setattr(ai_runner, "_rtdetr_model", None)
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", "custom.pt")
    ai_runner.get_models()
    assert loaded_yolo == [str(configured_weights)]

    loaded_yolo.clear()
    monkeypatch.setattr(ai_runner, "_yolo_model", None)
    monkeypatch.setattr(ai_runner, "_rtdetr_model", None)
    default_weights.unlink()
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", "missing.pt")
    ai_runner.get_models()
    assert loaded_yolo == [str(yolo_fallback)]
