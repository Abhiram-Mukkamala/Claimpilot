# app/services/email.py
import os
import logging
from typing import List, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings

logger = logging.getLogger("claimpilot.email")
logger.setLevel(logging.INFO)


async def _dispatch_email(to_email: str, subject: str, html_body: str, plain_body: str) -> bool:
  
    # Grab values from Pydantic settings first, falling back to os.getenv
    api_key = getattr(settings, "SENDGRID_API_KEY", os.getenv("SENDGRID_API_KEY"))
    from_email = getattr(settings, "SENDGRID_FROM_EMAIL", os.getenv("SENDGRID_FROM_EMAIL", "rahul.sutar25@vupune.ac.in"))

    # Dispatch via SendGrid API
    if api_key:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_body,
            html_content=html_body
        )
        try:
            sg = SendGridAPIClient(api_key)
            response = sg.send(message)
            logger.info(f"[SENDGRID DISPATCHED] Subject: '{subject}' to {to_email} | Status: {response.status_code}")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"[SENDGRID ERROR] Failed sending to {to_email}: {str(e)}")
            return False

    # Terminal mock fallback if SENDGRID_API_KEY is not set
    print(f"\n==================================================================")
    print(f"📧 [MOCK EMAIL DISPATCH] ClaimPilot Notification Service")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"==================================================================\n")
    logger.info(f"[MOCK EMAIL DISPATCHED] To: {to_email} | Subject: {subject}")
    return True


async def send_agent_approval_email(
    to_email: str,
    claim_number: str,
    token: str,
    min_cost: float = 8000.0,
    max_cost: float = 12000.0,
    claimant_name: str = "Valued Customer"
) -> bool:
    action_url = f"{settings.FRONTEND_URL}/claim/status?token={token}&claim={claim_number}"
    formatted_min = f"₹{min_cost:,.2f}"
    formatted_max = f"₹{max_cost:,.2f}"

    subject = f"✅ Claim Approved: Action Required for Settlement ({claim_number})"
    
    plain_text = f"Hello {claimant_name},\n\nYour claim {claim_number} is approved ({formatted_min} - {formatted_max}).\nReview here: {action_url}"

    html_content = f"""
    <html>
      <body style="font-family: sans-serif; background: #0d1117; color: #e6edf3; padding: 20px;">
        <h2>ClaimPilot Adjudication</h2>
        <p>Dear {claimant_name}, your claim <strong>{claim_number}</strong> has been approved.</p>
        <p>Approved bounds: <strong>{formatted_min} – {formatted_max}</strong></p>
        <a href="{action_url}" style="background: #238636; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px;">Confirm Settlement</a>
      </body>
    </html>
    """
    return await _dispatch_email(to_email, subject, html_content, plain_text)


async def send_agent_rejection_email(
    to_email: str,
    claim_number: str,
    reason: str,
    claimant_name: str = "Valued Customer",
    support_email: str = "support@claimpilot.com"
) -> bool:
    subject = f"⚠️ Notice of Claim Decision: Claim {claim_number}"
    plain_text = f"Hello {claimant_name},\n\nClaim {claim_number} was rejected.\nReason: {reason}"
    html_content = f"<html><body><h3>Claim Decision Notice</h3><p>Reason: {reason}</p></body></html>"
    return await _dispatch_email(to_email, subject, html_content, plain_text)


async def send_request_info_email(
    to_email: str,
    claim_number: str,
    requested_items: List[str],
    magic_token: str,
    claimant_name: str = "Valued Customer"
) -> bool:
    upload_url = f"{settings.FRONTEND_URL}/customer/claims/upload?token={magic_token}&claim={claim_number}"
    subject = f"📋 Additional Information Required: Claim {claim_number}"
    plain_text = f"Hello {claimant_name},\n\nPlease submit additional info for claim {claim_number}:\n{upload_url}"
    html_content = f"<html><body><h3>Action Required</h3><a href='{upload_url}'>Upload Evidence</a></body></html>"
    return await _dispatch_email(to_email, subject, html_content, plain_text)