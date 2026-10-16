from typing import Any, Dict

from fastapi import HTTPException, status


def user_id(user: Dict[str, Any]) -> Any:
    return user.get("user_id") or user.get("id") or user.get("sub")


def require_customer_claim_owner(claim: Dict[str, Any], user: Dict[str, Any]) -> None:
    claim_owner_id = claim.get("user_id") or claim.get("customer_id")
    if user.get("role") != "customer" or str(claim_owner_id) != str(user_id(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You are not authorized to access this customer claim."},
        )


def require_agent_claim_access(claim: Dict[str, Any], user: Dict[str, Any]) -> None:
    assigned_agent_id = claim.get("assigned_agent_id")
    if user.get("role") == "admin":
        return
    if user.get("role") != "agent" or str(assigned_agent_id) != str(user_id(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "You are not authorized to access this assigned claim."},
        )
