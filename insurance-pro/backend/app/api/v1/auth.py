from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import Dict, Any
import logging
from app.db.supabase import db, supabase_public, supabase_admin
from app.core.security import create_access_token, get_current_user
from app.schemas.claim import UserRegisterRequest, UserProfileResponse, OtpSendRequest, OtpChannel
from app.api.v1.auth_otp import send_otp

logger = logging.getLogger("claimpilot.auth")
router = APIRouter(prefix="/auth", tags=["Authentication & Profiles"])


@router.post("/login", response_model=Dict[str, Any])
async def login_user(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Step 1 of 2FA Login:
    Validate email + password against Supabase Auth.
    If valid, dispatch an OTP to email and mandate OTP verification before logging in.
    """
    email = (payload.get("email") or "").lower().strip()
    password = payload.get("password") or ""

    # ==================== LOGIN DEBUGGER ====================
    print("\n\033[1;33m" + "=" * 60)
    print("🔑 [LOGIN DEBUGGER - STEP 1: PASSWORD CHECK]")
    print(f"  • Email    : '{email}'")
    print(f"  • Password : '{password}' (Length: {len(password)})")
    print("=" * 60 + "\033[0m\n")
    # =======================================================

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Email and password are required"}
        )

    # 1. Authenticate email & password against Supabase Auth using public client
    try:
        auth_res = supabase_admin.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        supabase_user = auth_res.user
        if not supabase_user:
            raise Exception("Invalid credentials")
        
        print("\033[1;32m[LOGIN SUCCESS] Password verified in Supabase Auth. Triggering OTP...\033[0m\n")
    except Exception as auth_err:
        error_msg = str(auth_err)
        print(f"\033[1;31m[LOGIN ERROR] Invalid credentials: {error_msg}\033[0m\n")
        logger.warning(f"[LOGIN FAILED] email={email}: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "error": error_msg}
        )

    # 2. Password is valid -> Dispatch 6-digit OTP code to claimant's email
    otp_response = await send_otp(
        payload=OtpSendRequest(identifier=email, channel=OtpChannel.email),
        background_tasks=background_tasks
    )

    return {
        "message": "Credentials verified. Verification code sent to email.",
        "requires_otp": True,
        "email": email,
        "otp_details": otp_response
    }


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegisterRequest):
    email = payload.email.lower().strip()

    # ==================== REGISTER DEBUGGER ====================
    print("\n\033[1;32m" + "=" * 60)
    print("📝 [DIRECT /AUTH/REGISTER DEBUGGER]")
    print(f"  • Full Name        : '{payload.full_name}'")
    print(f"  • Parsed Email     : '{email}'")
    print(f"  • Phone Number     : '{payload.phone_number}'")
    print(f"  • DOB              : '{payload.dob}'")
    print(f"  • Received Password: '{payload.password}' (Length: {len(payload.password) if payload.password else 0})")
    print("=" * 60 + "\033[0m\n")
    # ===========================================================

    # 1. Check if profile already exists in public.profiles
    existing = await db.select("profiles", params={"email": f"eq.{email}"}, single=True)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An account with this email address already exists.", "email": email}
        )

    # 2. Attempt to create user in Supabase Auth (auth.users)
    try:
        auth_res = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": payload.full_name,
                "role": payload.role.value if hasattr(payload.role, "value") else str(payload.role)
            }
        })
        user_id = auth_res.user.id
        print(f"\033[1;32m[AUTH SUCCESS] Created auth.users record: {user_id}\033[0m")
    except Exception as auth_err:
        error_msg = str(auth_err)
        logger.error(f"[SUPABASE AUTH CREATION FAILED]: {error_msg}")
        
        if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "User already registered in authentication system.", "error": error_msg}
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Auth creation failed: {error_msg}", "error": error_msg}
        )

    # 3. Construct profile payload matching auth.users(id)
    role_value = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    dob_value = payload.dob.isoformat() if hasattr(payload.dob, "isoformat") else str(payload.dob)

    profile_data = {
        "id": user_id,
        "full_name": payload.full_name,
        "email": email,
        "phone_number": payload.phone_number,
        "dob": dob_value,
        "role": role_value
    }

    # 4. Insert into public.profiles using admin privileges
    try:
        supabase_admin.table("profiles").insert(profile_data).execute()
    except Exception as db_err:
        logger.error(f"[PROFILES DB INSERT FAILED]: {str(db_err)}")
        try:
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception as delete_err:
            logger.error(f"[AUTH CLEANUP FAILED]: {str(delete_err)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create user profile record", "error": str(db_err)}
        )

    # 5. Issue JWT access token
    token = create_access_token({
        "sub": user_id,
        "email": email,
        "role": role_value,
        "name": payload.full_name
    })

    return {
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": profile_data
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