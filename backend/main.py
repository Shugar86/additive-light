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
    output_dir: Optional[str] = None
) -> CADState:
    """Process an STL file through the complete CAD-Recode pipeline.

    This is the main entry point for reverse engineering STL files
    into parametric CAD models.

    Args:
        stl_path: Path to the input STL file.
        llm_client: Optional LLM client for agent operations.
        max_iterations: Maximum refinement iterations (default: 3).
        output_dir: Optional directory for output files.

    Returns:
        Final CADState with results.

    Raises:
        FileNotFoundError: If STL file doesn't exist.
        RuntimeError: If pipeline fails.

    Example:
        >>> result = process_stl("models/shaft.stl", max_iterations=5)
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
    logger.info(f"Max iterations: {max_iterations}")
    logger.info(f"=" * 60)

    # Create agents
    agents = create_default_agents(llm_client)

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
        if output_dir and final_state.final_output:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            script_path = output_path / f"{stl_file.stem}_parametric.py"
            with open(script_path, 'w') as f:
                f.write(final_state.final_output)
            
            logger.info(f"Output saved to: {script_path}")

        return final_state

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise RuntimeError(f"CAD-Recode pipeline failed: {e}") from e


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
            output_dir=args.output
        )
        
        if result.final_output:
            print("\n" + "=" * 60)
            print("SUCCESS: Parametric CAD model generated")
            print("=" * 60)
            print(f"Output location: {args.output}")
            print(f"Chamfer distance: {result.chamfer_distance:.4f}")
            print(f"Iterations used: {result.iteration_count}")
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