#!/usr/bin/env python3
"""Генерация наконечника крыла из ``sections_clean.json`` (mesh-strip + STL/STEP).

Цепочка v3: реальные сечения с эталона → внешний watertight-ish mesh → внутреннее
смещение (Shapely или радиальный fallback) → булева разность mesh.

Файлы::

  - ``wing_tip_outer_rebuild.stl`` / ``wing_tip_outer_rebuild.step`` — внешняя оболочка;
  - ``wing_tip_light_left.stl`` / ``wing_tip_light_left.step`` — после вычитания
    внутреннего тела (если boolean доступен).

Эллиптический loft v1 удалён; при необходимости старый режим храните в git.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path
from typing import Any

import yaml
from build123d import export_step, import_stl

from mesh_from_sections import (
    build_offset_sections,
    build_strip_mesh,
    load_sections_json,
    load_sections_meta,
    mesh_difference_or_none,
    radial_shrink_sections,
)


def load_spec(path: Path) -> dict[str, Any]:
    """Загрузка ``wing_tip_spec.yaml``."""

    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("YAML должен быть mapping.")
    return data


def mesh_to_step_face(mesh_path: Path, step_path: Path) -> None:
    """Импорт STL как ``Face`` и экспорт STEP (оболочка, не классический solid)."""

    face = import_stl(str(mesh_path.resolve()))
    export_step(face, str(step_path.resolve()))


def _fmt_volume_mm3(vol: Any) -> str:
    """Формат объёма для stdout без не-ASCII (консоль Windows)."""

    try:
        v = float(vol)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(v):
        return "nan"
    return f"{v:.1f}"


def main(argv: list[str] | None = None) -> int:
    """CLI."""

    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=Path("wing_tip_spec.yaml"))
    parser.add_argument(
        "--sections-json",
        type=Path,
        default=None,
        help="Путь к sections_clean.json (иначе из spec).",
    )
    parser.add_argument(
        "--outer-only",
        action="store_true",
        help="Только внешняя оболочка без вычитания полости.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    root = Path(__file__).resolve().parent
    spec_path = (args.spec if args.spec.is_absolute() else root / args.spec).resolve()

    try:
        spec = load_spec(spec_path)
    except (OSError, ValueError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 2

    sec_path = args.sections_json or spec.get("reconstruction", {}).get(
        "sections_clean_json", "sections_clean.json"
    )
    sections_file = (
        Path(sec_path) if Path(sec_path).is_absolute() else root / sec_path
    ).resolve()

    if not sections_file.is_file():
        logging.error("Нет файла сечений: %s (запустите extract_spiroid_sections.py)", sections_file)
        return 2

    meta = load_sections_meta(sections_file)
    ring_pts = int(meta.get("resample_points", 96))

    sections = load_sections_json(sections_file)
    outer_mesh = build_strip_mesh(sections)

    outer_stl = root / "wing_tip_outer_rebuild.stl"
    outer_mesh.export(str(outer_stl))
    mesh_to_step_face(outer_stl, root / "wing_tip_outer_rebuild.step")

    logging.info(
        "Outer mesh: watertight=%s volume=%.3f",
        outer_mesh.is_watertight,
        float(outer_mesh.volume),
    )

    if args.outer_only:
        print(
            f"Экспорт только внешней оболочки:\n  {outer_stl}\n  {root/'wing_tip_outer_rebuild.step'}"
        )
        return 0

    mdl = spec.get("model", {})
    skin_mm = float(mdl.get("skin_mm", 1.2))
    min_wall_mm = float(mdl.get("min_wall_mm", 0.95))

    inner_list, err_note = build_offset_sections(
        sections, skin_mm, min_wall_mm, ring_pts
    )

    if inner_list is None:
        logging.warning("Shapely offset не сработал (%s), пробуем radial_shrink.", err_note)
        inner_list = radial_shrink_sections(sections, skin_mm, ring_pts)

    inner_mesh = build_strip_mesh(inner_list)
    hollow, err_h = mesh_difference_or_none(outer_mesh, inner_mesh)

    final_stl = root / "wing_tip_light_left.stl"
    final_step = root / "wing_tip_light_left.step"

    if hollow is not None:
        hollow.export(str(final_stl))
        mesh_to_step_face(final_stl, final_step)
        print(
            f"Готово (hollow):\n  {final_stl}\n  {final_step}\n  volume~{_fmt_volume_mm3(hollow.volume)} mm3 err={err_h!r}"
        )
    else:
        outer_mesh.export(str(final_stl))
        mesh_to_step_face(final_stl, final_step)
        print(
            f"Boolean не удался ({err_h}); скопирован внешний STL как финал:\n  {final_stl}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
