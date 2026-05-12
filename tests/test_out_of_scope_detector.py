"""Acceptance tests for the Sprint 3 Spike Generator.

The detector flags z-bands whose cross-section deviates from a body of
revolution (keyway, cross-hole, flat, etc.) and emits ``SkillRequest``
payloads for the v2 swarm. The tests below check:

* known revolution bodies (plain shaft, cylinder) emit **no** requests;
* fixtures with explicit out-of-scope features emit at least one request;
* every emitted request has a non-empty hypothesis and a coherent region.

Heuristic calibration (``phi_variance_threshold``, ``min_band_samples``,
``max_gap_for_coalesce``) is owned by
:func:`backend.pipeline.deterministic_shaft._generate_skill_requests`.
The thresholds chosen there reflect the bench shipped in Sprint 1.3 and
should be revisited when the bench grows.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Tuple

import pytest

from backend.pipeline.deterministic_shaft import (
    _generate_skill_requests,
    run_deterministic_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(stl: str) -> Tuple[List, List]:
    """Run the full deterministic pipeline and return the Spike Generator output.

    The detector itself is invoked on the **axis-aligned** mesh, so we go
    through the whole pipeline (which does the alignment) rather than
    calling :func:`_generate_skill_requests` directly on the raw fixture.
    Skipping the build123d step keeps the test fast.
    """
    stl_path = str(REPO_ROOT / stl)
    with tempfile.TemporaryDirectory() as td:
        result = run_deterministic_pipeline(
            stl_path=stl_path,
            output_dir=td,
            execute_build123d=False,
        )
    plan = result.construction_plan
    assert plan is not None, "Pipeline did not produce a construction plan"
    return list(plan.skill_requests), list(plan.out_of_scope_regions)


class TestPureRevolutionBodies:
    """Detector must stay quiet on clean bodies of revolution."""

    @pytest.mark.parametrize(
        "stl_path",
        [
            "tests/fixtures/plain_shaft.stl",
            "benchmark_kit/ideal/ideal_cylinder.stl",
            "benchmark_kit/ideal/ideal_short_disc_shaft.stl",
        ],
    )
    def test_no_false_positives_on_revolution(self, stl_path: str) -> None:
        """Plain cylinders must emit zero ``SkillRequest`` objects."""
        skill_requests, regions = _run(stl_path)
        assert skill_requests == []
        assert regions == []


class TestOutOfScopeFixtures:
    """Detector must fire on every Sprint 3 acceptance fixture."""

    @pytest.mark.parametrize(
        "stl_path",
        [
            "tests/fixtures/shaft_with_keyway.stl",
            "tests/fixtures/shaft_with_cross_hole.stl",
            "tests/fixtures/shaft_with_flat.stl",
        ],
    )
    def test_at_least_one_request_emitted(self, stl_path: str) -> None:
        """Each fixture must produce at least one ``SkillRequest``."""
        skill_requests, regions = _run(stl_path)
        assert len(skill_requests) >= 1
        assert len(regions) == len(skill_requests)

    def test_request_payload_is_well_formed(self) -> None:
        """Inspect a single fixture in detail."""
        skill_requests, _regions = _run("tests/fixtures/shaft_with_keyway.stl")
        sr = skill_requests[0]
        assert sr.trigger == "non_revolution_region_detected"
        assert sr.needs_tool.startswith("feature_detector_for_")
        assert len(sr.hypothesis) >= 2
        assert sr.region.z_end > sr.region.z_start
        assert sr.region.max_phi_variance >= 0.15
        assert sr.region.sample_count >= 2
        assert 0.0 <= sr.confidence <= 1.0

    def test_top_hypothesis_matches_feature(self) -> None:
        """For a keyway fixture the top hypothesis should be 'keyway'."""
        skill_requests, _regions = _run("tests/fixtures/shaft_with_keyway.stl")
        keyway_first = [sr for sr in skill_requests if sr.hypothesis[0] == "keyway"]
        # The bench keyway peaks well above 0.20, where the heuristic
        # promotes the "keyway" candidate to the top of the list.
        assert keyway_first, "Expected at least one 'keyway'-led hypothesis"


class TestDetectorDeterminism:
    """The detector is pure on its inputs and must be repeatable."""

    def test_repeated_runs_produce_identical_output(self) -> None:
        sr1, r1 = _run("tests/fixtures/shaft_with_keyway.stl")
        sr2, r2 = _run("tests/fixtures/shaft_with_keyway.stl")
        assert len(sr1) == len(sr2)
        for a, b in zip(sr1, sr2):
            assert a.region.z_start == pytest.approx(b.region.z_start)
            assert a.region.z_end == pytest.approx(b.region.z_end)
            assert a.region.max_phi_variance == pytest.approx(b.region.max_phi_variance)
            assert a.needs_tool == b.needs_tool
