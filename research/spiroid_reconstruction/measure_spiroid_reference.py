#!/usr/bin/env python3
"""Импорт эталонного Spiroid STEP и запись параметров ограничивающего параллепипеда."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from build123d import import_step


def measured_spec(ref_path: Path) -> dict:
    """Строит словарь с bbox эталона.

    Args:
        ref_path: Путь к эталону STEP.

    Returns:
        Словарь с числовыми полями габаритов.

    Raises:
        FileNotFoundError: Если файл не найден.
        RuntimeError: Если топология недоступна.
    """
    if not ref_path.is_file():
        raise FileNotFoundError(ref_path)

    logging.info("Loading STEP …")
    shape = import_step(str(ref_path.resolve()))
    bb = shape.bounding_box()
    cx = (bb.min.X + bb.max.X) / 2.0
    cy = (bb.min.Y + bb.max.Y) / 2.0
    cz = (bb.min.Z + bb.max.Z) / 2.0

    return {
        "units_mm": True,
        "reference_step": ref_path.name,
        "bounding_box_mm": {
            "min": [bb.min.X, bb.min.Y, bb.min.Z],
            "max": [bb.max.X, bb.max.Y, bb.max.Z],
        },
        "overall_mm": {
            "span_x": bb.size.X,
            "breadth_y": bb.size.Y,
            "height_z": bb.size.Z,
        },
        "mounting_datum": {
            "description": (
                "Корень у минимального X (крыла). Центроид ограничивающего блока задаёт середины эллипсов loft."
            ),
            "root_center_xyz_mm": [cx, cy, cz],
        },
    }


def main() -> None:
    """Измерить эталон и перезаписать wing_tip_spec.yaml (слияние с редакторскими параметрами)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    here = Path(__file__).resolve().parent
    ref = here / "Spiroid winglet left.step"

    merged = measured_spec(ref)

    merged["model"] = _default_model_block()
    merged["notes"] = [
        "Эталон — только оболочка (shell STEP). FreeCAD Part Design может визуально «мусолить» сеткой.",
        "Перед сменой крыла переизмерьте STEP и заново совместите ellipse scale в коде генератора.",
    ]

    out = here / "wing_tip_spec.yaml"
    if out.is_file():
        try:
            existing = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
            if isinstance(existing.get("model"), dict):
                merged["model"] = {**_default_model_block(), **existing["model"]}
        except OSError:
            logging.exception("Сохраняем дефолтный блок model.")

    out.write_text(
        yaml.safe_dump(merged, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logging.info("Wrote %s", out)


def _default_model_block() -> dict:
    """Значения по умолчанию для wing_tip_light_left.py."""

    return {
        "skin_mm": 1.2,
        "root_cap_solid_mm": 8.0,
        "min_wall_mm": 0.95,
        "outer_section_positions_pct_along_span": [0.02, 0.22, 0.45, 0.68, 0.96],
        "toe_deg_max_abs": 8.5,
        "cant_deg_max_abs": 3.9,
    }


if __name__ == "__main__":
    main()
