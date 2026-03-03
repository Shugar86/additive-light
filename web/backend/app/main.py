"""GDI Web Backend - FastAPI Application.

Provides REST API and WebSocket endpoints for the GDI pipeline.
"""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .core.config import settings
from .core.models import (
    JobCreate, JobResponse, JobStatus, JobList,
    FileUploadResponse, WebSocketMessage, JobProgress
)
from .worker.celery_app import celery_app
from .worker.tasks import process_gdi_pipeline, process_sensor_phase

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Generative Design Intelligence Web API"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (replace with database in production)
# For MVP, we use simple dict storage backed by Celery results
jobs_store: dict = {}

# WebSocket connections
websocket_connections: dict = {}


# ============================================================================
# Health & Info
# ============================================================================

@app.get("/")
async def root():
    """API root."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check Redis connection
    try:
        celery_app.connection().ensure_connection(max_retries=1)
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
    
    return {
        "status": "healthy" if redis_status == "connected" else "degraded",
        "redis": redis_status,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# File Upload
# ============================================================================

@app.post("/api/v1/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload STL file for processing.
    
    In production, this would upload to S3.
    For MVP, we save to local storage.
    """
    # Validate file type
    if not file.filename.endswith(".stl"):
        raise HTTPException(400, "Only STL files are supported")
    
    # Generate file ID
    file_id = str(uuid.uuid4())
    
    # Save file
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / f"{file_id}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    file_size = len(content)
    
    logger.info(f"File uploaded: {file_id} ({file_size} bytes)")
    
    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename,
        url=f"/api/v1/files/{file_id}",
        size_bytes=file_size,
        uploaded_at=datetime.utcnow()
    )


# ============================================================================
# Jobs API
# ============================================================================

@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(job: JobCreate):
    """Create a new GDI processing job."""
    
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Create job record
    job_response = JobResponse(
        id=job_id,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
        source_stl=job.source_stl,
        base_axis=job.base_axis,
        confidence_threshold=job.confidence_threshold
    )
    
    jobs_store[job_id] = job_response
    
    # Queue Celery task
    task = process_gdi_pipeline.delay(
        stl_file=job.source_stl,
        base_axis=job.base_axis,
        job_id=job_id
    )
    
    logger.info(f"Job created: {job_id} (task: {task.id})")
    
    return job_response


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job status and results."""
    
    if job_id not in jobs_store:
        raise HTTPException(404, "Job not found")
    
    job = jobs_store[job_id]
    
    # Check Celery task status
    # In production, query task result from Redis
    
    return job


@app.get("/api/v1/jobs", response_model=JobList)
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 20,
    offset: int = 0
):
    """List jobs with optional filtering."""
    
    jobs = list(jobs_store.values())
    
    if status:
        jobs = [j for j in jobs if j.status == status]
    
    # Sort by created_at desc
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    total = len(jobs)
    jobs = jobs[offset:offset + limit]
    
    return JobList(total=total, jobs=jobs)


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its results."""
    
    if job_id not in jobs_store:
        raise HTTPException(404, "Job not found")
    
    del jobs_store[job_id]
    
    return {"message": "Job deleted"}


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

@app.websocket("/ws/jobs/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates."""
    
    await websocket.accept()
    websocket_connections[job_id] = websocket
    
    try:
        while True:
            # Wait for messages from client (ping/keepalive)
            data = await websocket.receive_text()
            
            # Could handle client commands here
            # For now, just echo back
            await websocket.send_json({
                "type": "pong",
                "job_id": job_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        del websocket_connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")


async def broadcast_progress(job_id: str, progress: JobProgress):
    """Broadcast progress update to connected WebSocket clients."""
    
    if job_id in websocket_connections:
        ws = websocket_connections[job_id]
        await ws.send_json(WebSocketMessage(
            type="progress",
            job_id=job_id,
            data=progress.model_dump()
        ).model_dump())


# ============================================================================
# Results API
# ============================================================================

@app.get("/api/v1/jobs/{job_id}/telemetry")
async def get_job_telemetry(job_id: str):
    """Get YAML telemetry for a job."""
    
    if job_id not in jobs_store:
        raise HTTPException(404, "Job not found")
    
    job = jobs_store[job_id]
    
    if not job.telemetry_url:
        raise HTTPException(404, "Telemetry not yet available")
    
    # Read and return YAML file
    import yaml
    
    yaml_path = Path(job.telemetry_url)
    if not yaml_path.exists():
        raise HTTPException(404, "Telemetry file not found")
    
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    return data


@app.get("/api/v1/jobs/{job_id}/code")
async def get_job_code(job_id: str):
    """Get generated code for a job."""
    
    if job_id not in jobs_store:
        raise HTTPException(404, "Job not found")
    
    job = jobs_store[job_id]
    
    if not job.generated_code:
        raise HTTPException(404, "Code not yet generated")
    
    return {"code": job.generated_code}


# ============================================================================
# Static Files (for uploaded files)
# ============================================================================

app.mount("/files", StaticFiles(directory="uploads"), name="files")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle generic exceptions."""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
