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
    
    # AI/LLM Configuration
    LLM_PROVIDER: str = "mock"  # Options: mock, openai, anthropic
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = ""  # e.g., "gpt-4", "claude-3-sonnet-20240229"
    
    # Parsing Configuration
    PARSING_CONFIDENCE_THRESHOLD: float = 0.6
    PARSING_USE_FEW_SHOT: bool = True


settings = Settings()
