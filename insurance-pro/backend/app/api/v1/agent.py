from datetime import datetime, timezone
import logging
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Query, Request
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.core.authorization import require_agent_claim_access, user_id
from app.core.request_logging import log_route_exception
from app.core.security import get_current_user, require_roles, create_claim_action_token
from app.db.supabase import db
from app.schemas.claim import (
    AgentActionType,
    AgentActionRequest,
    ClaimStatus,
    ClaimResponse
)
from app.services.email import (
    send_agent_approval_email,
    send_agent_rejection_email,
    send_request_info_email
)
from app.services.evidence_storage import analysis_for_authorized_claim, evidence_for_authorized_claim

router = APIRouter(prefix="/agent", tags=["Agent Adjudication Workbench"])
logger = logging.getLogger("claimpilot.agent")


async def _get_claim_by_id_or_number(claim_id: str) -> Optional[Dict[str, Any]]:
    """Helper to query claims table by either database UUID or human-readable claim_number."""
    if claim_id.startswith("CLM-"):
        query_filter = {"claim_number": f"eq.{claim_id}"}
    else:
        query_filter = {"id": f"eq.{claim_id}"}

    return await db.select("claims", params=query_filter, single=True)


@router.get("/claims", summary="Fetch Agent Adjudication Queue with triage filters")
async def get_agent_claims_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_filter: Optional[str] = Query(None, alias="risk"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: Dict[str, Any] = Depends(require_roles(["agent", "admin"]))
):
    params: Dict[str, str] = {"order": "created_at.desc", "limit": str(limit)}
    if user.get("role") == "agent":
        params["assigned_agent_id"] = f"eq.{user_id(user)}"
    if status_filter:
        params["status"] = f"eq.{status_filter}"
    if risk_filter:
        params["risk_level"] = f"eq.{risk_filter}"
    if search:
        params["or"] = f"(claim_number.ilike.*{search}*,policy_number.ilike.*{search}*,driver_name.ilike.*{search}*)"

    claims = await db.select("claims", params=params)
    return {"count": len(claims) if isinstance(claims, list) else 0, "claims": claims}


@router.get("/claims/{claim_id}", summary="Fetch single claim with deep investigation context")
async def get_agent_claim_detail(
    claim_id: str,
    user: Dict[str, Any] = Depends(require_roles(["agent", "admin"]))
):
    claim = await _get_claim_by_id_or_number(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Claim not found in adjudication database", "claim_id": claim_id}
        )

    require_agent_claim_access(claim, user)

    # Use resolved UUID primary key for secondary table joins
    real_claim_id = claim["id"]

    profile = await db.select("profiles", params={"id": f"eq.{claim['user_id']}"}, single=True)
    evidence = await db.select("claim_evidence", params={"claim_id": f"eq.{real_claim_id}"})
    ai_analysis = await db.select("claim_ai_analysis", params={"claim_id": f"eq.{real_claim_id}"}, single=True)
    private_evidence = await evidence_for_authorized_claim(
        evidence or [], owner_id=str(claim.get("user_id") or ""), database=db
    )
    ai_analysis = analysis_for_authorized_claim(ai_analysis, private_evidence)

    return {
        "claim": claim,
        "claimant": profile,
        "evidence": private_evidence,
        "ai_analysis": ai_analysis
    }


@router.post(
    "/claims/{claim_id}/action",
    summary="Execute Agent Adjudication Workflow State Machine",
    status_code=status.HTTP_200_OK
)

async def process_agent_claim_action(
    claim_id: str,
    payload: AgentActionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: Dict[str, Any] = Depends(require_roles(["agent", "admin"]))
):
    claim = await _get_claim_by_id_or_number(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Target claim not found", "claim_id": claim_id}
        )

    require_agent_claim_access(claim, user)

    real_claim_id = claim["id"]
    current_status = claim.get("status")
    terminal_statuses = [ClaimStatus.settlement_accepted.value, ClaimStatus.rejected.value]
    if current_status in terminal_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Illegal state transition. Cannot modify claim in terminal state '{current_status}'.",
                "current_status": current_status,
                "allowed_actions": []
            }
        )

    claimant = await db.select("profiles", params={"id": f"eq.{claim['user_id']}"}, single=True)
    recipient_email = claimant.get("email") if claimant else f"customer_{claim['user_id'][:6]}@claimpilot.com"
    claimant_name = claimant.get("full_name") if claimant else claim.get("driver_name", "Valued Policyholder")

    agent_id = user["user_id"]
    timestamp = datetime.now(timezone.utc).isoformat()

    if payload.action == AgentActionType.APPROVE:
        new_status = ClaimStatus.agent_approved.value

        ai_analysis = await db.select("claim_ai_analysis", params={"claim_id": f"eq.{real_claim_id}"}, single=True)

        # Determine settlement offer: explicit adjuster approved_amount takes precedence,
        # otherwise use persisted AI damage estimates if valid and positive.
        calculated_offer: Optional[float] = None
        min_cost: Optional[float] = None
        max_cost: Optional[float] = None

        if payload.approved_amount is not None and payload.approved_amount > 0:
            calculated_offer = float(payload.approved_amount)
            min_cost = calculated_offer
            max_cost = calculated_offer
        elif ai_analysis and ai_analysis.get("estimated_cost_max") is not None:
            try:
                raw_max = float(ai_analysis.get("estimated_cost_max"))
                raw_min = float(ai_analysis.get("estimated_cost_min") or 0.0)
                if raw_max > 0:
                    calculated_offer = raw_max
                    min_cost = raw_min
                    max_cost = raw_max
            except (ValueError, TypeError):
                calculated_offer = None

        if calculated_offer is None or calculated_offer <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Cannot approve claim without a valid settlement estimate. The claim lacks AI damage estimates; provide an explicit approved amount or route to manual engineering review.",
                    "claim_id": real_claim_id,
                    "status": "manual_review_required"
                }
            )

        update_data = {
            "status": new_status,
            "assigned_agent_id": agent_id,
            "approved_amount": calculated_offer,
            "agent_custom_notes": payload.reason or payload.custom_notes or "",
            "updated_at": timestamp
        }

        try:
            updated_claims = await db.update(
                "claims",
                filters={"id": f"eq.{real_claim_id}", "status": f"eq.{current_status}"},
                data=update_data,
            )
        except Exception as e:
            request_id = log_route_exception(logger, request, "agent.claim.approve_update_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to update claim to approved status", "error": f"Request ID: {request_id}"}
            )

        if not isinstance(updated_claims, list) or not updated_claims:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Claim was modified by another operation. Refresh and try again.",
                    "claim_id": real_claim_id,
                },
            )

        settlement_token = create_claim_action_token(
            claim_id=real_claim_id,
            action="settlement_confirmation",
            expires_minutes=48 * 60,
        )

        background_tasks.add_task(
            send_agent_approval_email,
            to_email=recipient_email,
            claim_number=claim["claim_number"],
            token=settlement_token,
            min_cost=min_cost,
            max_cost=max_cost,
            claimant_name=claimant_name
        )

        return {
            "status": "success",
            "action": payload.action.value,
            "claim_id": real_claim_id,
            "claim_number": claim["claim_number"],
            "previous_status": current_status,
            "new_status": new_status,
            "estimated_bounds": {"min": min_cost, "max": max_cost},
            "message": "Claim successfully approved. Settlement confirmation instructions dispatched to claimant."
        }

    elif payload.action == AgentActionType.REJECT:
        if not payload.reason or len(payload.reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "A detailed rejection reason is mandatory when executing REJECT action.",
                    "field": "reason"
                }
            )

        new_status = ClaimStatus.rejected.value
        rejection_reason = payload.reason.strip()
        update_data = {
            "status": new_status,
            "agent_rejection_reason": rejection_reason,
            "assigned_agent_id": agent_id,
            "updated_at": timestamp
        }

        try:
            updated_claims = await db.update(
                "claims",
                filters={"id": f"eq.{real_claim_id}", "status": f"eq.{current_status}"},
                data=update_data,
            )
        except Exception as e:
            request_id = log_route_exception(logger, request, "agent.claim.reject_update_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to update claim rejection in database", "error": f"Request ID: {request_id}"}
            )

        if not isinstance(updated_claims, list) or not updated_claims:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Claim was modified by another operation. Refresh and try again.",
                    "claim_id": real_claim_id,
                },
            )

        background_tasks.add_task(
            send_agent_rejection_email,
            to_email=recipient_email,
            claim_number=claim["claim_number"],
            reason=rejection_reason,
            claimant_name=claimant_name,
            support_email=settings.SUPPORT_EMAIL
        )

        return {
            "status": "success",
            "action": payload.action.value,
            "claim_id": real_claim_id,
            "claim_number": claim["claim_number"],
            "previous_status": current_status,
            "new_status": new_status,
            "agent_rejection_reason": rejection_reason,
            "support_contact": settings.SUPPORT_EMAIL,
            "message": "Claim rejected. Formal notification dispatched to claimant with logged rationale."
        }

    elif payload.action == AgentActionType.REQUEST_INFO:
        if not payload.requested_items or len(payload.requested_items) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "At least one requested item key must be provided in 'requested_items'.",
                    "field": "requested_items"
                }
            )

        new_status = ClaimStatus.action_required.value
        existing_notes = claim.get("requested_info_notes") or []
        if not isinstance(existing_notes, list):
            existing_notes = []

        new_note_entry = {
            "timestamp": timestamp,
            "agent_id": agent_id,
            "items": payload.requested_items,
            "custom_notes": payload.custom_notes or ""
        }
        updated_notes = existing_notes + [new_note_entry]

        update_data = {
            "status": new_status,
            "requested_info_notes": updated_notes,
            "assigned_agent_id": agent_id,
            "updated_at": timestamp
        }

        try:
            updated_claims = await db.update(
                "claims",
                filters={"id": f"eq.{real_claim_id}", "status": f"eq.{current_status}"},
                data=update_data,
            )
        except Exception as e:
            request_id = log_route_exception(logger, request, "agent.claim.notes_update_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to update claim notes in database", "error": f"Request ID: {request_id}"}
            )

        if not isinstance(updated_claims, list) or not updated_claims:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Claim was modified by another operation. Refresh and try again.",
                    "claim_id": real_claim_id,
                },
            )

        upload_magic_token = create_claim_action_token(
            claim_id=real_claim_id,
            action="evidence_reupload",
            expires_minutes=72 * 60,
        )

        background_tasks.add_task(
            send_request_info_email,
            to_email=recipient_email,
            claim_number=claim["claim_number"],
            requested_items=payload.requested_items,
            magic_token=upload_magic_token,
            claimant_name=claimant_name
        )

        return {
            "status": "success",
            "action": payload.action.value,
            "claim_id": real_claim_id,
            "claim_number": claim["claim_number"],
            "previous_status": current_status,
            "new_status": new_status,
            "requested_items": payload.requested_items,
            "magic_token": upload_magic_token,
            "message": "Claim flagged as 'action_required'. Evidence upload portal link dispatched."
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Unsupported agent action '{payload.action}'."}
        )
