#!/usr/bin/env python3
"""Extract a compact parametric contract from ``wing_tip_light_left.step``.

The output is intentionally small: global dimensions, top/profile stations,
four cross-sections, a separate hole feature block, and validation rules. This
is the handoff format for later text-to-CAD or Cursor-driven CAD generation.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from build123d import export_stl, import_step

_SOURCE_STEP = "wing_tip_light_left.step"
_PREVIEW_STL = "wing_tip_light_left_parameter_mesh.stl"
_PARAMETERS_JSON = "wing_tip_parameters.json"
_SCHEMA_JSON = "wing_tip_parameters.schema.json"
_REPORT_MD = "wing_tip_parameters.md"
_STL_TOLERANCE_MM = 0.18
_STL_ANGULAR_TOL = 0.18
_EDGE_MARGIN_MM = 0.75
_WIDTH_STATIONS = (0.0, 0.25, 0.5, 0.75, 0.9)
_SECTION_STATIONS = (0.0, 0.25, 0.5, 0.75)
_PROFILE_STATIONS = (0.0, 0.10, 0.25, 0.5, 0.75, 0.90, 1.0)


def _load_mesh_from_step(source_step: Path, preview_stl: Path) -> trimesh.Trimesh:
    """Import a STEP file and tessellate it to a Trimesh mesh.

    Args:
        source_step: Source STEP path.
        preview_stl: Destination STL used as a measurable mesh cache.

    Returns:
        Loaded triangular mesh.

    Raises:
        FileNotFoundError: The source STEP does not exist.
        RuntimeError: The tessellation result cannot be loaded as mesh data.
    """

    if not source_step.is_file():
        raise FileNotFoundError(source_step)

    shape = import_step(str(source_step.resolve()))
    export_stl(
        shape,
        str(preview_stl),
        tolerance=_STL_TOLERANCE_MM,
        angular_tolerance=_STL_ANGULAR_TOL,
    )

    loaded = trimesh.load(str(preview_stl), force="mesh")
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    if not isinstance(loaded, trimesh.Trimesh):
        raise RuntimeError(f"Cannot load mesh from {preview_stl}")
    return loaded


def _perimeter(points_yz: np.ndarray) -> float:
    """Return closed-loop perimeter for YZ points."""

    if len(points_yz) < 3:
        return 0.0
    closed = np.vstack([points_yz, points_yz[0:1]])
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def _section_paths_yz(mesh: trimesh.Trimesh, raw_x_mm: float) -> list[np.ndarray]:
    """Slice the mesh with ``X = raw_x_mm`` and return closed paths in YZ."""

    section = mesh.section(
        plane_origin=[float(raw_x_mm), 0.0, 0.0],
        plane_normal=[1.0, 0.0, 0.0],
    )
    if section is None:
        return []
    return [
        np.asarray(path[:, 1:3], dtype=np.float64)
        for path in section.discrete
        if len(path) >= 3
    ]


def _station_raw_x(xmin: float, xmax: float, station_pct: float) -> float:
    """Map a normalized station to source STEP X with a small edge inset."""

    length = xmax - xmin
    raw = xmin + length * station_pct
    if station_pct <= 0.0:
        return xmin + min(_EDGE_MARGIN_MM, length * 0.01)
    if station_pct >= 1.0:
        return xmax - min(_EDGE_MARGIN_MM, length * 0.01)
    return raw


def _dominant_section_yz(mesh: trimesh.Trimesh, raw_x_mm: float) -> np.ndarray:
    """Return the largest contour at a station.

    Raises:
        ValueError: No contour can be measured at the requested station.
    """

    paths = _section_paths_yz(mesh, raw_x_mm)
    if not paths:
        raise ValueError(f"No section at X={raw_x_mm:.3f} mm")
    return max(paths, key=_perimeter)


def _extent_at_z_fraction(points_yz: np.ndarray, fraction: float) -> float:
    """Measure horizontal Y extent near a relative Z height."""

    min_z = float(np.min(points_yz[:, 1]))
    max_z = float(np.max(points_yz[:, 1]))
    target_z = min_z + (max_z - min_z) * fraction
    tolerance = max((max_z - min_z) * 0.04, 0.25)
    band = points_yz[np.abs(points_yz[:, 1] - target_z) <= tolerance]
    if len(band) < 2:
        nearest = points_yz[np.argsort(np.abs(points_yz[:, 1] - target_z))[:8]]
        band = nearest
    return float(np.max(band[:, 0]) - np.min(band[:, 0]))


def _section_summary(
    name: str,
    station_pct: float,
    raw_x_mm: float,
    yz: np.ndarray,
    xmin: float,
    center_y_mm: float,
    base_z_mm: float,
) -> dict[str, Any]:
    """Build the compact cross-section description used by the CAD contract."""

    min_y = float(np.min(yz[:, 0]))
    max_y = float(np.max(yz[:, 0]))
    min_z = float(np.min(yz[:, 1]))
    max_z = float(np.max(yz[:, 1]))
    width = max_y - min_y
    height = max_z - min_z
    apex_candidates = yz[np.isclose(yz[:, 1], max_z, atol=max(height * 0.01, 0.1))]
    apex_y = float(np.mean(apex_candidates[:, 0])) if len(apex_candidates) else 0.0
    mid_width = _extent_at_z_fraction(yz, 0.5)
    top_width = _extent_at_z_fraction(yz, 0.9)

    return {
        "name": name,
        "station_pct": round(station_pct, 4),
        "x_mm": round(raw_x_mm - xmin, 4),
        "width_mm": round(width, 4),
        "height_mm": round(height, 4),
        "apex_offset_y_mm": round(apex_y - center_y_mm, 4),
        "apex_offset_z_mm": round(max_z - base_z_mm, 4),
        "side_roundness_ratio": round(mid_width / width if width > 1e-9 else 0.0, 4),
        "top_roundness_ratio": round(top_width / width if width > 1e-9 else 0.0, 4),
        "primitive": "flat_base_two_side_arcs_top_arc",
    }


def _profile_samples(
    mesh: trimesh.Trimesh,
    bounds: np.ndarray,
    stations: tuple[float, ...],
) -> dict[str, Any]:
    """Measure plan widths and top profile heights at normalized stations."""

    xmin, xmax = float(bounds[0][0]), float(bounds[1][0])
    base_z = float(bounds[0][2])
    samples: list[dict[str, Any]] = []
    for pct in stations:
        raw_x = _station_raw_x(xmin, xmax, pct)
        yz = _dominant_section_yz(mesh, raw_x)
        samples.append(
            {
                "station_pct": pct,
                "x_mm": raw_x - xmin,
                "width_mm": float(np.max(yz[:, 0]) - np.min(yz[:, 0])),
                "top_z_mm": float(np.max(yz[:, 1]) - base_z),
            }
        )
    return {"samples": samples}


def _estimate_slope_start_x(mesh: trimesh.Trimesh, bounds: np.ndarray) -> float:
    """Estimate where the top profile starts descending toward the nose."""

    xmin, xmax = float(bounds[0][0]), float(bounds[1][0])
    base_z = float(bounds[0][2])
    top_samples: list[tuple[float, float]] = []
    for pct in np.linspace(0.02, 0.98, 33):
        raw_x = _station_raw_x(xmin, xmax, float(pct))
        try:
            yz = _dominant_section_yz(mesh, raw_x)
        except ValueError:
            continue
        top_samples.append((raw_x - xmin, float(np.max(yz[:, 1]) - base_z)))

    if not top_samples:
        return 0.0

    max_top = max(z for _, z in top_samples)
    tolerance = max(max_top * 0.015, 0.5)
    for x_mm, z_mm in top_samples:
        if z_mm >= max_top - tolerance:
            return x_mm
    return top_samples[0][0]


def _detect_hole_feature(mesh: trimesh.Trimesh, bounds: np.ndarray) -> dict[str, Any]:
    """Detect a secondary inner loop that can seed a separate hole feature."""

    xmin, xmax = float(bounds[0][0]), float(bounds[1][0])
    length = xmax - xmin
    candidates: list[dict[str, float]] = []
    for pct in np.linspace(0.05, 0.95, 37):
        raw_x = xmin + length * float(pct)
        paths = sorted(_section_paths_yz(mesh, raw_x), key=_perimeter, reverse=True)
        if len(paths) < 2:
            continue
        outer = paths[0]
        outer_min_y, outer_min_z = np.min(outer, axis=0)
        outer_max_y, outer_max_z = np.max(outer, axis=0)
        outer_width = float(outer_max_y - outer_min_y)
        outer_height = float(outer_max_z - outer_min_z)
        for loop in paths[1:]:
            min_y, min_z = np.min(loop, axis=0)
            max_y, max_z = np.max(loop, axis=0)
            span_y = float(max_y - min_y)
            span_z = float(max_z - min_z)
            diameter = (span_y + span_z) / 2.0
            if diameter <= 0.5:
                continue
            if span_y > outer_width * 0.55 or span_z > outer_height * 0.55:
                continue
            circularity = min(span_y, span_z) / max(span_y, span_z, 1e-9)
            if circularity < 0.65:
                continue
            candidates.append(
                {
                    "diameter_mm": diameter,
                    "x_mm": raw_x - xmin,
                    "y_mm": float((min_y + max_y) / 2.0),
                    "z_mm": float((min_z + max_z) / 2.0 - bounds[0][2]),
                    "circularity": circularity,
                }
            )

    if not candidates:
        return {
            "detected": False,
            "diameter_mm": None,
            "center_mm": {"x": None, "y": None, "z": None},
            "axis_direction": [0.0, 1.0, 0.0],
            "note": (
                "No reliable inner loop was detected in X sections; keep the "
                "hole as a separate editable CAD feature."
            ),
        }

    best = max(candidates, key=lambda item: (item["diameter_mm"], item["circularity"]))
    return {
        "detected": True,
        "diameter_mm": round(best["diameter_mm"], 4),
        "center_mm": {
            "x": round(best["x_mm"], 4),
            "y": round(best["y_mm"], 4),
            "z": round(best["z_mm"], 4),
        },
        "axis_direction": [0.0, 1.0, 0.0],
        "confidence": round(best["circularity"], 4),
    }


def _manual_hole_feature(
    detected_feature: dict[str, Any],
    length_mm: float,
    width_center_y_mm: float,
    height_mm: float,
) -> dict[str, Any]:
    """Return a stable editable hole block for the CAD generator."""

    if detected_feature.get("detected"):
        detected_feature["editable"] = True
        return detected_feature

    return {
        "detected": False,
        "editable": True,
        "diameter_mm": round(max(8.0, min(height_mm * 0.18, 14.0)), 4),
        "center_mm": {
            "x": round(length_mm * 0.82, 4),
            "y": round(width_center_y_mm, 4),
            "z": round(height_mm * 0.22, 4),
        },
        "axis_direction": [0.0, 1.0, 0.0],
        "source": "manual_initial_estimate_from_reference_images",
        "note": (
            "The STEP did not expose a reliable hole loop; these values are "
            "editable seed dimensions for a transverse boolean cut."
        ),
    }


def _cad_intent(length_mm: float, width_mm: float, height_mm: float) -> dict[str, Any]:
    """Return screenshot-driven intent used by the cleaner parametric builder."""

    side_profile = [
        (0.00, 1.00),
        (0.10, 0.98),
        (0.25, 0.82),
        (0.50, 0.55),
        (0.75, 0.28),
        (0.90, 0.16),
        (1.00, 0.11),
    ]
    plan_profile = [
        (0.00, 1.00),
        (0.10, 0.98),
        (0.25, 0.78),
        (0.50, 0.52),
        (0.75, 0.25),
        (0.90, 0.10),
        (1.00, 0.06),
    ]
    return {
        "coordinate_assumption": "x=0 is the high rear/root wall; x=L is the low rounded nose.",
        "section_primitive": "flat_base_two_side_arcs_top_arc",
        "preserve_flat_base": True,
        "preserve_vertical_rear_wall": True,
        "side_profile_mm": [
            {
                "name": f"z{int(pct * 100):02d}",
                "station_pct": pct,
                "x_mm": round(length_mm * pct, 4),
                "z_top_mm": round(height_mm * scale, 4),
            }
            for pct, scale in side_profile
        ],
        "visual_plan_widths_mm": [
            {
                "name": f"VW{int(pct * 100):02d}",
                "station_pct": pct,
                "x_mm": round(length_mm * pct, 4),
                "width_mm": round(max(width_mm * scale, 3.5), 4),
            }
            for pct, scale in plan_profile
        ],
        "nose_radius_mm": round(max(3.0, min(width_mm * 0.08, height_mm * 0.08)), 4),
        "rear_wall_x_mm": 0.0,
    }


def _json_schema() -> dict[str, Any]:
    """Return the JSON schema for the generated parameter contract."""

    number_or_null = {"type": ["number", "null"]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "WingTipLoftParameters",
        "type": "object",
        "required": [
            "metadata",
            "core_dimensions_mm",
            "top_profile_mm",
            "plan_widths_mm",
            "sections",
            "cad_intent",
            "hole_feature",
            "validation_rules",
        ],
        "properties": {
            "metadata": {"type": "object"},
            "core_dimensions_mm": {"type": "object"},
            "top_profile_mm": {"type": "array", "items": {"type": "object"}},
            "plan_widths_mm": {"type": "array", "items": {"type": "object"}},
            "sections": {"type": "array", "items": {"type": "object"}, "minItems": 4},
            "cad_intent": {"type": "object"},
            "hole_feature": {
                "type": "object",
                "properties": {
                    "detected": {"type": "boolean"},
                    "diameter_mm": number_or_null,
                    "center_mm": {
                        "type": "object",
                        "properties": {
                            "x": number_or_null,
                            "y": number_or_null,
                            "z": number_or_null,
                        },
                    },
                    "axis_direction": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                },
            },
            "validation_rules": {"type": "array", "items": {"type": "string"}},
        },
    }


def _write_report(parameters: dict[str, Any], output_path: Path) -> None:
    """Write a compact Markdown report for manual review."""

    core = parameters["core_dimensions_mm"]
    widths = parameters["plan_widths_mm"]
    sections = parameters["sections"]
    cad_intent = parameters.get("cad_intent", {})
    hole = parameters["hole_feature"]

    lines = [
        "# Wing tip parameter contract",
        "",
        f"- Source STEP: `{parameters['metadata']['source_step']}`",
        f"- Units: `{parameters['metadata']['units']}`",
        f"- Axis mapping: `{parameters['metadata']['axis_mapping']}`",
        "",
        "## Core dimensions",
        "",
        f"- `L`: {core['L']:.3f} mm",
        f"- `W`: {core['W']:.3f} mm",
        f"- `H`: {core['H']:.3f} mm",
        f"- `x_s`: {core['x_s']:.3f} mm",
        f"- `r_n`: {core['r_n']:.3f} mm",
        "",
        "## Plan widths",
        "",
        "| Name | Station | X mm | Width mm |",
        "|---|---:|---:|---:|",
    ]
    for row in widths:
        lines.append(
            f"| `{row['name']}` | {row['station_pct']:.2f} | "
            f"{row['x_mm']:.3f} | {row['width_mm']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Cross-sections",
            "",
            "| Name | X mm | Width mm | Height mm | Side roundness | Top roundness |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for section in sections:
        lines.append(
            f"| `{section['name']}` | {section['x_mm']:.3f} | "
            f"{section['width_mm']:.3f} | {section['height_mm']:.3f} | "
            f"{section['side_roundness_ratio']:.3f} | "
            f"{section['top_roundness_ratio']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## CAD intent side profile",
            "",
            "| Name | Station | X mm | Top Z mm |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in cad_intent.get("side_profile_mm", []):
        lines.append(
            f"| `{row['name']}` | {row['station_pct']:.2f} | "
            f"{row['x_mm']:.3f} | {row['z_top_mm']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## CAD intent visual plan widths",
            "",
            "| Name | Station | X mm | Width mm |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in cad_intent.get("visual_plan_widths_mm", []):
        lines.append(
            f"| `{row['name']}` | {row['station_pct']:.2f} | "
            f"{row['x_mm']:.3f} | {row['width_mm']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Hole feature",
            "",
            f"- Detected: `{hole['detected']}`",
            f"- Diameter: `{hole['diameter_mm']}`",
            f"- Center: `{hole['center_mm']}`",
            f"- Axis direction: `{hole['axis_direction']}`",
        ]
    )
    if "note" in hole:
        lines.append(f"- Note: {hole['note']}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_parameters(parameters: dict[str, Any]) -> list[str]:
    """Validate the extracted contract before it is used for CAD generation.

    Args:
        parameters: Generated parameter dictionary.

    Returns:
        Human-readable validation errors. Empty means the contract is usable.
    """

    errors: list[str] = []
    core = parameters["core_dimensions_mm"]
    for key in ("L", "W", "H", "r_n"):
        if float(core[key]) <= 0.0:
            errors.append(f"{key} must be positive")

    widths = [float(row["width_mm"]) for row in parameters["plan_widths_mm"]]
    if any(width <= 0.0 for width in widths):
        errors.append("all plan widths must be positive")
    if any(a < b - 0.75 for a, b in zip(widths, widths[1:])):
        errors.append("plan widths should generally taper toward the nose")

    intent_widths = [
        float(row["width_mm"])
        for row in parameters.get("cad_intent", {}).get("visual_plan_widths_mm", [])
    ]
    if intent_widths and any(a < b - 0.75 for a, b in zip(intent_widths, intent_widths[1:])):
        errors.append("visual plan widths should taper toward the nose")

    for section in parameters["sections"]:
        if float(section["width_mm"]) <= 0.0 or float(section["height_mm"]) <= 0.0:
            errors.append(f"{section['name']} must have positive width and height")
        for key in ("side_roundness_ratio", "top_roundness_ratio"):
            value = float(section[key])
            if not math.isfinite(value) or value < 0.0:
                errors.append(f"{section['name']} {key} must be non-negative")

    hole = parameters["hole_feature"]
    if hole["detected"] and (hole["diameter_mm"] is None or hole["diameter_mm"] <= 0):
        errors.append("detected hole must have a positive diameter")

    return errors


def run_extract(root_dir: Path) -> dict[str, Any]:
    """Extract parameters and write JSON, schema, and Markdown artifacts.

    Args:
        root_dir: Directory containing ``wing_tip_light_left.step``.

    Returns:
        The generated parameter contract.

    Raises:
        FileNotFoundError: The source STEP file is missing.
        RuntimeError: Mesh generation or validation failed.
        ValueError: A requested station cannot be measured.
    """

    source_step = root_dir / _SOURCE_STEP
    preview_stl = root_dir / _PREVIEW_STL
    mesh = _load_mesh_from_step(source_step, preview_stl)
    bounds = mesh.bounds.astype(np.float64)
    xmin, xmax = float(bounds[0][0]), float(bounds[1][0])
    ymin, ymax = float(bounds[0][1]), float(bounds[1][1])
    zmin, zmax = float(bounds[0][2]), float(bounds[1][2])
    length = xmax - xmin
    width = ymax - ymin
    height = zmax - zmin
    center_y = (ymin + ymax) / 2.0

    profile_stations = tuple(sorted(set(_WIDTH_STATIONS + _PROFILE_STATIONS)))
    profile = _profile_samples(mesh, bounds, profile_stations)
    sample_by_pct = {sample["station_pct"]: sample for sample in profile["samples"]}
    width_rows = []
    for pct in _WIDTH_STATIONS:
        sample = sample_by_pct[pct]
        width_rows.append(
            {
                "name": f"W{int(pct * 100):02d}",
                "station_pct": pct,
                "x_mm": round(sample["x_mm"], 4),
                "width_mm": round(sample["width_mm"], 4),
            }
        )

    top_profile = [
        {
            "name": f"z{int(pct * 100):02d}",
            "station_pct": pct,
            "x_mm": round(sample_by_pct[pct]["x_mm"], 4),
            "z_top_mm": round(sample_by_pct[pct]["top_z_mm"], 4),
        }
        for pct in _PROFILE_STATIONS
    ]

    sections = []
    for pct in _SECTION_STATIONS:
        raw_x = _station_raw_x(xmin, xmax, pct)
        yz = _dominant_section_yz(mesh, raw_x)
        sections.append(
            _section_summary(
                f"S{int(pct * 100):02d}",
                pct,
                raw_x,
                yz,
                xmin,
                center_y,
                zmin,
            )
        )

    nose_width = float(width_rows[-1]["width_mm"])
    parameters: dict[str, Any] = {
        "metadata": {
            "source_step": _SOURCE_STEP,
            "preview_stl": _PREVIEW_STL,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "units": "millimeters",
            "stl_tolerance_mm": _STL_TOLERANCE_MM,
            "axis_mapping": {
                "x": "longitudinal: rear/root wall to nose/tip",
                "y": "transverse width, centered around the symmetry plane",
                "z": "vertical height from the lowest base datum",
            },
            "source_bounds_mm": {
                "min": [round(xmin, 6), round(ymin, 6), round(zmin, 6)],
                "max": [round(xmax, 6), round(ymax, 6), round(zmax, 6)],
            },
        },
        "core_dimensions_mm": {
            "L": round(length, 4),
            "W": round(width, 4),
            "H": round(height, 4),
            "x_s": round(_estimate_slope_start_x(mesh, bounds), 4),
            "r_n": round(nose_width / 2.0, 4),
        },
        "top_profile_mm": top_profile,
        "plan_widths_mm": width_rows,
        "sections": sections,
        "cad_intent": _cad_intent(length, width, height),
        "hole_feature": _manual_hole_feature(
            _detect_hole_feature(mesh, bounds),
            length,
            center_y,
            height,
        ),
        "validation_rules": [
            "Units are millimeters.",
            "Build half-body from Y center plane when symmetry is acceptable, then mirror.",
            "Plan widths should generally taper from W00 toward W90.",
            "CAD intent visual widths taper more aggressively to match the screenshot nose.",
            "Cross-sections use the primitive flat_base_two_side_arcs_top_arc.",
            "Apply hole_feature as a separate boolean cut after loft generation.",
        ],
    }

    errors = validate_parameters(parameters)
    if errors:
        raise RuntimeError("; ".join(errors))

    (root_dir / _PARAMETERS_JSON).write_text(
        json.dumps(parameters, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (root_dir / _SCHEMA_JSON).write_text(
        json.dumps(_json_schema(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_report(parameters, root_dir / _REPORT_MD)
    return parameters


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing wing_tip_light_left.step.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        result = run_extract(args.root.resolve())
    except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 2

    core = result["core_dimensions_mm"]
    logging.info(
        "Wrote %s, %s, %s (L=%.2f W=%.2f H=%.2f)",
        _PARAMETERS_JSON,
        _SCHEMA_JSON,
        _REPORT_MD,
        core["L"],
        core["W"],
        core["H"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
