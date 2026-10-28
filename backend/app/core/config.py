from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Resolve the .env file relative to this module file.
# This makes the path work regardless of where the process is invoked from.
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"  # backend/.env

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Includes configuration for database connection, security, and external services.
    """
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "AI-Native Enterprise CPQ Platform"
    API_V1_STR: str = "/api/v1"

    # Database Settings
    # Default to an async PostgreSQL URL (asyncpg driver)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cpq_db",
        description="Async database connection string"
    )

    # JWT Authentication Settings
    # WARNING: Change this key in production environment
    SECRET_KEY: str = Field(
        default="super_secret_key_for_development_purposes_only_1234567890",
        description="Secret key used for signing JWT tokens"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Google Gemini AI Settings
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for AI copilot functionality"
    )

    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Company branding used on client-facing proposals
    COMPANY_NAME: str = "Enterprise CPQ"
    COMPANY_ADDRESS: str = ""
    COMPANY_EMAIL: str = ""
    QUOTE_TERMS: str = (
        "Prices are quoted in the stated currency and are valid until the date shown. "
        "Recurring charges (MRC) are billed monthly; non-recurring charges (NRC) are billed once. "
        "Taxes, where applicable, are shown separately. Acceptance of this proposal constitutes agreement to these terms."
    )

    # Outbound email (SMTP). If SMTP_HOST is empty, sending fails with a clear error instead of faking success.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True   # STARTTLS on SMTP_PORT
    SMTP_USE_SSL: bool = False  # implicit TLS (typically port 465)

    # Salesforce Integration
    SALESFORCE_CLIENT_ID: str = ""
    SALESFORCE_CLIENT_SECRET: str = ""
    SALESFORCE_LOGIN_URL: str = "https://login.salesforce.com"  # use https://test.salesforce.com for sandboxes
    FRONTEND_URL: str = "http://localhost:3000"
    SALESFORCE_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/salesforce/callback"

settings = Settings()
