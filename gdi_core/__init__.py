"""GDI Core - Generative Design Intelligence Core Library.

This is the core business logic layer for GDI.
All functionality is exposed through gdi_core.api.GDIAPI.

For CLI/GUI usage, see gdi_app module.
For Web API, this core is wrapped in FastAPI endpoints (see web/ module).
"""

__version__ = "1.0.0"
__author__ = "GDI Team"

from .api import GDIAPI, run_gdi_pipeline
from .models import (
    SensorTelemetry,
    ApproximationResult,
    JudgeResult,
    RunManifest,
)

__all__ = [
    # Main API
    "GDIAPI",
    "run_gdi_pipeline",
    # Models
    "SensorTelemetry",
    "ApproximationResult",
    "JudgeResult",
    "RunManifest",
]
