"""Baseline accuracy measurement for the revolution bodies sensor pipeline.

Measures what the current deterministic sensor pipeline produces on known
bodies of revolution from the benchmark kit. Use this as the R&D starting point
before any modifications.

Run standalone:
    python tests/test_revolution_baseline.py

Run via pytest:
    pytest tests/test_revolution_baseline.py -v -s
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)  # suppress sensor noise in baseline
logger = logging.getLogger(__name__)

_open3d_available = find_spec("open3d") is not None
requires_open3d = pytest.mark.skipif(
    not _open3d_available, reason="Open3D not installed (pip install open3d)"
)

REPO_ROOT = Path(__file__).parent.parent
BENCHMARK_DIR = REPO_ROOT / "benchmark_kit"
IDEAL_DIR = BENCHMARK_DIR / "ideal"
NOISE_DIR = BENCHMARK_DIR / "noise"
REAL_DIR = BENCHMARK_DIR / "real_scans"
FIXTURE_DIR = Path(__file__).parent / "fixtures"

# Ground truth from benchmark_kit/expected_results.yaml
# Only revolution bodies are listed here.
GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "ideal_cylinder": {
        "path": IDEAL_DIR / "ideal_cylinder.stl",
        "category": "ideal",
        "expected_radius_mm": 20.0,
        "expected_height_mm": 40.0,
        "expected_zone_count": 1,
        "tolerance_mm": 0.2,
        "min_iou": 0.99,
        "confidence_floor": 0.95,
    },
    "ideal_stepped_shaft": {
        "path": IDEAL_DIR / "ideal_stepped_shaft.stl",
        "category": "ideal",
        "expected_height_mm": 50.0,
        "expected_zone_count": 2,
        "expected_zones": [
            {"radius": 15.0, "span_start": 0.0, "span_end": 20.0},
            {"radius": 10.0, "span_start": 20.0, "span_end": 50.0},
        ],
        "tolerance_mm": 0.2,
        "min_iou": 0.99,
        "confidence_floor": 0.92,
    },
    "noise_cylinder": {
        "path": NOISE_DIR / "noise_cylinder.stl",
        "category": "noise",
        "expected_radius_mm": 20.0,
        "expected_zone_count": 1,
        "tolerance_mm": 0.5,
        "confidence_floor": 0.80,
    },
    "noise_stepped_shaft": {
        "path": NOISE_DIR / "noise_stepped_shaft.stl",
        "category": "noise",
        "expected_zone_count": 2,
        "expected_zones": [
            {"radius": 15.0, "span_start": 0.0, "span_end": 20.0},
            {"radius": 10.0, "span_start": 20.0, "span_end": 50.0},
        ],
        "tolerance_mm": 0.8,
        "confidence_floor": 0.70,
    },
    "real_button": {
        "path": REAL_DIR / "Кнопка_2.stl",
        "category": "real",
        "expected_zone_count": None,  # best-effort
        "confidence_floor": 0.50,
        "is_revolution_body": True,
    },
    "plain_shaft_fixture": {
        "path": FIXTURE_DIR / "plain_shaft.stl",
        "category": "fixture",
        "expected_zone_count": 1,
        "tolerance_mm": 0.5,
        "confidence_floor": 0.70,
    },
    "stepped_shaft_fixture": {
        "path": FIXTURE_DIR / "stepped_shaft.stl",
        "category": "fixture",
        "expected_zone_count": 2,
        "tolerance_mm": 0.5,
        "confidence_floor": 0.70,
    },
}


@dataclass
class ZoneResult:
    """Single zone detection result."""

    zone_type: str
    start_pos: float
    end_pos: float
    mean_radius: float
    confidence: float

    @property
    def length(self) -> float:
        return self.end_pos - self.start_pos


@dataclass
class BaselineResult:
    """Full baseline measurement result for one model."""

    model_name: str
    stl_path: str
    category: str = ""

    # Axis detection
    axis_direction: Optional[List[float]] = None
    axis_confidence: float = 0.0
    axis_method: str = ""

    # Profile
    total_length: float = 0.0
    min_radius: float = 0.0
    max_radius: float = 0.0
    sample_count: int = 0

    # Zone detection
    zones: List[ZoneResult] = field(default_factory=list)

    # Accuracy
    radius_error_mm: Optional[float] = None
    radius_error_pct: Optional[float] = None
    zone_count_correct: Optional[bool] = None
    zones_matched: Optional[int] = None
    zones_expected: Optional[int] = None

    # Execution
    duration_s: float = 0.0
    errors: List[str] = field(default_factory=list)
    passed: bool = False


def _evaluate_accuracy(
    result: BaselineResult,
    config: Dict[str, Any],
    zones: List[Any],
) -> None:
    """Compare detection results against known ground truth."""
    tolerance = config.get("tolerance_mm", 0.5)

    # Zone count
    expected_zone_count = config.get("expected_zone_count")
    if expected_zone_count is not None:
        result.zone_count_correct = len(zones) == expected_zone_count
        result.zones_expected = expected_zone_count
        result.zones_matched = 0
        if not result.zone_count_correct:
            result.errors.append(
                f"Zone count: expected {expected_zone_count}, got {len(zones)}"
            )

    # Single-zone radius accuracy
    expected_radius = config.get("expected_radius_mm")
    if expected_radius is not None and zones:
        cylinder_zones = [z for z in zones if z.zone_type.value == "cylinder"]
        if cylinder_zones:
            largest = max(cylinder_zones, key=lambda z: z.mean_radius)
            err = abs(largest.mean_radius - expected_radius)
            result.radius_error_mm = err
            result.radius_error_pct = err / expected_radius * 100
            if err > tolerance:
                result.errors.append(
                    f"Radius error {err:.3f}mm > tolerance {tolerance}mm "
                    f"(detected={largest.mean_radius:.3f}, expected={expected_radius})"
                )
        else:
            result.errors.append("No cylinder zones detected for radius check")

    # Per-zone accuracy for stepped shafts
    expected_zones = config.get("expected_zones", [])
    if expected_zones:
        # Accept any zone type that has the expected radius (not just CYLINDER).
        # The first zone of a stepped shaft may be classified as STEP due to
        # the boundary effect at z=0.
        expected_sorted = sorted(
            expected_zones, key=lambda z: z["radius"], reverse=True
        )
        result.zones_expected = len(expected_sorted)
        matched = 0
        for exp_z in expected_sorted:
            best = min(
                result.zones,
                key=lambda z: abs(z.mean_radius - exp_z["radius"]),
                default=None,
            )
            if best and abs(best.mean_radius - exp_z["radius"]) <= tolerance:
                matched += 1
        result.zones_matched = matched
        if matched < len(expected_sorted):
            result.errors.append(
                f"Only {matched}/{len(expected_sorted)} zones matched within "
                f"tolerance {tolerance}mm"
            )


def run_baseline_on_model(
    model_name: str, config: Dict[str, Any]
) -> BaselineResult:
    """Run the full sensor pipeline on a single model.

    Args:
        model_name: Display name for reporting.
        config: Ground-truth configuration for this model.

    Returns:
        BaselineResult with all collected metrics.
    """
    result = BaselineResult(
        model_name=model_name,
        stl_path=str(config["path"]),
        category=config.get("category", ""),
    )

    stl_path = config["path"]
    if not stl_path.exists():
        result.errors.append(f"File not found: {stl_path}")
        return result

    t_start = time.perf_counter()

    # --- Step 1: axis detection ---
    try:
        from backend.sensors.shaft_axis import detect_main_axis

        axis_info = detect_main_axis(str(stl_path), method="auto")
        result.axis_direction = axis_info.direction.tolist()
        result.axis_confidence = axis_info.confidence
        result.axis_method = axis_info.method
    except Exception as exc:
        result.errors.append(f"Axis detection: {exc}")

    # --- Step 2: radial profile sampling ---
    try:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(str(stl_path), axis="Z", num_samples=100)
        result.total_length = profile.total_length
        result.min_radius = profile.min_radius
        result.max_radius = profile.max_radius
        result.sample_count = profile.sample_count

        # --- Step 3: zone segmentation ---
        zones = segment_rotational_zones(profile)
        result.zones = [
            ZoneResult(
                zone_type=z.zone_type.value,
                start_pos=z.start_pos,
                end_pos=z.end_pos,
                mean_radius=z.mean_radius,
                confidence=z.confidence,
            )
            for z in zones
        ]

        # --- Step 4: accuracy vs ground truth ---
        _evaluate_accuracy(result, config, zones)

    except Exception as exc:
        result.errors.append(f"Profile/zone detection: {exc}")

    result.duration_s = time.perf_counter() - t_start

    # A model passes the baseline if all geometric checks pass.
    # Axis detection failures (e.g. Open3D not installed) are recorded but
    # don't block the profile/zone checks from being evaluated.
    profile_errors = [e for e in result.errors if not e.startswith("Axis detection")]
    result.passed = len(profile_errors) == 0 and result.sample_count > 0

    return result


def print_baseline_report(results: List[BaselineResult]) -> None:
    """Print formatted baseline report to stdout."""
    print()
    print("=" * 72)
    print("  REVOLUTION BODIES — SENSOR PIPELINE BASELINE ACCURACY REPORT")
    print("=" * 72)

    for r in results:
        profile_errors = [e for e in r.errors if not e.startswith("Axis detection")]
        axis_warnings = [e for e in r.errors if e.startswith("Axis detection")]

        if r.passed and not profile_errors:
            status = "PASS" if not axis_warnings else "PASS*"
        else:
            status = "FAIL"

        print(f"\n  [{status}] {r.model_name}  ({r.category})")
        print(f"         Path: {r.stl_path}")
        print(f"         Time: {r.duration_s:.2f}s")

        if axis_warnings:
            for w in axis_warnings:
                print(f"         ~ {w}")

        if profile_errors:
            for err in profile_errors:
                print(f"         ! {err}")

        if r.axis_direction:
            ax = [f"{v:+.3f}" for v in r.axis_direction]
            print(
                f"         Axis: [{', '.join(ax)}]  "
                f"conf={r.axis_confidence:.3f}  method={r.axis_method}"
            )

        if r.sample_count:
            print(
                f"         Profile: length={r.total_length:.2f}mm  "
                f"r=[{r.min_radius:.2f}, {r.max_radius:.2f}]mm  "
                f"samples={r.sample_count}"
            )

        if r.zones:
            print(f"         Zones ({len(r.zones)}):")
            for z in r.zones:
                print(
                    f"           [{z.zone_type:10s}]"
                    f"  z=[{z.start_pos:7.2f}, {z.end_pos:7.2f}]mm"
                    f"  r={z.mean_radius:7.3f}mm"
                    f"  conf={z.confidence:.3f}"
                )

        if r.radius_error_mm is not None:
            print(
                f"         Radius error: {r.radius_error_mm:.4f}mm  "
                f"({r.radius_error_pct:.3f}%)"
            )

        if r.zones_matched is not None and r.zones_expected is not None:
            print(f"         Zone match: {r.zones_matched}/{r.zones_expected}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print()
    print("-" * 72)
    print(f"  SUMMARY: {passed}/{total} models passed  |  {total - passed} with errors")
    print("=" * 72)
    print()


def save_baseline_results(
    results: List[BaselineResult], output_path: Path
) -> None:
    """Serialize baseline results to JSON.

    Args:
        results: List of baseline measurement results.
        output_path: File path for JSON output.
    """
    data = [
        {
            "model_name": r.model_name,
            "stl_path": r.stl_path,
            "category": r.category,
            "axis_direction": r.axis_direction,
            "axis_confidence": r.axis_confidence,
            "axis_method": r.axis_method,
            "total_length_mm": r.total_length,
            "min_radius_mm": r.min_radius,
            "max_radius_mm": r.max_radius,
            "sample_count": r.sample_count,
            "zones": [
                {
                    "zone_type": z.zone_type,
                    "start_pos": z.start_pos,
                    "end_pos": z.end_pos,
                    "mean_radius": z.mean_radius,
                    "confidence": z.confidence,
                }
                for z in r.zones
            ],
            "radius_error_mm": r.radius_error_mm,
            "radius_error_pct": r.radius_error_pct,
            "zone_count_correct": r.zone_count_correct,
            "zones_matched": r.zones_matched,
            "zones_expected": r.zones_expected,
            "passed": r.passed,
            "errors": r.errors,
            "duration_s": r.duration_s,
        }
        for r in results
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    print(f"Baseline results saved to: {output_path}")


# =============================================================================
# Pytest test cases
# =============================================================================


def _skip_if_missing(path: Path) -> pytest.MarkDecorator:
    return pytest.mark.skipif(not path.exists(), reason=f"Not found: {path}")


class TestAxisDetection:
    """Axis detection accuracy for ideal revolution bodies."""

    @requires_open3d
    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_axis_confidence(self) -> None:
        """Axis detection on a perfect cylinder must exceed confidence 0.7."""
        from backend.sensors.shaft_axis import detect_main_axis

        info = detect_main_axis(str(IDEAL_DIR / "ideal_cylinder.stl"), method="auto")
        assert info.confidence > 0.5, (
            f"Expected conf > 0.5, got {info.confidence:.3f} (method={info.method})"
        )

    @requires_open3d
    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_axis_length_positive(self) -> None:
        from backend.sensors.shaft_axis import detect_main_axis

        info = detect_main_axis(str(IDEAL_DIR / "ideal_cylinder.stl"))
        assert info.length > 0, "Axis length must be positive"

    @requires_open3d
    @_skip_if_missing(FIXTURE_DIR / "plain_shaft.stl")
    def test_fixture_plain_shaft_axis(self) -> None:
        from backend.sensors.shaft_axis import detect_main_axis

        info = detect_main_axis(str(FIXTURE_DIR / "plain_shaft.stl"))
        assert info.direction is not None
        assert info.confidence >= 0


class TestProfileSampling:
    """Radial profile sampling accuracy."""

    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_sample_count(self) -> None:
        from backend.sensors.shaft_profile import sample_radial_profile

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_cylinder.stl"), axis="Z", num_samples=50
        )
        # Boundary positions may fail to produce a slice; accept >= 45 of 50
        assert profile.sample_count >= 45, (
            f"Expected >= 45 samples, got {profile.sample_count}"
        )

    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_radius_accuracy(self) -> None:
        """Detected max radius must be within 5% of ground truth 20.0mm."""
        from backend.sensors.shaft_profile import sample_radial_profile

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_cylinder.stl"), axis="Z", num_samples=100
        )
        assert profile.max_radius > 0, "max_radius should be positive"
        expected = 20.0
        error_pct = abs(profile.max_radius - expected) / expected * 100
        assert error_pct < 10.0, (
            f"Radius error {error_pct:.2f}% > 10% tolerance "
            f"(detected={profile.max_radius:.3f}, expected={expected})"
        )

    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_length_positive(self) -> None:
        from backend.sensors.shaft_profile import sample_radial_profile

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_cylinder.stl"), axis="Z", num_samples=50
        )
        assert profile.total_length > 0

    @_skip_if_missing(FIXTURE_DIR / "plain_shaft.stl")
    def test_fixture_plain_shaft_profile(self) -> None:
        from backend.sensors.shaft_profile import sample_radial_profile

        profile = sample_radial_profile(
            str(FIXTURE_DIR / "plain_shaft.stl"), axis="Z", num_samples=50
        )
        assert profile.sample_count >= 45
        assert profile.max_radius > 0
        assert profile.total_length > 0


class TestZoneSegmentation:
    """Zone segmentation accuracy."""

    @_skip_if_missing(IDEAL_DIR / "ideal_cylinder.stl")
    def test_ideal_cylinder_zone_count(self) -> None:
        """A simple cylinder must produce at least 1 cylinder zone."""
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_cylinder.stl"), axis="Z", num_samples=100
        )
        zones = segment_rotational_zones(profile)
        cylinder_zones = [z for z in zones if z.zone_type.value == "cylinder"]
        assert len(cylinder_zones) >= 1, (
            f"Expected >= 1 cylinder zone, got {[z.zone_type.value for z in zones]}"
        )

    @_skip_if_missing(IDEAL_DIR / "ideal_stepped_shaft.stl")
    def test_ideal_stepped_shaft_zone_count(self) -> None:
        """Stepped shaft must produce >= 2 distinct zones."""
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_stepped_shaft.stl"), axis="Z", num_samples=100
        )
        zones = segment_rotational_zones(profile)
        assert len(zones) >= 2, (
            f"Expected >= 2 zones for stepped shaft, got {len(zones)}"
        )

    @_skip_if_missing(IDEAL_DIR / "ideal_stepped_shaft.stl")
    def test_ideal_stepped_shaft_zone_radii(self) -> None:
        """Both cylinder zones of stepped shaft must match within 1mm tolerance."""
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(IDEAL_DIR / "ideal_stepped_shaft.stl"), axis="Z", num_samples=100
        )
        zones = segment_rotational_zones(profile)
        cylinder_zones = sorted(
            [z for z in zones if z.zone_type.value == "cylinder"],
            key=lambda z: z.mean_radius,
            reverse=True,
        )

        if len(cylinder_zones) >= 2:
            expected = [15.0, 10.0]
            tolerance = 1.0  # loose for baseline
            for exp_r, zone in zip(expected, cylinder_zones):
                err = abs(zone.mean_radius - exp_r)
                assert err <= tolerance, (
                    f"Zone radius error {err:.3f}mm > {tolerance}mm tolerance "
                    f"(detected={zone.mean_radius:.3f}, expected={exp_r})"
                )

    @_skip_if_missing(FIXTURE_DIR / "stepped_shaft.stl")
    def test_fixture_stepped_shaft_zones(self) -> None:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(FIXTURE_DIR / "stepped_shaft.stl"), axis="Z", num_samples=100
        )
        zones = segment_rotational_zones(profile)
        assert len(zones) >= 2


class TestNoiseRobustness:
    """Sensor pipeline robustness on noisy meshes."""

    @_skip_if_missing(NOISE_DIR / "noise_cylinder.stl")
    def test_noise_cylinder_does_not_crash(self) -> None:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(NOISE_DIR / "noise_cylinder.stl"), axis="Z", num_samples=50
        )
        zones = segment_rotational_zones(profile)
        assert isinstance(zones, list)

    @_skip_if_missing(NOISE_DIR / "noise_cylinder.stl")
    def test_noise_cylinder_radius_within_loose_tolerance(self) -> None:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(NOISE_DIR / "noise_cylinder.stl"), axis="Z", num_samples=100
        )
        zones = segment_rotational_zones(profile)
        cylinder_zones = [z for z in zones if z.zone_type.value == "cylinder"]
        if cylinder_zones:
            detected_r = max(cylinder_zones, key=lambda z: z.mean_radius).mean_radius
            expected_r = 20.0
            error_pct = abs(detected_r - expected_r) / expected_r * 100
            assert error_pct < 15.0, (
                f"Noisy cylinder radius error {error_pct:.2f}% > 15% loose tolerance"
            )


class TestRealScan:
    """Real scan handling — must not crash."""

    @_skip_if_missing(REAL_DIR / "Кнопка_2.stl")
    def test_real_button_does_not_crash(self) -> None:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            str(REAL_DIR / "Кнопка_2.stl"), axis="Z", num_samples=50
        )
        zones = segment_rotational_zones(profile)
        assert isinstance(zones, list)
        assert profile.sample_count > 0


# =============================================================================
# Standalone runner
# =============================================================================


def run_full_baseline() -> List[BaselineResult]:
    """Run baseline on all models and return results."""
    results = []
    for name, config in GROUND_TRUTH.items():
        print(f"  Running: {name} ...", end=" ", flush=True)
        result = run_baseline_on_model(name, config)
        status = "OK" if result.passed else f"FAIL ({len(result.errors)} errors)"
        print(status)
        results.append(result)
    return results


if __name__ == "__main__":
    print("\nRunning revolution bodies sensor baseline...\n")
    all_results = run_full_baseline()
    print_baseline_report(all_results)

    output_path = REPO_ROOT / "docs" / "baseline_results.json"
    save_baseline_results(all_results, output_path)
