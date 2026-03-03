"""Web Backend Configuration."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GDI Web API"
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # S3 / Object Storage
    S3_ENDPOINT: Optional[str] = None  # e.g., "https://s3.amazonaws.com"
    S3_BUCKET: str = "gdi-uploads"
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # GDI Settings
    CONFIDENCE_THRESHOLD: float = 0.7
    IOU_THRESHOLD: float = 0.98
    MAX_RETRIES: int = 3
    
    # LLM
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
