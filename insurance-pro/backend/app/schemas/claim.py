from datetime import date, datetime
from enum import Enum
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ----------------------------------------------------
# Custom Database-Aligned ENUMs
# ----------------------------------------------------

class UserRole(str, Enum):
    customer = "customer"
    agent = "agent"
    admin = "admin"


class ClaimType(str, Enum):
    accident = "Accident"
    theft = "Theft"
    fire = "Fire"
    natural_event = "Natural Event"


class ClaimStatus(str, Enum):
    pending_review = "pending_review"
    under_review = "under_review"
    flagged = "flagged"
    action_required = "action_required"
    agent_approved = "agent_approved"
    settlement_accepted = "settlement_accepted"
    disputed = "disputed"
    rejected = "rejected"


class EvidenceCategory(str, Enum):
    photo = "photo"
    walkaround_video = "walkaround_video"
    dl_front = "dl_front"
    dl_back = "dl_back"


class AgentActionType(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_INFO = "REQUEST_INFO"


class CustomerDecisionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DISPUTE = "DISPUTE"


class OtpChannel(str, Enum):
    email = "email"
    sms = "sms"


# ----------------------------------------------------
# OTP Schemas
# ----------------------------------------------------

class UserMetadata(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    dob: Optional[str] = None
    password: Optional[str] = None


class OtpSendRequest(BaseModel):
    identifier: str = Field(..., description="Email address or E.164 phone number (e.g. +919876543210)")
    channel: OtpChannel

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Identifier cannot be blank.")
        return clean


class OtpSendResponse(BaseModel):
    message: str
    identifier: str
    channel: str
    expires_in_minutes: int


class OtpVerifyRequest(BaseModel):
    identifier: str
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    channel: OtpChannel = OtpChannel.email
    metadata: Optional[UserMetadata] = None


class OtpVerifyResponse(BaseModel):
    message: str
    is_verified: bool
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ----------------------------------------------------
# Profile Models
# ----------------------------------------------------
class UserProfileBase(BaseModel):
    full_name: str
    email: str
    phone_number: str
    dob: date
    role: UserRole = UserRole.customer


class UserRegisterRequest(UserProfileBase):
    password: str = Field(..., min_length=6)


class UserProfileResponse(UserProfileBase):
    id: str
    is_email_verified: bool = False
    is_phone_verified: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------
# Claim Validation & DTO Schemas
# ----------------------------------------------------
class ClaimCreate(BaseModel):
    incident_type: ClaimType
    vehicle_name: str = Field(..., min_length=2, max_length=100)
    policy_number: str = Field(
        ..., 
        description="Policy number to identify insurance policy and assigned agent."
    )
    hsrp_number: str = Field(..., min_length=4, max_length=20)
    engine_number: str = Field(..., min_length=4, max_length=50)
    chassis_number: str = Field(..., min_length=4, max_length=50)
    incident_date: date
    location_address: str = Field(..., min_length=5)
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    pincode: Optional[str] = None
    description: str = Field(..., max_length=500)
    driver_name: str = Field(..., min_length=2, max_length=255)
    driver_dl_number: str
    claimed_amount: Optional[float] = 0.00

    @field_validator("policy_number")
    @classmethod
    def sanitize_policy_number(cls, v: str) -> str:
        clean_v = v.strip().upper()
        if not clean_v:
            raise ValueError("Policy number cannot be blank.")
        return clean_v

    @field_validator("incident_date")
    @classmethod
    def validate_incident_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Incident date cannot be in the future.")
        return v

    @field_validator("driver_dl_number")
    @classmethod
    def validate_dl_number(cls, v: str) -> str:
        clean_v = re.sub(r'[-\s]', '', v.strip().upper())
        pattern = r"^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$"
        if not re.match(pattern, clean_v):
            raise ValueError("driver_dl_number must match standard 15-character format: ^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$ (e.g. MH0220180012345)")
        return clean_v


class ClaimUpdate(BaseModel):
    assigned_agent_id: Optional[str] = None
    status: Optional[ClaimStatus] = None
    fraud_score: Optional[int] = Field(None, ge=0, le=100)
    risk_level: Optional[str] = None
    agent_rejection_reason: Optional[str] = None
    agent_custom_notes: Optional[str] = None
    requested_info_notes: Optional[List[Dict[str, Any]]] = None
    claimed_amount: Optional[float] = None
    approved_amount: Optional[float] = None


class ClaimEvidenceCreate(BaseModel):
    claim_id: str
    file_url: str
    storage_path: Optional[str] = "None"
    file_type: str
    category: EvidenceCategory


class ClaimEvidenceResponse(BaseModel):
    id: str
    claim_id: str
    file_url: str
    storage_path: Optional[str] = ""
    file_type: str
    category: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ClaimAIAnalysisResponse(BaseModel):
    id: str
    claim_id: str
    detected_damages: List[Dict[str, Any]] = []
    estimated_cost_min: float = 0.00
    estimated_cost_max: float = 0.00
    clahe_image_url: Optional[str] = None
    segmentation_masks: Optional[Dict[str, Any]] = {}
    surface_area_px: Optional[int] = 0
    relative_deformation_z: Optional[Dict[str, Any]] = {}
    dsine_vectors: Optional[Dict[str, Any]] = {}
    fraud_flags: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: str
    claim_number: str
    user_id: str
    assigned_agent_id: Optional[str] = None
    incident_type: str
    vehicle_name: str
    policy_number: str
    hsrp_number: str
    engine_number: str
    chassis_number: str
    incident_date: date
    location_address: str
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    pincode: Optional[str] = None
    description: str
    driver_name: str
    driver_dl_number: str
    claimed_amount: Optional[float] = 0.00
    approved_amount: Optional[float] = 0.00
    status: ClaimStatus
    fraud_score: int = 0
    risk_level: str = "Low Risk"
    agent_rejection_reason: Optional[str] = None
    agent_custom_notes: Optional[str] = None
    requested_info_notes: List[Any] = []
    dispute_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    evidence: Optional[List[ClaimEvidenceResponse]] = []
    ai_analysis: Optional[ClaimAIAnalysisResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------
# Action & Workflow Request/Response DTOs
# ----------------------------------------------------
class AgentActionRequest(BaseModel):
    action: AgentActionType
    reason: Optional[str] = Field(None, description="Mandatory when action is REJECT")
    requested_items: Optional[List[str]] = Field(None, description="Array of requested item keys when action is REQUEST_INFO")
    custom_notes: Optional[str] = None


class CustomerSettlementDecisionRequest(BaseModel):
    claim_id: str
    decision: CustomerDecisionType
    dispute_notes: Optional[str] = None


class PresignedUploadUrlRequest(BaseModel):
    file_name: str
    file_type: str
    category: EvidenceCategory = EvidenceCategory.walkaround_video
    file_size_bytes: int = Field(..., le=104857600, description="Max 100 MB (104,857,600 bytes)")

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        max_bytes = 100 * 1024 * 1024
        if v > max_bytes:
            raise ValueError(f"File size exceeds 100MB maximum limit. Got {v} bytes.")
        return v


class PresignedUploadUrlResponse(BaseModel):
    upload_url: str
    file_path: str
    public_url: str
    expires_in_seconds: int
    category: str