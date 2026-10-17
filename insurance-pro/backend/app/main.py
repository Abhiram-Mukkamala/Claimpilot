from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import logging
import os

from app.core.request_logging import log_route_exception

logger = logging.getLogger("claimpilot.api")

from app.core.config import settings
from app.db.supabase import db
from app.api.v1 import api_v1_router

# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Production-ready FastAPI backend for ClaimPilot AI Motor Insurance Platform, powered by Supabase (PostgreSQL, Auth, Storage).",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ----------------------------------------------------
# CORS Middleware Configuration
# ----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# Structured Exception Handlers
# ----------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Ensure consistent structured HTTP exception response across all endpoints."""
    detail = exc.detail
    if isinstance(detail, str):
        detail = {"message": detail}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "status_code": exc.status_code,
            "detail": detail
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic schema validation failures with precise parameter breakdown."""
    errors = []
    for err in exc.errors():
        field = ".".join([str(loc) for loc in err.get("loc", []) if loc != "body"])
        errors.append({
            "field": field,
            "message": err.get("msg"),
            "type": err.get("type")
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": {
                "message": "Input validation failed. Please check the supplied parameters.",
                "errors": errors
            }
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Return a client-safe error and log only non-sensitive diagnostic metadata."""
    request_id = log_route_exception(
        logger, request, "api.unhandled_exception", exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": {
                "message": "An unexpected internal server error occurred.",
                "error": f"Request ID: {request_id}"
            }
        }
    )


# ----------------------------------------------------
# Global Routers
# ----------------------------------------------------
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", summary="Root Health Check", tags=["System Diagnostics"])
async def root_health():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/health", summary="Liveness Probe", tags=["System Diagnostics"])
async def health_check():
    # Liveness deliberately does not depend on downstream services.
    return {"status": "healthy"}


@app.get("/health/ready", summary="Supabase and OTP readiness probe", tags=["System Diagnostics"])
async def readiness_check():
    """Verify backend Data API access and required email-OTP configuration."""
    try:
        rows = await db.select("profiles", params={"select": "id", "limit": "1"})
        if not isinstance(rows, list):
            raise RuntimeError("Supabase Data API returned an unexpected response")
    except Exception as exc:
        logger.warning(
            "event=readiness.database outcome=unavailable error_type=%s",
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "dependencies": {"database": "unavailable"},
            },
        )

    email_configured = bool(settings.SENDGRID_API_KEY and settings.SENDGRID_FROM_EMAIL)
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    fixed_code = os.environ.get("OTP_DEV_FIXED_CODE", "")
    local_fixed_code = (
        environment in {"development", "test"}
        and len(fixed_code) == 6
        and fixed_code.isdigit()
    )
    if not email_configured and not local_fixed_code:
        logger.warning("event=readiness.otp_email outcome=not_configured")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "dependencies": {
                    "database": "reachable",
                    "email_otp": "not_configured",
                },
            },
        )

    return {
        "status": "ready",
        "dependencies": {
            "database": "reachable",
            "email_otp": "configured" if email_configured else "development_fixed_code",
        },
    }


async def warn_deprecated_cors_origins():
    """Warn when the legacy CORS_ORIGINS environment variable is present."""
    if "CORS_ORIGINS" in os.environ:
        logger.warning(
            "event=config.deprecated_setting setting=CORS_ORIGINS "
            "replacement=ALLOWED_ORIGINS"
        )


@app.on_event("startup")
async def _warn_deprecated_cors_origins_on_startup():
    await warn_deprecated_cors_origins()
