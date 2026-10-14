import logging
import random
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import Dict, Any, List

from app.core.config import settings
from app.core.authorization import require_customer_claim_owner
from app.core.request_logging import log_route_exception
from app.core.security import get_current_user
from app.db.supabase import db
from app.schemas.claim import (
    ClaimCreate,
    ClaimResponse,
    CustomerSettlementDecisionRequest,
    CustomerDecisionType,
    ClaimStatus
)

router = APIRouter(prefix="/claims", tags=["Customer Claims Portal"])
logger = logging.getLogger("claimpilot.claims")


def generate_claim_number() -> str:
    year = datetime.now(timezone.utc).year
    suffix = random.randint(10000, 99999)
    return f"CLM-{year}-{suffix}"


@router.post(
    "",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new insurance claim"
)
async def create_claim(
    payload: ClaimCreate,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user)
):
    if user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can create claims.")
    logger.info("event=claim.create.started")
    user_id = user.get("user_id") or user.get("id") or user.get("sub")
    claim_id = str(uuid.uuid4())
    claim_number = generate_claim_number()
    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Validate presence of target policy_number in request body
    target_policy_number = payload.policy_number
    if not target_policy_number or not target_policy_number.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Policy number is required to file a claim."}
        )
    target_policy_number = target_policy_number.strip().upper()

    # 2. STEP 1: Query 'agent_policies' FIRST (Source of Truth for Agent-Policy Mapping)
    agent_mapping = await db.select(
        "agent_policies",
        params={"policy_number": f"eq.{target_policy_number}"},
        single=True
    )

    assigned_agent_id = None

    if agent_mapping and agent_mapping.get("agent_id"):
        assigned_agent_id = agent_mapping.get("agent_id")
        logger.info("event=claim.create.policy_mapping_found")
    else:
        # Fallback: Check if policy already exists in 'policies' table
        logger.info("event=claim.create.policy_mapping_fallback")
        existing_policy = await db.select(
            "policies",
            params={"policy_number": f"eq.{target_policy_number}"},
            single=True
        )
        if existing_policy:
            assigned_agent_id = existing_policy.get("assigned_agent_id") or existing_policy.get("agent_id")
            logger.info("event=claim.create.policy_found")

    if not assigned_agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": f"Policy '{target_policy_number}' is invalid or not registered to any active agent."
            }
        )

    # 3. STEP 2: Verify assigned agent profile exists in public.profiles
    agent_profile = await db.select("profiles", params={"id": f"eq.{assigned_agent_id}"}, single=True)
    if not agent_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": f"Assigned agent for policy '{target_policy_number}' was not found in profiles."
            }
        )
    logger.info("event=claim.create.agent_profile_verified")

    # 4. STEP 3: Create or update row in public.policies on-the-fly
    policy_record = await db.select(
        "policies", 
        params={"policy_number": f"eq.{target_policy_number}"}, 
        single=True
    )

    if not policy_record:
        logger.info("event=claim.create.policy_record_create_started")
        new_policy_dict = {
            "id": str(uuid.uuid4()),
            "policy_number": target_policy_number,
            "assigned_agent_id": assigned_agent_id,
            "customer_name": payload.driver_name,
            "vehicle_model": payload.vehicle_name,
            "created_at": timestamp
        }

        try:
            policy_record = await db.insert("policies", new_policy_dict)
            logger.info("event=claim.create.policy_record_created")
        except Exception as e:
            request_id = log_route_exception(logger, request, "claim.create.policy_record_create_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"success": False, "message": "Failed to create policy record in database", "error": f"Request ID: {request_id}"}
            )
    else:
        # Keep assigned_agent_id in sync if it differed
        current_agent = policy_record.get("assigned_agent_id") or policy_record.get("agent_id")
        if current_agent != assigned_agent_id:
            logger.info("event=claim.create.policy_agent_sync_started")
            try:
                await db.update(
                    "policies",
                    filters={"policy_number": f"eq.{target_policy_number}"},
                    data={"assigned_agent_id": assigned_agent_id}
                )
            except Exception as sync_err:
                logger.warning(
                    "event=claim.create.policy_agent_sync_failed error_type=%s",
                    type(sync_err).__name__,
                )

    # 5. STEP 4: Construct and save claim record
    claim_dict = {
        "id": claim_id,
        "claim_number": claim_number,
        "user_id": user_id,
        "assigned_agent_id": assigned_agent_id,
        "incident_type": payload.incident_type.value,
        "vehicle_name": payload.vehicle_name,
        "policy_number": target_policy_number,
        "hsrp_number": payload.hsrp_number,
        "engine_number": payload.engine_number,
        "chassis_number": payload.chassis_number,
        "incident_date": payload.incident_date.isoformat(),
        "location_address": payload.location_address,
        "description": payload.description,
        "driver_name": payload.driver_name,
        "driver_dl_number": payload.driver_dl_number,
        "status": ClaimStatus.pending_review.value,
        "fraud_score": 0,
        "risk_level": "Low Risk",
        "requested_info_notes": [],
        "created_at": timestamp,
        "updated_at": timestamp
    }

    try:
        logger.info("event=claim.create.record_insert_started")
        created = await db.insert("claims", claim_dict)
        logger.info("event=claim.create.record_inserted")
    except Exception as e:
        request_id = log_route_exception(logger, request, "claim.create.record_insert_failed", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Failed to create claim record in database", "error": f"Request ID: {request_id}"}
        )

    return {
        "success": True,
        "message": "Claim filed successfully. Upload damage photos to start the AI assessment.",
        "claim_id": claim_id,
        "claim_number": claim_number,
        "status": ClaimStatus.pending_review.value,
        "claim": claim_dict
    }


@router.get(
    "",
    summary="List all claims belonging to the authenticated customer"
)
async def list_customer_claims(user: Dict[str, Any] = Depends(get_current_user)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can list customer claims.")
    user_id = user.get("user_id") or user.get("id") or user.get("sub")
    claims = await db.select("claims", params={"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    return {"claims": claims or []}


@router.get(
    "/{claim_id}",
    summary="Fetch single claim details for customer portal"
)
async def get_customer_claim_detail(
    claim_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    claim = None
    
    # Check if claim_id is a valid UUID
    is_uuid = False
    try:
        uuid.UUID(claim_id)
        is_uuid = True
    except ValueError:
        is_uuid = False

    # 1. Query by primary key if UUID, otherwise query by claim_number
    if is_uuid:
        claim = await db.select("claims", params={"id": f"eq.{claim_id}"}, single=True)
    
    if not claim:
        claim = await db.select("claims", params={"claim_number": f"eq.{claim_id}"}, single=True)
        
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Claim not found", "claim_id": claim_id}
        )

    require_customer_claim_owner(claim, user)

    # Resolve real claim UUID for child queries
    real_claim_id = claim.get("id")

    evidence = await db.select("claim_evidence", params={"claim_id": f"eq.{real_claim_id}"})
    ai_analysis = await db.select("claim_ai_analysis", params={"claim_id": f"eq.{real_claim_id}"}, single=True)

    return {
        "claim": claim,
        "evidence": evidence or [],
        "ai_analysis": ai_analysis
    }


@router.get(
    "/{claim_id}/ai-analysis",
    summary="Fetch AI Analysis results for a specific claim"
)
async def get_claim_ai_analysis(
    claim_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    claim = None
    try:
        uuid.UUID(claim_id)
        claim = await db.select("claims", params={"id": f"eq.{claim_id}"}, single=True)
    except ValueError:
        claim = await db.select("claims", params={"claim_number": f"eq.{claim_id}"}, single=True)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Claim not found", "claim_id": claim_id},
        )
    require_customer_claim_owner(claim, user)

    real_claim_id = claim.get("id")
    ai_analysis = await db.select("claim_ai_analysis", params={"claim_id": f"eq.{real_claim_id}"}, single=True)
    if not ai_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "AI analysis not found or still processing for this claim", "claim_id": claim_id}
        )

    return ai_analysis


@router.post(
    "/portal/decision",
    summary="Customer Settlement Decision: Accept or Dispute Settlement",
    status_code=status.HTTP_200_OK
)
async def process_customer_settlement_decision(
    payload: CustomerSettlementDecisionRequest,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user)
):
    claim_id = payload.claim_id
    claim = await db.select("claims", params={"id": f"eq.{claim_id}"}, single=True)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Claim not found", "claim_id": claim_id}
        )

    current_user_id = user.get("user_id") or user.get("id") or user.get("sub")
    require_customer_claim_owner(claim, user)

    timestamp = datetime.now(timezone.utc).isoformat()

    if payload.decision == CustomerDecisionType.ACCEPT:
        new_status = ClaimStatus.settlement_accepted.value
        payout_batch_id = f"PAY-BAT-{uuid.uuid4().hex[:8].upper()}"

        try:
            await db.update(
                "claims",
                filters={"id": f"eq.{claim_id}"},
                data={
                    "status": new_status,
                    "updated_at": timestamp
                }
            )
        except Exception as e:
            request_id = log_route_exception(logger, request, "claim.settlement.accept_update_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to update claim status to settlement_accepted", "error": f"Request ID: {request_id}"}
            )

        return {
            "status": "success",
            "decision": payload.decision.value,
            "claim_id": claim_id,
            "claim_number": claim["claim_number"],
            "new_status": new_status,
            "payout_pipeline": {
                "payout_status": "initiated",
                "batch_id": payout_batch_id,
                "disbursement_channel": "Direct Bank Account / UPI",
                "estimated_settlement_hours": 24
            },
            "message": "Settlement offer accepted. Direct electronic payout pipeline has been queued."
        }

    elif payload.decision in [CustomerDecisionType.REJECT, CustomerDecisionType.DISPUTE]:
        new_status = ClaimStatus.disputed.value
        dispute_entry = {
            "timestamp": timestamp,
            "claimant_id": current_user_id,
            "dispute_notes": payload.dispute_notes or "Claimant disputed proposed repair settlement amount."
        }
        
        existing_notes = claim.get("requested_info_notes") or []
        if not isinstance(existing_notes, list):
            existing_notes = []
        updated_notes = existing_notes + [dispute_entry]

        try:
            await db.update(
                "claims",
                filters={"id": f"eq.{claim_id}"},
                data={
                    "status": new_status,
                    "risk_level": "High Risk",
                    "requested_info_notes": updated_notes,
                    "updated_at": timestamp
                }
            )
        except Exception as e:
            request_id = log_route_exception(logger, request, "claim.settlement.dispute_update_failed", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Failed to flag claim as disputed", "error": f"Request ID: {request_id}"}
            )

        return {
            "status": "disputed",
            "decision": payload.decision.value,
            "claim_id": claim_id,
            "claim_number": claim["claim_number"],
            "new_status": new_status,
            "priority": "HIGH_PRIORITY_REQUEUE",
            "modal_trigger": True,
            "support_contact": {
                "support_email": settings.SUPPORT_EMAIL,
                "phone_number": "+91 (800) 252-4674",
                "desk_hours": "24/7 Priority Dispute Assistance",
                "message": "Your claim has been escalated to a senior adjuster for re-evaluation. A specialist will reach out within 4 business hours."
            },
            "message": "Claim settlement disputed. Case re-queued to Agent Dashboard with High Priority escalation."
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Invalid settlement decision '{payload.decision}'. Allowed: ACCEPT, REJECT, DISPUTE."}
        )
