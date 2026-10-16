"""Validation and response helpers for private claim evidence objects."""

import re
from typing import Any, Dict, Iterable, List
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, status

from app.core.config import settings


_CATEGORIES = {"photo", "walkaround_video", "dl_front", "dl_back"}


def canonical_evidence_path(value: str, *, category: str, owner_id: str) -> str:
    """Extract a safe, owner-scoped object path from a path or legacy URL."""
    if category not in _CATEGORIES or not owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence object is not authorized.")

    raw_value = (value or "").strip()
    if not raw_value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence object is not authorized.")

    parsed = urlparse(raw_value)
    if parsed.scheme or parsed.netloc:
        configured = urlparse(settings.SUPABASE_URL)
        accepted_prefixes = (
            f"/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/",
            f"/storage/v1/object/sign/{settings.SUPABASE_STORAGE_BUCKET}/",
        )
        if (
            parsed.scheme != configured.scheme
            or parsed.netloc != configured.netloc
            or not any(parsed.path.startswith(prefix) for prefix in accepted_prefixes)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence object is not authorized.")
        prefix = next(prefix for prefix in accepted_prefixes if parsed.path.startswith(prefix))
        raw_path = parsed.path[len(prefix):]
    else:
        raw_path = raw_value

    path = unquote(raw_path)
    parts = path.split("/")
    expected_prefix = ["evidence", category, str(owner_id)]
    if (
        "%" in path
        or len(parts) != 4
        or parts[:3] != expected_prefix
        or any(part in {"", ".", ".."} for part in parts)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[3])
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence object is not authorized.")
    return path


async def evidence_for_authorized_claim(
    rows: Iterable[Dict[str, Any]], *, owner_id: str, database: Any, expires_in: int = 300
) -> List[Dict[str, Any]]:
    """Return evidence rows with short-lived private URLs after route authorization."""
    result = []
    for row in rows:
        item = dict(row)
        category = str(item.get("category") or "")
        if category == "damage_photo":
            category = "photo"
        stored_path = item.get("storage_path")
        if not isinstance(stored_path, str) or stored_path.strip().lower() in {"", "none", "null"}:
            stored_path = item.get("file_url")
        path_value = stored_path or ""
        try:
            path = canonical_evidence_path(path_value, category=category, owner_id=owner_id)
            signed = await database.create_signed_read_url(
                bucket=settings.SUPABASE_STORAGE_BUCKET,
                file_path=path,
                expires_in=expires_in,
            )
            item["file_url"] = signed["signed_url"]
        except (HTTPException, KeyError, TypeError, ValueError):
            # Legacy or malformed rows are never returned as directly fetchable URLs.
            item["file_url"] = ""
        item["storage_path"] = ""
        result.append(item)
    return result


def analysis_for_authorized_claim(analysis: Any, evidence: Iterable[Dict[str, Any]]) -> Any:
    """Replace persisted object paths with the authorized short-lived URL."""
    if not isinstance(analysis, dict):
        return analysis
    result = dict(analysis)
    primary_url = next(
        (
            item.get("file_url")
            for item in evidence
            if item.get("category") in {"photo", "damage_photo"} and item.get("file_url")
        ),
        "",
    )
    for field in ("image_url", "clahe_image_url"):
        if field in result:
            result[field] = primary_url
    return result
