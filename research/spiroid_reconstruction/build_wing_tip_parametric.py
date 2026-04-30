#!/usr/bin/env python3
"""Build a printable wing tip analogue from ``wing_tip_parameters.json``.

This builder intentionally favors a clean, controllable silhouette over exact
BREP reconstruction. It creates a mesh strip from custom cross-sections with a
flat base, rounded sides, a top arc, a vertical rear datum, and a separate
transverse hole cut.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from build123d import export_step, import_stl

from mesh_from_sections import (
    arc_length_resample_closed,
    build_strip_mesh,
    mesh_difference_or_none,
)

_PARAMETERS_JSON = "wing_tip_parameters.json"
_OUTER_STL = "wing_tip_parametric_outer.stl"
_FINAL_STL = "wing_tip_parametric.stl"
_FINAL_STEP = "wing_tip_parametric.step"
_REPORT_MD = "wing_tip_parametric_report.md"
_RING_POINTS = 96


def load_parameters(path: Path) -> dict[str, Any]:
    """Load a wing tip parameter contract.

    Args:
        path: JSON parameter file path.

    Returns:
        Parsed parameter mapping.

    Raises:
        FileNotFoundError: The JSON file is missing.
        ValueError: The top-level JSON value is not an object.
        json.JSONDecodeError: The JSON file is malformed.
    """

    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Parameter JSON top level must be an object.")
    return data


def _interp_rows(rows: list[dict[str, Any]], key: str, station_pct: float) -> float:
    """Interpolate a numeric row field by normalized station."""

    if not rows:
        raise ValueError("Cannot interpolate an empty row set.")
    stations = np.asarray([float(row["station_pct"]) for row in rows], dtype=np.float64)
    values = np.asarray([float(row[key]) for row in rows], dtype=np.float64)
    order = np.argsort(stations)
    return float(np.interp(float(station_pct), stations[order], values[order]))


def _smoothstep(value: float) -> float:
    """Return cubic smoothstep in ``[0, 1]``."""

    x = max(0.0, min(1.0, float(value)))
    return x * x * (3.0 - 2.0 * x)


def _custom_section_yz(
    width_mm: float,
    height_mm: float,
    apex_offset_y_mm: float,
    top_roundness_ratio: float,
    ring_points: int,
) -> np.ndarray:
    """Create a closed YZ ring: flat base, side arcs, and top arc.

    Args:
        width_mm: Total section width.
        height_mm: Total section height above the base.
        apex_offset_y_mm: Top apex Y offset from the center plane.
        top_roundness_ratio: Approximate top shoulder width ratio.
        ring_points: Number of points after arc-length resampling.

    Returns:
        Closed section ring without duplicate final point.
    """

    if width_mm <= 0.0 or height_mm <= 0.0:
        raise ValueError("Section width and height must be positive.")

    half_w = width_mm / 2.0
    apex_y = max(-half_w * 0.45, min(half_w * 0.45, apex_offset_y_mm))
    shoulder_half = half_w * max(0.12, min(0.55, top_roundness_ratio * 0.45))
    shoulder_z = height_mm * 0.90
    left_shoulder = apex_y - shoulder_half
    right_shoulder = apex_y + shoulder_half

    points: list[list[float]] = []
    points.append([-half_w, 0.0])

    for idx in range(1, 13):
        t = idx / 12.0
        s = _smoothstep(t)
        y = (1.0 - s) * (-half_w) + s * left_shoulder
        z = shoulder_z * (math.sin(t * math.pi / 2.0) ** 0.82)
        points.append([y, z])

    for idx in range(1, 11):
        t = idx / 10.0
        angle = math.pi * t
        y = apex_y - shoulder_half * math.cos(angle)
        z = shoulder_z + (height_mm - shoulder_z) * math.sin(angle)
        points.append([y, z])

    for idx in range(1, 13):
        t = idx / 12.0
        s = _smoothstep(t)
        y = (1.0 - s) * right_shoulder + s * half_w
        z = shoulder_z * (math.cos(t * math.pi / 2.0) ** 0.82)
        points.append([y, z])

    for idx in range(1, 9):
        t = idx / 8.0
        y = (1.0 - t) * half_w + t * (-half_w)
        points.append([y, 0.0])

    return arc_length_resample_closed(np.asarray(points, dtype=np.float64), ring_points)


def _build_sections(parameters: dict[str, Any], ring_points: int) -> list[dict[str, Any]]:
    """Build section dictionaries compatible with ``build_strip_mesh``."""

    core = parameters["core_dimensions_mm"]
    intent = parameters.get("cad_intent", {})
    length = float(core["L"])
    visual_widths = intent.get("visual_plan_widths_mm") or parameters["plan_widths_mm"]
    side_profile = intent.get("side_profile_mm") or parameters["top_profile_mm"]
    source_sections = sorted(
        parameters["sections"], key=lambda section: float(section["station_pct"])
    )
    station_values = sorted(
        {
            0.0,
            0.10,
            0.25,
            0.50,
            0.75,
            0.90,
            1.0,
            *[float(section["station_pct"]) for section in source_sections],
        }
    )

    sections: list[dict[str, Any]] = []
    for station in station_values:
        width = _interp_rows(visual_widths, "width_mm", station)
        height = _interp_rows(side_profile, "z_top_mm", station)
        apex = _interp_rows(source_sections, "apex_offset_y_mm", min(station, 0.75))
        top_roundness = _interp_rows(
            source_sections, "top_roundness_ratio", min(station, 0.75)
        )
        yz = _custom_section_yz(width, height, apex, top_roundness, ring_points)
        cy = float(np.mean(yz[:, 0]))
        cz = float(np.mean(yz[:, 1]))
        sections.append(
            {
                "plane_x_mm": round(length * station, 6),
                "centroid_y_mm": cy,
                "centroid_z_mm": cz,
                "points_sketch_uv_mm": [
                    [float(row[0] - cy), float(row[1] - cz)] for row in yz
                ],
                "station_pct": station,
            }
        )
    return sections


def _hole_mesh(parameters: dict[str, Any]) -> trimesh.Trimesh | None:
    """Create a transverse cylinder mesh for the hole boolean cut."""

    hole = parameters.get("hole_feature", {})
    diameter = hole.get("diameter_mm")
    center = hole.get("center_mm", {})
    if diameter is None or center.get("x") is None or center.get("z") is None:
        return None

    core = parameters["core_dimensions_mm"]
    height = float(core["W"]) * 2.5
    radius = float(diameter) / 2.0
    cylinder = trimesh.creation.cylinder(radius=radius, height=height, sections=48)
    rotate_to_y = trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0])
    cylinder.apply_transform(rotate_to_y)
    cylinder.apply_translation(
        [
            float(center["x"]),
            float(center.get("y") or 0.0),
            float(center["z"]),
        ]
    )
    return cylinder


def _cut_hole(
    outer_mesh: trimesh.Trimesh, parameters: dict[str, Any]
) -> tuple[trimesh.Trimesh, str]:
    """Apply the editable hole feature as a boolean cut when possible."""

    cutter = _hole_mesh(parameters)
    if cutter is None:
        return outer_mesh, "hole-skip-missing-parameters"
    cut, err = mesh_difference_or_none(outer_mesh, cutter)
    if cut is None:
        return outer_mesh, f"hole-boolean-failed:{err}"
    return cut, ""


def _mesh_to_step(mesh_path: Path, step_path: Path) -> None:
    """Export an STL mesh as a STEP shell through build123d."""

    imported = import_stl(str(mesh_path.resolve()))
    export_step(imported, str(step_path.resolve()))


def _measure_section(mesh: trimesh.Trimesh, x_mm: float) -> tuple[float, float] | None:
    """Measure width and top height at ``X = x_mm``."""

    min_x, max_x = float(mesh.bounds[0][0]), float(mesh.bounds[1][0])
    safe_x = max(min_x + 1e-4, min(max_x - 1e-4, float(x_mm)))
    section = mesh.section(plane_origin=[safe_x, 0.0, 0.0], plane_normal=[1.0, 0.0, 0.0])
    if section is None or not section.discrete:
        return None
    path = max(section.discrete, key=lambda pts: len(pts))
    width = float(np.max(path[:, 1]) - np.min(path[:, 1]))
    top_z = float(np.max(path[:, 2]) - np.min(mesh.bounds[:, 2]))
    return width, top_z


def _write_comparison_report(
    path: Path,
    parameters: dict[str, Any],
    mesh: trimesh.Trimesh,
    hole_status: str,
) -> None:
    """Write target-vs-generated metrics for quick visual tuning."""

    core = parameters["core_dimensions_mm"]
    intent = parameters.get("cad_intent", {})
    bounds = mesh.bounds
    generated = {
        "L": float(bounds[1][0] - bounds[0][0]),
        "W": float(bounds[1][1] - bounds[0][1]),
        "H": float(bounds[1][2] - bounds[0][2]),
    }

    lines = [
        "# Wing tip parametric comparison",
        "",
        "## Bounding dimensions",
        "",
        "| Metric | Target mm | Generated mm | Delta mm |",
        "|---|---:|---:|---:|",
    ]
    for key in ("L", "W", "H"):
        target = float(core[key])
        value = generated[key]
        lines.append(f"| `{key}` | {target:.3f} | {value:.3f} | {value - target:.3f} |")

    lines.extend(
        [
            "",
            "## Station checks",
            "",
            "| Station | Target width | Generated width | Target top Z | Generated top Z |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    width_rows = intent.get("visual_plan_widths_mm") or parameters["plan_widths_mm"]
    side_rows = intent.get("side_profile_mm") or parameters["top_profile_mm"]
    stations = sorted({float(row["station_pct"]) for row in width_rows})
    for station in stations:
        x_mm = float(core["L"]) * station
        measured = _measure_section(mesh, x_mm)
        target_w = _interp_rows(width_rows, "width_mm", station)
        target_z = _interp_rows(side_rows, "z_top_mm", station)
        if measured is None:
            lines.append(f"| {station:.2f} | {target_w:.3f} | n/a | {target_z:.3f} | n/a |")
        else:
            width, top_z = measured
            lines.append(
                f"| {station:.2f} | {target_w:.3f} | {width:.3f} | "
                f"{target_z:.3f} | {top_z:.3f} |"
            )

    hole = parameters.get("hole_feature", {})
    lines.extend(
        [
            "",
            "## Hole feature",
            "",
            f"- Target diameter: `{hole.get('diameter_mm')}` mm",
            f"- Target center: `{hole.get('center_mm')}`",
            f"- Boolean status: `{hole_status or 'ok'}`",
            "",
            "## Notes",
            "",
            "- The rear wall is the first capped section at `x=0`.",
            "- The base is constrained to `z=0` in every section.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parametric_tip(
    parameters: dict[str, Any],
    ring_points: int = _RING_POINTS,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh, str]:
    """Build outer and final wing tip meshes from parameter JSON."""

    sections = _build_sections(parameters, ring_points)
    outer = build_strip_mesh(sections)
    final, hole_status = _cut_hole(outer, parameters)
    final.remove_unreferenced_vertices()
    final.fill_holes()
    if final.volume < 0:
        final.invert()
    final.fix_normals()
    return outer, final, hole_status


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=Path(_PARAMETERS_JSON))
    parser.add_argument("--ring-points", type=int, default=_RING_POINTS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    root = Path(__file__).resolve().parent
    params_path = (
        args.parameters if args.parameters.is_absolute() else root / args.parameters
    ).resolve()

    try:
        parameters = load_parameters(params_path)
        outer_mesh, final_mesh, hole_status = build_parametric_tip(
            parameters, int(args.ring_points)
        )
        outer_stl = root / _OUTER_STL
        final_stl = root / _FINAL_STL
        final_step = root / _FINAL_STEP
        outer_mesh.export(str(outer_stl))
        final_mesh.export(str(final_stl))
        _mesh_to_step(final_stl, final_step)
        _write_comparison_report(root / _REPORT_MD, parameters, final_mesh, hole_status)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 2

    print(
        "Generated parametric wing tip:\n"
        f"  {outer_stl}\n"
        f"  {final_stl}\n"
        f"  {final_step}\n"
        f"  {root / _REPORT_MD}\n"
        f"  hole_status={hole_status or 'ok'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
