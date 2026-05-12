"""Generate benchmark STL files for revolution bodies test suite.

Run once to populate ``benchmark_kit/`` and ``tests/fixtures/``::

    python scripts/generate_benchmark_stl.py

Sprint 1.3 adds six "evil-shafts" that cover the full ``scope v1`` palette
of revolution features (chamfers, fillets, cones, barrels, hourglasses,
short discs). Every new shaft is generated from an explicit ``r(z)`` profile
so the ground truth radii / segment boundaries are known exactly. This is
what powers the Sprint 2 arc-gap acceptance test and the Sber500 metrics
slide.

The generator deliberately depends on **trimesh only** (no build123d, no
open3d) so it remains the cheapest path to grow the bench during R&D.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

try:
    import trimesh
except ImportError:
    print("Error: trimesh not installed. Run: pip install trimesh")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Profile → revolution mesh helper (used by Sprint 1.3 shafts)
# ---------------------------------------------------------------------------


@dataclass
class ProfilePoint:
    """One sample on the meridian curve of a revolution body."""

    z: float
    r: float


def _ring(z: float, r: float, sections: int) -> np.ndarray:
    """Generate ``sections`` 3-D vertices forming a circle of radius ``r`` at height ``z``."""
    angles = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    return np.column_stack([r * np.cos(angles), r * np.sin(angles), np.full(sections, z)])


def revolve_profile(
    profile: Sequence[ProfilePoint],
    sections: int = 128,
) -> trimesh.Trimesh:
    """Build a closed revolution body from an ordered meridian profile.

    The profile is a list of ``(z, r)`` samples with ``r >= 0`` and monotonic
    ``z``. The function rotates the polyline around the z-axis, triangulates
    the resulting surface and caps any non-axis end-rings.

    Args:
        profile: Ordered meridian samples from bottom to top.
        sections: Number of angular subdivisions (default 128).

    Returns:
        A water-tight ``trimesh.Trimesh`` representing the revolution body.

    Raises:
        ValueError: If the profile has fewer than two points, any radius is
            negative, or ``z`` is not strictly increasing.
    """
    if len(profile) < 2:
        raise ValueError("Profile must have at least two points")
    for i, p in enumerate(profile):
        if p.r < 0:
            raise ValueError(f"Profile point {i} has negative radius {p.r}")
    zs = [p.z for p in profile]
    if any(zs[i] >= zs[i + 1] for i in range(len(zs) - 1)):
        raise ValueError("Profile z-values must be strictly increasing")

    vertices: List[np.ndarray] = []
    faces: List[Tuple[int, int, int]] = []
    # Side surface: a ring of ``sections`` vertices per profile sample.
    for p in profile:
        if p.r > 1e-9:
            vertices.append(_ring(p.z, p.r, sections))
        else:
            # Degenerate ring on the axis — collapse to a single apex vertex
            # so triangulation does not produce zero-area triangles.
            vertices.append(np.array([[0.0, 0.0, p.z]]))
    # Compute index offsets for each ring (may be 1 for apex rings).
    offsets = np.cumsum([0] + [v.shape[0] for v in vertices])
    all_verts = np.concatenate(vertices, axis=0)

    for i in range(len(profile) - 1):
        below = profile[i]
        above = profile[i + 1]
        n_b = vertices[i].shape[0]
        n_a = vertices[i + 1].shape[0]
        off_b = offsets[i]
        off_a = offsets[i + 1]
        if n_b == sections and n_a == sections:
            for k in range(sections):
                k2 = (k + 1) % sections
                faces.append((off_b + k, off_b + k2, off_a + k2))
                faces.append((off_b + k, off_a + k2, off_a + k))
        elif n_b == sections and n_a == 1:
            for k in range(sections):
                k2 = (k + 1) % sections
                faces.append((off_b + k, off_b + k2, off_a))
        elif n_b == 1 and n_a == sections:
            for k in range(sections):
                k2 = (k + 1) % sections
                faces.append((off_b, off_a + k2, off_a + k))
        else:
            # Both rings on the axis — nothing to triangulate.
            continue
        # Suppress unused-variable lints for above/below; they document intent.
        _ = (above.r, below.r)

    # Cap the bottom ring if it has finite radius.
    if profile[0].r > 1e-9:
        cap_idx = len(all_verts)
        all_verts = np.vstack([all_verts, [0.0, 0.0, profile[0].z]])
        off = offsets[0]
        for k in range(sections):
            k2 = (k + 1) % sections
            faces.append((cap_idx, off + k2, off + k))
    # Cap the top ring if it has finite radius.
    if profile[-1].r > 1e-9:
        cap_idx = len(all_verts)
        all_verts = np.vstack([all_verts, [0.0, 0.0, profile[-1].z]])
        off = offsets[len(profile) - 1]
        for k in range(sections):
            k2 = (k + 1) % sections
            faces.append((cap_idx, off + k, off + k2))

    mesh = trimesh.Trimesh(vertices=all_verts, faces=np.asarray(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _arc_points(
    center: Tuple[float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    n: int = 16,
) -> List[ProfilePoint]:
    """Sample ``n`` points on a circular arc in the (r, z) plane.

    Used to approximate fillets / chamfers / barrel sections with the same
    polyline trick that ``coder_agent._build_revolve_polyline`` will need
    in Sprint 2.4 — keeping the math local here means the bench fixtures
    are an independent oracle.

    Args:
        center: ``(r_centre, z_centre)`` of the arc.
        radius: Arc radius.
        start_angle: Start angle (radians) measured from +r axis.
        end_angle: End angle (radians).
        n: Number of samples (default 16, matches Sprint 2 default).
    """
    angles = np.linspace(start_angle, end_angle, n)
    return [
        ProfilePoint(z=float(center[1] + radius * np.sin(a)),
                    r=float(center[0] + radius * np.cos(a)))
        for a in angles
    ]


def make_stepped_shaft(
    r1: float, h1: float, r2: float, h2: float, sections: int = 128
) -> trimesh.Trimesh:
    """Build stepped shaft from two cylinders.

    Args:
        r1: Radius of bottom cylinder.
        h1: Height of bottom cylinder.
        r2: Radius of top cylinder.
        h2: Height of top cylinder.
        sections: Number of radial sections for discretization.

    Returns:
        Combined mesh with filled holes and fixed normals.
    """
    # cylinder 1: z = 0..h1
    cyl1 = trimesh.creation.cylinder(radius=r1, height=h1, sections=sections)
    cyl1.apply_translation([0, 0, h1 / 2])

    # cylinder 2: z = h1..h1+h2
    cyl2 = trimesh.creation.cylinder(radius=r2, height=h2, sections=sections)
    cyl2.apply_translation([0, 0, h1 + h2 / 2])

    # concatenate and repair
    mesh = trimesh.util.concatenate([cyl1, cyl2])
    trimesh.repair.fill_holes(mesh)
    mesh.fix_normals()
    return mesh


def add_gaussian_noise(
    mesh: trimesh.Trimesh, sigma_mm: float, seed: int = 42
) -> trimesh.Trimesh:
    """Add Gaussian noise to mesh vertices.

    Args:
        mesh: Input mesh (modified in place).
        sigma_mm: Standard deviation of noise in millimeters.
        seed: Random seed for reproducibility.

    Returns:
        The same mesh with noise applied and normals fixed.
    """
    np.random.seed(seed)
    noise = np.random.normal(0, sigma_mm, mesh.vertices.shape)
    mesh.vertices += noise
    mesh.fix_normals()
    return mesh


def _shift_cylinder_to_z0(mesh: trimesh.Trimesh, height: float) -> trimesh.Trimesh:
    """Shift a centered cylinder so its bottom is at z=0.

    trimesh.creation.cylinder() centers the cylinder at origin.
    This shifts it so z ranges from 0 to height.
    """
    mesh.apply_translation([0, 0, height / 2])
    return mesh


# ---------------------------------------------------------------------------
# Sprint 1.3 evil-shafts (revolution scope v1 coverage)
# ---------------------------------------------------------------------------


def make_hourglass_shaft(
    r_end: float = 18.0,
    r_waist: float = 8.0,
    height: float = 60.0,
    sections: int = 128,
) -> trimesh.Trimesh:
    """Build a concave "diabolo" shaft.

    Profile: r(z) = r_end - (r_end - r_waist) * sin(pi * z / height). Smooth
    concave generatrix; rotation-symmetric; exercises the ``fit_arc`` path
    for concave segments and the PCA edge case when L ≈ D.
    """
    n = 41
    zs = np.linspace(0.0, height, n)
    rs = r_end - (r_end - r_waist) * np.sin(np.pi * zs / height)
    profile = [ProfilePoint(z=float(z), r=float(r)) for z, r in zip(zs, rs)]
    return revolve_profile(profile, sections=sections)


def make_chamfer_shaft(sections: int = 128) -> trimesh.Trimesh:
    """Stepped shaft with explicit 30°, 45°, 60° chamfers.

    Three cylindrical segments with explicit chamfer transitions of three
    different angles. Used as the **golden test** for arc-gap closing in
    Sprint 2.4: linear polyline reconstruction will overshoot the chamfer
    by ``s * (1 - cos(angle/2))`` while a discretised reconstruction will
    not.
    """
    profile: List[ProfilePoint] = []
    # Section 1: r=20, z=0..15
    profile.append(ProfilePoint(z=0.0, r=20.0))
    profile.append(ProfilePoint(z=15.0, r=20.0))
    # 30° chamfer down to r=15 (chamfer length on profile = 5 / tan(30°))
    chamfer1_dz = 5.0 / np.tan(np.deg2rad(30.0))
    profile.append(ProfilePoint(z=15.0 + chamfer1_dz, r=15.0))
    # Section 2: r=15
    profile.append(ProfilePoint(z=15.0 + chamfer1_dz + 12.0, r=15.0))
    # 45° chamfer down to r=10
    chamfer2_dz = 5.0  # tan(45°) = 1
    z0 = 15.0 + chamfer1_dz + 12.0
    profile.append(ProfilePoint(z=z0 + chamfer2_dz, r=10.0))
    # Section 3: r=10
    profile.append(ProfilePoint(z=z0 + chamfer2_dz + 10.0, r=10.0))
    # 60° chamfer down to r=6 (chamfer length = 4 / tan(60°))
    chamfer3_dz = 4.0 / np.tan(np.deg2rad(60.0))
    z1 = z0 + chamfer2_dz + 10.0
    profile.append(ProfilePoint(z=z1 + chamfer3_dz, r=6.0))
    # End cap section
    profile.append(ProfilePoint(z=z1 + chamfer3_dz + 8.0, r=6.0))
    return revolve_profile(profile, sections=sections)


def make_fillet_shaft(sections: int = 128) -> trimesh.Trimesh:
    """Stepped shaft with R0.5, R2, R5 fillets between cylindrical sections.

    Each fillet is sampled as a 16-point arc so the source mesh carries the
    full fillet curvature. The reconstructed mesh will only match if the
    revolve polyline also discretises the arc (Sprint 2.4 target).
    """
    profile: List[ProfilePoint] = []
    # Bottom cylinder r=15, z=0..15
    profile.append(ProfilePoint(z=0.0, r=15.0))
    profile.append(ProfilePoint(z=15.0, r=15.0))
    # R5 fillet down to r=10 (concave, centre at (10, 15+5) → arc from 0 to pi/2)
    profile += _arc_points(center=(10.0, 20.0), radius=5.0,
                           start_angle=np.pi / 2, end_angle=0.0, n=16)
    # Cylinder r=10, z=20..32
    profile.append(ProfilePoint(z=32.0, r=10.0))
    # R2 fillet down to r=8 (centre at (8, 32+2))
    profile += _arc_points(center=(8.0, 34.0), radius=2.0,
                           start_angle=np.pi / 2, end_angle=0.0, n=16)
    # Cylinder r=8
    profile.append(ProfilePoint(z=42.0, r=8.0))
    # R0.5 fillet down to r=6 (centre at (6, 42+0.5))
    profile += _arc_points(center=(6.0, 42.5), radius=0.5,
                           start_angle=np.pi / 2, end_angle=0.0, n=16)
    # End cylinder
    profile.append(ProfilePoint(z=50.0, r=6.0))

    # Deduplicate exact z duplicates that arc sampling may introduce.
    deduped: List[ProfilePoint] = [profile[0]]
    for p in profile[1:]:
        if p.z - deduped[-1].z > 1e-6:
            deduped.append(p)
    return revolve_profile(deduped, sections=sections)


def make_conical_shaft(sections: int = 128) -> trimesh.Trimesh:
    """Cone + cylinder + cone (mirror) symmetric about the mid-plane.

    Targets ``fit_cone``: the two cone zones must be detected with opposite
    slopes and the central cylinder must keep its mean radius.
    """
    profile = [
        ProfilePoint(z=0.0, r=8.0),
        ProfilePoint(z=15.0, r=20.0),  # First cone (r=8 → r=20)
        ProfilePoint(z=25.0, r=20.0),  # Cylinder
        ProfilePoint(z=40.0, r=8.0),   # Mirror cone (r=20 → r=8)
    ]
    return revolve_profile(profile, sections=sections)


def make_barrel_shaft(
    r_end: float = 10.0,
    r_mid: float = 20.0,
    height: float = 60.0,
    sections: int = 128,
) -> trimesh.Trimesh:
    """Barrel-shaped shaft with a quadratic (spline-like) generatrix.

    Profile: ``r(z) = r_end + (r_mid - r_end) * (1 - ((z - h/2) / (h/2))^2)``.
    The convex spline section currently stubs out in ``fit_zone``; this
    fixture is the canary that catches when we enable the spline path.
    """
    n = 41
    zs = np.linspace(0.0, height, n)
    t = (zs - height / 2.0) / (height / 2.0)
    rs = r_end + (r_mid - r_end) * (1.0 - t**2)
    profile = [ProfilePoint(z=float(z), r=float(r)) for z, r in zip(zs, rs)]
    return revolve_profile(profile, sections=sections)


def make_short_disc_shaft(
    radius: float = 25.0,
    height: float = 10.0,
    sections: int = 128,
) -> trimesh.Trimesh:
    """Short fat shaft (L ≈ D / 2.5) — PCA edge case.

    The principal-axis solver has near-degenerate eigenvalues here; this
    fixture is the smoke test for ``shaft_axis`` robustness once RANSAC is
    rescued from P8-P9 (Sprint 2.2).
    """
    profile = [
        ProfilePoint(z=0.0, r=radius),
        ProfilePoint(z=height, r=radius),
    ]
    return revolve_profile(profile, sections=sections)


def generate_all() -> None:
    """Generate all benchmark STL files."""
    # Create cylinders and shift to z=0..height
    cyl_ideal = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=128)
    _shift_cylinder_to_z0(cyl_ideal, 40.0)

    cyl_noise = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=128)
    _shift_cylinder_to_z0(cyl_noise, 40.0)

    cyl_fixture = trimesh.creation.cylinder(radius=9.984, height=50.0, sections=64)
    _shift_cylinder_to_z0(cyl_fixture, 50.0)

    files_to_generate = {
        REPO_ROOT / "benchmark_kit/ideal/ideal_cylinder.stl": (
            "ideal",
            cyl_ideal,
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_stepped_shaft.stl": (
            "ideal",
            make_stepped_shaft(
                r1=15.0, h1=20.0, r2=10.0, h2=30.0, sections=128
            ),
        ),
        REPO_ROOT / "benchmark_kit/noise/noise_cylinder.stl": (
            "noise",
            add_gaussian_noise(cyl_noise, sigma_mm=0.3, seed=42),
        ),
        REPO_ROOT / "benchmark_kit/noise/noise_stepped_shaft.stl": (
            "noise",
            add_gaussian_noise(
                make_stepped_shaft(
                    r1=15.0, h1=20.0, r2=10.0, h2=30.0, sections=128
                ),
                sigma_mm=0.5,
                seed=42,
            ),
        ),
        REPO_ROOT / "tests/fixtures/plain_shaft.stl": (
            "fixture",
            cyl_fixture,
        ),
        REPO_ROOT / "tests/fixtures/stepped_shaft.stl": (
            "fixture",
            make_stepped_shaft(
                r1=15.0, h1=20.0, r2=10.0, h2=30.0, sections=64
            ),
        ),
        # Sprint 1.3 evil-shafts ----------------------------------------------
        REPO_ROOT / "benchmark_kit/ideal/ideal_hourglass_shaft.stl": (
            "ideal",
            make_hourglass_shaft(r_end=18.0, r_waist=8.0, height=60.0),
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_chamfer_shaft.stl": (
            "ideal",
            make_chamfer_shaft(),
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_fillet_shaft.stl": (
            "ideal",
            make_fillet_shaft(),
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_conical_shaft.stl": (
            "ideal",
            make_conical_shaft(),
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_barrel_shaft.stl": (
            "ideal",
            make_barrel_shaft(r_end=10.0, r_mid=20.0, height=60.0),
        ),
        REPO_ROOT / "benchmark_kit/ideal/ideal_short_disc_shaft.stl": (
            "ideal",
            make_short_disc_shaft(radius=25.0, height=10.0),
        ),
    }

    generated_count = 0
    for path, (category, mesh) in files_to_generate.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(path))
        verts = len(mesh.vertices)
        faces = len(mesh.faces)
        rel_path = str(path.relative_to(REPO_ROOT))
        print(
            f"  [{category:6s}] {rel_path:50s} "
            f"({verts:5d} vertices, {faces:5d} faces)"
        )
        generated_count += 1

    print(f"\nGenerated {generated_count} STL files.")


if __name__ == "__main__":
    print("Generating benchmark STL files for revolution bodies...\n")
    generate_all()
