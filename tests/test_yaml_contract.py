"""Test YAML Contract Validation

Acceptance test for YAML v1.0 contract validation.
"""

import pytest
import yaml
from pydantic import ValidationError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gdi_core.models import (
    GlobalState,
    ZoneParameters,
    TopologicalZone,
    AgentTask,
    SensorTelemetry,
    ApproximationResult,
    JudgeResult,
    RunManifest,
)
from gdi_core.models.yaml_contract import GeometryType, CrossSectionType


class TestGlobalState:
    """Test GlobalState model validation."""
    
    def test_valid_global_state(self):
        """AC-001: Valid GlobalState should pass validation."""
        gs = GlobalState(
            target_action="Generate parametric B-Rep code",
            target_library="build123d",
            base_axis="Z",
            total_height=40.0,
            yaml_version="1.0"
        )
        assert gs.base_axis == "Z"
        assert gs.total_height == 40.0
        assert gs.yaml_version == "1.0"
    
    def test_invalid_axis(self):
        """AC-002: Invalid axis should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            GlobalState(
                base_axis="W",  # Invalid
                total_height=40.0
            )
        assert "base_axis" in str(exc_info.value)
    
    def test_negative_height(self):
        """AC-003: Negative height should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            GlobalState(
                base_axis="Z",
                total_height=-10.0
            )
        assert "total_height" in str(exc_info.value)
    
    def test_zero_height(self):
        """AC-004: Zero height should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            GlobalState(
                base_axis="Z",
                total_height=0.0
            )
        assert "total_height" in str(exc_info.value)


class TestZoneParameters:
    """Test ZoneParameters model validation."""
    
    def test_valid_cylinder_params(self):
        """AC-005: Valid cylinder parameters should pass."""
        zp = ZoneParameters(
            radius=20.0,
            height=40.0
        )
        assert zp.radius == 20.0
        assert zp.height == 40.0
    
    def test_negative_radius(self):
        """AC-006: Negative radius should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneParameters(radius=-5.0)
        assert "radius" in str(exc_info.value)


class TestTopologicalZone:
    """Test TopologicalZone model validation."""
    
    def test_valid_zone(self):
        """AC-007: Valid zone should pass validation."""
        tz = TopologicalZone(
            zone_id=1,
            span_z=[0.0, 40.0],
            geometry=GeometryType.CONSTANT_PROFILE,
            cross_section=CrossSectionType.CIRCLE,
            parameters=ZoneParameters(radius=20.0, height=40.0),
            sensor_hint="Stable RANSAC fit. Cylinder detected.",
            confidence=0.95
        )
        assert tz.zone_id == 1
        assert tz.confidence == 0.95
    
    def test_invalid_span_z_order(self):
        """AC-008: span_z with start >= end should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            TopologicalZone(
                zone_id=1,
                span_z=[40.0, 0.0],  # Invalid order
                geometry=GeometryType.CONSTANT_PROFILE,
                cross_section=CrossSectionType.CIRCLE,
                parameters=ZoneParameters(radius=20.0),
                sensor_hint="Test",
                confidence=0.95
            )
        assert "span_z" in str(exc_info.value)
    
    def test_confidence_out_of_range(self):
        """AC-009: Confidence outside [0, 1] should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            TopologicalZone(
                zone_id=1,
                span_z=[0.0, 40.0],
                geometry=GeometryType.CONSTANT_PROFILE,
                cross_section=CrossSectionType.CIRCLE,
                parameters=ZoneParameters(radius=20.0),
                sensor_hint="Test",
                confidence=1.5  # Invalid
            )
        assert "confidence" in str(exc_info.value)
    
    def test_short_sensor_hint(self):
        """AC-010: Sensor hint shorter than 10 chars should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            TopologicalZone(
                zone_id=1,
                span_z=[0.0, 40.0],
                geometry=GeometryType.CONSTANT_PROFILE,
                cross_section=CrossSectionType.CIRCLE,
                parameters=ZoneParameters(radius=20.0),
                sensor_hint="Short",  # Too short
                confidence=0.95
            )
        assert "sensor_hint" in str(exc_info.value)


class TestAgentTask:
    """Test AgentTask model validation."""
    
    def test_valid_agent_task(self):
        """AC-011: Valid agent task should pass."""
        at = AgentTask(
            thought_process="Step 1: Detect cylinder. Step 2: Generate code.",
            code_output="from build123d import *"
        )
        assert "Step 1" in at.thought_process
    
    def test_short_thought_process(self):
        """AC-012: Thought process shorter than 50 chars should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentTask(
                thought_process="Too short."
            )
        assert "thought_process" in str(exc_info.value)


class TestSensorTelemetry:
    """Test SensorTelemetry model validation."""
    
    def test_valid_telemetry(self):
        """AC-013: Valid telemetry should pass."""
        st = SensorTelemetry(
            global_state=GlobalState(
                base_axis="Z",
                total_height=40.0
            ),
            topological_zones=[
                TopologicalZone(
                    zone_id=1,
                    span_z=[0.0, 40.0],
                    geometry=GeometryType.CONSTANT_PROFILE,
                    cross_section=CrossSectionType.CIRCLE,
                    parameters=ZoneParameters(radius=20.0, height=40.0),
                    sensor_hint="Stable RANSAC fit. Cylinder detected with radius 20mm.",
                    confidence=0.95
                )
            ],
            agent_task=AgentTask(
                thought_process="Step 1: Analyzed 400 slices. Step 2: Detected single cylinder zone.",
                code_output="with BuildPart(): ..."
            ),
            source_file="test_cylinder.stl"
        )
        assert st.global_state.total_height == 40.0
        assert len(st.topological_zones) == 1
        assert st.topological_zones[0].confidence == 0.95
    
    def test_empty_zones(self):
        """AC-014: Empty zones list should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            SensorTelemetry(
                global_state=GlobalState(
                    base_axis="Z",
                    total_height=40.0
                ),
                topological_zones=[],  # Empty - should fail
                agent_task=AgentTask(
                    thought_process="Step 1: Analyzed slices but found no zones. Step 2: Fallback to manual review required.",
                )
            )
        assert "topological_zones" in str(exc_info.value)


class TestApproximationResult:
    """Test ApproximationResult model validation."""
    
    def test_valid_result(self):
        """AC-015: Valid approximation result should pass."""
        ar = ApproximationResult(
            telemetry=SensorTelemetry(
                global_state=GlobalState(
                    base_axis="Z",
                    total_height=40.0
                ),
                topological_zones=[
                    TopologicalZone(
                        zone_id=1,
                        span_z=[0.0, 40.0],
                        geometry=GeometryType.CONSTANT_PROFILE,
                        cross_section=CrossSectionType.CIRCLE,
                        parameters=ZoneParameters(radius=20.0),
                        sensor_hint="Cylinder detected.",
                        confidence=0.95
                    )
                ],
                agent_task=AgentTask(
                    thought_process="Step 1: Analyzed slices. Step 2: Detected cylinder.",
                )
            ),
            global_confidence=0.95,
            fallback_required=False
        )
        assert ar.global_confidence == 0.95
        assert not ar.fallback_required
    
    def test_low_confidence_fallback(self):
        """AC-016: Low confidence should trigger fallback."""
        ar = ApproximationResult(
            telemetry=SensorTelemetry(
                global_state=GlobalState(
                    base_axis="Z",
                    total_height=40.0
                ),
                topological_zones=[
                    TopologicalZone(
                        zone_id=1,
                        span_z=[0.0, 40.0],
                        geometry=GeometryType.CONSTANT_PROFILE,
                        cross_section=CrossSectionType.CIRCLE,
                        parameters=ZoneParameters(radius=20.0),
                        sensor_hint="Low quality data, uncertain detection.",
                        confidence=0.45
                    )
                ],
                agent_task=AgentTask(
                    thought_process="Step 1: Analyzed slices. Step 2: Low confidence detection.",
                )
            ),
            global_confidence=0.45,
            fallback_required=True,
            fallback_reason="Confidence below threshold (0.45 < 0.70)"
        )
        assert ar.fallback_required
        assert "threshold" in ar.fallback_reason


class TestYamlSerialization:
    """Test YAML serialization/deserialization."""
    
    def test_telemetry_to_yaml_dict(self):
        """AC-017: Telemetry should serialize to YAML-compatible dict."""
        st = SensorTelemetry(
            global_state=GlobalState(
                base_axis="Z",
                total_height=40.0
            ),
            topological_zones=[
                TopologicalZone(
                    zone_id=1,
                    span_z=[0.0, 40.0],
                    geometry=GeometryType.CONSTANT_PROFILE,
                    cross_section=CrossSectionType.CIRCLE,
                    parameters=ZoneParameters(radius=20.0, height=40.0),
                    sensor_hint="Cylinder detected with RANSAC.",
                    confidence=0.95
                )
            ],
            agent_task=AgentTask(
                thought_process="Analysis complete. Ready for synthesis.",
                code_output="code here"
            ),
            source_file="test.stl"
        )
        
        yaml_dict = st.to_yaml_dict()
        assert "global_state" in yaml_dict
        assert "topological_zones" in yaml_dict
        assert "agent_task" in yaml_dict
        assert yaml_dict["global_state"]["base_axis"] == "Z"
    
    def test_yaml_roundtrip(self):
        """AC-018: YAML roundtrip should preserve data."""
        original = SensorTelemetry(
            global_state=GlobalState(
                base_axis="Z",
                total_height=40.0
            ),
            topological_zones=[
                TopologicalZone(
                    zone_id=1,
                    span_z=[0.0, 40.0],
                    geometry=GeometryType.CONSTANT_PROFILE,
                    cross_section=CrossSectionType.CIRCLE,
                    parameters=ZoneParameters(radius=20.0),
                    sensor_hint="Cylinder detected.",
                    confidence=0.95
                )
            ],
            agent_task=AgentTask(
                thought_process="Analysis complete.",
            ),
            source_file="test.stl"
        )
        
        # Serialize to YAML
        yaml_dict = original.to_yaml_dict()
        yaml_str = yaml.dump(yaml_dict)
        
        # Deserialize
        loaded_dict = yaml.safe_load(yaml_str)
        restored = SensorTelemetry(**loaded_dict)
        
        assert restored.global_state.total_height == original.global_state.total_height
        assert restored.topological_zones[0].confidence == original.topological_zones[0].confidence


class TestRunManifest:
    """Test RunManifest model validation."""
    
    def test_valid_manifest(self):
        """AC-019: Valid run manifest should pass."""
        rm = RunManifest(
            run_id="test-run-001",
            prompt_version="1.0",
            yaml_schema_version="1.0",
            source_stl="test.stl",
            output_yaml="output.yaml",
            final_iou=0.98,
            status="success"
        )
        assert rm.run_id == "test-run-001"
        assert rm.final_iou == 0.98
        assert rm.status == "success"
    
    def test_invalid_status(self):
        """AC-020: Invalid status should raise error."""
        with pytest.raises(ValidationError) as exc_info:
            RunManifest(
                run_id="test",
                prompt_version="1.0",
                yaml_schema_version="1.0",
                source_stl="test.stl",
                status="invalid_status"  # Invalid
            )
        assert "status" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
