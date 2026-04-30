"""Pytest skeleton for the wing tip parameter contract."""

from __future__ import annotations

from typing import Any

import numpy as np

from build_wing_tip_parametric import _custom_section_yz, build_parametric_tip
from extract_wing_tip_parameters import validate_parameters


def _valid_contract() -> dict[str, Any]:
    """Return a minimal valid parameter contract for validation tests."""

    return {
        "core_dimensions_mm": {"L": 100.0, "W": 30.0, "H": 20.0, "r_n": 2.0},
        "cad_intent": {
            "visual_plan_widths_mm": [
                {"name": "VW00", "station_pct": 0.0, "width_mm": 30.0},
                {"name": "VW50", "station_pct": 0.5, "width_mm": 16.0},
                {"name": "VW100", "station_pct": 1.0, "width_mm": 4.0},
            ],
            "side_profile_mm": [
                {"name": "z00", "station_pct": 0.0, "z_top_mm": 20.0},
                {"name": "z50", "station_pct": 0.5, "z_top_mm": 12.0},
                {"name": "z100", "station_pct": 1.0, "z_top_mm": 3.0},
            ],
        },
        "plan_widths_mm": [
            {"name": "W00", "width_mm": 30.0},
            {"name": "W25", "width_mm": 24.0},
            {"name": "W50", "width_mm": 18.0},
            {"name": "W75", "width_mm": 12.0},
            {"name": "W90", "width_mm": 6.0},
        ],
        "sections": [
            {
                "name": "S00",
                "width_mm": 30.0,
                "height_mm": 20.0,
                "side_roundness_ratio": 1.0,
                "top_roundness_ratio": 0.6,
            },
            {
                "name": "S25",
                "width_mm": 24.0,
                "height_mm": 18.0,
                "side_roundness_ratio": 0.95,
                "top_roundness_ratio": 0.58,
            },
            {
                "name": "S50",
                "width_mm": 18.0,
                "height_mm": 14.0,
                "side_roundness_ratio": 0.9,
                "top_roundness_ratio": 0.55,
            },
            {
                "name": "S75",
                "width_mm": 12.0,
                "height_mm": 10.0,
                "side_roundness_ratio": 0.85,
                "top_roundness_ratio": 0.5,
            },
        ],
        "hole_feature": {
            "detected": True,
            "diameter_mm": 4.0,
            "center_mm": {"x": 40.0, "y": 0.0, "z": 8.0},
        },
    }


def test_validate_parameters_accepts_minimal_contract() -> None:
    """Validation accepts a compact, monotonic wing tip contract."""

    assert validate_parameters(_valid_contract()) == []


def test_validate_parameters_rejects_invalid_dimensions() -> None:
    """Validation rejects non-positive core dimensions and section sizes."""

    contract = _valid_contract()
    contract["core_dimensions_mm"]["L"] = 0.0
    contract["sections"][0]["height_mm"] = -1.0

    errors = validate_parameters(contract)

    assert "L must be positive" in errors
    assert "S00 must have positive width and height" in errors


def test_custom_section_preserves_flat_base() -> None:
    """Custom section has the requested size and a printable flat base."""

    section = _custom_section_yz(
        width_mm=30.0,
        height_mm=20.0,
        apex_offset_y_mm=0.0,
        top_roundness_ratio=0.6,
        ring_points=64,
    )

    assert section.shape == (64, 2)
    assert np.min(section[:, 1]) == 0.0
    assert np.max(section[:, 1]) > 19.0
    assert np.max(section[:, 0]) - np.min(section[:, 0]) > 29.0


def test_parametric_builder_creates_expected_envelope() -> None:
    """Parametric builder creates a mesh with the target longitudinal length."""

    outer, final, hole_status = build_parametric_tip(_valid_contract(), ring_points=48)

    assert hole_status == ""
    assert outer.vertices.shape[0] > 0
    assert final.vertices.shape[0] > 0
    assert np.isclose(final.bounds[1][0] - final.bounds[0][0], 100.0)
