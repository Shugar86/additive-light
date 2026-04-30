#!/usr/bin/env python3
"""Грубая проверка: габаритный ящик эталона Spiroid STEP и сгенерированного STEP."""

from __future__ import annotations

from pathlib import Path

from build123d import import_step


def _sizes_mm(shape_path: Path) -> tuple[float, float, float]:
    """Вычисляет Δx, Δy, Δz для STEP."""

    shape = import_step(str(shape_path.resolve()))
    bbox = shape.bounding_box()
    return (bbox.size.X, bbox.size.Y, bbox.size.Z)


def main() -> None:
    """Выводит сравнение ограничивающих размеров."""

    here = Path(__file__).resolve().parent
    ref_path = here / "Spiroid winglet left.step"
    gen_path = here / "wing_tip_light_left.step"

    rx, ry, rz = _sizes_mm(ref_path)
    gx, gy, gz = _sizes_mm(gen_path)

    print("Spiroid reference [mm]:", rx, ry, rz)
    print("Generated wing_tip    [mm]:", gx, gy, gz)
    dx = abs(gx - rx) / rx * 100 if rx else 0.0
    dy = abs(gy - ry) / ry * 100 if ry else 0.0
    dz = abs(gz - rz) / rz * 100 if rz else 0.0
    print(f"Relative delta [%]: span {dx:.1f}; breadth_y {dy:.1f}; height_z {dz:.1f}")


if __name__ == "__main__":
    main()
