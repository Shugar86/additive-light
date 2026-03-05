"""Pydantic models for LangGraph state management.

This module defines the typed state objects that flow through
the multi-agent system graph.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class Axis(str, Enum):
    """Enumeration for Cartesian axes."""
    X = "X"
    Y = "Y"
    Z = "Z"


class SliceFeature(BaseModel):
    """Represents a geometric feature found in a 2D slice.
    
    Attributes:
        feature_type: Type of feature (circle, rectangle, polygon, etc.)
        center: Center coordinates [x, y]
        radius: Radius if circular feature
        dimensions: Width, height for rectangular features
        area: Area of the feature
        perimeter: Perimeter length
        confidence: Detection confidence (0.0-1.0)
    """
    feature_type: str = Field(..., description="Type of geometric feature")
    center: List[float] = Field(default_factory=list)
    radius: Optional[float] = None
    dimensions: Optional[List[float]] = None
    area: float = Field(..., ge=0.0)
    perimeter: float = Field(..., ge=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SliceReport(BaseModel):
    """Report from a sensor agent analyzing one axis.
    
    Attributes:
        axis: Which axis was analyzed (X, Y, or Z)
        slice_positions: Positions along the axis where slices were taken
        features_by_slice: Features found at each slice position
        overall_bounds: Bounding box of analyzed region
        analysis_summary: Natural language summary from the agent
    """
    axis: Axis
    slice_positions: List[float] = Field(default_factory=list)
    features_by_slice: Dict[str, List[SliceFeature]] = Field(default_factory=dict)
    overall_bounds: List[float] = Field(default_factory=list)  # [min_x, min_y, min_z, max_x, max_y, max_z]
    analysis_summary: str = ""
    anomalies_detected: List[str] = Field(default_factory=list)


class Feature3D(BaseModel):
    """Aggregated 3D feature identified by the Coordinator.
    
    Attributes:
        feature_type: Type of 3D feature (cylinder, hole, slot, etc.)
        position: 3D center position [x, y, z]
        orientation: Primary axis orientation
        dimensions: Key dimensions (diameter, length, etc.)
        evidence: Which sensor reports contributed to this identification
    """
    feature_type: str
    position: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    orientation: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    dimensions: Dict[str, float] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class BuildStep(BaseModel):
    """Single step in the parametric construction plan.
    
    Attributes:
        step_number: Order in the construction sequence
        operation: Type of operation (sketch, extrude, cut, fillet, etc.)
        description: Human-readable description
        parameters: Operation-specific parameters
        dependencies: Which previous steps this depends on
    """
    step_number: int
    operation: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[int] = Field(default_factory=list)


class CADState(BaseModel):
    """Main state object flowing through the LangGraph.
    
    This is the central state container that carries all information
    through the multi-agent pipeline.
    
    Attributes:
        stl_path: Path to the input STL file
        aligned_mesh_path: Path to the centered/aligned mesh
        sensor_reports: Reports from X, Y, Z sensor agents
        identified_features: 3D features aggregated by Coordinator
        construction_plan: Step-by-step plan for parametric CAD
        generated_code: Current build123d code
        validation_errors: Errors from AST/safety validation
        execution_errors: Errors from running the code
        geometric_errors: Errors from VibeGuard comparison
        iteration_count: Number of refinement iterations
        final_output: Final validated build123d script
    """
    stl_path: Optional[str] = None
    aligned_mesh_path: Optional[str] = None
    
    # Sensor outputs
    sensor_reports: Dict[Axis, SliceReport] = Field(default_factory=dict)
    
    # Coordinator outputs
    identified_features: List[Feature3D] = Field(default_factory=list)
    construction_plan: List[BuildStep] = Field(default_factory=list)
    
    # Coder outputs
    generated_code: str = ""
    
    # Validation outputs
    validation_errors: List[str] = Field(default_factory=list)
    execution_errors: List[str] = Field(default_factory=list)
    geometric_errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Refinement tracking
    iteration_count: int = 0
    max_iterations: int = 3
    
    # Final output
    final_output: Optional[str] = None
    final_mesh_path: Optional[str] = None
    
    # Metrics
    chamfer_distance: Optional[float] = None
    hausdorff_distance: Optional[float] = None