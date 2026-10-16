import os
from typing import List, Optional, Union
from pydantic import Field, ValidationError
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    USE_PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseSettings
    USE_PYDANTIC_V2 = False


class Settings(BaseSettings):
    PROJECT_NAME: str = "ClaimPilot AI Platform API"
    API_V1_STR: str = "/api/v1"
    
    # Supabase Credentials (Required - must be set via environment or .env)
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = Field(default="claim-evidence")

    # JWT Settings (Required - must be set via environment or .env)
    JWT_SECRET: str
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Fraud analysis settings (Optional for local/offline use)
    PHASH_DISTANCE_THRESHOLD: int = Field(default=5, ge=0)
    FRAUD_LLM_PROVIDER: Optional[str] = Field(default="openai")
    FRAUD_LLM_API_KEY: Optional[str] = Field(default=None)
    FRAUD_LLM_MODEL: Optional[str] = Field(default="gpt-4o-mini")

    # Frontend URL (for email magic links and CORS)
    FRONTEND_URL: str = "http://localhost:5173"
    # Explicit frontend origins only; wildcard origins are never accepted.
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # SendGrid Settings
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    SENDGRID_FROM_EMAIL: Optional[str] = Field(default=None)

    # Email Settings (SMTP)
    SMTP_HOST: str = "smtp.claimpilot.internal"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notifications@claimpilot.com"
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_FROM_EMAIL: str = "notifications@claimpilot.com"
    SMTP_FROM_NAME: str = "ClaimPilot Claims Engine"
    SUPPORT_EMAIL: str = "support@claimpilot.com"

    # SMS Provider Settings (Twilio or Fast2SMS)
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: str = Field(default="")
    TWILIO_PHONE_NUMBER: str = Field(default="")
    FAST2SMS_API_KEY: str = Field(default="")

    # OTP Security Settings
    OTP_EXPIRE_MINUTES: int = 10
    MAX_OTP_ATTEMPTS: int = 3

    @property
    def allowed_origin_list(self) -> List[str]:
        # Exclude wildcard entries even if accidentally supplied in configuration.
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip() and origin.strip() != "*"
        ]

    if USE_PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=False
        )
    else:
        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"


try:
    settings = Settings()
except ValidationError as exc:
    invalid_names = sorted({str(error["loc"][0]) for error in exc.errors()})
    names = ", ".join(invalid_names)
    raise RuntimeError(f"Invalid or missing configuration variable(s): {names}") from None