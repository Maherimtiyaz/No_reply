from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
    # App
    APP_NAME: str = "NoReply"
    DEBUG: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/finemail"
    
    # OAuth - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    
    # OAuth - Security
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ENCRYPTION_KEY: str = ""  # Will be derived from SECRET_KEY if not provided
    
    # Frontend URL for redirects after OAuth
    FRONTEND_URL: str = "http://localhost:3000"


settings = Settings()
