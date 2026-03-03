"""LangGraph Pipeline for GDI.

Orchestrates the complete flow:
prepare_payload -> synthesize_code -> compile_and_check -> evaluate_iou -> (retry|accept)
"""

from typing import TypedDict, Optional, List, Any, Annotated, Dict
from dataclasses import dataclass, field
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..models.yaml_contract import (
    SensorTelemetry,
    ApproximationResult,
    JudgeResult,
    RunManifest,
    JudgePhase1Result,
    JudgePhase2Result,
)
from ..judge.judge import Judge
from .synthesizer import Synthesizer
from ..sandbox.executor import execute_build123d_code


class PipelineState(TypedDict):
    """State for the LangGraph pipeline."""
    
    # Inputs
    telemetry: SensorTelemetry
    source_stl: str
    prompt_version: str
    
    # Intermediate results
    generated_code: Optional[str]
    step_file_path: Optional[str]
    approximation_result: Optional[ApproximationResult]
    judge_result: Optional[JudgeResult]
    
    # Retry tracking
    retry_count: int
    max_retries: int
    retry_history: Annotated[List[Dict[str, Any]], operator.add]
    
    # Final output
    final_code: Optional[str]
    final_iou: Optional[float]
    run_manifest: Optional[RunManifest]
    status: str  # "success", "failure", "manual_review_required"
    
    # Error handling
    error_message: Optional[str]


def create_llm_client(model_name: str = "gpt-4o", api_key: Optional[str] = None):
    """Create LLM client for synthesis."""
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0.1,  # Low temperature for deterministic code
    )


def prepare_payload_node(state: PipelineState) -> PipelineState:
    """Prepare the payload for LLM synthesis."""
    # Telemetry is already in state
    return state


def synthesize_code_node(state: PipelineState) -> PipelineState:
    """Synthesize build123d code from telemetry."""
    telemetry = state["telemetry"]
    
    # Check if this is a retry
    retry_history = state.get("retry_history", [])
    previous_attempt = state.get("generated_code") if retry_history else None
    feedback = retry_history[-1].get("feedback") if retry_history else None
    
    try:
        # Use our new real LLM Synthesizer
        synthesizer = Synthesizer()
        code = synthesizer.generate_code(
            telemetry=telemetry,
            previous_attempt=previous_attempt,
            feedback=feedback
        )
        
        return {
            **state,
            "generated_code": code,
            "retry_count": state.get("retry_count", 0),
        }
    except Exception as e:
        return {
            **state,
            "error_message": f"LLM synthesis failed: {e}",
            "status": "failure",
        }


def compile_and_check_node(state: PipelineState) -> PipelineState:
    """Phase 1: Compile and check syntax/topology."""
    code = state.get("generated_code")
    
    if not code:
        return {
            **state,
            "status": "failure",
            "error_message": "No code generated",
        }
    
    # For Phase 1, check syntax
    from ..judge.topology_checker import check_code_syntax, check_build123d_imports
    
    syntax_valid, errors = check_code_syntax(code)
    patterns_valid, warnings = check_build123d_imports(code)
    
    if not syntax_valid:
        # Phase 1 failed - need retry
        return {
            **state,
            "judge_result": JudgeResult(
                phase1=JudgePhase1Result(
                    passed=False,
                    syntax_valid=False,
                    topology_valid=True,
                    errors=errors,
                    topology_log=None
                ),
                phase2=None,
                accepted=False,
                retry_recommended=state["retry_count"] < state["max_retries"],
                feedback_for_llm=f"Syntax errors: {errors}"
            ),
            "retry_count": state["retry_count"] + 1,
            "retry_history": state.get("retry_history", []) + [{
                "phase": "compile",
                "status": "failed",
                "errors": errors,
                "feedback": f"Syntax errors: {errors}"
            }],
            "step_file_path": None,
        }
    
    # Phase 1 passed - move to code execution in Sandbox
    import tempfile
    import os
    
    # Create output dir for execution
    output_dir = os.path.join(tempfile.gettempdir(), "gdi_sandbox")
    os.makedirs(output_dir, exist_ok=True)
    
    step_path = execute_build123d_code(code=code, output_dir=output_dir)
    
    if not step_path:
        error_msg = "Execution Sandbox failed. Check syntax or runtime logic."
        return {
            **state,
            "judge_result": JudgeResult(
                phase1=JudgePhase1Result(
                    passed=False,
                    syntax_valid=True,
                    topology_valid=False,
                    errors=[error_msg],
                    topology_log=None
                ),
                phase2=None,
                accepted=False,
                retry_recommended=state["retry_count"] < state["max_retries"],
                feedback_for_llm=error_msg
            ),
            "retry_count": state["retry_count"] + 1,
            "retry_history": state.get("retry_history", []) + [{
                "phase": "execution",
                "status": "failed",
                "errors": [error_msg],
                "feedback": error_msg
            }],
            "step_file_path": None,
        }
    
    return {
        **state,
        "step_file_path": step_path,
        "judge_result": None,  # Will be set by evaluate_iou
    }


def evaluate_iou_node(state: PipelineState) -> PipelineState:
    """Phase 2: Evaluate IoU if STEP file available."""
    step_file = state.get("step_file_path")
    source_stl = state["source_stl"]
    code = state.get("generated_code")
    
    if not step_file:
        # No STEP file to compare - skip Phase 2
        return {
            **state,
            "final_code": code,
            "final_iou": None,
            "status": "success" if code else "failure",
        }
    
    # Run full judge
    judge = Judge(iou_threshold=0.98, max_retries=state["max_retries"])
    result = judge.judge(
        code=code,
        original_stl_path=source_stl,
        generated_step_path=step_file,
        retry_count=state["retry_count"]
    )
    
    if result.accepted:
        return {
            **state,
            "judge_result": result,
            "final_code": code,
            "final_iou": result.phase2.iou_score if result.phase2 else None,
            "status": "success",
        }
    elif result.retry_recommended:
        return {
            **state,
            "judge_result": result,
            "retry_count": state["retry_count"] + 1,
            "retry_history": state.get("retry_history", []) + [{
                "phase": "iou",
                "iou_score": result.phase2.iou_score if result.phase2 else 0,
                "feedback": result.feedback_for_llm
            }],
        }
    else:
        # Max retries exceeded
        return {
            **state,
            "judge_result": result,
            "final_code": code,
            "final_iou": result.phase2.iou_score if result.phase2 else None,
            "status": "manual_review_required",
        }


def should_retry(state: PipelineState) -> str:
    """Determine if we should retry or end."""
    judge_result = state.get("judge_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if judge_result and judge_result.retry_recommended and retry_count < max_retries:
        return "retry"
    
    return "end"


def create_pipeline(max_retries: int = 3) -> StateGraph:
    """Create the LangGraph pipeline.
    
    Args:
        max_retries: Maximum retry attempts
        
    Returns:
        Compiled StateGraph
    """
    # Create graph
    workflow = StateGraph(PipelineState)
    
    # Add nodes
    workflow.add_node("prepare", prepare_payload_node)
    workflow.add_node("synthesize", synthesize_code_node)
    workflow.add_node("compile_check", compile_and_check_node)
    workflow.add_node("evaluate_iou", evaluate_iou_node)
    
    # Add edges
    workflow.set_entry_point("prepare")
    workflow.add_edge("prepare", "synthesize")
    workflow.add_edge("synthesize", "compile_check")
    workflow.add_edge("compile_check", "evaluate_iou")
    
    # Conditional edge for retry
    workflow.add_conditional_edges(
        "evaluate_iou",
        should_retry,
        {
            "retry": "synthesize",  # Go back to synthesis with feedback
            "end": END,
        }
    )
    
    return workflow.compile()


# Convenience function for direct use
def run_pipeline(
    telemetry: SensorTelemetry,
    source_stl: str,
    max_retries: int = 3,
    prompt_version: str = "1.0"
) -> RunManifest:
    """Run the complete pipeline.
    
    Args:
        telemetry: Sensor telemetry from Approximator
        source_stl: Path to source STL file
        max_retries: Maximum retry attempts
        prompt_version: Version of prompt used
        
    Returns:
        RunManifest with complete results
    """
    import uuid
    from datetime import datetime
    
    # Create initial state
    initial_state: PipelineState = {
        "telemetry": telemetry,
        "source_stl": source_stl,
        "prompt_version": prompt_version,
        "generated_code": None,
        "step_file_path": None,
        "approximation_result": None,
        "judge_result": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "retry_history": [],
        "final_code": None,
        "final_iou": None,
        "run_manifest": None,
        "status": "pending",
        "error_message": None,
    }
    
    # Create and run pipeline
    pipeline = create_pipeline(max_retries)
    
    try:
        final_state = pipeline.invoke(initial_state)
        
        # Create run manifest
        run_id = str(uuid.uuid4())
        manifest = RunManifest(
            run_id=run_id,
            prompt_version=prompt_version,
            yaml_schema_version="1.0",
            source_stl=source_stl,
            final_code=final_state.get("final_code"),
            final_iou=final_state.get("final_iou"),
            retry_count=final_state.get("retry_count", 0),
            retry_history=final_state.get("retry_history", []),
            status=final_state.get("status", "failure"),
            error_log=final_state.get("error_message"),
        )
        
        return manifest
        
    except Exception as e:
        # Create failure manifest
        return RunManifest(
            run_id=str(uuid.uuid4()),
            prompt_version=prompt_version,
            yaml_schema_version="1.0",
            source_stl=source_stl,
            status="failure",
            error_log=str(e),
        )
