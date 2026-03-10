"""Main entry point for the Multi-Agent CAD-Recode system.

This module provides the high-level API for running the complete
reverse engineering pipeline on STL files.

Example:
    >>> from backend.main import process_stl
    >>> result = process_stl("path/to/model.stl")
    >>> print(result.final_output)
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import system components
from backend.core.state import CADState
from backend.core.graph import run_cad_recode

# Import agent factories
from backend.agents.sensor_agent import create_sensor_agent_factory
from backend.agents.coordinator_agent import create_coordinator_agent
from backend.agents.coder_agent import create_coder_agent
from backend.agents.vibeguard_agent import create_vibeguard_agent
from backend.validators.ast_validator import create_validator_agent
from backend.executor.secure_executor import create_executor_agent
from backend.skills.skill_library import SkillLibrary


def create_default_agents(
    llm_client: Optional[Any] = None
) -> Dict[str, Any]:
    """Create default agent instances.

    Args:
        llm_client: Optional LLM client to share across agents.

    Returns:
        Dictionary of agent factory functions.
    """
    # Initialize skill library
    skill_library = SkillLibrary()
    
    return {
        'sensor': create_sensor_agent_factory(llm_client),
        'coordinator': create_coordinator_agent(llm_client),
        'coder': create_coder_agent(llm_client),
        'validator': create_validator_agent(),
        'executor': create_executor_agent(),
        'vibeguard': create_vibeguard_agent()
    }


def process_stl(
    stl_path: str,
    llm_client: Optional[Any] = None,
    max_iterations: int = 3,
    output_dir: Optional[str] = None,
    part_type: str = "generic"
) -> CADState:
    """Process an STL file through the complete CAD-Recode pipeline.

    This is the main entry point for reverse engineering STL files
    into parametric CAD models.

    Args:
        stl_path: Path to the input STL file.
        llm_client: Optional LLM client for agent operations.
        max_iterations: Maximum refinement iterations (default: 3).
        output_dir: Optional directory for output files.
        part_type: Type of part ("generic" or "shaft").

    Returns:
        Final CADState with results.

    Raises:
        FileNotFoundError: If STL file doesn't exist.
        RuntimeError: If pipeline fails.

    Example:
        >>> result = process_stl("models/shaft.stl", max_iterations=5, part_type="shaft")
        >>> if result.final_output:
        ...     print("Success! Generated build123d script")
        ...     print(result.final_output[:500])
    """
    stl_file = Path(stl_path)
    if not stl_file.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    logger.info(f"=" * 60)
    logger.info(f"CAD-Recode Pipeline Starting")
    logger.info(f"Input: {stl_path}")
    logger.info(f"Part type: {part_type}")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info(f"=" * 60)

    # Create agents with part type
    agents = create_agents_for_part_type(llm_client, part_type)

    try:
        # Run the pipeline
        final_state = run_cad_recode(
            stl_path=str(stl_file.absolute()),
            agent_factories=agents,
            max_iterations=max_iterations
        )

        # Log results
        logger.info(f"=" * 60)
        logger.info(f"Pipeline Complete")
        logger.info(f"Iterations: {final_state.iteration_count}")
        logger.info(f"Chamfer distance: {final_state.chamfer_distance}")
        logger.info(f"Success: {final_state.final_output is not None}")
        logger.info(f"=" * 60)

        # Save outputs if directory provided
        if output_dir:
            _save_output_package(final_state, stl_file, output_dir, part_type)

        return final_state

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise RuntimeError(f"CAD-Recode pipeline failed: {e}") from e


def create_agents_for_part_type(
    llm_client: Optional[Any],
    part_type: str
) -> Dict[str, Any]:
    """Create agent factories configured for specific part type.
    
    Args:
        llm_client: Optional LLM client.
        part_type: Type of part ("generic" or "shaft").
    
    Returns:
        Dictionary of agent factory functions.
    """
    from backend.agents.coordinator_agent import create_coordinator_agent
    from backend.agents.coder_agent import create_coder_agent
    from backend.agents.sensor_agent import create_sensor_agent_factory
    from backend.agents.vibeguard_agent import create_vibeguard_agent
    from backend.validators.ast_validator import create_validator_agent
    from backend.executor.secure_executor import create_executor_agent
    
    return {
        'sensor': create_sensor_agent_factory(llm_client),
        'coordinator': create_coordinator_agent(llm_client, part_type=part_type),
        'coder': create_coder_agent(llm_client, part_type=part_type),
        'validator': create_validator_agent(),
        'executor': create_executor_agent(),
        'vibeguard': create_vibeguard_agent()
    }


def _save_output_package(
    state: CADState,
    stl_file: Path,
    output_dir: str,
    part_type: str
) -> None:
    """Save complete output package with all artifacts.
    
    Creates:
    - <name>_parametric.py: Generated build123d script
    - <name>_construction_plan.json: Construction plan (structured)
    - <name>_preview.stl: Generated mesh preview
    - <name>.step: Generated STEP file
    - <name>_report.json: Validation report with metrics
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    name = stl_file.stem
    
    # 1. Parametric Python script
    if state.final_output:
        script_path = output_path / f"{name}_parametric.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(state.final_output)
        logger.info(f"Saved: {script_path}")
    
    # 2. Construction plan JSON (strict contract)
    if state.shaft_construction_plan:
        plan_path = output_path / f"{name}_construction_plan.json"
        import json
        with open(plan_path, 'w', encoding='utf-8') as f:
            json.dump(state.shaft_construction_plan.to_dict(), f, indent=2)
        logger.info(f"Saved: {plan_path}")
    
    # 3. Preview STL and STEP files from executor
    if state.final_mesh_path:
        import shutil
        
        # Copy generated STL preview
        mesh_path = Path(state.final_mesh_path)
        if mesh_path.exists():
            preview_path = output_path / f"{name}_preview.stl"
            shutil.copy2(mesh_path, preview_path)
            logger.info(f"Saved: {preview_path}")
        
        # Copy generated STEP if available
        # The executor may have generated additional files
        step_candidates = [
            mesh_path.parent / "shaft.step",
            mesh_path.parent / f"output_{id(state.final_output)}.step" if state.final_output else None,
        ]
        for step_candidate in step_candidates:
            if step_candidate and step_candidate.exists():
                step_path = output_path / f"{name}.step"
                shutil.copy2(step_candidate, step_path)
                logger.info(f"Saved: {step_path}")
                break
    
    # 4. Validation report JSON
    report = {
        "input_file": str(stl_file),
        "part_type": part_type,
        "success": state.final_output is not None,
        "iterations": state.iteration_count,
        "metrics": {
            "chamfer_distance": state.chamfer_distance,
            "hausdorff_distance": state.hausdorff_distance
        },
        "validation_errors": state.validation_errors,
        "execution_errors": state.execution_errors,
        "geometric_errors": state.geometric_errors
    }
    
    # Add confidence if available
    if state.shaft_construction_plan:
        report["confidence"] = state.shaft_construction_plan.confidence
    
    report_path = output_path / f"{name}_report.json"
    import json
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved: {report_path}")
    
    logger.info(f"Output package saved to: {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Multi-Agent CAD-Recode: Reverse engineer STL to parametric CAD"
    )
    parser.add_argument(
        "stl_file",
        help="Path to input STL file"
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated files (default: output)"
    )
    parser.add_argument(
        "-i", "--iterations",
        type=int,
        default=3,
        help="Maximum refinement iterations (default: 3)"
    )
    parser.add_argument(
        "-t", "--type",
        default="generic",
        choices=["generic", "shaft"],
        help="Part type for specialized processing (default: generic)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        result = process_stl(
            stl_path=args.stl_file,
            max_iterations=args.iterations,
            output_dir=args.output,
            part_type=args.type
        )
        
        if result.final_output:
            print("\n" + "=" * 60)
            print("SUCCESS: Parametric CAD model generated")
            print("=" * 60)
            print(f"Output location: {args.output}")
            print(f"Chamfer distance: {result.chamfer_distance:.4f}")
            print(f"Iterations used: {result.iteration_count}")
            if result.shaft_construction_plan:
                print(f"Confidence: {result.shaft_construction_plan.confidence:.2%}")
            return 0
        else:
            print("\n" + "=" * 60)
            print("FAILED: Could not generate valid CAD model")
            print("=" * 60)
            if result.validation_errors:
                print("Validation errors:")
                for e in result.validation_errors:
                    print(f"  - {e}")
            if result.execution_errors:
                print("Execution errors:")
                for e in result.execution_errors:
                    print(f"  - {e}")
            if result.geometric_errors:
                print("Geometric errors:")
                for e in result.geometric_errors:
                    print(f"  - {e.get('description', 'Unknown')}")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())