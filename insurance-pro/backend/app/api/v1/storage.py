import os
import uuid
import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import Dict, Any

from app.core.config import settings
from app.core.security import get_current_user
from app.db.supabase import db
from app.schemas.claim import (
    PresignedUploadUrlRequest,
    PresignedUploadUrlResponse,
    ClaimEvidenceCreate,
    ClaimEvidenceResponse
)
from app.services.ai_runner import trigger_ai_assessment

router = APIRouter(prefix="/storage", tags=["Storage & Evidence Uploads"])

# Constants for evidence validation
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB Supabase Limit
MAX_PHOTO_COUNT = 10
MAX_VIDEO_COUNT = 2


@router.post(
    "/presigned-url", 
    response_model=PresignedUploadUrlResponse, 
    status_code=status.HTTP_200_OK,
    summary="Generate direct client-to-Supabase signed upload URL"
)
async def generate_presigned_upload_url(
    payload: PresignedUploadUrlRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    category_val = payload.category.value if hasattr(payload.category, 'value') else str(payload.category)

    # 1. Enforce 50MB max file size limit check
    if getattr(payload, 'file_size_bytes', 0) and payload.file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "message": f"File size exceeds maximum allowed limit of 50MB ({payload.file_size_bytes} bytes provided). Please compress your media.",
                "max_allowed_bytes": MAX_FILE_SIZE_BYTES
            }
        )

    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(payload.file_name))
    unique_prefix = uuid.uuid4().hex[:12]
    timestamp = int(datetime.now(timezone.utc).timestamp())
    
    file_path = f"evidence/{category_val}/{user['user_id']}/{timestamp}_{unique_prefix}_{clean_name}"
    expires_in = 900

    try:
        sign_result = await db.create_signed_upload_url(
            bucket=settings.SUPABASE_STORAGE_BUCKET,
            file_path=file_path,
            expires_in=expires_in
        )
        
        public_url = (
            f"{settings.SUPABASE_URL}/storage/v1/object/public/"
            f"{settings.SUPABASE_STORAGE_BUCKET}/{file_path}"
        )

        return PresignedUploadUrlResponse(
            upload_url=sign_result["signed_url"],
            file_path=file_path,
            public_url=public_url,
            expires_in_seconds=expires_in,
            category=category_val
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Failed to generate storage upload URL from Supabase",
                "error": str(e),
                "bucket": settings.SUPABASE_STORAGE_BUCKET
            }
        )


@router.post(
    "/evidence",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Register uploaded evidence media in catalog"
)
async def catalog_evidence(
    payload: ClaimEvidenceCreate,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user)
):
    category_val = payload.category.value if hasattr(payload.category, 'value') else str(payload.category)

    claim = await db.select("claims", params={"id": f"eq.{payload.claim_id}"}, single=True)
    if not claim:
        claim = await db.select("claims", params={"claim_number": f"eq.{payload.claim_id}"}, single=True)
        
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Target claim not found", "claim_id": payload.claim_id}
        )
    
    claim_user_id = claim.get("user_id") or claim.get("customer_id")
    claim_assigned_agent_id = claim.get("assigned_agent_id")
    current_user_id = user.get("user_id") or user.get("id") or user.get("sub")
    user_role = user.get("role", "customer")

    is_authorized = (
        str(claim_user_id) == str(current_user_id) or
        (claim_assigned_agent_id and str(claim_assigned_agent_id) == str(current_user_id)) or
        user_role in ["agent", "admin"]
    )

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You are not authorized to catalog evidence for this claim."}
        )

    # 2. Enforce Evidence Quantity Limits per Claim
    existing_evidence = await db.select("claim_evidence", params={"claim_id": f"eq.{payload.claim_id}"})
    existing_evidence = existing_evidence or []

    category_counts = {}
    for item in existing_evidence:
        cat = item.get("category")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    if category_val == "photo" and category_counts.get("photo", 0) >= MAX_PHOTO_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Maximum limit of {MAX_PHOTO_COUNT} damage photos reached for this claim."}
        )

    if category_val in ["video", "walkaround_video"] and category_counts.get(category_val, 0) >= MAX_VIDEO_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Maximum limit of {MAX_VIDEO_COUNT} videos reached for this claim."}
        )

    if category_val in ["dl_front", "dl_back"] and category_counts.get(category_val, 0) >= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Only one upload is allowed for {category_val}."}
        )

    # 3. Derive storage_path to satisfy NOT NULL database constraint
    storage_path = getattr(payload, "storage_path", None)
    if not storage_path and payload.file_url:
        clean_url = payload.file_url.split("?")[0]
        if "/storage/v1/object/public/" in clean_url:
            storage_path = clean_url.split("/storage/v1/object/public/")[-1]
        else:
            storage_path = f"evidence/{payload.claim_id}/{clean_url.split('/')[-1]}"

    evidence_data = {
        "claim_id": payload.claim_id,
        "file_url": payload.file_url,
        "storage_path": storage_path,  # Satisfies NOT NULL constraint on claim_evidence.storage_path
        "file_type": payload.file_type,
        "category": category_val
    }

    try:
        created = await db.insert("claim_evidence", evidence_data)

        # Trigger AI assessment in background when a damage photo is uploaded
        if category_val == "photo":
            background_tasks.add_task(trigger_ai_assessment, claim_id=payload.claim_id)

        return {"message": "Evidence cataloged successfully", "evidence": created}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to register evidence entry", "error": str(e)}
        )