"""Web Backend Database Models."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class JobStatus(str, Enum):
    """Processing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENSOR_COMPLETE = "sensor_complete"
    SYNTHESIZING = "synthesizing"
    JUDGE_COMPLETE = "judge_complete"
    OPTIMIZING = "optimizing"
    COMPLETE = "complete"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class JobBase(BaseModel):
    """Base job model."""
    source_stl: str
    base_axis: str = "Z"
    confidence_threshold: float = 0.7


class JobCreate(JobBase):
    """Job creation model."""
    pass


class JobResponse(JobBase):
    """Job response model."""
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    telemetry_url: Optional[str] = None
    generated_code: Optional[str] = None
    step_file_url: Optional[str] = None
    nc_file_url: Optional[str] = None
    
    # Metrics
    global_confidence: Optional[float] = None
    final_iou: Optional[float] = None
    retry_count: int = 0
    
    # Error handling
    error_message: Optional[str] = None
    fallback_reason: Optional[str] = None


class JobProgress(BaseModel):
    """Job progress update."""
    job_id: str
    status: JobStatus
    percent_complete: int = Field(ge=0, le=100)
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class JobList(BaseModel):
    """List of jobs response."""
    total: int
    jobs: List[JobResponse]


class FileUploadResponse(BaseModel):
    """File upload response."""
    file_id: str
    filename: str
    url: str
    size_bytes: int
    uploaded_at: datetime


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str  # "progress", "complete", "error"
    job_id: str
    data: dict
