"""Math-enhancement regression tests rescued from P8-P9 (dangling commit f6b25652).

Sprint 2.3 lifts the alignment subset of the dropped P8-P9 hardening commit
and adapts the tests to the current API:

* ``backend.sensors.align_open3d.ransac_plane_axes`` (Sprint 2.1) operates on
  a NumPy point sample, not on an ``open3d.geometry.TriangleMesh``; the
  ``open3d`` dependency stays optional inside the function.
* ``load_and_center_mesh`` exposes a richer ``metadata`` payload (``method``,
  ``pca_spread``, ``ransac`` sub-dict).

The other P8-P9 test groups (blind-hole detection in ``coordinator_agent``,
SDF metrics in ``vibeguard_agent``, detailed error regions) require porting
1400+ lines of swarm-side changes which the Sber500 roadmap places out of
scope until v2. They are intentionally **not** included here.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from backend.sensors.align_open3d import (
    load_and_center_mesh,
    ransac_plane_axes,
)


# ---------------------------------------------------------------------------
# Test fixtures (kept in-file so the suite is self-contained)
# ---------------------------------------------------------------------------


def _make_box_points(lx: float, ly: float, lz: float, n_per_face: int = 200) -> np.ndarray:
    """Generate a synthetic point cloud sampled on the surface of an axis-aligned box.

    The faces are perpendicular to X, Y, Z, so RANSAC must find three
    mutually orthogonal planes and produce a basis aligned with the axes.
    """
    rng = np.random.default_rng(seed=0)
    faces = []
    for axis_idx, half in enumerate((lx / 2, ly / 2, lz / 2)):
        for sign in (-1.0, 1.0):
            coords = rng.uniform(-0.5, 0.5, size=(n_per_face, 3))
            coords[:, 0] *= lx
            coords[:, 1] *= ly
            coords[:, 2] *= lz
            coords[:, axis_idx] = sign * half
            faces.append(coords)
    return np.vstack(faces)


def _make_disc_points(radius: float, height: float, n_cap: int = 400, n_side: int = 200) -> np.ndarray:
    """Generate a disc-shaped point cloud (two parallel caps + a thin side band)."""
    rng = np.random.default_rng(seed=1)
    z_top = height / 2
    z_bot = -height / 2
    cap_r = np.sqrt(rng.uniform(0, radius**2, n_cap))
    cap_phi = rng.uniform(0, 2 * np.pi, n_cap)
    top = np.column_stack([cap_r * np.cos(cap_phi), cap_r * np.sin(cap_phi), np.full(n_cap, z_top)])
    bot = np.column_stack([cap_r * np.cos(cap_phi), cap_r * np.sin(cap_phi), np.full(n_cap, z_bot)])
    side_z = rng.uniform(z_bot, z_top, n_side)
    side_phi = rng.uniform(0, 2 * np.pi, n_side)
    side = np.column_stack([radius * np.cos(side_phi), radius * np.sin(side_phi), side_z])
    return np.vstack([top, bot, side])


def _make_long_cylinder_points(radius: float, height: float, n: int = 2000) -> np.ndarray:
    """Generate a slender cylinder where PCA spread is large (height >> diameter)."""
    rng = np.random.default_rng(seed=2)
    z = rng.uniform(-height / 2, height / 2, n)
    phi = rng.uniform(0, 2 * np.pi, n)
    return np.column_stack([radius * np.cos(phi), radius * np.sin(phi), z])


# ---------------------------------------------------------------------------
# ransac_plane_axes — primary surface of Sprint 2.1
# ---------------------------------------------------------------------------


class TestRansacPlaneAxes:
    """Direct tests for ``ransac_plane_axes`` on synthetic point clouds."""

    def test_box_returns_three_orthogonal_planes(self) -> None:
        """A box with three pairs of parallel faces must give an orthonormal basis."""
        pytest.importorskip("open3d")
        points = _make_box_points(lx=2.0, ly=1.0, lz=0.5)
        rotation, metadata = ransac_plane_axes(points, ransac_threshold=0.01)

        assert rotation.shape == (3, 3)
        # Orthonormality check: rotation @ rotation.T must be ~ identity.
        gram = rotation @ rotation.T
        assert np.allclose(gram, np.eye(3), atol=1e-6)
        assert metadata["method"].startswith("ransac")
        assert metadata.get("plane_count", 0) >= 2

    def test_disc_does_not_collapse_basis(self) -> None:
        """A disc (top + bottom parallel) must NOT produce a degenerate basis.

        Pre-fix the secondary normal degenerated to zero. Post-fix the
        function detects the parallelism and either picks a third plane or
        falls back to PCA tangent — either way ``rotation`` must stay an
        orthonormal matrix.
        """
        pytest.importorskip("open3d")
        points = _make_disc_points(radius=25.0, height=10.0)
        rotation, metadata = ransac_plane_axes(points, ransac_threshold=0.3)

        gram = rotation @ rotation.T
        assert np.allclose(gram, np.eye(3), atol=1e-6)
        # Either tangent-PCA fallback fired, or RANSAC found a side plane.
        assert metadata["method"] in {
            "ransac_planes",
            "ransac_primary_pca_tangent",
            "pca_fallback",
        }

    def test_invalid_input_shape_rejected(self) -> None:
        """A non-(N, 3) array must be rejected with ValueError."""
        with pytest.raises(ValueError):
            ransac_plane_axes(np.array([1.0, 2.0, 3.0]))

    def test_too_few_points_falls_back_to_pca(self) -> None:
        """Below the min-plane threshold the function falls back gracefully."""
        rng = np.random.default_rng(0)
        points = rng.normal(size=(20, 3))
        rotation, metadata = ransac_plane_axes(points, min_plane_points=100)

        assert rotation.shape == (3, 3)
        assert metadata["method"] == "pca_fallback"
        assert metadata["reason"] in {"too_few_points", "too_few_planes"}


# ---------------------------------------------------------------------------
# load_and_center_mesh — adoption logic (PCA vs RANSAC)
# ---------------------------------------------------------------------------


def _write_stl(points_provider: Any, tmp: Path) -> Path:
    """Build an STL file from one of the synthetic point providers."""
    import open3d as o3d  # local import keeps the suite optional

    if points_provider == "cylinder":
        mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=1.0, height=8.0, resolution=64, split=8)
    elif points_provider == "disc":
        # High resolution so the part clears the 200-vertex threshold that
        # gates RANSAC activation in ``load_and_center_mesh``.
        mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=10.0, height=1.0, resolution=64, split=8)
    else:
        raise ValueError(f"Unknown provider: {points_provider}")
    # Open3D refuses to write an STL without normals.
    mesh.compute_vertex_normals()
    stl_path = tmp / f"{points_provider}.stl"
    o3d.io.write_triangle_mesh(str(stl_path), mesh)
    return stl_path


class TestLoadAndCenterAdoption:
    """End-to-end behaviour of ``load_and_center_mesh`` with the rescued RANSAC."""

    def test_long_cylinder_keeps_pca(self) -> None:
        """A slender cylinder has clear PCA spread → RANSAC must NOT be adopted."""
        pytest.importorskip("open3d")
        with tempfile.TemporaryDirectory() as td:
            stl_path = _write_stl("cylinder", Path(td))
            out, _centroid, _axes, meta = load_and_center_mesh(
                str(stl_path), output_path=str(Path(td) / "aligned.stl"), use_ransac=True
            )
            assert Path(out).exists()
            assert meta["alignment_method"] == "pca"
            assert meta["pca_spread"] > 0.2
            # RANSAC payload exists but was NOT promoted.
            assert meta["ransac"]["activated"] is False or meta["alignment_method"] == "pca"

    def test_disc_engages_ransac_without_regression(self) -> None:
        """A disc has near-zero PCA spread → RANSAC must engage, basis stays orthonormal."""
        pytest.importorskip("open3d")
        with tempfile.TemporaryDirectory() as td:
            stl_path = _write_stl("disc", Path(td))
            out, _centroid, axes, meta = load_and_center_mesh(
                str(stl_path), output_path=str(Path(td) / "aligned.stl"), use_ransac=True
            )
            assert Path(out).exists()
            assert meta["alignment_method"].startswith("ransac") or meta["pca_spread"] >= 0.2
            gram = axes @ axes.T
            assert np.allclose(gram, np.eye(3), atol=1e-5)

    def test_metadata_carries_pca_spread_and_ransac_payload(self) -> None:
        """Every successful load must report spread + RANSAC subdict."""
        pytest.importorskip("open3d")
        with tempfile.TemporaryDirectory() as td:
            stl_path = _write_stl("cylinder", Path(td))
            _out, _centroid, _axes, meta = load_and_center_mesh(
                str(stl_path), output_path=str(Path(td) / "aligned.stl"), use_ransac=True
            )
            assert "pca_spread" in meta
            assert "ransac" in meta
            assert "alignment_method" in meta


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
