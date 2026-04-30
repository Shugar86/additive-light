#!/usr/bin/env python3
"""Построение закрытых триангуляционных оболочек из ``sections_clean.json``.

Реализация: боковые грани между кольцами + крышки (``triangle.c`` через
``trimesh.creation.triangulate_polygon``). Альтернатива нестабильному OCCT loft
на длинном spiroid.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPoly
from trimesh.creation import triangulate_polygon


def _yz_cap_mesh(x_plane: float, ring_yz: np.ndarray, flip_normals: bool) -> trimesh.Trimesh:
    """Триангулированная крышка в плоскости постоянного X."""

    poly = ShapelyPoly([(float(p[0]), float(p[1])) for p in ring_yz])
    # Не добавлять Steiner–точки (иначе край триангуляции разъехался бы с вершинами
    # кольца в бандах). Earcut режет только по контуру экстерьера polygon.
    verts2d, faces = triangulate_polygon(poly, engine="earcut")
    vertices_3 = np.column_stack(
        [
            np.full(len(verts2d), float(x_plane), dtype=np.float64),
            verts2d[:, 0],
            verts2d[:, 1],
        ]
    )
    cap_mesh = trimesh.Trimesh(
        vertices_3,
        faces.astype(np.int64),
        process=True,
        validate=False,
    )
    if flip_normals:
        cap_mesh.invert()
    return cap_mesh


def arc_length_resample_closed(points_xy: np.ndarray, num: int) -> np.ndarray:
    """Ресэмплирование замкнутого полигона по длине дуги (2D плоскость)."""

    poly = np.asarray(points_xy, dtype=np.float64)
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


def load_sections_json(path: Path) -> list[dict[str, Any]]:
    """Загружает и сортирует сечения."""

    blob = json.loads(path.read_text(encoding="utf-8"))
    secs = blob["sections"]
    return sorted(secs, key=lambda s: float(s["plane_x_mm"]))


def load_sections_meta(path: Path) -> dict[str, Any]:
    """Читает ``meta`` из ``sections_clean.json``."""

    blob = json.loads(path.read_text(encoding="utf-8"))
    meta = blob.get("meta", {})
    return meta if isinstance(meta, dict) else {}


def global_points_yz(section: dict[str, Any]) -> tuple[np.ndarray, float]:
    """Глобальные точки контура в YZ и X плоскости."""

    xp = float(section["plane_x_mm"])
    cy = float(section["centroid_y_mm"])
    cz = float(section["centroid_z_mm"])
    yz = np.array(
        [[cy + float(u), cz + float(v)] for u, v in section["points_sketch_uv_mm"]],
        dtype=np.float64,
    )
    return yz, xp


def build_strip_mesh(sections: list[dict[str, Any]]) -> trimesh.Trimesh:
    """Оболочка: банда между кольцами и две крышки."""

    if len(sections) < 2:
        raise ValueError("Нужно минимум два сечения.")

    ring_n = len(sections[0]["points_sketch_uv_mm"])
    if any(len(s["points_sketch_uv_mm"]) != ring_n for s in sections):
        raise ValueError("Разное число вершин между кольцами.")

    nb = len(sections)
    rings_yz: list[np.ndarray] = []

    for s in sections:
        yz, _ = global_points_yz(s)
        rings_yz.append(yz)

    verts_band: list[list[float]] = []
    for s in sections:
        yz, _ = global_points_yz(s)
        for yy, zz in yz:
            verts_band.append([float(s["plane_x_mm"]), float(yy), float(zz)])

    band_vertices = np.asarray(verts_band, dtype=np.float64)
    band_faces: list[list[int]] = []

    for ix in range(nb - 1):
        for ks in range(ring_n):
            ks_n = (ks + 1) % ring_n
            i0 = ix * ring_n + ks
            i1 = ix * ring_n + ks_n
            j0 = (ix + 1) * ring_n + ks
            j1 = (ix + 1) * ring_n + ks_n
            band_faces.append([i0, i1, j1])
            band_faces.append([i0, j1, j0])

    side_mesh = trimesh.Trimesh(
        band_vertices,
        np.asarray(band_faces, dtype=np.int64),
        process=True,
        validate=False,
    )

    x_first = float(sections[0]["plane_x_mm"])
    x_last = float(sections[-1]["plane_x_mm"])
    cap_front = _yz_cap_mesh(x_first, rings_yz[0], flip_normals=True)
    cap_back = _yz_cap_mesh(x_last, rings_yz[-1], flip_normals=False)

    combined = trimesh.util.concatenate([side_mesh, cap_front, cap_back])
    combined.merge_vertices(digits_vertex=6)
    combined.remove_unreferenced_vertices()
    combined.fill_holes()
    if combined.volume < 0:
        combined.invert()
    combined.fix_normals()
    return combined


def build_offset_sections(
    sections: list[dict[str, Any]],
    skin_mm: float,
    min_wall_mm: float,
    ring_pts: int,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Внутренние секции методом буфера Shapely в плоскости YZ."""

    inner: list[dict[str, Any]] = []
    skin = float(skin_mm)

    for s in sections:
        yz_pts, xp = global_points_yz(s)
        shell_pts = [(float(p[0]), float(p[1])) for p in yz_pts]

        exterior = ShapelyPoly(shell_pts)
        shrunk = exterior.buffer(-skin, join_style=2, mitre_limit=3.5)

        if shrunk.is_empty:
            return None, f"buffer-empty-x≈{xp:.2f}"

        if shrunk.geom_type == "Polygon":
            polys = [shrunk]
        elif shrunk.geom_type == "MultiPolygon":
            polys = list(shrunk.geoms)
        else:
            return None, f"buffer-badgeom-x≈{xp}"

        polygon = max(polys, key=lambda gg: gg.area)
        if polygon.area < float(min_wall_mm) ** 2 * 16.0:
            return None, f"buffer-small-x≈{xp}"

        boundary = np.asarray(polygon.exterior.coords[:-1], dtype=np.float64)
        resampled = (
            arc_length_resample_closed(boundary, ring_pts)
            if len(boundary) != ring_pts
            else boundary
        )

        c_y = float(np.mean(resampled[:, 0]))
        c_z = float(np.mean(resampled[:, 1]))
        pts_uv = [[float(r[0] - c_y), float(r[1] - c_z)] for r in resampled]

        inner.append(
            {
                "plane_x_mm": float(xp),
                "centroid_y_mm": c_y,
                "centroid_z_mm": c_z,
                "points_sketch_uv_mm": pts_uv,
            }
        )

    return inner, None


def radial_shrink_sections(
    sections: list[dict[str, Any]],
    skin_mm: float,
    ring_pts: int,
) -> list[dict[str, Any]]:
    """Fallback: радиальное поджимание узлов контура от центроида кольца."""

    skin = float(skin_mm)
    out_s: list[dict[str, Any]] = []

    for s in sections:
        yz_pts, xp = global_points_yz(s)
        cy = float(np.mean(yz_pts[:, 0]))
        cz = float(np.mean(yz_pts[:, 1]))
        offs = yz_pts - np.array([cy, cz], dtype=np.float64)
        radi = np.linalg.norm(offs, axis=1)
        rf = float(np.max(radi)) if len(radi) else skin + 1.0
        factor = max(0.06, min(0.995, (rf - skin) / (rf + 1e-9)))
        yz_new = np.array([cy, cz], dtype=np.float64) + factor * offs
        yz_sm = arc_length_resample_closed(yz_new, ring_pts) if yz_new.shape[0] != ring_pts else yz_new
        cy_n = float(np.mean(yz_sm[:, 0]))
        cz_n = float(np.mean(yz_sm[:, 1]))
        uv_rows = [[float(r[0] - cy_n), float(r[1] - cz_n)] for r in yz_sm]

        out_s.append(
            {
                "plane_x_mm": float(xp),
                "centroid_y_mm": cy_n,
                "centroid_z_mm": cz_n,
                "points_sketch_uv_mm": uv_rows,
                "fallback_radial_scale": factor,
            }
        )

    return out_s


def mesh_difference_or_none(
    outer: trimesh.Trimesh, inner_mesh: trimesh.Trimesh
) -> tuple[trimesh.Trimesh | None, str]:
    """Разность meshes (внешняя минус внутреннее)."""

    for eng in ("manifold", None):
        try:
            # ``meshes[0] - meshes[1:]`` — один список, не два аргумента.
            result = trimesh.boolean.difference(
                [outer, inner_mesh], engine=eng, check_volume=False
            )
            if hasattr(result, "fill_holes"):
                result.fill_holes()
            result.remove_unreferenced_vertices()
            if result.volume < 0:
                result.invert()
            return result, ""
        except Exception as exc:
            logging.warning("boolean [%s]: %s: %s", eng, type(exc).__name__, exc)

    return None, "boolean-failed"

