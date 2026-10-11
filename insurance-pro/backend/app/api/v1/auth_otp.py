# app/api/v1/auth_otp.py
import random
import logging
import os
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, Any

from app.core.config import settings
from app.core.security import create_access_token
from app.db.supabase import db, supabase_admin
from app.schemas.claim import (
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
    OtpChannel
)
from app.services.email import _dispatch_email

router = APIRouter(prefix="/auth/otp", tags=["Dual OTP Authentication (Email & SMS)"])
logger = logging.getLogger("claimpilot.otp")

_environment = os.environ.get("ENVIRONMENT", "").strip().lower()
_dev_fixed_code = os.environ.get("OTP_DEV_FIXED_CODE")
if _dev_fixed_code is not None:
    if _environment != "development":
        raise RuntimeError("OTP_DEV_FIXED_CODE is allowed only when ENVIRONMENT=development")
    if len(_dev_fixed_code) != 6 or not _dev_fixed_code.isdigit():
        raise RuntimeError("OTP_DEV_FIXED_CODE must be exactly six digits")


async def send_otp_via_email(email: str, otp_code: str):
    """Deliver formatted HTML OTP to claimant's email address."""
    subject = f"🔐 Your ClaimPilot Verification Code: {otp_code}"
    plain_text = f"Your ClaimPilot 6-digit verification code is: {otp_code}. This code expires in 10 minutes."
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0d1117; color: #e6edf3; padding: 20px; }}
    .card {{ max-width: 480px; margin: 0 auto; background: #161b22; border-radius: 12px; border: 1px solid #30363d; padding: 32px; text-align: center; }}
    .logo {{ font-size: 20px; font-weight: 700; color: #388bfd; margin-bottom: 8px; }}
    .otp-display {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #58a6ff; background: #21262d; border-radius: 8px; padding: 16px 24px; margin: 24px 0; border: 1px dashed #388bfd; }}
    .footer {{ font-size: 12px; color: #8b949e; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">ClaimPilot Identity Verification</div>
    <p>Please enter the following one-time code to authenticate your session:</p>
    <div class="otp-display">{otp_code}</div>
    <p style="font-size: 14px; color: #8b949e;">This code will expire in <strong>10 minutes</strong>. Do not share this code with anyone.</p>
    <div class="footer">ClaimPilot Security &bull; support@claimpilot.com</div>
  </div>
</body>
</html>
"""
    await _dispatch_email(email, subject, html_content, plain_text)


async def send_otp_via_sms(phone_number: str, otp_code: str, user_id: str | None = None):
    """Deliver SMS OTP via Twilio REST API or Fast2SMS with local fallback."""
    sms_body = f"ClaimPilot: Your verification code is {otp_code}. Valid for 10 minutes. Do not share this OTP."

    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        data = {
            "From": settings.TWILIO_PHONE_NUMBER,
            "To": phone_number,
            "Body": sms_body
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, auth=auth, data=data)
                if resp.status_code >= 400:
                    logger.error("event=auth.otp.sms outcome=failure user_id=%s", user_id or "unknown")
                else:
                    logger.info("event=auth.otp.sms outcome=sent user_id=%s", user_id or "unknown")
        except Exception as e:
            logger.error("event=auth.otp.sms outcome=failure user_id=%s", user_id or "unknown")
    
    elif settings.FAST2SMS_API_KEY:
        clean_number = "".join([c for c in phone_number if c.isdigit()])[-10:]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "authorization": settings.FAST2SMS_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                payload = {
                    "variables_values": otp_code,
                    "route": "otp",
                    "numbers": clean_number
                }
                resp = await client.post("https://www.fast2sms.com/dev/bulkV2", headers=headers, data=payload)
                outcome = "failure" if resp.status_code >= 400 else "sent"
                logger.info("event=auth.otp.sms outcome=%s user_id=%s", outcome, user_id or "unknown")
        except Exception as e:
            logger.error("event=auth.otp.sms outcome=failure user_id=%s", user_id or "unknown")

    else:
        logger.info("event=auth.otp.sms outcome=not_configured user_id=%s", user_id or "unknown")


@router.post("/send", response_model=OtpSendResponse, status_code=status.HTTP_200_OK)
async def send_otp(payload: OtpSendRequest, background_tasks: BackgroundTasks):
    clean_identifier = payload.identifier.strip()
    if payload.channel == OtpChannel.email:
        clean_identifier = clean_identifier.lower()
    
    user_filter = "email" if payload.channel == OtpChannel.email else "phone_number"
    existing_user = await db.select("profiles", params={user_filter: f"eq.{clean_identifier}"}, single=True)
    user_id = existing_user.get("id") if isinstance(existing_user, dict) else None
    
    # A fixed code is available only for SMS in development, validated at import.
    if payload.channel == OtpChannel.sms and _dev_fixed_code is not None:
        otp_code = _dev_fixed_code
    else:
        otp_code = f"{random.randint(0, 999999):06d}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    otp_record = {
        "identifier": clean_identifier,
        "otp_code": str(otp_code),
        "channel": payload.channel.value,
        "attempts": 0,
        "is_verified": False,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat()
    }

    try:
        await db.insert("otp_verifications", otp_record)
        logger.info("event=auth.otp.send outcome=recorded user_id=%s", user_id or "unknown")
    except Exception as e:
        logger.error("event=auth.otp.send outcome=record_failed user_id=%s", user_id or "unknown")

    if payload.channel == OtpChannel.email:
        background_tasks.add_task(send_otp_via_email, clean_identifier, otp_code)
    else:
        background_tasks.add_task(send_otp_via_sms, clean_identifier, otp_code, user_id)

    return OtpSendResponse(
        message=f"6-digit verification code dispatched via {payload.channel.value.upper()}.",
        identifier=clean_identifier,
        channel=payload.channel.value,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES
    )


@router.post("/verify", response_model=OtpVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_otp(payload: OtpVerifyRequest):
    identifier = payload.identifier.strip()
    if "@" in identifier:
        identifier = identifier.lower()

    user_otp = str(payload.otp_code).strip()

    # Extract raw metadata payload sent from frontend
    meta = getattr(payload, "metadata", None) or getattr(payload, "user_metadata", None)
    
    # Safely inspect password across dict or object
    password_val = None
    if meta:
        password_val = meta.get("password") if isinstance(meta, dict) else getattr(meta, "password", None)

    # ==================== REGISTER / OTP DEBUGGER ====================
    # =================================================================

    # Query latest unverified OTP record for the identifier
    records = await db.select(
        "otp_verifications",
        params={
            "identifier": f"eq.{identifier}",
            "is_verified": "eq.false",
            "order": "created_at.desc",
            "limit": "1"
        }
    )

    if not records or len(records) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP request found. Please request a new OTP."
        )

    active_otp = records[0]
    otp_id = active_otp["id"]
    current_attempts = active_otp.get("attempts", 0)

    # Validate expiration
    expires_at_raw = active_otp.get("expires_at")
    if expires_at_raw:
        expires_at_dt = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new OTP."
            )

    # Check attempt threshold
    if current_attempts >= settings.MAX_OTP_ATTEMPTS:
        await db.update("otp_verifications", filters={"id": f"eq.{otp_id}"}, data={"is_verified": False, "attempts": current_attempts + 1})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum verification attempts exceeded (3/3). Please request a fresh code."
        )

    # Guarantee 6-digit string alignment for comparison
    raw_db_otp = str(active_otp["otp_code"]).strip()
    db_otp = raw_db_otp.zfill(6) if raw_db_otp.isdigit() else raw_db_otp

    if db_otp != user_otp:
        new_attempts = current_attempts + 1
        await db.update("otp_verifications", filters={"id": f"eq.{otp_id}"}, data={"attempts": new_attempts})
        remaining = settings.MAX_OTP_ATTEMPTS - new_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining."
        )

    # Mark OTP as verified
    await db.update(
        "otp_verifications", 
        filters={"id": f"eq.{otp_id}"}, 
        data={"is_verified": True, "attempts": current_attempts + 1}
    )

    channel = active_otp.get("channel", "email")
    user_filter = "email" if channel == "email" else "phone_number"
    
    # Check if user already exists in public.profiles
    profile = await db.select("profiles", params={user_filter: f"eq.{identifier}"}, single=True)
    
    if profile:
        # Existing user -> Complete 2FA login flow
        user_id = profile["id"]
        update_fields = {"is_email_verified": True} if channel == "email" else {"is_phone_verified": True}
        
        # Update metadata if passed from UI
        if meta:
            full_name_val = meta.get("full_name") if isinstance(meta, dict) else getattr(meta, "full_name", None)
            phone_val = meta.get("phone_number") if isinstance(meta, dict) else getattr(meta, "phone_number", None)
            dob_val = meta.get("dob") if isinstance(meta, dict) else getattr(meta, "dob", None)

            if full_name_val:
                update_fields["full_name"] = full_name_val
            if phone_val:
                update_fields["phone_number"] = phone_val
            if dob_val:
                update_fields["dob"] = str(dob_val)

        await db.update("profiles", filters={"id": f"eq.{user_id}"}, data=update_fields)
        
        # Refresh profile details for JWT payload
        profile = await db.select("profiles", params={"id": f"eq.{user_id}"}, single=True)
        role = profile.get("role", "customer")
        full_name = profile.get("full_name", "Verified User")
        email = profile.get("email", identifier if channel == "email" else "")
    else:
        # New user -> Complete sign-up flow & provision user in Supabase Auth
        email_prefix = identifier.split("@")[0] if "@" in identifier else identifier
        
        full_name_val = meta.get("full_name") if isinstance(meta, dict) else getattr(meta, "full_name", None)
        phone_val = meta.get("phone_number") if isinstance(meta, dict) else getattr(meta, "phone_number", None)
        dob_val = meta.get("dob") if isinstance(meta, dict) else getattr(meta, "dob", None)

        full_name = full_name_val or email_prefix.capitalize()
        phone_number = phone_val or (identifier if channel == "sms" else "")
        dob = str(dob_val) if dob_val else "2000-01-01"
        role = "customer"
        email = identifier if channel == "email" else f"{identifier}@claimpilot.sms"

        # 1. Provision user inside Supabase Auth (auth.users)
        try:
            create_params = {
                "email": email,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": full_name,
                    "phone_number": phone_number,
                    "role": role
                }
            }
            if password_val:
                create_params["password"] = str(password_val)

            auth_res = supabase_admin.auth.admin.create_user(create_params)
            user_id = auth_res.user.id
            logger.info("event=auth.otp.verify outcome=auth_user_created user_id=%s", user_id)
        except Exception as auth_err:
            logger.warning("event=auth.otp.verify outcome=auth_user_creation_failed")
            import uuid
            user_id = str(uuid.uuid4())

        # 2. Insert into public.profiles matching auth.users ID
        new_user = {
            "id": user_id,
            "full_name": full_name,
            "email": email,
            "phone_number": phone_number,
            "dob": dob,
            "role": role,
            "is_email_verified": True if channel == "email" else False,
            "is_phone_verified": True if channel == "sms" else False
        }
        try:
            supabase_admin.table("profiles").insert(new_user).execute()
            profile = new_user
        except Exception as db_err:
            logger.error("event=auth.otp.verify outcome=profile_insert_failed user_id=%s", user_id)
            profile = {"id": user_id, "full_name": full_name, "email": email, "phone_number": phone_number, "dob": dob, "role": role}

    # Issue session access token upon successful OTP verification
    token = create_access_token({
        "sub": user_id,
        "email": email,
        "role": role,
        "name": full_name
    })
    logger.info("event=auth.otp.verify outcome=success user_id=%s", user_id)

    return OtpVerifyResponse(
        message="Identity successfully verified.",
        is_verified=True,
        access_token=token,
        token_type="bearer",
        user=profile
    )
