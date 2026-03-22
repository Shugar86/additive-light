"""Generate benchmark STL files for revolution bodies test suite.

Run once to populate benchmark_kit/ and tests/fixtures/:
    python scripts/generate_benchmark_stl.py

Requires: trimesh, numpy
Does NOT require: build123d, open3d
"""

import sys
from pathlib import Path
from typing import Tuple

import numpy as np

try:
    import trimesh
except ImportError:
    print("Error: trimesh not installed. Run: pip install trimesh")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("Error: numpy not installed. Run: pip install numpy")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent


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
