from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.auth_otp import router as auth_otp_router
from app.api.v1.claims import router as claims_router
from app.api.v1.agent import router as agent_router
from app.api.v1.storage import router as storage_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(auth_otp_router)
api_v1_router.include_router(claims_router)
api_v1_router.include_router(agent_router)
api_v1_router.include_router(storage_router)

__all__ = [
    "api_v1_router", 
    "auth_router", 
    "auth_otp_router",
    "claims_router", 
    "agent_router", 
    "storage_router"
]
