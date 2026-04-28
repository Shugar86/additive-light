"""Proposed Pydantic shapes for manufacturing_intent YAML (experimental).

These models mirror the informal sketch under ``docs/examples/manufacturing_intent.example.yaml``.
They are **not** imported by ``backend.main``, ``backend.core.graph``, or agent nodes.

Todo (planned research): converge with a versioned YAML schema once the research track stabilizes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PartRefExperimental(BaseModel):
    """Opaque references to geometry inputs (placeholders).

    Attributes:
        stl_sha256: Optional content hash for traceability.
        cad_session_id: Optional session/run identifier from upstream tooling.
    """

    stl_sha256: Optional[str] = None
    cad_session_id: Optional[str] = None


class LabeledFeatureExperimental(BaseModel):
    """Semantic label provisional on a reconstructed feature."""

    feature_id: str = Field(default="", description="External id aligned with planner output.")
    geometry_ref: Dict[str, Any] = Field(default_factory=dict, description="Pointer into recovered geometry.")
    label: str = Field(default="", description="Human-readable semantic tag (hypothesis).")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


class ManufacturingIntentExperimental(BaseModel):
    """High-level provisional intent—not a drawing substitute."""

    process_family: Optional[str] = None
    stock_assumption: Optional[str] = None
    primary_datum_hypothesis: Optional[str] = None
    tolerance_notes: List[str] = Field(default_factory=list)


class RouteHintsExperimental(BaseModel):
    """Non-authoritative process sequence suggestions."""

    suggested_steps: List[str] = Field(default_factory=list)


class ManufacturingIntentBundleExperimental(BaseModel):
    """Top-level bundle for experimentation and offline tooling.

    Mirrors ``schema_version`` and nested keys from the YAML example doc.
    """

    schema_version: str = Field(
        default="0.proposed-experimental",
        description="Informal revision tag until a semver schema exists.",
    )
    part_ref: PartRefExperimental = Field(default_factory=PartRefExperimental)
    labeled_features: List[LabeledFeatureExperimental] = Field(default_factory=list)
    manufacturing_intent: ManufacturingIntentExperimental = Field(
        default_factory=ManufacturingIntentExperimental
    )
    route_hints_experimental: RouteHintsExperimental = Field(
        default_factory=RouteHintsExperimental
    )
