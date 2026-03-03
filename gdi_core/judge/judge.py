"""Two-phase Judge system.

Phase 1: Fail-fast syntax and topology check
Phase 2: IoU geometric comparison (only if Phase 1 passes)
"""

from typing import Optional, Tuple
import logging

from ..models.yaml_contract import (
    JudgeResult,
    JudgePhase1Result,
    JudgePhase2Result,
)
from .topology_checker import check_topology, check_code_syntax, check_build123d_imports
from .iou_calculator import calculate_iou

logger = logging.getLogger(__name__)


class Phase1Judge:
    """Phase 1: Fail-fast validation.
    
    Checks syntax, topology, and basic validity before expensive IoU calculation.
    """
    
    def judge(
        self,
        code: str,
        step_file_path: Optional[str] = None
    ) -> JudgePhase1Result:
        """Perform Phase 1 validation.
        
        Args:
            code: Generated build123d code
            step_file_path: Path to generated STEP file (if available)
            
        Returns:
            Phase 1 result
        """
        errors = []
        
        # Check 1: Python syntax
        syntax_valid, syntax_errors = check_code_syntax(code)
        if not syntax_valid:
            errors.extend(syntax_errors)
            logger.warning(f"Phase 1 failed: syntax errors - {syntax_errors}")
            return JudgePhase1Result(
                passed=False,
                syntax_valid=False,
                topology_valid=False,
                errors=errors,
                topology_log=None
            )
        
        # Check 2: build123d patterns
        patterns_valid, pattern_warnings = check_build123d_imports(code)
        if pattern_warnings:
            # Warnings don't fail phase 1, but we log them
            logger.info(f"Phase 1 warnings: {pattern_warnings}")
        
        # Check 3: Topology (if STEP file available)
        topology_valid = True
        topology_log = None
        
        if step_file_path:
            topology_valid, topo_errors, topology_log = check_topology(step_file_path)
            if not topology_valid:
                errors.extend(topo_errors)
                logger.warning(f"Phase 1 failed: topology errors - {topo_errors}")
        
        passed = syntax_valid and topology_valid
        
        return JudgePhase1Result(
            passed=passed,
            syntax_valid=syntax_valid,
            topology_valid=topology_valid,
            errors=errors,
            topology_log=topology_log
        )


class Phase2Judge:
    """Phase 2: Geometric validation via IoU.
    
    Only runs if Phase 1 passes. Expensive comparison of meshes.
    """
    
    def __init__(self, iou_threshold: float = 0.98):
        """Initialize Phase 2 judge.
        
        Args:
            iou_threshold: Minimum IoU score to pass
        """
        self.iou_threshold = iou_threshold
    
    def judge(
        self,
        original_stl_path: str,
        generated_step_path: str,
        num_slices: int = 10
    ) -> JudgePhase2Result:
        """Perform Phase 2 validation.
        
        Args:
            original_stl_path: Path to original STL file
            generated_step_path: Path to generated STEP file
            num_slices: Number of slices for IoU comparison
            
        Returns:
            Phase 2 result
        """
        try:
            import trimesh
            
            # Load meshes
            original_mesh = trimesh.load(original_stl_path)
            generated_mesh = trimesh.load(generated_step_path)
            
            # Calculate IoU
            iou_score, comparisons = calculate_iou(
                original_mesh,
                generated_mesh,
                num_slices=num_slices
            )
            
            passed = iou_score >= self.iou_threshold
            
            logger.info(
                f"Phase 2: IoU={iou_score:.4f}, threshold={self.iou_threshold}, "
                f"passed={passed}"
            )
            
            return JudgePhase2Result(
                passed=passed,
                iou_score=iou_score,
                iou_threshold=self.iou_threshold,
                slice_comparisons=comparisons
            )
            
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}")
            return JudgePhase2Result(
                passed=False,
                iou_score=0.0,
                iou_threshold=self.iou_threshold,
                slice_comparisons=[{"error": str(e)}]
            )


class Judge:
    """Complete two-phase judge system."""
    
    def __init__(
        self,
        iou_threshold: float = 0.98,
        max_retries: int = 3
    ):
        """Initialize judge.
        
        Args:
            iou_threshold: IoU threshold for acceptance
            max_retries: Maximum retry attempts
        """
        self.phase1 = Phase1Judge()
        self.phase2 = Phase2Judge(iou_threshold)
        self.max_retries = max_retries
        self.iou_threshold = iou_threshold
    
    def judge(
        self,
        code: str,
        original_stl_path: str,
        generated_step_path: Optional[str] = None,
        retry_count: int = 0
    ) -> JudgeResult:
        """Perform complete two-phase validation.
        
        Args:
            code: Generated build123d code
            original_stl_path: Path to original STL
            generated_step_path: Path to generated STEP (if available)
            retry_count: Current retry attempt
            
        Returns:
            Complete judge result
        """
        # Phase 1: Fail-fast
        phase1_result = self.phase1.judge(code, generated_step_path)
        
        if not phase1_result.passed:
            # Phase 1 failed - don't bother with Phase 2
            feedback = self._generate_feedback(phase1_result, None)
            
            return JudgeResult(
                phase1=phase1_result,
                phase2=None,
                accepted=False,
                retry_recommended=retry_count < self.max_retries,
                feedback_for_llm=feedback
            )
        
        # Phase 2: IoU comparison (only if STEP file available)
        phase2_result = None
        
        if generated_step_path:
            phase2_result = self.phase2.judge(
                original_stl_path,
                generated_step_path
            )
            
            accepted = phase2_result.passed
            retry_recommended = (
                not accepted and 
                retry_count < self.max_retries and
                phase2_result.iou_score > 0.70  # Only retry if somewhat close
            )
        else:
            # No STEP file to compare - accept based on Phase 1 only
            accepted = True
            retry_recommended = False
        
        feedback = self._generate_feedback(phase1_result, phase2_result)
        
        return JudgeResult(
            phase1=phase1_result,
            phase2=phase2_result,
            accepted=accepted,
            retry_recommended=retry_recommended,
            feedback_for_llm=feedback
        )
    
    def _generate_feedback(
        self,
        phase1: JudgePhase1Result,
        phase2: Optional[JudgePhase2Result]
    ) -> str:
        """Generate structured feedback for LLM retry.
        
        Args:
            phase1: Phase 1 result
            phase2: Phase 2 result (if performed)
            
        Returns:
            Feedback string for LLM
        """
        feedback_lines = ["# JUDGE FEEDBACK:"]
        
        if not phase1.passed:
            feedback_lines.append("## Phase 1 (Syntax/Topology) FAILED:")
            for error in phase1.errors:
                feedback_lines.append(f"- {error}")
            
            if not phase1.syntax_valid:
                feedback_lines.append("\nACTION REQUIRED: Fix syntax errors in the code.")
            elif not phase1.topology_valid:
                feedback_lines.append("\nACTION REQUIRED: Fix topological errors (self-intersections, inverted normals).")
        
        elif phase2 and not phase2.passed:
            feedback_lines.append("## Phase 2 (Geometric IoU) FAILED:")
            feedback_lines.append(f"- IoU score: {phase2.iou_score:.4f}")
            feedback_lines.append(f"- Required: {phase2.iou_threshold:.4f}")
            
            # Analyze which slices failed
            if phase2.slice_comparisons:
                bad_slices = [
                    s for s in phase2.slice_comparisons 
                    if s.get("iou", 0) < 0.90
                ]
                if bad_slices:
                    feedback_lines.append(f"\n- Poorly matching slices: {len(bad_slices)}")
                    for s in bad_slices[:3]:  # Show first 3
                        feedback_lines.append(
                            f"  - Height {s['height']:.1f}mm: IoU={s['iou']:.3f}, "
                            f"areas orig={s['orig_area']:.1f} gen={s['gen_area']:.1f}"
                        )
            
            feedback_lines.append(
                f"\nACTION REQUIRED: Adjust zone parameters to better match original geometry. "
                f"Focus on the heights with poor IoU scores."
            )
        
        else:
            feedback_lines.append("## All checks PASSED!")
            if phase2:
                feedback_lines.append(f"- Final IoU: {phase2.iou_score:.4f}")
        
        return "\n".join(feedback_lines)
