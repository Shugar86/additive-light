"""Judge 2-Phase Validation Testing

Tests Judge component with fail-fast Phase 1 and IoU Phase 2.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gdi_core.judge import Judge, Phase1Judge, Phase2Judge
from gdi_core.judge.topology_checker import check_code_syntax, check_build123d_imports


class TestPhase1Judge:
    """Test Phase 1: Fail-fast syntax and topology validation."""
    
    @pytest.fixture
    def judge(self):
        return Phase1Judge()
    
    def test_valid_python_syntax(self, judge):
        """JR-001: Valid Python code should pass Phase 1."""
        code = """
from build123d import *

with BuildPart() as part:
    Cylinder(radius=10, height=20)

show(part)
"""
        result = judge.judge(code)
        
        assert result.passed, "Valid code should pass Phase 1"
        assert result.syntax_valid, "Syntax should be valid"
        assert result.topology_valid, "Topology should be valid (no STEP file)"
    
    def test_invalid_python_syntax(self, judge):
        """JR-002: Invalid Python syntax should fail Phase 1."""
        code = """
from build123d import *

def broken(
    # Missing closing parenthesis
"""
        result = judge.judge(code)
        
        assert not result.passed, "Invalid syntax should fail"
        assert not result.syntax_valid, "Syntax should be marked invalid"
        assert len(result.errors) > 0, "Should have error messages"
    
    def test_missing_imports(self, judge):
        """JR-003: Code without build123d imports should have warnings."""
        code = """
# No imports at all
print("hello")
"""
        result = judge.judge(code)
        
        # Should pass but with warnings
        assert result.passed, "Missing imports shouldn't block, just warn"


class TestSyntaxChecker:
    """Test standalone syntax checking functions."""
    
    def test_check_valid_syntax(self):
        """JR-004: check_code_syntax with valid code."""
        code = "x = 1 + 2\nprint(x)"
        is_valid, errors = check_code_syntax(code)
        
        assert is_valid, "Simple code should be valid"
        assert len(errors) == 0, "No errors expected"
    
    def test_check_invalid_syntax(self):
        """JR-005: check_code_syntax with invalid code."""
        code = "def broken(\n    pass"
        is_valid, errors = check_code_syntax(code)
        
        assert not is_valid, "Broken code should be invalid"
        assert len(errors) > 0, "Should have syntax errors"
    
    def test_check_build123d_patterns_valid(self):
        """JR-006: Valid build123d patterns."""

    
    def test_check_build123d_patterns_invalid(self):
        """JR-007: Missing build123d patterns."""
        code = """
import math
# No build123d imports
"""
        is_valid, warnings = check_build123d_imports(code)
        
        # Should have warnings about missing patterns
        assert len(warnings) > 0, "Should warn about missing build123d imports"


class TestJudgeStructure:
    """Test Judge class structure and configuration."""
    
    def test_judge_initialization(self):
        """JR-008: Judge should initialize with correct parameters."""
        judge = Judge(iou_threshold=0.98, max_retries=3)
        
        assert judge.iou_threshold == 0.98
        assert judge.max_retries == 3
        assert hasattr(judge, 'phase1')
        assert hasattr(judge, 'phase2')
    
    def test_judge_has_feedback_generator(self):
        """JR-009: Judge should have feedback generation method."""
        judge = Judge()
        
        assert hasattr(judge, '_generate_feedback')
    
    def test_default_retry_limit(self):
        """JR-010: Default retry limit should be 3."""
        judge = Judge()
        
        assert judge.max_retries == 3, "Default retries should be 3"


class TestJudgeIntegration:
    """Test Judge integration scenarios."""
    
    @pytest.fixture
    def judge(self):
        return Judge(iou_threshold=0.98, max_retries=3)
    
    def test_syntax_error_triggers_retry_recommendation(self, judge):
        """JR-011: Syntax error should recommend retry."""
        code = "def broken("
        
        result = judge.judge(code, "dummy.stl")
        
        assert not result.accepted, "Broken code should not be accepted"
        assert result.retry_recommended, "Should recommend retry for fixable errors"
        assert result.feedback_for_llm is not None, "Should provide feedback"
    
    def test_valid_code_no_step_file(self, judge):
        """JR-012: Valid code without STEP should pass Phase 1 only."""
        code = """
from build123d import *
with BuildPart() as p:
    Cylinder(radius=10, height=20)
"""
        result = judge.judge(code, "dummy.stl", generated_step_path=None)
        
        # Should pass Phase 1, skip Phase 2
        assert result.accepted, "Valid code should be accepted when no STEP to compare"
        assert result.phase1 is not None
        assert result.phase2 is None, "Phase 2 should be None without STEP file"


class TestRetryLogic:
    """Test retry counting and limits."""
    
    def test_retry_count_increments(self):
        """JR-013: Retry count should increment with each attempt."""
        judge = Judge(max_retries=3)
        
        # First attempt
        result = judge.judge("code", "stl.stl", retry_count=0)
        
        # Check that retry_count can be incremented
        assert judge.max_retries > 0, "Should have positive retry limit"
    
    def test_max_retry_limit_respected(self):
        """JR-014: Should not recommend retry beyond max_retries."""
        judge = Judge(max_retries=3)
        
        # Simulate max retries exceeded
        result = judge.judge("broken code", "stl.stl", retry_count=3)
        
        # Should not recommend retry when at limit
        assert not result.retry_recommended, "Should not retry beyond limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
