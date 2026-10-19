from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Request
from typing import Dict, Any
import logging
from app.db.supabase import db, supabase_public
from app.core.security import get_current_user
from app.core.request_logging import log_route_exception
from app.schemas.claim import UserRegisterRequest, OtpSendRequest, OtpChannel
from app.api.v1.auth_otp import issue_otp

logger = logging.getLogger("claimpilot.auth")
router = APIRouter(prefix="/auth", tags=["Authentication & Profiles"])


@router.post("/login", response_model=Dict[str, Any])
async def login_user(payload: Dict[str, Any], background_tasks: BackgroundTasks, request: Request):
    """
    Step 1 of 2FA Login:
    Validate email or phone number + password against Supabase Auth.
    If valid, dispatch an OTP and mandate OTP verification before logging in.
    """
    identifier = (payload.get("email") or payload.get("identifier") or "").strip()
    password = payload.get("password") or ""

    if not identifier or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Email and password are required"}
        )

    # Determine if input is an email or a phone number
    is_email = "@" in identifier
    if is_email:
        email = identifier.lower()
    else:
        # If it's a phone number, clean it and look up the associated email from the profiles table
        clean_phone = "".join([c for c in identifier if c.isdigit()])[-10:]
        try:
            profile = await db.select("profiles", params={"phone_number": f"ilike.*{clean_phone}*"}, single=True)
        except Exception as exc:
            logger.error("event=auth.login outcome=phone_lookup_failed error_type=%s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Database lookup failed during login."}
            )

        if not profile or not isinstance(profile, dict) or not profile.get("email"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "No account found registered with this phone number."}
            )
        email = profile.get("email")

    # Validate the password before creating the login OTP challenge.
    try:
        # Never perform end-user password sign-in on the shared service-role client.
        auth_res = supabase_public.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        supabase_user = auth_res.user
        if not supabase_user:
            raise Exception("Invalid credentials")
        logger.info("event=auth.login outcome=credentials_verified user_id=%s", supabase_user.id)

    except Exception as auth_err:
        logger.warning("event=auth.login outcome=failure")
        request_id = log_route_exception(logger, request, "auth.login.failed", auth_err)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "error": f"Request ID: {request_id}"}
        )

    # The purpose- and user-bound OTP challenge is issued only after password auth.
    otp_channel = OtpChannel.email if is_email else OtpChannel.sms
    otp_identifier = email if is_email else identifier
    otp_response = await issue_otp(
        payload=OtpSendRequest(identifier=otp_identifier, channel=otp_channel),
        background_tasks=background_tasks,
        purpose="login",
        authenticated_user_id=str(supabase_user.id),
    )

    message = (
        "Password accepted. An email verification challenge was recorded; enter the code once it arrives."
        if is_email
        else "Password accepted. An SMS verification challenge was recorded; enter the code once it arrives."
    )
    return {
        "message": message,
        "requires_otp": True,
        "email": email,
        "otp_details": otp_response
    }


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
async def register_user(payload: UserRegisterRequest, background_tasks: BackgroundTasks, request: Request):
    email = payload.email.lower().strip()
    phone_number = (payload.phone_number or "").strip()
    clean_phone = "".join([c for c in phone_number if c.isdigit()])[-10:] if phone_number else ""

    try:
        existing_email = await db.select("profiles", params={"email": f"eq.{email}"}, single=True)
        existing_phone = None
        if clean_phone:
            existing_phone = await db.select(
                "profiles",
                params={"phone_number": f"ilike.*{clean_phone}*"},
                single=True,
            )
    except Exception as db_err:
        request_id = log_route_exception(logger, request, "auth.register.profile_lookup_failed", db_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Unable to start registration verification.", "error": f"Request ID: {request_id}"},
        ) from db_err

    if existing_email and isinstance(existing_email, dict) and existing_email.get("id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An account with this email address already exists.", "email": email}
        )

    if existing_phone and isinstance(existing_phone, dict) and existing_phone.get("id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An account with this phone number already exists.", "phone_number": phone_number}
        )

    otp_response = await issue_otp(
        payload=OtpSendRequest(identifier=email, channel=OtpChannel.email),
        background_tasks=background_tasks,
        purpose="signup",
    )
    logger.info("event=auth.register outcome=verification_dispatched")
    return {
        "message": "Verification challenge created. Enter the emailed code once it arrives to finish registration.",
        "requires_otp": True,
        "otp_details": otp_response,
    }


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["user_id"]
    profile = await db.select("profiles", params={"id": f"eq.{user_id}"}, single=True)
    if not profile:
        return {
            "id": user_id,
            "email": user.get("email"),
            "role": user.get("role", "customer"),
            "full_name": user.get("raw_payload", {}).get("name", "User")
        }
    return profile
