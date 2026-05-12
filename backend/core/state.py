"""Pydantic models for LangGraph state management.

This module defines the typed state objects that flow through
the multi-agent system graph.
"""

from typing import List, Dict, Any, Literal, Optional
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


# =============================================================================
# Shaft MVP: Strict Construction Plan Models
# =============================================================================

class ShaftZoneType(str, Enum):
    """Types of zones in a shaft construction plan."""
    CYLINDER = "cylinder"
    CONE = "cone"           # Linearly tapered frustum section
    FILLET = "fillet"
    CHAMFER = "chamfer"
    GROOVE = "groove"
    STEP = "step"


class ShaftZoneSpec(BaseModel):
    """Specification for a shaft zone (segment).

    This is the core building block for revolve-based shaft construction.
    Each zone represents a section with constant or varying radius.

    Sprint 2.4 adds three optional fields (``arc_center_z``, ``arc_center_r``,
    ``arc_radius``) so the construction plan can carry the fitted arc
    geometry for FILLET and CHAMFER zones. The revolve polyline builder
    uses them to discretise the arc instead of falling back to a straight
    segment between ``start_radius`` and ``end_radius``. Keeping the fields
    optional preserves wire-format backward compatibility with reports
    written before Sprint 2.4.
    """
    zone_type: ShaftZoneType
    start_pos: float = Field(..., description="Start position along shaft axis")
    end_pos: float = Field(..., description="End position along shaft axis")
    start_radius: float = Field(..., ge=0, description="Radius at start position")
    end_radius: float = Field(..., ge=0, description="Radius at end position")
    mean_radius: float = Field(..., ge=0, description="Average radius in zone")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Additional metadata for specific zone types
    chamfer_angle: Optional[float] = Field(None, description="Chamfer angle in degrees (for chamfer zones)")
    fillet_radius: Optional[float] = Field(None, ge=0, description="Fillet radius (for fillet zones)")

    # Sprint 2.4: fitted-arc parameters for FILLET / CHAMFER zones.
    arc_center_z: Optional[float] = Field(
        None, description="Z coordinate of fitted arc centre (Sprint 2.4)"
    )
    arc_center_r: Optional[float] = Field(
        None, description="Radial coordinate of fitted arc centre (Sprint 2.4)"
    )
    arc_radius: Optional[float] = Field(
        None, ge=0.0, description="Fitted arc radius (Sprint 2.4)"
    )


class LocalFeatureType(str, Enum):
    """Types of local features on shafts."""
    KEYWAY = "keyway"
    FLAT = "flat"
    CROSS_HOLE = "cross_hole"
    GROOVE = "groove"
    SNAP_RING = "snap_ring"


class LocalFeatureSpec(BaseModel):
    """Specification for a local feature (keyway, flat, hole).
    
    These features are applied after the base revolve geometry.
    """
    feature_type: LocalFeatureType
    position: List[float] = Field(..., min_length=3, max_length=3, description="3D center position [x, y, z]")
    orientation: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0], min_length=3, max_length=3)
    dimensions: Dict[str, float] = Field(default_factory=dict, description="Feature dimensions (width, depth, length, diameter)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    zone_index: Optional[int] = Field(None, description="Which zone this feature belongs to")


class AxisSpec(BaseModel):
    """Specification for the shaft main axis."""
    direction: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0], min_length=3, max_length=3)
    origin: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    length: float = Field(..., gt=0, description="Shaft length along axis")


class MeasurementLogEntry(BaseModel):
    """Single entry in the measurement log."""
    timestamp: str
    operation: str
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)


class OutOfScopeRegion(BaseModel):
    """A z-band whose cross-section is not a body of revolution.

    Sprint 3 introduces the Spike Generator: instead of silently smearing
    over a keyway / cross-hole / flat with an average radius, the pipeline
    detects regions of high ``phi_variance`` (deviation of boundary points
    from a perfect circle) and records them here. The data is consumed by
    :class:`SkillRequest` to formulate an explicit ask for the v2 swarm.
    """

    z_start: float = Field(..., description="Lower bound of the region along the axis")
    z_end: float = Field(..., description="Upper bound of the region along the axis")
    max_phi_variance: float = Field(..., ge=0.0, description="Peak phi_variance score observed in the band")
    mean_phi_variance: float = Field(..., ge=0.0, description="Mean phi_variance score across the band")
    sample_count: int = Field(..., ge=0, description="Number of slices that contributed to the region")
    mean_radius_mm: float = Field(..., ge=0.0, description="Mean boundary radius across the band (mm)")


class SkillRequest(BaseModel):
    """An explicit request emitted by the Spike Generator for a missing tool.

    The blind engineer metaphor: when the deterministic toolkit can not
    handle a region of the part, it tells the swarm what kind of tool it
    needs ("a transverse-hole detector for z=[12.5, 14.0]"), rather than
    silently producing a low-confidence reconstruction. Activation of the
    bootstrapper that fulfils the request lives in roadmap v2 — the v1
    payload below is what the report carries today.
    """

    trigger: str = Field(..., description="Why the request was raised (e.g. 'non_revolution_region_detected')")
    region: OutOfScopeRegion
    hypothesis: List[str] = Field(
        default_factory=list,
        description="Candidate feature types in order of likelihood (e.g. ['transverse_hole', 'flat'])",
    )
    needs_tool: str = Field(..., description="Name of the tool / skill that would resolve the request")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Detector confidence in the hypothesis")


class ShaftConstructionPlan(BaseModel):
    """Strict construction plan for shaft reverse engineering.
    
    This is the hard contract between sensor pipeline and code generator.
    NO free text - only structured, machine-checkable data.
    
    Attributes:
        part_type: Always "shaft" for shaft parts
        base_axis: Main rotational axis specification
        segments: List of shaft zones (cylinders, fillets, etc.)
        features: List of local features (keyways, holes, etc.)
        fillets: List of fillet specifications
        chamfers: List of chamfer specifications
        out_of_scope_regions: Bands flagged by the Spike Generator (Sprint 3)
        skill_requests: Explicit tool-asks for the v2 swarm (Sprint 3)
        confidence: Overall detection confidence
        measurement_log: Audit trail of measurements
    """
    part_type: Literal["shaft"] = "shaft"
    base_axis: AxisSpec
    segments: List[ShaftZoneSpec] = Field(default_factory=list)
    features: List[LocalFeatureSpec] = Field(default_factory=list)
    fillets: List[Dict[str, Any]] = Field(default_factory=list)
    chamfers: List[Dict[str, Any]] = Field(default_factory=list)
    out_of_scope_regions: List[OutOfScopeRegion] = Field(default_factory=list)
    skill_requests: List[SkillRequest] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    measurement_log: List[MeasurementLogEntry] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return self.model_dump()
    
    def validate_geometry(self) -> List[str]:
        """Validate construction plan geometry.
        
        Returns:
            List of validation errors (empty if valid).
        """
        errors = []
        
        # Check for segments
        if not self.segments:
            errors.append("No shaft segments defined")
        
        # Check segment continuity
        for i in range(len(self.segments) - 1):
            seg1 = self.segments[i]
            seg2 = self.segments[i + 1]
            
            # End of one should match start of next
            if abs(seg1.end_pos - seg2.start_pos) > 0.01:
                errors.append(f"Gap between segment {i} and {i+1}")
            
            # Radius continuity at transitions
            if abs(seg1.end_radius - seg2.start_radius) > 0.1:
                # Large jump might indicate a step (allowed) or error
                pass  # Steps are valid
        
        # Check for negative radii
        for seg in self.segments:
            if seg.start_radius < 0 or seg.end_radius < 0:
                errors.append(f"Negative radius in segment at {seg.start_pos}")
        
        return errors


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
    
    # Shaft MVP: Dedicated construction plan
    shaft_construction_plan: Optional[ShaftConstructionPlan] = None
    
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