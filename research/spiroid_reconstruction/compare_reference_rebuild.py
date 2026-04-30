#!/usr/bin/env python3
"""Сравнение эталонного mesh (preview STL) и пересобранной внешней оболочки.

Метрики: bbox, объём, двунаправленная выборка поверхности → расстояние до другой
оболочки (mean / percentiles / max). Результат — ``comparison_report.md``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
import yaml


@dataclass(frozen=True)
class SurfaceDistanceStats:
    """Статистика расстояний от точек на mesh_a до ближайшей поверхности mesh_b."""

    mean_mm: float
    p50_mm: float
    p95_mm: float
    p99_mm: float
    max_mm: float
    samples: int


def load_yaml(path: Path) -> dict[str, Any]:
    """Загрузка YAML в mapping."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Ожидался YAML mapping.")
    return data


def bbox_dict(mesh: trimesh.Trimesh) -> dict[str, list[float]]:
    """Ограничивающий параллелепипед mesh в мм."""

    bb = mesh.bounds
    return {"min": [float(x) for x in bb[0]], "max": [float(x) for x in bb[1]]}


def surface_to_mesh_distances(
    mesh_from: trimesh.Trimesh, mesh_to: trimesh.Trimesh, sample_count: int
) -> SurfaceDistanceStats:
    """Расстояния от случайных точек на ``mesh_from`` до ``mesh_to``."""

    if sample_count < 100:
        raise ValueError("sample_count слишком мал.")
    points, _face_id = trimesh.sample.sample_surface(mesh_from, sample_count)
    _closest, distances, _tid = mesh_to.nearest.on_surface(points)
    d = np.asarray(distances, dtype=np.float64)
    return SurfaceDistanceStats(
        mean_mm=float(np.mean(d)),
        p50_mm=float(np.percentile(d, 50)),
        p95_mm=float(np.percentile(d, 95)),
        p99_mm=float(np.percentile(d, 99)),
        max_mm=float(np.max(d)),
        samples=int(len(d)),
    )


def write_report(
    path: Path,
    reference_path: Path,
    rebuild_path: Path,
    ref_mesh: trimesh.Trimesh,
    rb_mesh: trimesh.Trimesh,
    a_to_b: SurfaceDistanceStats,
    b_to_a: SurfaceDistanceStats,
    tolerance_mm: float,
) -> None:
    """Записывает markdown-отчёт."""

    lines = [
        "# Сравнение эталон vs rebuild (mesh)",
        "",
        f"- Эталон: `{reference_path.name}`",
        f"- Rebuild: `{rebuild_path.name}`",
        f"- Порог tolerance (из spec): **{tolerance_mm:.3f} mm**",
        "",
        "## Bounding box (mm)",
        "",
        "### Reference",
        f"```\n{bbox_dict(ref_mesh)}\n```",
        "",
        "### Rebuild",
        f"```\n{bbox_dict(rb_mesh)}\n```",
        "",
        "## Объём (mesh encloses, mm³)",
        "",
        f"- Reference: {float(ref_mesh.volume):.3f}",
        f"- Rebuild: {float(rb_mesh.volume):.3f}",
        "",
        "## Расстояние поверхность → поверхность",
        "",
        "Точки на поверхности A, ближайшая точка на B.",
        "",
        f"### A = reference → B = rebuild ({a_to_b.samples} samples)",
        "",
        f"| mean | p50 | p95 | p99 | max |",
        f"| --- | --- | --- | --- | --- |",
        f"| {a_to_b.mean_mm:.4f} | {a_to_b.p50_mm:.4f} | {a_to_b.p95_mm:.4f} | "
        f"{a_to_b.p99_mm:.4f} | {a_to_b.max_mm:.4f} |",
        "",
        f"### A = rebuild → B = reference ({b_to_a.samples} samples)",
        "",
        f"| mean | p50 | p95 | p99 | max |",
        f"| --- | --- | --- | --- | --- |",
        f"| {b_to_a.mean_mm:.4f} | {b_to_a.p50_mm:.4f} | {b_to_a.p95_mm:.4f} | "
        f"{b_to_a.p99_mm:.4f} | {b_to_a.max_mm:.4f} |",
        "",
        "## Вердикт",
        "",
    ]
    combined_max = max(a_to_b.max_mm, b_to_a.max_mm)
    if combined_max <= tolerance_mm:
        lines.append(
            f"**PASS:** max двунаправленного отклонения **{combined_max:.4f} mm** "
            f"≤ {tolerance_mm:.3f} mm."
        )
    else:
        lines.append(
            f"**REVIEW:** max двунаправленного отклонения **{combined_max:.4f} mm** "
            f"> {tolerance_mm:.3f} mm — уточнить сетку/сечения/ремонт mesh."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI."""

    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=Path("wing_tip_spec.yaml"))
    parser.add_argument(
        "--reference-stl",
        type=Path,
        default=None,
        help="STL эталона (иначе reconstruction.reference_preview_stl в spec).",
    )
    parser.add_argument(
        "--rebuild-stl",
        type=Path,
        default=None,
        help="STL rebuild (иначе reconstruction.rebuilt_outer_stl).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        help="Число точек выборки на направление (иначе из spec).",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    root = Path(__file__).resolve().parent
    spec_path = args.spec if args.spec.is_absolute() else root / args.spec

    try:
        spec = load_yaml(spec_path.resolve())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 2

    reco = spec.get("reconstruction", {})
    if not isinstance(reco, dict):
        reco = {}

    ref_name = (
        args.reference_stl.name
        if args.reference_stl
        else reco.get("reference_preview_stl", "reference_mesh_preview.stl")
    )
    rb_name = (
        args.rebuild_stl.name if args.rebuild_stl else reco.get("rebuilt_outer_stl", "wing_tip_outer_rebuild.stl")
    )

    reference_stl = (
        Path(args.reference_stl).resolve()
        if args.reference_stl is not None
        else root / ref_name
    )
    rebuild_stl = (
        Path(args.rebuild_stl).resolve()
        if args.rebuild_stl is not None
        else root / rb_name
    )

    tol = float(reco.get("tolerance_comparison_mm", reco.get("tolerance_mm", 1.0)))
    n_samples = int(
        args.samples
        if args.samples is not None
        else reco.get("comparison_sample_count", 12000)
    )

    for label, path in (("reference", reference_stl), ("rebuild", rebuild_stl)):
        if not path.is_file():
            logging.error("Нет файла (%s): %s", label, path)
            return 2

    try:
        ref_mesh = trimesh.load(str(reference_stl), force="mesh")
        rb_mesh = trimesh.load(str(rebuild_stl), force="mesh")
    except (OSError, ValueError) as exc:
        logging.error("Загрузка STL: %s: %s", type(exc).__name__, exc)
        return 2

    if not isinstance(ref_mesh, trimesh.Trimesh) or not isinstance(rb_mesh, trimesh.Trimesh):
        logging.error("Ожидался Trimesh после load.")
        return 2

    ref_mesh.remove_unreferenced_vertices()
    rb_mesh.remove_unreferenced_vertices()

    a_to_b = surface_to_mesh_distances(ref_mesh, rb_mesh, n_samples)
    b_to_a = surface_to_mesh_distances(rb_mesh, ref_mesh, n_samples)

    out_md = root / "comparison_report.md"
    try:
        write_report(
            out_md,
            reference_stl,
            rebuild_stl,
            ref_mesh,
            rb_mesh,
            a_to_b,
            b_to_a,
            tol,
        )
    except OSError as exc:
        logging.error("Запись отчёта: %s: %s", type(exc).__name__, exc)
        return 2

    print(f"Отчёт: {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
