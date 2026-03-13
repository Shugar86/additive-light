"""Integration tests for the complete CAD-Recode pipeline.

These tests verify that all components work together correctly
using synthetic test meshes.
"""

import pytest
import tempfile
from pathlib import Path

# Skip all tests if dependencies not available
try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

try:
    from langgraph.graph import StateGraph
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False


@pytest.fixture
def test_cylinder_stl():
    """Create a temporary cylinder STL for testing."""
    if not HAS_OPEN3D:
        pytest.skip("Open3D not installed")
    
    mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=5.0, height=20.0, resolution=32)
    mesh.compute_vertex_normals()
    
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
        temp_path = f.name
    
    o3d.io.write_triangle_mesh(temp_path, mesh)
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestSensorIntegration:
    """Integration tests for sensor pipeline."""

    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    def test_align_and_slice_integration(self, test_cylinder_stl):
        """Test that alignment and slicing work together."""
        from backend.sensors.align_open3d import load_and_center_mesh
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        # Step 1: Align the mesh
        aligned_path, centroid, axes = load_and_center_mesh(test_cylinder_stl)
        
        assert Path(aligned_path).exists()
        assert centroid is not None
        
        # Step 2: Slice the aligned mesh
        analyzer = SliceAnalyzer(aligned_path)
        slices = analyzer.slice_along_axis('Z', slice_count=10)
        
        assert len(slices) > 0
        
        # Step 3: Verify slices contain circular features
        for slice_data in slices:
            features = slice_data.get("features", [])
            circles = [f for f in features if f["type"] == "circle"]
            
            # Cylinder should have circular cross-sections
            if circles:
                # Radius should be approximately 5.0
                radius = circles[0]["radius"]
                assert abs(radius - 5.0) < 0.5
        
        # Cleanup
        Path(aligned_path).unlink(missing_ok=True)


class TestAgentFactories:
    """Tests for agent factory functions."""

    def test_sensor_agent_factory(self):
        """Test that sensor agent factory creates valid agents."""
        from backend.agents.sensor_agent import create_sensor_agent_factory
        from backend.core.state import Axis
        
        factory = create_sensor_agent_factory(llm_client=None)
        
        # Create agents for each axis
        for axis in [Axis.X, Axis.Y, Axis.Z]:
            agent = factory(axis)
            assert agent.axis == axis
            assert agent.slice_count > 0

    def test_coordinator_agent(self):
        """Test coordinator agent factory."""
        from backend.agents.coordinator_agent import create_coordinator_agent
        
        agent_fn = create_coordinator_agent(llm_client=None)
        assert callable(agent_fn)

    def test_coder_agent(self):
        """Test coder agent factory."""
        from backend.agents.coder_agent import create_coder_agent
        
        agent_fn = create_coder_agent(llm_client=None)
        assert callable(agent_fn)

    def test_validator_agent(self):
        """Test validator agent factory."""
        from backend.validators.ast_validator import create_validator_agent
        
        validator_fn = create_validator_agent()
        assert callable(validator_fn)
        
        # Test validation on simple code
        test_code = "from build123d import *\npart = Box(1, 2, 3)"
        errors = validator_fn(test_code)
        assert isinstance(errors, list)

    def test_executor_agent(self):
        """Test executor agent factory."""
        from backend.executor.secure_executor import create_executor_agent
        
        executor_fn = create_executor_agent()
        assert callable(executor_fn)

    def test_vibeguard_agent(self):
        """Test vibeguard agent factory."""
        from backend.agents.vibeguard_agent import create_vibeguard_agent
        
        vibeguard_fn = create_vibeguard_agent()
        assert callable(vibeguard_fn)


class TestStateFlow:
    """Tests for state management."""

    def test_cad_state_creation(self):
        """Test CADState can be created and modified."""
        from backend.core.state import CADState, SliceReport, Axis
        
        state = CADState(
            stl_path="test.stl",
            max_iterations=3
        )
        
        assert state.stl_path == "test.stl"
        assert state.max_iterations == 3
        assert state.iteration_count == 0
        
        # Add a sensor report
        report = SliceReport(
            axis=Axis.Z,
            slice_positions=[0.0, 1.0, 2.0],
            analysis_summary="Test report"
        )
        
        state.sensor_reports[Axis.Z] = report
        assert Axis.Z in state.sensor_reports

    def test_state_serialization(self):
        """Test that state can be serialized to dict."""
        from backend.core.state import CADState, SliceReport, Axis
        
        state = CADState(stl_path="test.stl")
        
        report = SliceReport(
            axis=Axis.Z,
            slice_positions=[0.0, 1.0],
            analysis_summary="Test"
        )
        state.sensor_reports[Axis.Z] = report
        
        # Convert to dict
        data = state.model_dump()
        
        assert data["stl_path"] == "test.stl"
        assert "sensor_reports" in data


class TestSkillLibrary:
    """Tests for skill bootstrapping system."""

    def test_skill_library_initialization(self):
        """Test that skill library can be initialized."""
        from backend.skills.skill_library import SkillLibrary
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(library_path=tmpdir)
            
            assert library is not None
            assert library.list_skills() == []  # Empty initially

    def test_skill_creation_and_save(self):
        """Test creating and saving a skill."""
        from backend.skills.skill_library import SkillLibrary, Skill
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(library_path=tmpdir)
            
            # Create a skill
            skill = Skill(
                name="test_analyze",
                description="Test analysis function",
                code="def test_analyze(x): return x * 2",
                signature={"input": {"x": "float"}, "output": {"result": "float"}}
            )
            
            # Save it
            library.save_skill(skill)
            
            # Verify it was saved
            assert "test_analyze" in library.list_skills()
            
            # Retrieve it
            retrieved = library.get_skill("test_analyze")
            assert retrieved is not None
            assert retrieved.name == "test_analyze"


class TestCodeGeneration:
    """Tests for code generation and validation."""

    def test_coder_generates_valid_build123d(self):
        """Test that coder produces valid-looking build123d code."""
        from backend.agents.coder_agent import CoderAgent
        from backend.core.state import CADState, BuildStep, Feature3D
        
        agent = CoderAgent(llm_client=None)
        
        # Create a simple state with construction plan
        state = CADState(stl_path="test.stl")
        state.construction_plan = [
            BuildStep(
                step_number=1,
                operation="base_sketch",
                description="Create circle",
                parameters={"shape": "circle", "radius": 10.0}
            ),
            BuildStep(
                step_number=2,
                operation="extrude",
                description="Extrude cylinder",
                parameters={"distance": 20.0}
            )
        ]
        
        # Generate code
        code = agent.generate_code(state)
        
        # Verify code contains expected elements
        assert "from build123d import" in code
        assert "with BuildPart()" in code
        assert "Circle" in code or "circle" in code.lower()
        assert "extrude" in code.lower()

    def test_validator_catches_forbidden_imports(self):
        """Test that validator catches forbidden imports."""
        from backend.validators.ast_validator import ASTValidator
        
        validator = ASTValidator()
        
        # Code with forbidden import
        bad_code = """
import os
import build123d
os.system("rm -rf /")
"""
        
        errors = validator.validate(bad_code)
        
        # Should have errors about forbidden imports
        assert any("os" in e for e in errors)

    def test_validator_allows_good_code(self):
        """Test that valid build123d code passes validation."""
        from backend.validators.ast_validator import ASTValidator
        
        validator = ASTValidator()
        
        # Valid code
        good_code = """
from build123d import *
import math

with BuildPart() as model:
    with BuildSketch() as sketch:
        Circle(radius=10)
    extrude(amount=20)

part = model.part
"""
        
        errors = validator.validate(good_code)
        
        # Should have no errors
        assert len(errors) == 0


class TestEndToEnd:
    """End-to-end tests of the complete system."""

    @pytest.mark.skipif(not HAS_OPEN3D, reason="Open3D not installed")
    @pytest.mark.skipif(not HAS_TRIMESH, reason="Trimesh not installed")
    def test_full_pipeline_with_cylinder(self, test_cylinder_stl):
        """Test the complete pipeline on a simple cylinder."""
        from backend.main import create_default_agents
        from backend.core.state import CADState
        from backend.agents.sensor_agent import create_sensor_agent_factory
        from backend.agents.coordinator_agent import create_coordinator_agent
        from backend.agents.coder_agent import create_coder_agent
        
        # Create agents
        agents = {
            'sensor': create_sensor_agent_factory(None),
            'coordinator': create_coordinator_agent(None),
            'coder': create_coder_agent(None),
            'validator': lambda code: [],  # Always pass
            'executor': lambda state: {"success": True, "output_path": None},
            'vibeguard': lambda state: {"chamfer_distance": 0.05, "errors": [], "passed": True}
        }
        
        # Create initial state
        state = CADState(stl_path=test_cylinder_stl, max_iterations=1)
        
        # Run sensor analysis for Z axis
        sensor_z = agents['sensor'](Axis.Z)
        report = sensor_z.analyze(test_cylinder_stl)
        
        # Verify we got meaningful results
        assert report.axis.value == "Z"
        assert len(report.slice_positions) > 0
        
        # Store in state
        state.sensor_reports[Axis.Z] = report
        
        # Run coordinator
        coord_result = agents['coordinator'](state)
        
        # Should have identified features
        assert len(coord_result.get("features", [])) > 0
        
        # Update state with coordinator results
        state.identified_features = coord_result.get("features", [])
        state.construction_plan = coord_result.get("plan", [])
        
        # Generate code
        if state.construction_plan:
            code = agents['coder'](state)
            assert len(code) > 0
            assert "build123d" in code


# Mark slow tests
pytestmark = [
    pytest.mark.integration,
]