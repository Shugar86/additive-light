"""YAML Contract Models for GDI Pipeline.

This module defines the strict YAML v1.0 schema used for communication
between deterministic "sensors" (Python) and the "brain" (LLM).
"""

from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class GeometryType(str, Enum):
    """Supported geometry types for topological zones."""
    CONSTANT_PROFILE = "Constant_Profile"
    CONSTANT_PROFILE_WITH_HOLES = "Constant_Profile_with_Holes"
    LINEAR_REGRESSION = "Linear_Regression"  # Chamfer/Cone
    COMPLEX = "Complex"  # Fallback for non-parametric shapes


class CrossSectionType(str, Enum):
    """Supported cross-section types."""
    CIRCLE = "Circle"
    RECTANGLE = "Rectangle"
    L_PROFILE = "L_Profile"
    POLYGON = "Polygon"


class GlobalState(BaseModel):
    """Global state block - metadata about the target operation."""
    
    target_action: Literal["Generate parametric B-Rep code"] = Field(
        default="Generate parametric B-Rep code",
        description="The action to be performed by the LLM"
    )
    target_library: Literal["build123d"] = Field(
        default="build123d",
        description="Target CAD library for code generation"
    )
    base_axis: Literal["X", "Y", "Z"] = Field(
        default="Z",
        description="Primary build axis of the part"
    )
    total_height: float = Field(
        ...,  # Required
        gt=0,
        description="Total height of the part along base_axis (mm)"
    )
    yaml_version: Literal["1.0"] = Field(
        default="1.0",
        description="YAML schema version for compatibility"
    )
    
    class Config:
        validate_assignment = True


class ZoneParameters(BaseModel):
    """Parameters specific to a topological zone.
    
    Different geometry types require different parameter sets.
    """
    # Common parameters
    radius: Optional[float] = Field(None, gt=0, description="Radius for circular profiles")
    height: Optional[float] = Field(None, gt=0, description="Height of the zone")
    
    # Rectangle parameters
    width: Optional[float] = Field(None, gt=0, description="Width for rectangular profiles")
    depth: Optional[float] = Field(None, gt=0, description="Depth for rectangular profiles")
    
    # Linear transition (chamfer/cone)
    radius_start: Optional[float] = Field(None, gt=0, description="Starting radius for linear transitions")
    radius_end: Optional[float] = Field(None, gt=0, description="Ending radius for linear transitions")
    
    # Hole parameters
    hole_count: Optional[int] = Field(None, ge=0, description="Number of holes detected")
    hole_radius: Optional[float] = Field(None, gt=0, description="Radius of holes")
    hole_pitch_radius: Optional[float] = Field(None, gt=0, description="Pitch radius for polar array of holes")
    
    # Pocket/cutout parameters
    pocket_radius: Optional[float] = Field(None, gt=0, description="Radius of central pocket")
    pocket_depth: Optional[float] = Field(None, gt=0, description="Depth of central pocket")
    
    # Polygon/L-profile specific
    center: Optional[List[float]] = Field(
        default=None,
        min_items=2,
        max_items=3,
        description="Center point [x, y, z] of the zone"
    )
    
    class Config:
        extra = "allow"  # Allow additional parameters for future extensibility


class TopologicalZone(BaseModel):
    """A single topological zone representing a segment of the part.
    
    Each zone has a span along Z-axis, geometry type, and detected parameters.
    """
    zone_id: int = Field(..., ge=1, description="Unique identifier for the zone")
    span_z: List[float] = Field(
        ...,
        min_items=2,
        max_items=2,
        description="Z-range [start, end] of the zone in mm"
    )
    geometry: GeometryType = Field(
        ...,
        description="Type of geometry in this zone"
    )
    cross_section: CrossSectionType = Field(
        ...,
        description="Shape of the cross-section"
    )
    parameters: ZoneParameters = Field(
        ...,
        description="Detected geometric parameters"
    )
    sensor_hint: str = Field(
        ...,
        min_length=10,
        description="Human-readable hint from sensor about this zone"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this zone (0.0-1.0)"
    )
    
    @validator("span_z")
    def validate_span_z(cls, v):
        """Ensure span_z[0] < span_z[1]."""
        if v[0] >= v[1]:
            raise ValueError(f"span_z start ({v[0]}) must be less than end ({v[1]})")
        return v
    
    class Config:
        validate_assignment = True


class AgentTask(BaseModel):
    """Agent task block - instructions and reasoning for the LLM.
    
    Enforces Structured Chain-of-Thought (SCoT) discipline.
    """
    rules: List[str] = Field(
        default=[
            "Do not use visual assumptions. Rely ONLY on the Parameters above.",
            "Use 'with BuildPart():' and 'with BuildSketch():' context managers.",
            "Round floats to 1 decimal place (Beautification).",
        ],
        description="Rules the LLM must follow"
    )
    thought_process: str = Field(
        ...,
        min_length=50,
        description="Step-by-step reasoning the LLM MUST fill before writing code"
    )
    code_output: Optional[str] = Field(
        None,
        description="Generated build123d code (filled by LLM)"
    )
    
    class Config:
        validate_assignment = True


class SensorTelemetry(BaseModel):
    """Complete YAML payload sent from Sensor/Approximator to LLM.
    
    This is the main communication contract between deterministic
    sensors and the LLM synthesizer.
    """
    global_state: GlobalState = Field(..., description="Global configuration")
    topological_zones: List[TopologicalZone] = Field(
        ...,
        min_items=1,
        description="Detected topological zones"
    )
    agent_task: AgentTask = Field(..., description="Task for the LLM")
    
    # Metadata for tracing
    source_file: Optional[str] = Field(None, description="Source STL file path")
    generated_at: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of generation"
    )
    
    class Config:
        validate_assignment = True
        
    def to_yaml_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for YAML serialization."""
        return self.model_dump(by_alias=False, exclude_none=True)


class ApproximationResult(BaseModel):
    """Result from the Approximator module.
    
    Contains the detected zones and global confidence score.
    """
    telemetry: SensorTelemetry = Field(..., description="YAML payload for LLM")
    global_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for the approximation"
    )
    fallback_required: bool = Field(
        ...,
        description="Whether manual review is required (confidence below threshold)"
    )
    fallback_reason: Optional[str] = Field(
        None,
        description="Reason for fallback if applicable"
    )
    processing_time_ms: Optional[int] = Field(
        None,
        description="Processing time in milliseconds"
    )
    
    class Config:
        validate_assignment = True


class JudgePhase1Result(BaseModel):
    """Result from Judge Phase 1 (syntax and topology check)."""
    passed: bool = Field(..., description="Whether phase 1 passed")
    syntax_valid: bool = Field(..., description="Whether code syntax is valid")
    topology_valid: bool = Field(..., description="Whether topology is valid")
    errors: List[str] = Field(default=[], description="List of error messages")
    topology_log: Optional[str] = Field(None, description="BRepCheck_Analyzer log")


class JudgePhase2Result(BaseModel):
    """Result from Judge Phase 2 (IoU geometric comparison)."""
    passed: bool = Field(..., description="Whether IoU threshold met")
    iou_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Intersection over Union score"
    )
    iou_threshold: float = Field(
        default=0.98,
        ge=0.0,
        le=1.0,
        description="Threshold that was required"
    )
    slice_comparisons: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Per-slice comparison details"
    )


class JudgeResult(BaseModel):
    """Complete result from the Judge (both phases)."""
    phase1: JudgePhase1Result = Field(..., description="Syntax/topology check result")
    phase2: Optional[JudgePhase2Result] = Field(
        None,
        description="IoU check result (only if phase1 passed)"
    )
    accepted: bool = Field(..., description="Whether part is accepted")
    retry_recommended: bool = Field(
        default=False,
        description="Whether to retry with feedback"
    )
    feedback_for_llm: Optional[str] = Field(
        None,
        description="Structured feedback to send back to LLM on retry"
    )
    
    class Config:
        validate_assignment = True


class RunManifest(BaseModel):
    """Complete manifest for a single pipeline run.
    
    Provides full traceability and audit trail.
    """
    run_id: str = Field(..., description="Unique run identifier (UUID)")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of run start"
    )
    
    # Configuration versions
    yaml_schema_version: str = Field(default="1.0")
    prompt_version: str = Field(..., description="Version of LLM prompt used")
    
    # Source and outputs
    source_stl: str = Field(..., description="Path to source STL file")
    output_yaml: Optional[str] = Field(None, description="Path to generated YAML")
    output_step: Optional[str] = Field(None, description="Path to generated STEP file")
    output_nc: Optional[str] = Field(None, description="Path to generated G-code")
    
    # Pipeline results
    approximation_result: Optional[ApproximationResult] = None
    judge_result: Optional[JudgeResult] = None
    final_iou: Optional[float] = Field(None, ge=0.0, le=1.0)
    final_code: Optional[str] = None
    
    # Retry tracking
    retry_count: int = Field(default=0, ge=0)
    retry_history: List[Dict[str, Any]] = Field(default=[])
    
    # Status
    status: Literal["success", "failure", "manual_review_required"] = Field(
        ...,
        description="Final status of the run"
    )
    error_log: Optional[str] = None
    
    class Config:
        validate_assignment = True
