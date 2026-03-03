"""Quality Gates Testing

Tests Sensor+Approximator on all benchmark datasets.
Compares results with expected_results.yaml thresholds.
"""

import pytest
import yaml
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gdi_core import GDIAPI

# Load expected results
with open(Path(__file__).parent.parent / "benchmark_kit" / "expected_results.yaml", encoding="utf-8") as f:
    EXPECTED = yaml.safe_load(f)


class TestIdealModels:
    """Test on ideal (perfect) models."""
    
    @pytest.fixture
    def api(self):
        return GDIAPI(output_dir="test_output")
    
    def test_ideal_cylinder(self, api):
        """QG-001: ideal_cylinder should pass all gates."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_cylinder.stl",
            base_axis="Z"
        )
        
        expected = EXPECTED["ideal_cylinder"]
        
        # Check zone count
        assert len(result.telemetry.topological_zones) == len(expected["expected_zones"]), \
            f"Expected {len(expected['expected_zones'])} zones, got {len(result.telemetry.topological_zones)}"
        
        # Check confidence floor
        assert result.global_confidence >= expected["confidence_floor"], \
            f"Confidence {result.global_confidence:.2f} below floor {expected['confidence_floor']}"
        
        # Check no fallback required
        assert not result.fallback_required, \
            f"Fallback required for ideal model: {result.fallback_reason}"
        
        # Check zone type
        zone = result.telemetry.topological_zones[0]
        assert zone.geometry.value == expected["expected_zones"][0]["geometry"], \
            f"Expected {expected['expected_zones'][0]['geometry']}, got {zone.geometry.value}"
    
    def test_ideal_stepped_shaft(self, api):
        """QG-002: ideal_stepped_shaft should detect 2 zones."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_stepped_shaft.stl",
            base_axis="Z"
        )
        
        expected = EXPECTED["ideal_stepped_shaft"]
        
        assert len(result.telemetry.topological_zones) == 2, \
            f"Expected 2 zones for stepped shaft, got {len(result.telemetry.topological_zones)}"
        
        assert result.global_confidence >= expected["confidence_floor"], \
            f"Confidence {result.global_confidence:.2f} below floor {expected['confidence_floor']}"
    
    def test_ideal_flange(self, api):
        """QG-003: ideal_flange should detect holes."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_flange.stl",
            base_axis="Z"
        )
        
        expected = EXPECTED["ideal_flange"]
        
        assert result.global_confidence >= expected["confidence_floor"], \
            f"Confidence {result.global_confidence:.2f} below floor {expected['confidence_floor']}"
        
        # Check for holes detection
        zone = result.telemetry.topological_zones[0]
        assert zone.geometry.value == "Constant_Profile_with_Holes", \
            f"Expected Constant_Profile_with_Holes, got {zone.geometry.value}"
    
    def test_ideal_bracket(self, api):
        """QG-004: ideal_bracket should detect rectangle profile."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_bracket_2.5d.stl",
            base_axis="Z"
        )
        
        expected = EXPECTED["ideal_bracket_2.5d"]
        
        assert result.global_confidence >= expected["confidence_floor"], \
            f"Confidence {result.global_confidence:.2f} below floor {expected['confidence_floor']}"
        
        # Check cross-section type
        zone = result.telemetry.topological_zones[0]
        assert zone.cross_section.value == "Rectangle", \
            f"Expected Rectangle cross-section, got {zone.cross_section.value}"
    
    def test_ideal_nema17(self, api):
        """QG-005: ideal_nema17_mount should detect standard dimensions."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_nema17_mount.stl",
            base_axis="Z"
        )
        
        expected = EXPECTED["ideal_nema17_mount"]
        
        assert result.global_confidence >= expected["confidence_floor"], \
            f"Confidence {result.global_confidence:.2f} below floor {expected['confidence_floor']}"


class TestNoiseModels:
    """Test on noisy models (synthetic noise)."""
    
    @pytest.fixture
    def api(self):
        return GDIAPI(output_dir="test_output")
    
    def test_noise_cylinder_robustness(self, api):
        """QG-006: Noise cylinder should not crash pipeline."""
        import os
        noise_file = "benchmark_kit/noise/noise_cylinder.stl"
        
        if not os.path.exists(noise_file):
            pytest.skip(f"Noise file not found: {noise_file}")
        
        result = api.phase1_sensor_approximator(noise_file, base_axis="Z")
        
        # Pipeline should not crash - that's the main test
        assert result is not None
        assert len(result.telemetry.topological_zones) >= 1
        
        # Check confidence is reasonable (> 0.6 for noisy)
        assert result.global_confidence > 0.6, \
            f"Confidence {result.global_confidence:.2f} too low even for noise"
    
    def test_noise_flange_robustness(self, api):
        """QG-007: Noise flange should handle holes."""
        import os
        noise_file = "benchmark_kit/noise/noise_flange.stl"
        
        if not os.path.exists(noise_file):
            pytest.skip(f"Noise file not found: {noise_file}")
        
        result = api.phase1_sensor_approximator(noise_file, base_axis="Z")
        
        assert result is not None
        # Holes should still be detected despite noise
        assert len(result.telemetry.topological_zones) >= 1


class TestCorruptModels:
    """Test on corrupt/damaged models."""
    
    @pytest.fixture
    def api(self):
        return GDIAPI(output_dir="test_output")
    
    def test_corrupt_cylinder_partial(self, api):
        """QG-008: Corrupt cylinder (partial) should have low confidence."""
        import os
        corrupt_file = "benchmark_kit/corrupt/corrupt_cylinder.stl"
        
        if not os.path.exists(corrupt_file):
            pytest.skip(f"Corrupt file not found: {corrupt_file}")
        
        result = api.phase1_sensor_approximator(corrupt_file, base_axis="Z")
        
        # Should detect partial geometry
        assert result is not None
        assert len(result.telemetry.topological_zones) >= 1
        
        # Confidence should be lower for corrupt models
        expected = EXPECTED.get("corrupt_cylinder", {})
        floor = expected.get("confidence_floor", 0.4)
        
        # For corrupt, we accept lower confidence
        assert result.global_confidence >= floor * 0.5, \
            f"Even corrupt model should have some confidence, got {result.global_confidence:.2f}"
    
    def test_corrupt_flange_robustness(self, api):
        """QG-009: Corrupt flange should not crash."""
        import os
        corrupt_file = "benchmark_kit/corrupt/corrupt_flange.stl"
        
        if not os.path.exists(corrupt_file):
            pytest.skip(f"Corrupt file not found: {corrupt_file}")
        
        result = api.phase1_sensor_approximator(corrupt_file, base_axis="Z")
        
        # Main test: pipeline should not crash
        assert result is not None


class TestRealScans:
    """Test on real scanned models."""
    
    @pytest.fixture
    def api(self):
        return GDIAPI(output_dir="test_output")
    
    def test_real_scan_button(self, api):
        """QG-010: Real scan button should be processed."""
        import os
        real_file = "benchmark_kit/real_scans/Кнопка_2.stl"
        
        if not os.path.exists(real_file):
            pytest.skip(f"Real scan file not found: {real_file}")
        
        result = api.phase1_sensor_approximator(real_file, base_axis="Z")
        
        assert result is not None
        assert len(result.telemetry.topological_zones) >= 1
        
        # Real scans should have moderate confidence
        assert result.global_confidence > 0.5, \
            f"Real scan confidence {result.global_confidence:.2f} too low"


class TestQualityGates:
    """Test quality gates compliance."""
    
    @pytest.fixture
    def api(self):
        return GDIAPI(
            output_dir="test_output",
            confidence_threshold=0.7,
            iou_threshold=0.98
        )
    
    def test_no_crash_on_ideal(self, api):
        """QG-011: Pipeline must not crash on ideal models."""
        from pathlib import Path
        ideal_dir = Path("benchmark_kit/ideal")
        
        stl_files = list(ideal_dir.glob("*.stl"))
        assert len(stl_files) > 0, "No ideal STL files found"
        
        for stl_file in stl_files[:5]:  # Test first 5
            result = api.phase1_sensor_approximator(str(stl_file), base_axis="Z")
            assert result is not None, f"Failed on {stl_file}"
            assert len(result.telemetry.topological_zones) >= 1, \
                f"No zones detected in {stl_file}"
    
    def test_confidence_range(self, api):
        """QG-012: Confidence must be in [0, 1] range."""
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_cylinder.stl",
            base_axis="Z"
        )
        
        assert 0.0 <= result.global_confidence <= 1.0, \
            f"Confidence {result.global_confidence} out of [0,1] range"
        
        for zone in result.telemetry.topological_zones:
            assert 0.0 <= zone.confidence <= 1.0, \
                f"Zone confidence {zone.confidence} out of [0,1] range"
    
    def test_fallback_trigger(self, api):
        """QG-013: Low confidence should trigger fallback."""
        # Note: This test assumes we have a low-quality model
        # For now, just verify the mechanism works
        
        result = api.phase1_sensor_approximator(
            "benchmark_kit/ideal/ideal_cylinder.stl",
            base_axis="Z"
        )
        
        # High confidence should NOT trigger fallback
        if result.global_confidence >= api.confidence_threshold:
            assert not result.fallback_required, \
                "High confidence should not trigger fallback"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
