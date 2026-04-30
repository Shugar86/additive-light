#!/usr/bin/env python3
"""Извлечение 25–45 плоских сечений эталонного shell STEP через тесселяцию в mesh.

Сохраняет:
  - ``reference_mesh_preview.stl`` — проверка формы;
  - ``sections_raw.json`` — сырые контуры;
  - ``sections_clean.json`` — очищенные, ресэмплированные контуры + метаданные;
  - ``sections_report.md`` — краткий отчёт.

Требует ``networkx`` (trimesh traversal), ``trimesh``, ``numpy``, ``build123d``.
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
from build123d import export_stl, import_step

_STL_TOLERANCE_MM = 0.35
_STL_ANGULAR_TOL = 0.25
_SECTION_COUNT = 37
_RESAMPLE_POINTS = 96
_EDGE_MARGIN_MM = 1.5


def _arc_length_resample_closed(
    points_yz: np.ndarray, num: int
) -> np.ndarray:
    """Равномерный ресэмпл по длине дуги для замкнутого полигона.

    Args:
        points_yz: Массив формы ``(n, 2)``, первая точка не обязана дублировать последнюю.
        num: Целевое число вершин.

    Returns:
        Массив формы ``(num, 2)`` без дублирования замыкания.
    """

    poly = np.asarray(points_yz, dtype=np.float64)
    if len(poly) < 3:
        raise ValueError("Нужно минимум три точки.")
    if not np.allclose(poly[0], poly[-1]):
        poly = np.vstack([poly, poly[0:1]])
    edge_len = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    total = float(np.sum(edge_len))
    if total < 1e-9:
        raise ValueError("Нулевая длина контура.")
    cum = np.concatenate([[0.0], np.cumsum(edge_len)])
    targets = np.linspace(0.0, total, num, endpoint=False)
    resampled = np.zeros((num, 2), dtype=np.float64)
    j = 0
    for i, t in enumerate(targets):
        while j + 1 < len(cum) and cum[j + 1] < t:
            j += 1
        if j + 1 >= len(cum):
            j = len(cum) - 2
        seg_start = cum[j]
        seg_end = cum[j + 1]
        alpha = 0.0 if seg_end <= seg_start else (t - seg_start) / (seg_end - seg_start)
        resampled[i] = (1.0 - alpha) * poly[j] + alpha * poly[j + 1]
    return resampled


def _signed_area_yz(points_yz: np.ndarray) -> float:
    """Знак площади для ориентации обхода (CCW > 0)."""

    x = points_yz[:, 0]
    y = points_yz[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def _longest_discrete_path(section: trimesh.path.Path3D) -> np.ndarray | None:
    """Возвращает longest closed loop из ``Path3D.discrete``."""

    if section is None:
        return None
    paths = section.discrete
    if not paths:
        return None
    best: np.ndarray | None = None
    best_len = -1.0
    for path in paths:
        if len(path) < 3:
            continue
        plen = float(
            np.sum(np.linalg.norm(np.diff(np.vstack([path, path[0:1]]), axis=0), axis=1))
        )
        if plen > best_len:
            best_len = plen
            best = path
    return best


def _section_yz_at_x(
    mesh: trimesh.Trimesh, x_plane: float
) -> tuple[np.ndarray | None, str | None]:
    """Сечение mesh плоскостью X=const; возвращает Nx2 (y,z) в мировых координатах."""

    sec = mesh.section(
        plane_origin=[float(x_plane), 0.0, 0.0],
        plane_normal=[1.0, 0.0, 0.0],
    )
    path3 = _longest_discrete_path(sec) if sec is not None else None
    if path3 is None:
        return None, "empty_section"
    yz = path3[:, 1:3].copy()
    return yz, None


def _x_positions(xmin: float, xmax: float, n: int) -> list[float]:
    """Неравномерная сетка: плотнее у концов за счёт косинуса."""

    span = xmax - xmin - 2.0 * _EDGE_MARGIN_MM
    if span <= 0:
        raise ValueError("Слишком узкий диапазон после margin.")
    t = np.linspace(0.0, 1.0, n)
    u = 0.5 - 0.5 * np.cos(math.pi * t)
    return [float(xmin + _EDGE_MARGIN_MM + span * float(ui)) for ui in u]


def run_extract(
    here: Path,
    section_count: int,
    resample_n: int,
    stl_tolerance: float,
) -> dict[str, Any]:
    """Выполняет извлечение и возвращает метаданные для JSON."""

    ref_step = here / "Spiroid winglet left.step"
    if not ref_step.is_file():
        raise FileNotFoundError(ref_step)

    logging.info("Импорт STEP …")
    shape = import_step(str(ref_step.resolve()))
    stl_path = here / "reference_mesh_preview.stl"
    logging.info("Тесселяция → %s (tolerance=%.3f mm)", stl_path.name, stl_tolerance)
    export_stl(
        shape,
        str(stl_path),
        tolerance=stl_tolerance,
        angular_tolerance=_STL_ANGULAR_TOL,
    )

    mesh = trimesh.load(str(stl_path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    bounds = mesh.bounds
    xmin, xmax = float(bounds[0][0]), float(bounds[1][0])
    xs = _x_positions(xmin, xmax, section_count)

    raw_sections: list[dict[str, Any]] = []
    clean_sections: list[dict[str, Any]] = []
    warnings: list[str] = []

    for idx, x_plane in enumerate(xs):
        yz, err = _section_yz_at_x(mesh, x_plane)
        if yz is None or err:
            warnings.append(f"x={x_plane:.3f}: {err or 'failed'}")
            continue
        if _signed_area_yz(yz) < 0:
            yz = yz[::-1]
        cy = float(np.mean(yz[:, 0]))
        cz = float(np.mean(yz[:, 1]))
        local = np.column_stack([yz[:, 0] - cy, yz[:, 1] - cz])
        try:
            smooth = _arc_length_resample_closed(local, resample_n)
        except ValueError as exc:
            warnings.append(f"x={x_plane:.3f}: resample {exc}")
            continue

        raw_sections.append(
            {
                "index": idx,
                "plane_x_mm": x_plane,
                "point_count": int(len(yz)),
                "points_yz_mm": yz.tolist(),
            }
        )
        clean_sections.append(
            {
                "index": idx,
                "plane_x_mm": x_plane,
                "centroid_y_mm": cy,
                "centroid_z_mm": cz,
                "points_sketch_uv_mm": smooth.tolist(),
            }
        )

    meta = {
        "source_step": ref_step.name,
        "mesh_stl": stl_path.name,
        "stl_tolerance_mm": stl_tolerance,
        "angular_tolerance_rad": _STL_ANGULAR_TOL,
        "section_count_requested": section_count,
        "section_count_ok": len(clean_sections),
        "resample_points": resample_n,
        "bbox_x_mm": [xmin, xmax],
        "warnings": warnings,
    }

    (here / "sections_raw.json").write_text(
        json.dumps({"meta": meta, "sections": raw_sections}, indent=2),
        encoding="utf-8",
    )
    clean_blob = {"meta": meta, "sections": clean_sections}
    (here / "sections_clean.json").write_text(
        json.dumps(clean_blob, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# Отчёт по сечениям spiroid",
        "",
        f"- Исходный STEP: `{ref_step.name}`",
        f"- Preview mesh: `{stl_path.name}`",
        f"- Запрошено сечений: {section_count}, успешно: {len(clean_sections)}",
        f"- Ресэмплирование контурка: **{resample_n}** точек",
        "",
        "## Предупреждения",
    ]
    if warnings:
        for w in warnings:
            report_lines.append(f"- {w}")
    else:
        report_lines.append("- (нет)")
    report_lines.extend(["", "## Диапазон X мм", "", f"[{xmin:.3f}, {xmax:.3f}]"])
    (here / "sections_report.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    return meta


def main() -> int:
    """CLI."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sections",
        type=int,
        default=_SECTION_COUNT,
        help="Число плоскостей X (по умолчанию 37).",
    )
    parser.add_argument(
        "--resample",
        type=int,
        default=_RESAMPLE_POINTS,
        help="Число вершин на контур после выравнивания.",
    )
    parser.add_argument(
        "--stl-tolerance",
        type=float,
        default=_STL_TOLERANCE_MM,
        help="Линейный допуск тесселя STEP→STL мм.",
    )
    args = parser.parse_args()

    try:
        here = Path(__file__).resolve().parent
        run_extract(here, args.sections, args.resample, args.stl_tolerance)
        logging.info("Готово: sections_clean.json, sections_raw.json, sections_report.md")
        return 0
    except (OSError, ValueError, FileNotFoundError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
