"""Celery Tasks for GDI Pipeline.

Each phase of the pipeline is a separate Celery task
with progress updates via WebSocket or callbacks.
"""

import logging
from typing import Optional
from pathlib import Path

from .celery_app import celery_app
from web.backend.app.core.config import settings

# Import GDI Core
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from gdi_core.api import GDIAPI
from gdi_core.models import ApproximationResult, JudgeResult

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_gdi_pipeline(
    self,
    stl_file: str,
    base_axis: str = "Z",
    job_id: Optional[str] = None
) -> dict:
    """Complete GDI pipeline as a Celery task.
    
    Args:
        self: Celery task instance (for progress updates)
        stl_file: Path to input STL file
        base_axis: Build axis
        job_id: Optional job identifier
        
    Returns:
        Complete results dict
    """
    api = GDIAPI(
        slice_step=0.1,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        iou_threshold=settings.IOU_THRESHOLD,
        max_retries=settings.MAX_RETRIES,
        output_dir=f"runs/{job_id}" if job_id else "runs"
    )
    
    # Set up progress callback
    def progress_callback(message: str, percent: int):
        self.update_state(
            state='PROGRESS',
            meta={
                'message': message,
                'percent': percent,
                'phase': 'sensor' if percent < 40 else 'approximator' if percent < 50 else 'synthesis'
            }
        )
    
    api.set_progress_callback(progress_callback)
    
    try:
        # Run pipeline
        manifest = api.run_pipeline(
            stl_file=stl_file,
            base_axis=base_axis,
            align=True,
            skip_low_confidence=False,  # Let it run through
            llm_model=settings.LLM_MODEL,
            llm_api_key=settings.OPENAI_API_KEY
        )
        
        return {
            "status": manifest.status,
            "run_id": manifest.run_id,
            "global_confidence": manifest.approximation_result.global_confidence if manifest.approximation_result else None,
            "final_iou": manifest.final_iou,
            "yaml_path": manifest.output_yaml,
            "fallback_required": manifest.approximation_result.fallback_required if manifest.approximation_result else False,
            "fallback_reason": manifest.approximation_result.fallback_reason if manifest.approximation_result else None,
            "error": manifest.error_log
        }
        
    except Exception as e:
        logger.exception(f"Pipeline failed for job {job_id}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True)
def process_sensor_phase(
    self,
    stl_file: str,
    base_axis: str = "Z"
) -> dict:
    """Phase 1 only: Sensor + Approximator.
    
    Args:
        self: Celery task instance
        stl_file: Input STL file
        base_axis: Build axis
        
    Returns:
        Approximation result dict
    """
    self.update_state(state='PROCESSING', meta={'phase': 'sensor'})
    
    api = GDIAPI(
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        output_dir="runs"
    )
    
    try:
        result = api.phase1_sensor_approximator(
            stl_file=stl_file,
            base_axis=base_axis,
            align=True
        )
        
        # Save telemetry
        yaml_path = api.save_telemetry(result)
        
        return {
            "status": "success",
            "global_confidence": result.global_confidence,
            "fallback_required": result.fallback_required,
            "fallback_reason": result.fallback_reason,
            "zones_count": len(result.telemetry.topological_zones),
            "yaml_path": yaml_path
        }
        
    except Exception as e:
        logger.exception("Sensor phase failed")
        raise


@celery_app.task
def process_synthesis_phase(
    telemetry_data: dict,
    model: str = "gpt-4o"
) -> str:
    """Phase 2 only: LLM Synthesis.
    
    Args:
        telemetry_data: Sensor telemetry dict
        model: LLM model name
        
    Returns:
        Generated code
    """
    from gdi_core.models import SensorTelemetry
    
    telemetry = SensorTelemetry(**telemetry_data)
    
    api = GDIAPI(
        llm_model=model,
        llm_api_key=settings.OPENAI_API_KEY
    )
    
    code = api.phase2_synthesize(
        telemetry=telemetry,
        model=model
    )
    
    return code


@celery_app.task
def process_judge_phase(
    code: str,
    original_stl: str,
    generated_step: Optional[str] = None
) -> dict:
    """Phase 3 only: Judge validation.
    
    Args:
        code: Generated code
        original_stl: Original STL path
        generated_step: Generated STEP path (optional)
        
    Returns:
        Judge result dict
    """
    api = GDIAPI(iou_threshold=settings.IOU_THRESHOLD)
    
    result = api.phase3_judge(
        code=code,
        original_stl=original_stl,
        generated_step=generated_step
    )
    
    return {
        "accepted": result.accepted,
        "phase1_passed": result.phase1.passed if result.phase1 else False,
        "phase2_passed": result.phase2.passed if result.phase2 else None,
        "iou_score": result.phase2.iou_score if result.phase2 else None,
        "retry_recommended": result.retry_recommended,
        "feedback": result.feedback_for_llm
    }
