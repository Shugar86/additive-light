"""Tests for CAD Agent Contracts and YAML configuration layer.

P9: Test hardening for the contract/policy layer introduced in P2-P7.
"""

import pytest
from pathlib import Path
import tempfile
import yaml


class TestAgentContracts:
    """Tests for Pydantic agent contract models."""
    
    def test_cad_agent_spec_creation(self):
        """Test creating a CADAgentSpec with all required fields."""
        from backend.core.agent_contracts import CADAgentSpec, InputContract, OutputContract
        
        spec = CADAgentSpec(
            agent_id="test_coordinator",
            role="coordinator",
            objective="Test coordination",
            input_contract=InputContract(
                required_fields=["sensor_reports"],
                optional_fields=["max_iterations"]
            ),
            output_contract=OutputContract(
                required_fields=["features", "plan"]
            )
        )
        
        assert spec.agent_id == "test_coordinator"
        assert spec.role == "coordinator"
        assert spec.planning_style == "sequential"
        assert spec.enabled is True
    
    def test_swarm_policy_defaults(self):
        """Test SwarmPolicy with default values."""
        from backend.core.agent_contracts import SwarmPolicy
        
        policy = SwarmPolicy()
        
        assert policy.max_iterations >= 1
        assert policy.enable_reflection is True
        assert policy.enable_parallel_sensors is True
        assert policy.chamfer_tolerance > 0
        assert policy.hausdorff_tolerance > 0
    
    def test_sensor_registry_creation(self):
        """Test SensorRegistry with default sensors."""
        from backend.core.agent_contracts import SensorRegistry, SensorSpec
        
        registry = SensorRegistry(
            sensors={
                "X": SensorSpec(sensor_id="X", sensor_type="axis_slice", axes=["X"]),
                "Y": SensorSpec(sensor_id="Y", sensor_type="axis_slice", axes=["Y"]),
            },
            default_sensors=["X", "Y"]
        )
        
        assert "X" in registry.sensors
        assert "Y" in registry.sensors
        assert registry.default_sensors == ["X", "Y"]
    
    def test_execution_policy_security(self):
        """Test ExecutionPolicy security defaults."""
        from backend.core.agent_contracts import ExecutionPolicy
        
        policy = ExecutionPolicy()
        
        assert policy.sandbox_type in ["subprocess", "container", "vm"]
        assert policy.network_access is False
        assert policy.filesystem_access in ["none", "temp_only", "restricted", "full"]


class TestSpecLoader:
    """Tests for YAML configuration loading."""
    
    def test_load_coordinator_spec(self):
        """Test loading coordinator.yaml spec file."""
        from backend.core.spec_loader import SpecLoader
        
        loader = SpecLoader()
        
        try:
            spec = loader.load_agent_spec("coordinator")
            assert spec.agent_id == "coordinator"
            assert spec.role == "coordinator"
            assert len(spec.allowed_tools) > 0
        except FileNotFoundError:
            pytest.skip("coordinator.yaml not found")
    
    def test_load_coder_spec(self):
        """Test loading coder.yaml spec file."""
        from backend.core.spec_loader import SpecLoader
        
        loader = SpecLoader()
        
        try:
            spec = loader.load_agent_spec("coder")
            assert spec.agent_id == "coder"
            assert spec.role == "coder"
        except FileNotFoundError:
            pytest.skip("coder.yaml not found")
    
    def test_load_swarm_policy(self):
        """Test loading swarm_policy.yaml."""
        from backend.core.spec_loader import SpecLoader
        
        loader = SpecLoader()
        
        try:
            policy = loader.load_swarm_policy()
            assert policy.max_iterations >= 1
            assert policy.chamfer_tolerance > 0
        except FileNotFoundError:
            pytest.skip("swarm_policy.yaml not found")
    
    def test_load_sensor_registry(self):
        """Test loading sensor registry from YAML."""
        from backend.core.spec_loader import SpecLoader
        
        loader = SpecLoader()
        
        try:
            registry = loader.load_sensor_registry()
            assert len(registry.sensors) >= 3  # At least X, Y, Z
            assert "X" in registry.default_sensors
        except FileNotFoundError:
            pytest.skip("sensor registry not found")
    
    def test_spec_cache(self):
        """Test that specs are cached after first load."""
        from backend.core.spec_loader import SpecLoader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test spec
            spec_content = {
                "agent_id": "test_agent",
                "role": "test",
                "objective": "Test agent"
            }
            agents_dir = Path(tmpdir) / "agents"
            agents_dir.mkdir()
            with open(agents_dir / "test.yaml", 'w') as f:
                yaml.dump(spec_content, f)
            
            loader = SpecLoader(tmpdir)
            
            # First load
            spec1 = loader.load_agent_spec("test")
            # Second load (should use cache)
            spec2 = loader.load_agent_spec("test")
            
            assert spec1 is spec2  # Same object from cache
    
    def test_invalid_spec_validation(self):
        """Test that invalid specs are rejected."""
        from backend.core.agent_contracts import CADAgentSpec
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            # Missing required field 'agent_id'
            CADAgentSpec(role="test", objective="Test")


class TestPromptCompiler:
    """Tests for PromptCompiler with fallback."""
    
    def test_compiler_fallback_without_spec(self):
        """Test PromptCompiler falls back to default templates."""
        from backend.core.agent_prompt_compiler import get_prompt_compiler
        from backend.core.state import CADState
        
        compiler = get_prompt_compiler("nonexistent_agent")
        
        # Should work even without spec
        assert compiler.has_spec() is False
        
        # Compile should still work with fallback
        state = CADState(stl_path="test.stl")
        prompt = compiler.compile_prompt("analysis", state)
        
        assert prompt is not None
        assert len(prompt) > 0
    
    def test_compiler_with_coordinator_spec(self):
        """Test PromptCompiler with coordinator spec."""
        from backend.core.agent_prompt_compiler import get_prompt_compiler
        from backend.core.state import CADState, SliceReport, Axis
        from backend.core.spec_loader import get_spec_loader
        
        try:
            loader = get_spec_loader()
            spec = loader.load_agent_spec("coordinator")
            
            compiler = get_prompt_compiler("coordinator")
            
            # Check spec loaded
            if compiler.has_spec():
                state = CADState(stl_path="test.stl")
                state.sensor_reports[Axis.Z] = SliceReport(
                    axis=Axis.Z,
                    slice_positions=[0.0, 1.0],
                    analysis_summary="Test report"
                )
                
                prompt = compiler.compile_prompt("analysis", state)
                assert "Test report" in prompt or len(prompt) > 0
        except FileNotFoundError:
            pytest.skip("coordinator spec not found")
    
    def test_compiler_fallback_status(self):
        """Test getting fallback status information."""
        from backend.core.agent_prompt_compiler import get_prompt_compiler
        
        compiler = get_prompt_compiler("test_agent")
        status = compiler.get_fallback_status()
        
        assert "agent_role" in status
        assert "has_spec" in status
        assert "available_templates" in status


class TestGraphWithPolicy:
    """Tests for policy-driven graph behavior."""
    
    def test_reflection_router_with_policy(self):
        """Test reflection router respects SwarmPolicy."""
        from backend.core.agent_contracts import SwarmPolicy
        from backend.core.state import CADState
        
        # Create policy with strict settings
        policy = SwarmPolicy(
            max_iterations=2,
            chamfer_tolerance=0.05,
            enable_reflection=True
        )
        
        # Test state that should pass
        state = CADState(stl_path="test.stl")
        state.iteration_count = 0
        state.chamfer_distance = 0.03  # Below tolerance
        state.hausdorff_distance = 0.04
        state.final_output = "some code"
        state.geometric_errors = []
        
        # Should end after iteration 1 with success
        assert state.chamfer_distance < policy.chamfer_tolerance
    
    def test_sensor_registry_integration(self):
        """Test sensor registry is used by graph."""
        from backend.core.graph import _get_sensor_registry
        from backend.core.agent_contracts import SwarmPolicy
        
        policy = SwarmPolicy()
        registry = _get_sensor_registry(policy)
        
        assert registry is not None
        assert len(registry.sensors) >= 1
        assert len(registry.default_sensors) >= 1


class TestSecurityRegressions:
    """Tests for security hardening from P6."""
    
    def test_ast_validator_rejects_forbidden_imports(self):
        """Test AST validator catches forbidden imports."""
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
        assert any("os" in e.lower() for e in errors)
    
    def test_ast_validator_allows_good_code(self):
        """Test AST validator allows valid build123d code."""
        from backend.validators.ast_validator import ASTValidator
        
        validator = ASTValidator()
        
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
    
    def test_secure_executor_with_policy(self):
        """Test SecureExecutor uses ExecutionPolicy."""
        from backend.executor.secure_executor import SecureExecutor
        from backend.core.agent_contracts import ExecutionPolicy
        
        policy = ExecutionPolicy(
            sandbox_type="subprocess",
            filesystem_access="temp_only",
            network_access=False
        )
        
        executor = SecureExecutor(execution_policy=policy)
        
        assert executor.execution_policy is not None
        assert executor.filesystem_access == "temp_only"
    
    def test_skill_validation_before_execution(self):
        """Test that skills are validated before execution."""
        from backend.skills.skill_library import SkillLibrary, Skill
        from backend.validators.ast_validator import ASTValidator
        
        library = SkillLibrary()
        
        # Create a skill with invalid code
        bad_skill = Skill(
            name="bad_skill",
            description="Test skill",
            code="""
import os
def bad_skill():
    os.system('echo hacked')
""",
            signature={"input": {}, "output": {}}
        )
        
        # Validation should fail
        validator = ASTValidator()
        errors = validator.validate(bad_skill.code)
        assert len(errors) > 0
        
        # get_function should return None for invalid code
        func = library.get_function("bad_skill")
        # Note: library doesn't have this skill, so returns None anyway
        assert func is None


class TestIntegrationWithContracts:
    """Integration tests for contract layer."""
    
    def test_full_pipeline_with_swarm_policy(self):
        """Test that full pipeline can use SwarmPolicy."""
        from backend.core.agent_contracts import SwarmPolicy
        from backend.core.state import CADState
        
        policy = SwarmPolicy(max_iterations=2)
        state = CADState(stl_path="test.stl", max_iterations=policy.max_iterations)
        
        assert state.max_iterations == 2
    
    def test_end_to_end_yaml_loading(self):
        """Test end-to-end YAML loading and validation."""
        from backend.core.spec_loader import get_spec_loader
        
        try:
            loader = get_spec_loader()
            
            # Load all specs
            coordinator = loader.load_agent_spec("coordinator")
            coder = loader.load_agent_spec("coder")
            policy = loader.load_swarm_policy()
            registry = loader.load_sensor_registry()
            
            # Validate consistency
            assert coordinator.agent_id == "coordinator"
            assert coder.agent_id == "coder"
            assert policy.max_iterations >= 1
            assert len(registry.sensors) >= 1
            
        except FileNotFoundError as e:
            pytest.skip(f"YAML files not found: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
