import asyncio
import io
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import imagehash
from PIL import Image, ImageDraw

# Fraud tests isolate settings from any developer environment or local .env file.
os.environ["SUPABASE_URL"] = "https://unit-test.invalid"
os.environ["SUPABASE_ANON_KEY"] = "dummy-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "dummy-service-role-key"
os.environ["JWT_SECRET"] = "dummy-jwt-signing-secret"

# The fraud service tests do not exercise JWT code. Keep test collection offline
# when the development environment has not installed this listed backend dependency.
try:
    import jose  # noqa: F401
except ImportError:
    jose_stub = ModuleType("jose")

    class JWTError(Exception):
        pass

    jose_stub.jwt = object()
    jose_stub.JWTError = JWTError
    sys.modules["jose"] = jose_stub

# Avoid services/__init__.py eager-loading email and model-runtime dependencies.
services_package = ModuleType("app.services")
services_package.__path__ = [str(Path(__file__).resolve().parents[1] / "app" / "services")]
sys.modules.setdefault("app.services", services_package)

from app.core.config import settings
from app.services import fraud_analysis_service as fraud_service


NOW = datetime(2026, 8, 22, tzinfo=UTC)


class MockDatabase:
    """Small in-memory stand-in for the async PostgREST methods used by the service."""

    def __init__(self):
        self.evidence = []
        self.claims = []

    async def select(self, table, params=None, single=False):
        params = params or {}
        if table == "claim_evidence":
            excluded_claim = params.get("claim_id", "").removeprefix("neq.")
            rows = [
                {"claim_id": row["claim_id"], "phash": row.get("phash")}
                for row in self.evidence
                if row["claim_id"] != excluded_claim and row.get("phash")
            ]
        elif table == "claims":
            user_id = params.get("user_id", "").removeprefix("eq.")
            return [
                {"id": row["id"], "created_at": row["created_at"]}
                for row in self.claims
                if row["user_id"] == user_id
            ]
        else:
            raise AssertionError(f"Unexpected table: {table}")
        offset = int(params.get("offset", "0"))
        limit = int(params.get("limit", str(len(rows))))
        return rows[offset:offset + limit]

    async def update(self, table, filters, data):
        assert table == "claim_evidence"
        evidence_id = filters["id"].removeprefix("eq.")
        for row in self.evidence:
            if row["id"] == evidence_id:
                row.update(data)
                return [row]
        raise AssertionError(f"Unknown evidence id: {evidence_id}")

    def add_claim(self, claim_id, user_id, created_at=NOW):
        self.claims.append({
            "id": claim_id,
            "user_id": user_id,
            "created_at": created_at.isoformat(),
        })

    def add_evidence(self, evidence_id, claim_id):
        row = {"id": evidence_id, "claim_id": claim_id, "phash": None}
        self.evidence.append(row)
        return row


def image_bytes(kind="panel", shift=0):
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    if kind == "panel":
        draw.rectangle((12 + shift, 12, 38 + shift, 38), fill="black")
        draw.line((0, 60, 63, 5), fill="gray", width=2)
    elif kind == "ellipse":
        draw.ellipse((14, 4, 55, 45), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def run_analysis(database, claim_id, user_id, images=(), description="collision", damages=None, checker=None):
    return asyncio.run(
        fraud_service.analyze_fraud(
            claim_id=claim_id,
            claimant_id=user_id,
            description=description,
            submitted_at=NOW.isoformat(),
            damages=damages if damages is not None else [{"severity": "Minor"}],
            evidence_images=list(images),
            db_client=database,
            consistency_checker=checker,
            now=NOW,
        )
    )


def seed_old_hashed_claim(database, image):
    database.add_claim("old", "another-claimant", NOW - timedelta(days=30))
    database.add_evidence("old-image", "old")
    run_analysis(
        database,
        "old",
        "another-claimant",
        images=[{"evidence_id": "old-image", "image_bytes": image}],
        checker=lambda _description, _severity: (True, "Consistent"),
    )


def test_exact_duplicate_is_detected_across_claims_and_only_hash_is_persisted():
    database = MockDatabase()
    image = image_bytes()
    seed_old_hashed_claim(database, image)
    database.add_claim("target", "new-claimant")
    database.add_evidence("target-image", "target")

    result = run_analysis(
        database,
        "target",
        "new-claimant",
        images=[{"evidence_id": "target-image", "image_bytes": image}],
        checker=lambda _description, _severity: (True, "Consistent"),
    )

    target_row = next(row for row in database.evidence if row["id"] == "target-image")
    assert result.score == 50
    assert result.indicators[0].passed is False
    assert result.indicators[0].message == "Image matches a previously submitted claim"
    assert len(target_row["phash"]) == 16
    assert "image_bytes" not in target_row


def test_near_duplicate_within_configured_threshold_is_detected():
    database = MockDatabase()
    original = image_bytes()
    near_duplicate = image_bytes(shift=1)
    assert 0 < imagehash.phash(Image.open(io.BytesIO(original))) - imagehash.phash(
        Image.open(io.BytesIO(near_duplicate))
    ) <= settings.PHASH_DISTANCE_THRESHOLD
    seed_old_hashed_claim(database, original)
    database.add_claim("target", "new-claimant")
    database.add_evidence("target-image", "target")

    result = run_analysis(
        database,
        "target",
        "new-claimant",
        images=[{"evidence_id": "target-image", "image_bytes": near_duplicate}],
        checker=lambda _description, _severity: (True, "Consistent"),
    )

    assert result.indicators[0].passed is False


def test_different_image_is_not_flagged_as_duplicate():
    database = MockDatabase()
    seed_old_hashed_claim(database, image_bytes())
    database.add_claim("target", "new-claimant")
    database.add_evidence("target-image", "target")

    result = run_analysis(
        database,
        "target",
        "new-claimant",
        images=[{"evidence_id": "target-image", "image_bytes": image_bytes("ellipse")}],
        checker=lambda _description, _severity: (True, "Consistent"),
    )

    assert result.score == 10
    assert result.indicators[0].passed is True


def test_duplicate_search_includes_hashes_past_rest_page_limit():
    database = MockDatabase()
    database.add_claim("target", "new-claimant")
    database.add_evidence("target-image", "target")
    database.evidence.extend(
        {"id": f"older-{index}", "claim_id": f"older-claim-{index}", "phash": "invalid"}
        for index in range(1000)
    )
    database.evidence.append({"id": "last-prior-image", "claim_id": "last-prior-claim", "phash": "b636c1cdb08de932"})

    result = run_analysis(
        database,
        "target",
        "new-claimant",
        images=[{"evidence_id": "target-image", "image_bytes": image_bytes()}],
        checker=lambda _description, _severity: (True, "Consistent"),
    )

    assert result.indicators[0].passed is False


def test_first_ever_claim_has_no_repeat_pattern():
    database = MockDatabase()
    database.add_claim("first", "new-claimant")

    result = run_analysis(
        database,
        "first",
        "new-claimant",
        checker=lambda _description, _severity: (True, "Consistent"),
    )

    assert result.score == 10
    assert result.riskLevel.value == "LOW RISK"
    assert result.indicators[-1].passed is True
    assert result.indicators[-1].message == "Claimant has fewer than 3 claims in the last 6 months"


def test_prototype_weighted_score_clamps_at_100():
    database = MockDatabase()
    seed_old_hashed_claim(database, image_bytes())
    database.add_claim("previous-1", "repeat-user", NOW - timedelta(days=2))
    database.add_claim("previous-2", "repeat-user", NOW - timedelta(days=1))
    database.add_claim("target", "repeat-user", NOW)
    database.add_evidence("target-image", "target")

    result = run_analysis(
        database,
        "target",
        "repeat-user",
        images=[{"evidence_id": "target-image", "image_bytes": image_bytes()}],
        description="small cosmetic scratch",
        damages=[{"severity": "Severe"}],
        checker=lambda _description, _severity: (False, "Narrative mismatch"),
    )

    assert result.score == 100
    assert result.riskLevel.value == "HIGH RISK"
    assert sum(not indicator.passed for indicator in result.indicators) == 3


def test_clean_claim_preserves_prototype_base_score():
    database = MockDatabase()
    database.add_claim("clean", "clean-user")

    result = run_analysis(
        database,
        "clean",
        "clean-user",
        description="minor scratch while parking",
        damages=[{"severity": "Minor"}],
        checker=lambda _description, _severity: (True, "Incident narrative matches detected damage severity"),
    )

    assert result.score == 10
    assert result.riskLevel.value == "LOW RISK"
    assert all(indicator.passed for indicator in result.indicators)


def test_llm_unavailable_uses_heuristic_and_adds_skipped_indicator(monkeypatch):
    monkeypatch.setattr(settings, "FRAUD_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "FRAUD_LLM_API_KEY", None)
    database = MockDatabase()
    database.add_claim("fallback", "fallback-user")

    result = run_analysis(
        database,
        "fallback",
        "fallback-user",
        description="small cosmetic scratch",
        damages=[{"severity": "Severe"}],
    )

    assert result.score == 45
    assert result.indicators[1].passed is False
    assert result.indicators[1].message == "Claimed minor damage; detected damage exceeds expected severity"
    assert any("LLM check was skipped" in indicator.message for indicator in result.indicators)


def test_llm_call_failure_falls_back_without_raising(monkeypatch):
    class BrokenResponses:
        async def create(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    class BrokenClient:
        def __init__(self, **_kwargs):
            self.responses = BrokenResponses()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(settings, "FRAUD_LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "FRAUD_LLM_API_KEY", "test-placeholder")
    monkeypatch.setattr(fraud_service, "AsyncOpenAI", BrokenClient)
    database = MockDatabase()
    database.add_claim("fallback", "fallback-user")

    result = run_analysis(
        database,
        "fallback",
        "fallback-user",
        description="small cosmetic scratch",
        damages=[{"severity": "Severe"}],
    )

    assert result.score == 45
    assert any("LLM check was skipped" in indicator.message for indicator in result.indicators)
