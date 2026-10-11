import os
from typing import List, Optional, Union
from pydantic import Field
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    USE_PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseSettings
    USE_PYDANTIC_V2 = False


class Settings(BaseSettings):
    PROJECT_NAME: str = "ClaimPilot AI Platform API"
    API_V1_STR: str = "/api/v1"
    
    # Supabase Credentials
    SUPABASE_URL: str = Field(default="https://zegygoxpmnxpdhutdpqf.supabase.co")
    SUPABASE_ANON_KEY: str = Field(default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplZ3lnb3hwbW54cGRodXRkcHFmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1Njk5ODYsImV4cCI6MjEwNTE0NTk4Nn0.f5cV4peE89XlqWpO2oPUn5eqcLQWdPyu9OzY9lm-8eQ")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplZ3lnb3hwbW54cGRodXRkcHFmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4OTU2OTk4NiwiZXhwIjoyMTA1MTQ1OTg2fQ.WkW2XX2PzvKyaWycaXxtbvz-BGA_Id7WEnQJMTXqO3E")
    SUPABASE_STORAGE_BUCKET: str = Field(default="claim-evidence")

    # JWT Settings
    JWT_SECRET: str = Field(default="claimpilot-secure-production-jwt-secret-key-2026-v1")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Frontend URL (for email magic links and CORS)
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,*"

    # SendGrid Settings
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    SENDGRID_FROM_EMAIL: Optional[str] = Field(default="rahul.sutar25@vupune.ac.in")

    # Email Settings (SMTP)
    SMTP_HOST: str = "smtp.claimpilot.internal"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notifications@claimpilot.com"
    SMTP_PASSWORD: str = "mock-smtp-password"
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
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

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


settings = Settings()