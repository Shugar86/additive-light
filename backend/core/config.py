"""Configuration settings for the CAD-Recode system.

All configuration is loaded from environment variables with sensible defaults.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # LLM Configuration
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    
    # Model selection
    fast_llm_model: str = Field(default="google/gemini-flash-1.5", alias="FAST_LLM_MODEL")
    smart_llm_model: str = Field(default="anthropic/claude-3.5-sonnet", alias="SMART_LLM_MODEL")
    
    # Sensor Configuration
    default_slice_count: int = Field(default=20, alias="DEFAULT_SLICE_COUNT")
    slice_tolerance: float = Field(default=0.01, alias="SLICE_TOLERANCE")
    
    # Validation
    max_code_execution_time: int = Field(default=60, alias="MAX_CODE_EXECUTION_TIME")
    allowed_imports: list = Field(
        default_factory=lambda: [
            "build123d",
            "bd_warehouse",
            "ocp_vscode",
            "math",
            "numpy",
        ],
        alias="ALLOWED_IMPORTS"
    )
    forbidden_imports: list = Field(
        default_factory=lambda: [
            "os",
            "sys",
            "subprocess",
            "socket",
            "requests",
            "urllib",
        ],
        alias="FORBIDDEN_IMPORTS"
    )
    
    # VibeGuard thresholds
    chamfer_tolerance: float = Field(default=0.1, alias="CHAMFER_TOLERANCE")
    hausdorff_tolerance: float = Field(default=0.5, alias="HAUSDORFF_TOLERANCE")
    sample_point_count: int = Field(default=10000, alias="SAMPLE_POINT_COUNT")
    
    # Paths
    skills_library_path: str = Field(default="backend/skills/library", alias="SKILLS_LIBRARY_PATH")
    temp_output_path: str = Field(default="temp", alias="TEMP_OUTPUT_PATH")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()