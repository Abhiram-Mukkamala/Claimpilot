# app/api/v1/auth_otp.py
import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import uuid
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Any

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
MAX_OTP_SENDS = 3
OTP_SEND_WINDOW_MINUTES = 10
_send_locks = tuple(asyncio.Lock() for _ in range(64))


_environment = (os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT).strip().lower()
_dev_fixed_code = os.environ.get("OTP_DEV_FIXED_CODE", settings.OTP_DEV_FIXED_CODE)
if _dev_fixed_code is not None:
    if _environment not in {"development", "test"}:
        raise RuntimeError("OTP_DEV_FIXED_CODE is allowed only when ENVIRONMENT=development or test")
    if len(_dev_fixed_code) != 6 or not _dev_fixed_code.isdigit():
        raise RuntimeError("OTP_DEV_FIXED_CODE must be exactly six digits")


def _otp_delivery_configured(channel: OtpChannel) -> bool:
    """Return whether a real provider or explicit test mode supports this channel."""
    if _environment == "test":
        return True
    if channel == OtpChannel.email:
        return bool(settings.SENDGRID_API_KEY and settings.SENDGRID_FROM_EMAIL)
    twilio_ready = bool(
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_PHONE_NUMBER
    )
    return twilio_ready or bool(settings.FAST2SMS_API_KEY)


def _otp_tag(
    otp_code: str,
    *,
    identifier: str,
    channel: str,
    purpose: str,
    user_id: str,
    challenge_id: str,
    created_at: str,
) -> str:
    """Return a schema-compatible keyed tag; never persist the raw OTP."""
    key = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        b"claimpilot:otp-verification:v1",
        hashlib.sha256,
    ).digest()
    message = "\0".join((purpose, identifier, channel, user_id, challenge_id, created_at, otp_code))
    digest = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def _parse_expiry(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing OTP expiry")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _canonical_timestamp(value: Any) -> str:
    parsed = _parse_expiry(value)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


async def issue_otp(
    payload: OtpSendRequest,
    background_tasks: BackgroundTasks,
    *,
    purpose: str,
    authenticated_user_id: str = "",
) -> OtpSendResponse:
    """Create a short-lived login or signup challenge and dispatch its code."""
    fixed_code_mode = _environment in {"development", "test"} and _dev_fixed_code is not None
    if not fixed_code_mode and not _otp_delivery_configured(payload.channel):
        logger.error(
            "event=auth.otp.send outcome=provider_not_configured channel=%s",
            payload.channel.value,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification delivery is not configured for this channel.",
        )

    clean_identifier = payload.identifier.strip()
    if payload.channel == OtpChannel.email:
        clean_identifier = clean_identifier.lower()

    user_filter = "email" if payload.channel == OtpChannel.email else "phone_number"
    existing_user = await db.select("profiles", params={user_filter: f"eq.{clean_identifier}"}, single=True)
    user_id = str(existing_user.get("id")) if isinstance(existing_user, dict) and existing_user.get("id") else ""

    if purpose == "signup":
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to start verification for this identifier.",
            )
    elif purpose == "login":
        if not user_id or user_id != str(authenticated_user_id):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to start verification.",
            )
    else:
        raise ValueError("Unsupported OTP purpose")

    # Process-local serialization closes the check-then-insert race within one
    # worker. A database RPC/constraint is still required across workers.
    lock_key = f"{clean_identifier}\0{payload.channel.value}"
    lock = _send_locks[hash(lock_key) % len(_send_locks)]
    async with lock:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=OTP_SEND_WINDOW_MINUTES)
        recent_requests = await db.select(
            "otp_verifications",
            params={
                "identifier": f"eq.{clean_identifier}",
                "created_at": f"gte.{window_start.isoformat()}",
                "select": "id",
                "limit": str(MAX_OTP_SENDS),
            },
        )
        if not isinstance(recent_requests, list):
            logger.error("event=auth.otp.send outcome=rate_limit_check_failed")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to send a verification code.")
        if len(recent_requests) >= MAX_OTP_SENDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification codes requested. Please try again later.",
            )

        # Fixed codes are import-time gated to development/test only.
        otp_code = _dev_fixed_code if _dev_fixed_code is not None else f"{secrets.randbelow(1_000_000):06d}"
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        challenge_id = str(uuid.uuid4())
        created_at = _canonical_timestamp(now.isoformat())
        otp_record = {
            "id": challenge_id,
            "identifier": clean_identifier,
            "otp_code": _otp_tag(
                otp_code,
                identifier=clean_identifier,
                channel=payload.channel.value,
                purpose=purpose,
                user_id=user_id,
                challenge_id=challenge_id,
                created_at=created_at,
            ),
            "channel": payload.channel.value,
            "purpose": purpose,
            "user_id": user_id or None,
            "attempts": 0,
            "is_verified": False,
            "expires_at": expires_at.isoformat(),
            "created_at": created_at,
        }

        try:
            await db.insert("otp_verifications", otp_record)
        except Exception as exc:
            logger.error("event=auth.otp.send outcome=record_failed user_id=%s", user_id or "unknown")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send a verification code.",
            ) from exc

    logger.info("event=auth.otp.send outcome=recorded user_id=%s", user_id or "unknown")
    if fixed_code_mode:
        # Do not enqueue a mock transport for a configured local/test fixed code.
        logger.info("event=auth.otp.delivery outcome=fixed_code_mode user_id=%s", user_id or "unknown")
    elif payload.channel == OtpChannel.email:
        background_tasks.add_task(send_otp_via_email, clean_identifier, otp_code)
    else:
        background_tasks.add_task(send_otp_via_sms, clean_identifier, otp_code, user_id or None)

    message = (
        "Verification challenge created using a development/test fixed code."
        if fixed_code_mode
        else f"Verification challenge recorded; delivery was scheduled via {payload.channel.value.upper()}."
    )
    return OtpSendResponse(
        message=message,
        identifier=clean_identifier,
        channel=payload.channel.value,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        challenge_id=challenge_id,
    )

async def send_otp_via_email(email: str, otp_code: str) -> bool:
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
    return await _dispatch_email(email, subject, html_content, plain_text)


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
    return await issue_otp(payload, background_tasks, purpose="signup")


@router.post("/verify", response_model=OtpVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_otp(payload: OtpVerifyRequest):
    identifier = payload.identifier.strip()
    if "@" in identifier:
        identifier = identifier.lower()
    user_otp = str(payload.otp_code).strip()
    channel = payload.channel.value
    user_filter = "email" if payload.channel == OtpChannel.email else "phone_number"

    otp_filters = {
        "identifier": f"eq.{identifier}",
        "channel": f"eq.{channel}",
        "is_verified": "eq.false",
        "order": "created_at.desc,id.desc",
        "limit": "1",
    }
    try:
        records = await db.select(
            "otp_verifications",
            params=otp_filters,
        )
    except Exception as exc:
        logger.error("event=auth.otp.verify outcome=lookup_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.") from exc
    if not isinstance(records, list):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.")
    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP request found. Please request a new OTP."
        )

    active_otp = records[0]
    otp_id = active_otp.get("id")
    created_at = active_otp.get("created_at")
    if payload.challenge_id and payload.challenge_id != str(otp_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification challenge has been replaced. Please use the latest code.",
        )
    if not otp_id or not created_at or active_otp.get("channel") != channel:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code is invalid. Please request a new code.")

    # A login challenge exists only when the password-authenticated login path
    # inserted it. Public OTP sends are signup-only and reject existing users.
    try:
        profile = await db.select("profiles", params={user_filter: f"eq.{identifier}"}, single=True)
    except Exception as exc:
        logger.error("event=auth.otp.verify outcome=profile_lookup_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.") from exc
    if profile and not isinstance(profile, dict):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.")
    purpose = "login" if profile else "signup"
    user_id = str(profile.get("id")) if profile and profile.get("id") else ""
    if purpose == "login" and not user_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.")

    # The stored challenge's purpose and identity are authoritative bindings.
    # Never infer a signup challenge from a login challenge (or vice versa).
    stored_purpose = active_otp.get("purpose")
    stored_user_id = str(active_otp.get("user_id") or "")
    if (
        stored_purpose != purpose
        or (purpose == "login" and stored_user_id != user_id)
        or (purpose == "signup" and stored_user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is invalid. Please request a new code.",
        )

    try:
        current_attempts = int(active_otp.get("attempts", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is invalid. Please request a new OTP.",
        ) from exc

    try:
        expires_at_dt = _parse_expiry(active_otp.get("expires_at"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new OTP.",
        ) from exc
    now = datetime.now(timezone.utc)
    if now >= expires_at_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new OTP."
        )

    # Check attempt threshold
    if current_attempts >= settings.MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Maximum verification attempts exceeded "
                f"({settings.MAX_OTP_ATTEMPTS}/{settings.MAX_OTP_ATTEMPTS}). Please request a fresh code."
            )
        )

    expected_tag = _otp_tag(
        user_otp,
        identifier=identifier,
        channel=channel,
        purpose=purpose,
        user_id=user_id,
        challenge_id=str(otp_id),
        created_at=_canonical_timestamp(created_at),
    )
    stored_tag = str(active_otp.get("otp_code") or "").strip().zfill(6)

    # Signup needs the metadata required to provision a real Auth identity.
    meta = payload.metadata
    if purpose == "signup":
        if (
            not meta
            or not meta.full_name
            or not meta.full_name.strip()
            or not meta.password
            or len(meta.password) < 6
            or not meta.dob
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Registration details are required to complete verification.",
            )

    if len(user_otp) != 6 or not user_otp.isdigit() or not hmac.compare_digest(stored_tag, expected_tag):
        new_attempts = current_attempts + 1
        try:
            attempt_update = await db.update(
                "otp_verifications",
                filters={
                    "id": f"eq.{otp_id}",
                    "is_verified": "eq.false",
                    "attempts": f"eq.{current_attempts}",
                    "expires_at": f"gt.{now.isoformat()}",
                },
                data={"attempts": new_attempts},
            )
        except Exception as exc:
            logger.error("event=auth.otp.verify outcome=attempt_update_failed error_type=%s", type(exc).__name__)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.") from exc
        if not attempt_update:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Verification attempts are being processed. Please try again.",
            )
        remaining = max(settings.MAX_OTP_ATTEMPTS - new_attempts, 0)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining."
        )

    # Consume the challenge with one conditional update that also enforces
    # server-side expiry and the attempt count observed above.
    try:
        claimed_otp = await db.update(
            "otp_verifications",
            filters={
                "id": f"eq.{otp_id}",
                "is_verified": "eq.false",
                "attempts": f"eq.{current_attempts}",
                "expires_at": f"gt.{now.isoformat()}",
            },
            data={"is_verified": True, "attempts": current_attempts + 1},
        )
    except Exception as exc:
        logger.error("event=auth.otp.verify outcome=consume_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify the code.") from exc
    if not claimed_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has already been used. Please request a new OTP.",
        )

    if profile:
        role = profile.get("role") or "customer"
        full_name = profile.get("full_name") or "Verified User"
        email = profile.get("email") or (identifier if channel == "email" else "")
    else:
        full_name = meta.full_name.strip()
        phone_number = meta.phone_number or (identifier if channel == "sms" else "")
        dob = str(meta.dob)
        role = "customer"
        email = identifier if channel == "email" else f"{identifier}@claimpilot.sms"

        # Provision Auth only after OTP proof; failures never mint a session.
        try:
            create_params = {
                "email": email,
                "password": meta.password,
                "email_confirm": channel == "email",
                "user_metadata": {
                    "full_name": full_name,
                    "phone_number": phone_number,
                    "role": role
                }
            }
            auth_res = supabase_admin.auth.admin.create_user(create_params)
            user_id = str(auth_res.user.id)
            if not user_id:
                raise RuntimeError("Auth user ID missing")
            logger.info("event=auth.otp.verify outcome=auth_user_created user_id=%s", user_id)
        except Exception as auth_err:
            logger.warning("event=auth.otp.verify outcome=auth_user_creation_failed error_type=%s", type(auth_err).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to create the account. Please request a new code and try again.",
            ) from auth_err

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
        except Exception as profile_err:
            logger.error("event=auth.otp.verify outcome=profile_insert_failed user_id=%s error_type=%s", user_id, type(profile_err).__name__)
            try:
                supabase_admin.auth.admin.delete_user(user_id)
            except Exception as cleanup_err:
                logger.error("event=auth.otp.verify_cleanup outcome=failure user_id=%s error_type=%s", user_id, type(cleanup_err).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to create the account profile. Please request a new code and try again.",
            ) from profile_err

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
