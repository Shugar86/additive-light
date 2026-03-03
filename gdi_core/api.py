"""GDI Core API - Web-ready interface layer.

This module provides a clean API boundary between the core business logic
and presentation layers (CLI, GUI, Web). Following Clean Architecture principles
to ensure easy migration to Web in Phase 2.

All core functionality is exposed through this API, making the web migration
simply a matter of wrapping these functions in HTTP endpoints.
"""

from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import logging
import uuid
from datetime import datetime

from .models.yaml_contract import (
    SensorTelemetry,
    ApproximationResult,
    JudgeResult,
    RunManifest,
)
from .sensors import Sensor, align_mesh_to_origin
from .approximator import Approximator
from .judge import Judge
from .optimizer import Optimizer
from .utils import ManifestWriter

logger = logging.getLogger(__name__)


class GDIAPI:
    """Main API for GDI operations.
    
    This class encapsulates all core business logic and provides
    a clean interface for any presentation layer.
    """
    
    def __init__(
        self,
        slice_step: float = 0.1,
        confidence_threshold: float = 0.7,
        iou_threshold: float = 0.98,
        max_retries: int = 3,
        output_dir: str = "output"
    ):
        """Initialize GDI API.
        
        Args:
            slice_step: Distance between slices in mm
            confidence_threshold: Minimum confidence before manual review
            iou_threshold: IoU threshold for judge acceptance
            max_retries: Maximum retry attempts for synthesis
            output_dir: Directory for output files
        """
        self.slice_step = slice_step
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.max_retries = max_retries
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.sensor = Sensor(slice_step=slice_step)
        self.approximator = Approximator(confidence_threshold=confidence_threshold)
        self.judge = Judge(iou_threshold=iou_threshold, max_retries=max_retries)
        self.optimizer = Optimizer()
        self.manifest_writer = ManifestWriter(str(self.output_dir / "manifests"))
        
        # Progress callback (for async updates in web mode)
        self.progress_callback: Optional[Callable[[str, int], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """Set callback for progress updates.
        
        Args:
            callback: Function receiving (message, percent_complete)
        """
        self.progress_callback = callback
    
    def _emit_progress(self, message: str, percent: int):
        """Emit progress update if callback is set."""
        logger.info(f"[{percent}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percent)
    
    # =========================================================================
    # PHASE 1: SENSOR + APPROXIMATOR
    # =========================================================================
    
    def phase1_sensor_approximator(
        self,
        stl_file: str,
        base_axis: str = "Z",
        align: bool = True
    ) -> ApproximationResult:
        """Phase 1: Process STL through Sensor and Approximator.
        
        This is the deterministic "sensing" phase that converts
        raw mesh to structured YAML telemetry.
        
        Args:
            stl_file: Path to input STL file
            base_axis: Build axis (X/Y/Z)
            align: Whether to auto-align mesh to origin
            
        Returns:
            ApproximationResult with telemetry and confidence
        """
        self._emit_progress("Loading STL file...", 5)
        
        import trimesh
        mesh = trimesh.load(stl_file)
        
        if align:
            mesh = align_mesh_to_origin(mesh)
        
        self._emit_progress(f"Slicing mesh (step={self.slice_step}mm)...", 15)
        slices = self.sensor.slice_mesh(mesh, axis=base_axis)
        
        self._emit_progress(f"Analyzing {len(slices)} slices for zone detection...", 35)
        result = self.approximator.approximate(
            slices=slices,
            source_file=stl_file,
            base_axis=base_axis
        )
        
        self._emit_progress("Phase 1 complete", 40)
        
        return result
    
    def save_telemetry(
        self,
        result: ApproximationResult,
        base_name: Optional[str] = None
    ) -> str:
        """Save telemetry YAML to file.
        
        Args:
            result: ApproximationResult to save
            base_name: Base filename (defaults to source file name)
            
        Returns:
            Path to saved YAML file
        """
        import yaml
        
        if base_name is None:
            base_name = Path(result.telemetry.source_file or "unknown").stem
        
        yaml_file = self.output_dir / f"{base_name}_telemetry.yaml"
        
        with open(yaml_file, "w") as f:
            yaml.dump(result.telemetry.to_yaml_dict(), f, default_flow_style=False)
        
        logger.info(f"Telemetry saved to {yaml_file}")
        return str(yaml_file)
    
    # =========================================================================
    # PHASE 2: SYNTHESIS (LLM)
    # =========================================================================
    
    def phase2_synthesize(
        self,
        telemetry: SensorTelemetry,
        model: str = "gpt-4o",
        api_key: Optional[str] = None
    ) -> str:
        """Phase 2: Synthesize build123d code from telemetry.
        
        This is the LLM-based synthesis phase.
        
        Args:
            telemetry: Sensor telemetry from Phase 1
            model: LLM model name
            api_key: API key for LLM service
            
        Returns:
            Generated Python code
        """
        self._emit_progress("Synthesizing code with LLM...", 50)
        
        # Import here to avoid dependency if not used
        from .synthesis.synthesizer import Synthesizer
        
        synthesizer = Synthesizer(model_name=model, api_key=api_key)
        code = synthesizer.generate_code(telemetry)
        
        self._emit_progress("Code synthesized", 60)
        
        return code
    
    # =========================================================================
    # PHASE 3: JUDGE
    # =========================================================================
    
    def phase3_judge(
        self,
        code: str,
        original_stl: str,
        generated_step: Optional[str] = None,
        retry_count: int = 0
    ) -> JudgeResult:
        """Phase 3: Validate generated code through Judge.
        
        Two-phase validation: syntax/topology (fail-fast), then IoU.
        
        Args:
            code: Generated Python code
            original_stl: Path to original STL for comparison
            generated_step: Path to generated STEP file (if available)
            retry_count: Current retry attempt
            
        Returns:
            JudgeResult with acceptance status
        """
        self._emit_progress("Phase 1 validation (syntax/topology)...", 70)
        
        result = self.judge.judge(
            code=code,
            original_stl_path=original_stl,
            generated_step_path=generated_step,
            retry_count=retry_count
        )
        
        if result.phase1 and result.phase1.passed:
            self._emit_progress("Phase 1 passed", 75)
            
            if result.phase2:
                self._emit_progress(
                    f"Phase 2 complete (IoU={result.phase2.iou_score:.2%})", 
                    85
                )
        
        return result
    
    # =========================================================================
    # PHASE 4: OPTIMIZER
    # =========================================================================
    
    def phase4_optimize(self, code: str) -> str:
        """Phase 4: Optimize code to engineering standards.
        
        Extracts parameters and beautifies dimensions.
        
        Args:
            code: Raw generated code
            
        Returns:
            Optimized code
        """
        self._emit_progress("Optimizing code (parameter extraction)...", 90)
        
        optimized = self.optimizer.optimize(code)
        
        self._emit_progress("Optimization complete", 95)
        
        return optimized
    
    # =========================================================================
    # COMPLETE PIPELINE
    # =========================================================================
    
    def run_pipeline(
        self,
        stl_file: str,
        base_axis: str = "Z",
        align: bool = True,
        skip_low_confidence: bool = True,
        llm_model: str = "gpt-4o",
        llm_api_key: Optional[str] = None
    ) -> RunManifest:
        """Run complete GDI pipeline.
        
        This is the main entry point that orchestrates all phases.
        
        Args:
            stl_file: Input STL file path
            base_axis: Build axis
            align: Whether to auto-align
            skip_low_confidence: If True, stop early if confidence below threshold
            llm_model: LLM model for synthesis
            llm_api_key: API key for LLM
            
        Returns:
            Complete RunManifest
        """
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"Starting pipeline run {run_id} for {stl_file}")
        
        try:
            # Phase 1: Sensor + Approximator
            approx_result = self.phase1_sensor_approximator(stl_file, base_axis, align)
            
            # Check confidence threshold
            if skip_low_confidence and approx_result.fallback_required:
                logger.warning(f"Low confidence ({approx_result.global_confidence:.2f}) - stopping pipeline")
                
                manifest = RunManifest(
                    run_id=run_id,
                    timestamp=start_time.isoformat(),
                    prompt_version="1.0",
                    yaml_schema_version="1.0",
                    source_stl=stl_file,
                    approximation_result=approx_result,
                    status="manual_review_required",
                    error_log=f"Low confidence: {approx_result.fallback_reason}"
                )
                
                self.manifest_writer.write(manifest)
                return manifest
            
            # Save telemetry
            yaml_path = self.save_telemetry(approx_result)
            
            # Phase 2: Synthesize (if confidence is acceptable)
            code = self.phase2_synthesize(approx_result.telemetry, llm_model, llm_api_key)
            
            # Phase 3: Judge
            judge_result = self.phase3_judge(code, stl_file)
            
            # If failed and retry recommended, we could retry here
            # For now, just note it in the manifest
            
            # Phase 4: Optimize
            if judge_result.accepted:
                final_code = self.phase4_optimize(code)
            else:
                final_code = code  # Keep original if not accepted
            
            # Determine final status
            if judge_result.accepted:
                status = "success"
            elif approx_result.fallback_required:
                status = "manual_review_required"
            else:
                status = "failure"
            
            # Create manifest
            manifest = RunManifest(
                run_id=run_id,
                timestamp=start_time.isoformat(),
                prompt_version="1.0",
                yaml_schema_version="1.0",
                source_stl=stl_file,
                output_yaml=yaml_path,
                approximation_result=approx_result,
                judge_result=judge_result,
                final_code=final_code,
                final_iou=judge_result.phase2.iou_score if judge_result.phase2 else None,
                retry_count=0,  # Would be updated for actual retries
                status=status,
                error_log=None if status == "success" else judge_result.feedback_for_llm
            )
            
            self.manifest_writer.write(manifest)
            
            self._emit_progress("Pipeline complete", 100)
            
            logger.info(f"Pipeline {run_id} completed with status: {status}")
            
            return manifest
            
        except Exception as e:
            logger.exception(f"Pipeline {run_id} failed")
            
            manifest = RunManifest(
                run_id=run_id,
                timestamp=start_time.isoformat(),
                prompt_version="1.0",
                yaml_schema_version="1.0",
                source_stl=stl_file,
                status="failure",
                error_log=str(e)
            )
            
            self.manifest_writer.write(manifest)
            return manifest
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_manifest(self, run_id: str) -> Optional[RunManifest]:
        """Get run manifest by ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            RunManifest or None if not found
        """
        from .utils import ManifestReader
        
        reader = ManifestReader(str(self.output_dir / "manifests"))
        return reader.read(run_id)
    
    def list_manifests(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List recent run manifests.
        
        Args:
            status: Filter by status
            limit: Maximum number of results
            
        Returns:
            List of manifest summaries
        """
        from .utils import ManifestReader
        
        reader = ManifestReader(str(self.output_dir / "manifests"))
        manifests = reader.list_runs(status=status)
        
        return manifests[:limit]


# Convenience function for direct use
def run_gdi_pipeline(
    stl_file: str,
    base_axis: str = "Z",
    output_dir: str = "output",
    **kwargs
) -> RunManifest:
    """Convenience function to run GDI pipeline.
    
    Args:
        stl_file: Input STL file
        base_axis: Build axis
        output_dir: Output directory
        **kwargs: Additional arguments passed to GDIAPI
        
    Returns:
        RunManifest with complete results
    """
    api = GDIAPI(output_dir=output_dir, **kwargs)
    return api.run_pipeline(stl_file, base_axis)
