"""Cross-claim image and narrative fraud checks for the async Supabase backend."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import imagehash
from PIL import Image

from app.core.config import settings
from app.schemas.claim import FraudAnalysis, FraudIndicator, FraudRiskLevel

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional provider dependency
    AsyncOpenAI = None


logger = logging.getLogger("claimpilot.fraud_analysis")
SIX_MONTHS = timedelta(days=183)
PHASH_COLUMN_MISSING_MESSAGE = (
    "claim_evidence.phash is missing; apply migration_v3_phash.sql in the Supabase SQL editor."
)


class PhashColumnMissingError(RuntimeError):
    """Raised when the manual pHash schema migration has not been applied."""

    def __init__(self):
        super().__init__(PHASH_COLUMN_MISSING_MESSAGE)


def _is_missing_phash_column(error: Any) -> bool:
    if isinstance(error, dict):
        error_code = str(error.get("code") or "")
        error_text = " ".join(
            str(error.get(key) or "")
            for key in ("message", "details", "hint", "error")
        )
    else:
        error_code = ""
        error_text = str(error)
    normalized = error_text.lower()
    return "phash" in normalized and (
        error_code == "42703"
        or "does not exist" in normalized
        or "could not find" in normalized
        or "schema cache" in normalized
    )


def compute_image_phash(image_bytes: bytes) -> str:
    """Return the 64-bit pHash string; callers must never persist image bytes."""
    import io

    with Image.open(io.BytesIO(image_bytes)) as image:
        return str(imagehash.phash(image.convert("RGB")))


def _normalise_severity(value: str | None) -> str:
    severity = (value or "unknown").strip().lower()
    return {
        "light": "minor",
        "low": "minor",
        "medium": "moderate",
        "high": "major",
        "severe": "major",
    }.get(severity, severity)


def _fallback_consistency(description: str, severity: str) -> tuple[bool, str]:
    """Prototype keyword heuristic used whenever the configured LLM is unavailable."""
    claims_minor = re.search(r"\b(scratch|minor|small|light|cosmetic)\b", description, re.I)
    if claims_minor and severity == "major":
        return False, "Claimed minor damage; detected damage exceeds expected severity"
    return True, "Incident narrative matches detected damage severity"


async def _narrative_consistency(
    description: str,
    severity: str,
) -> tuple[bool, str, bool]:
    """Return consistency, its indicator message, and whether the LLM was skipped."""
    provider = (settings.FRAUD_LLM_PROVIDER or "").strip().lower()
    api_key = settings.FRAUD_LLM_API_KEY
    if not provider or not api_key or provider != "openai" or AsyncOpenAI is None:
        consistent, message = _fallback_consistency(description, severity)
        return consistent, message, True

    prompt = (
        "Assess whether the claim narrative is consistent with detected vehicle damage. "
        'Return only JSON: {"consistent": boolean, "claimedSeverity": string}. '
        "Only mark false for a material contradiction; do not infer fraud.\n"
        f"Narrative: {description}\nDetected severity: {severity}"
    )
    try:
        async with AsyncOpenAI(api_key=api_key) as client:
            response = await client.responses.create(
                model=settings.FRAUD_LLM_MODEL or "gpt-4o-mini",
                input=prompt,
                temperature=0,
            )
        payload = json.loads(response.output_text)
        consistent = bool(payload["consistent"])
        claimed = str(payload.get("claimedSeverity") or "damage")
        message = (
            "Incident narrative matches detected damage severity"
            if consistent
            else f"Claimed {claimed}; detected damage exceeds expected severity"
        )
        return consistent, message, False
    except Exception as exc:  # provider/network/response errors must never fail the pipeline
        logger.warning("Fraud narrative LLM check failed; using deterministic fallback (%s)", type(exc).__name__)
        consistent, message = _fallback_consistency(description, severity)
        return consistent, message, True


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _select_all_rows(database: Any, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    """Read every matching row despite the REST API's per-response row limit."""
    page_size = 1000
    offset = 0
    rows: list[dict[str, Any]] = []
    while True:
        page = await database.select(
            table,
            params={**params, "limit": str(page_size), "offset": str(offset)},
        )
        if not isinstance(page, list):
            if table == "claim_evidence" and _is_missing_phash_column(page):
                raise PhashColumnMissingError()
            raise RuntimeError(f"Could not read all matching rows from {table}")
        rows.extend(row for row in page if isinstance(row, dict))
        if len(page) < page_size:
            return rows
        offset += page_size


def _highest_severity(damages: list[dict[str, Any]]) -> str:
    severities = [
        _normalise_severity(item.get("severity"))
        for item in damages
        if isinstance(item, dict)
    ]
    if "major" in severities:
        return "major"
    if "moderate" in severities:
        return "moderate"
    if severities:
        return "minor"
    return "unknown"


def _risk_level(score: int) -> FraudRiskLevel:
    if score < 30:
        return FraudRiskLevel.low
    if score < 70:
        return FraudRiskLevel.medium
    return FraudRiskLevel.high


def _weighted_score(duplicate: bool, severity_mismatch: bool, repeat_claim_pattern: bool) -> int:
    return max(
        0,
        min(
            100,
            10
            + (40 if duplicate else 0)
            + (35 if severity_mismatch else 0)
            + (15 if repeat_claim_pattern else 0),
        ),
    )


async def analyze_fraud(
    *,
    claim_id: str,
    claimant_id: str | None,
    description: str,
    submitted_at: Any,
    damages: list[dict[str, Any]],
    evidence_images: list[dict[str, Any]],
    db_client: Any = None,
    consistency_checker: Callable[[str, str], tuple[bool, str]] | None = None,
    now: datetime | None = None,
) -> FraudAnalysis:
    """Analyze one claim using stored pHashes, claimant history, and damage severity.

    ``evidence_images`` contains only transient upload bytes and the evidence row id.
    Only the computed pHash string is written to Postgres.
    """
    database = db_client
    if database is None:
        from app.db.supabase import db as database
    prior_hash_rows = await _select_all_rows(
        database,
        "claim_evidence",
        {
            "select": "claim_id,phash",
            "claim_id": f"neq.{claim_id}",
            "phash": "not.is.null",
        },
    )
    prior_hashes = [
        row.get("phash")
        for row in prior_hash_rows
        if isinstance(row, dict) and row.get("phash")
    ]

    duplicate = False
    threshold = settings.PHASH_DISTANCE_THRESHOLD
    for evidence in evidence_images:
        try:
            current_hash = compute_image_phash(evidence["image_bytes"])
        except Exception as exc:
            logger.warning("Could not compute pHash for evidence row (%s)", type(exc).__name__)
            continue

        for stored_hash in prior_hashes:
            try:
                if imagehash.hex_to_hash(current_hash) - imagehash.hex_to_hash(stored_hash) <= threshold:
                    duplicate = True
            except (TypeError, ValueError):
                # A malformed older hash must not stop comparisons with other claims.
                continue

        evidence_id = evidence.get("evidence_id")
        if evidence_id:
            try:
                await database.update(
                    "claim_evidence",
                    filters={"id": f"eq.{evidence_id}"},
                    data={"phash": current_hash},
                )
            except Exception as exc:
                if _is_missing_phash_column(exc):
                    raise PhashColumnMissingError() from exc
                logger.warning("Could not persist pHash for evidence row (%s)", type(exc).__name__)

    duplicate_indicator = FraudIndicator(
        passed=not duplicate,
        message=(
            "Image matches a previously submitted claim"
            if duplicate
            else "No duplicate images detected"
        ),
    )
    severity = _highest_severity(damages)
    if consistency_checker is None:
        consistent, narrative_message, llm_skipped = await _narrative_consistency(description, severity)
    else:
        consistent, narrative_message = consistency_checker(description, severity)
        llm_skipped = False
    indicators = [duplicate_indicator, FraudIndicator(passed=consistent, message=narrative_message)]
    if llm_skipped:
        indicators.append(
            FraudIndicator(
                passed=True,
                message="LLM check was skipped; deterministic keyword/severity heuristic used",
            )
        )

    as_of = now or datetime.now(UTC)
    window_start = as_of - SIX_MONTHS
    history_rows: list[dict[str, Any]] = []
    if claimant_id:
        claim_rows = await _select_all_rows(
            database,
            "claims",
            {"select": "id,created_at", "user_id": f"eq.{claimant_id}"},
        )
        history_rows = claim_rows

    # The current claim participates in the prototype's inclusive 3-claim check.
    if not any(str(row.get("id")) == str(claim_id) for row in history_rows):
        history_rows.append({"id": claim_id, "created_at": submitted_at})
    recent_claims = sum(
        1
        for row in history_rows
        if (claim_time := _parse_time(row.get("created_at"))) is not None
        and window_start <= claim_time <= as_of
    )
    frequent_claimant = recent_claims >= 3
    indicators.append(
        FraudIndicator(
            passed=not frequent_claimant,
            message=(
                "Claimant has submitted 3 or more claims in the last 6 months"
                if frequent_claimant
                else "Claimant has fewer than 3 claims in the last 6 months"
            ),
        )
    )

    score = _weighted_score(duplicate, not consistent, frequent_claimant)
    return FraudAnalysis(
        claimId=claim_id,
        score=score,
        riskLevel=_risk_level(score),
        indicators=indicators,
    )
