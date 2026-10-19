import asyncio
import io
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from fastapi import BackgroundTasks

for name, value in {
    "SUPABASE_URL": "https://unit-test.invalid",
    "SUPABASE_ANON_KEY": "dummy-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "dummy-service-role-key",
    "JWT_SECRET": "dummy-jwt-signing-secret",
}.items():
    os.environ[name] = value

from app.schemas.claim import ClaimEvidenceCreate, FraudAnalysis, FraudIndicator, FraudRiskLevel


def _image_bytes():
    image = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(image).rectangle((12, 12, 40, 40), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class MockPipelineDb:
    def __init__(self):
        self.claim_id = "claim-sync-100"
        self.claim = {
            "id": self.claim_id,
            "user_id": "cust-sync-1",
            "description": "front collision scratch and dent",
            "created_at": datetime.now(UTC).isoformat(),
            "status": "pending_review",
        }
        self.claims = [self.claim]
        self.evidence = []
        self.ai_analysis = None
        self.fraud_analysis = None
        self.downloaded_paths = []

    async def select(self, table, params=None, single=False):
        params = params or {}
        if table == "claims":
            claim_id = params.get("id", "").removeprefix("eq.")
            return next((c for c in self.claims if c["id"] == claim_id), None)
        if table == "claim_evidence":
            claim_id = params.get("claim_id", "").removeprefix("eq.")
            return [e for e in self.evidence if e["claim_id"] == claim_id]
        if table == "claim_ai_analysis":
            return self.ai_analysis
        if table == "claim_fraud_analyses":
            return self.fraud_analysis
        return []

    async def insert(self, table, data):
        if table == "claim_evidence":
            row = {**data, "id": f"ev-{len(self.evidence) + 1}"}
            self.evidence.append(row)
            return [row]
        if table == "claim_ai_analysis":
            self.ai_analysis = dict(data)
            return self.ai_analysis
        if table == "claim_fraud_analyses":
            self.fraud_analysis = dict(data)
            return self.fraud_analysis
        return [data]

    async def update(self, table, filters, data):
        if table == "claims":
            cid = filters.get("id", "").removeprefix("eq.")
            claim = next((c for c in self.claims if c["id"] == cid), None)
            if not claim:
                return []
            expected_status = filters.get("status")
            if expected_status and claim.get("status") != expected_status.removeprefix("eq."):
                return []
            claim.update(data)
            return [claim]
        if table == "claim_evidence":
            eid = filters.get("id", "").removeprefix("eq.")
            ev = next((e for e in self.evidence if e["id"] == eid), None)
            if not ev:
                return []
            ev.update(data)
            return [ev]
        if table == "claim_ai_analysis" and self.ai_analysis:
            self.ai_analysis.update(data)
            return [self.ai_analysis]
        if table == "claim_fraud_analyses" and self.fraud_analysis:
            self.fraud_analysis.update(data)
            return [self.fraud_analysis]
        return []

    async def download_storage_object(self, bucket, file_path):
        self.downloaded_paths.append((bucket, file_path))
        return _image_bytes()

    async def create_signed_read_url(self, bucket, file_path, expires_in=300):
        return {"signed_url": f"https://mock.invalid/private/{file_path}?expires={expires_in}"}


class Tensor1D:
    def __init__(self, val):
        self.val = val

    def tolist(self):
        return self.val


class Tensor2D:
    def __init__(self, val):
        self.val = val

    def __getitem__(self, idx):
        return Tensor1D(self.val[idx])


class MockBox:
    cls = [0]
    conf = [0.85]
    xyxy = Tensor2D([[10.0, 10.0, 30.0, 30.0]])


class MockResult:
    orig_shape = (100, 100)
    boxes = [MockBox()]


class MockDetectionModel:
    names = {0: "dent", 1: "scratch"}

    def predict(self, _path, **_kwargs):
        return [MockResult()]


@pytest.fixture
def mock_storage_env(monkeypatch):
    import app.api.v1.storage as storage_mod
    import app.services.ai_runner as ai_runner_mod

    db = MockPipelineDb()
    monkeypatch.setattr(storage_mod, "db", db)
    monkeypatch.setattr(ai_runner_mod, "db", db)
    monkeypatch.setattr(ai_runner_mod, "get_models", lambda: (MockDetectionModel(), None))

    async def fake_analyze_fraud(**kwargs):
        return FraudAnalysis(
            claimId=kwargs.get("claim_id", "test"),
            score=15,
            riskLevel=FraudRiskLevel.low,
            indicators=[
                FraudIndicator(
                    passed=True,
                    message="Image hash consistency check passed",
                )
            ],
        )

    monkeypatch.setattr(ai_runner_mod, "analyze_fraud", fake_analyze_fraud)
    return storage_mod, ai_runner_mod, db


def test_sync_mode_success_returns_analysis_and_persists(mock_storage_env, monkeypatch):
    storage_mod, ai_runner_mod, db = mock_storage_env
    monkeypatch.setenv("AI_PROCESSING_SYNC", "true")

    payload = ClaimEvidenceCreate(
        claim_id=db.claim_id,
        file_url="evidence/photo/cust-sync-1/1700000000_dmg.png",
        storage_path="evidence/photo/cust-sync-1/1700000000_dmg.png",
        file_type="image/png",
        category="photo",
    )
    tasks = BackgroundTasks()
    user = {"user_id": "cust-sync-1", "role": "customer"}

    result = asyncio.run(storage_mod.catalog_evidence(
        payload, tasks, SimpleNamespace(state=SimpleNamespace()), user
    ))

    # Evidence cataloged
    assert result["message"] == "Evidence cataloged successfully"
    assert len(db.evidence) == 1
    # Analysis was executed synchronously and returned
    assert "analysis" in result
    assert result["analysis"]["analysis_status"] == "completed"
    assert len(result["analysis"]["detected_damages"]) == 1
    assert result["analysis"]["detected_damages"][0]["type"] == "Dent"

    # DB persistence verified
    assert db.claim["status"] == "under_review"
    assert db.ai_analysis is not None
    assert db.ai_analysis["analysis_status"] == "completed"
    assert db.fraud_analysis is not None
    assert db.fraud_analysis["analysis_status"] == "completed"

    # BackgroundTasks was NOT used
    assert len(tasks.tasks) == 0


def test_sync_mode_inference_failure_routes_to_flagged(mock_storage_env, monkeypatch):
    storage_mod, ai_runner_mod, db = mock_storage_env
    monkeypatch.setenv("AI_PROCESSING_SYNC", "true")

    class BrokenModel:
        def predict(self, *_args, **_kwargs):
            raise RuntimeError("Model evaluation crashed")

    monkeypatch.setattr(ai_runner_mod, "get_models", lambda: (BrokenModel(), None))

    payload = ClaimEvidenceCreate(
        claim_id=db.claim_id,
        file_url="evidence/photo/cust-sync-1/1700000000_dmg.png",
        storage_path="evidence/photo/cust-sync-1/1700000000_dmg.png",
        file_type="image/png",
        category="photo",
    )
    tasks = BackgroundTasks()
    user = {"user_id": "cust-sync-1", "role": "customer"}

    # Must not raise 500
    result = asyncio.run(storage_mod.catalog_evidence(
        payload, tasks, SimpleNamespace(state=SimpleNamespace()), user
    ))

    assert result["message"] == "Evidence cataloged successfully"
    assert "analysis" in result
    assert result["analysis"]["analysis_status"] == "failed"
    # Claim moved to flagged, not crashed
    assert db.claim["status"] == "flagged"
    assert db.ai_analysis["analysis_status"] == "failed"


def test_sync_mode_idempotency_second_photo_skips_duplicate_analysis(mock_storage_env, monkeypatch):
    storage_mod, ai_runner_mod, db = mock_storage_env
    monkeypatch.setenv("AI_PROCESSING_SYNC", "true")

    user = {"user_id": "cust-sync-1", "role": "customer"}

    # First photo triggers analysis
    payload1 = ClaimEvidenceCreate(
        claim_id=db.claim_id,
        file_url="evidence/photo/cust-sync-1/1700000000_dmg1.png",
        storage_path="evidence/photo/cust-sync-1/1700000000_dmg1.png",
        file_type="image/png",
        category="photo",
    )
    res1 = asyncio.run(storage_mod.catalog_evidence(
        payload1, BackgroundTasks(), SimpleNamespace(state=SimpleNamespace()), user
    ))
    assert res1["analysis"]["analysis_status"] == "completed"
    assert db.claim["status"] == "under_review"

    # Second photo uploads and catalogs cleanly without re-running or breaking idempotency
    payload2 = ClaimEvidenceCreate(
        claim_id=db.claim_id,
        file_url="evidence/photo/cust-sync-1/1700000001_dmg2.png",
        storage_path="evidence/photo/cust-sync-1/1700000001_dmg2.png",
        file_type="image/png",
        category="photo",
    )
    res2 = asyncio.run(storage_mod.catalog_evidence(
        payload2, BackgroundTasks(), SimpleNamespace(state=SimpleNamespace()), user
    ))
    assert res2["message"] == "Evidence cataloged successfully"
    assert len(db.evidence) == 2
    # Second analysis returns skipped / already_started without corrupting state
    assert res2["analysis"]["status"] == "skipped"
    assert res2["analysis"]["reason"] == "already_started"
    assert db.claim["status"] == "under_review"


def test_default_mode_preserves_background_execution(mock_storage_env, monkeypatch):
    storage_mod, ai_runner_mod, db = mock_storage_env
    monkeypatch.delenv("AI_PROCESSING_SYNC", raising=False)

    payload = ClaimEvidenceCreate(
        claim_id=db.claim_id,
        file_url="evidence/photo/cust-sync-1/1700000000_dmg.png",
        storage_path="evidence/photo/cust-sync-1/1700000000_dmg.png",
        file_type="image/png",
        category="photo",
    )
    tasks = BackgroundTasks()
    user = {"user_id": "cust-sync-1", "role": "customer"}

    result = asyncio.run(storage_mod.catalog_evidence(
        payload, tasks, SimpleNamespace(state=SimpleNamespace()), user
    ))

    # In default mode, no analysis key in immediate response; task is scheduled in BackgroundTasks
    assert result["message"] == "Evidence cataloged successfully"
    assert "analysis" not in result
    assert len(tasks.tasks) == 1
