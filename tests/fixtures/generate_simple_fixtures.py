"""Generate simple test fixture STL files for shaft reverse engineering.

Creates 10 test cases using trimesh (already installed).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pathlib import Path
import numpy as np

try:
    import trimesh
except ImportError:
    print("trimesh not installed. Run: pip install trimesh")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent


def _cylinder_mesh(radius: float, height: float, sections: int = 32) -> trimesh.Trimesh:
    """Create a cylinder mesh."""
    cylinder = trimesh.creation.cylinder(
        radius=radius,
        height=height,
        sections=sections
    )
    return cylinder


def _add_noise(mesh: trimesh.Trimesh, scale: float = 0.05) -> trimesh.Trimesh:
    """Add noise to mesh vertices."""
    mesh = mesh.copy()
    noise = np.random.normal(0, scale, mesh.vertices.shape)
    mesh.vertices += noise
    return mesh


def generate_plain_shaft() -> Path:
    """Generate a simple uniform cylinder shaft."""
    print("Generating: plain_shaft.stl")
    shaft = _cylinder_mesh(radius=10, height=100)
    output_path = OUTPUT_DIR / "plain_shaft.stl"
    shaft.export(output_path)
    return output_path


def generate_stepped_shaft() -> Path:
    """Generate a shaft with multiple diameter sections."""
    print("Generating: stepped_shaft.stl")
    
    cyl1 = _cylinder_mesh(radius=15, height=30)
    cyl2 = _cylinder_mesh(radius=10, height=40)
    cyl3 = _cylinder_mesh(radius=12.5, height=30)
    
    cyl1.apply_translation([0, 0, -35])
    cyl3.apply_translation([0, 0, 35])
    
    shaft = trimesh.util.concatenate([cyl1, cyl2, cyl3])
    
    output_path = OUTPUT_DIR / "stepped_shaft.stl"
    shaft.export(output_path)
    return output_path


def generate_shaft_with_keyway() -> Path:
    """Generate a shaft with a keyway-like slot (simplified as a flat)."""
    print("Generating: shaft_with_keyway.stl")
    
    # Simplified: use a flattened cylinder to represent keyway area
    shaft = _cylinder_mesh(radius=10, height=80)
    
    # Apply local flattening by scaling vertices in one region
    vertices = np.array(shaft.vertices)
    # Find vertices near the surface at certain Z range
    z_range = (vertices[:, 2] > -10) & (vertices[:, 2] < 10)
    x_outer = vertices[:, 0] > 8
    
    mask = z_range & x_outer
    # Flatten these vertices (move them inward)
    vertices[mask, 0] *= 0.6  # Reduce x by 40%
    
    shaft.vertices = vertices
    
    output_path = OUTPUT_DIR / "shaft_with_keyway.stl"
    shaft.export(output_path)
    return output_path


def generate_shaft_with_flat() -> Path:
    """Generate a shaft with a machined flat surface."""
    print("Generating: shaft_with_flat.stl")
    
    shaft = _cylinder_mesh(radius=10, height=80)
    
    # Flatten one side
    vertices = np.array(shaft.vertices)
    # Find vertices on one side
    mask = vertices[:, 0] > 5
    # Flatten these vertices
    vertices[mask, 0] = 8
    
    shaft.vertices = vertices
    
    output_path = OUTPUT_DIR / "shaft_with_flat.stl"
    shaft.export(output_path)
    return output_path


def generate_shaft_with_cross_hole() -> Path:
    """Generate a shaft with a perpendicular drilled hole (simplified)."""
    print("Generating: shaft_with_cross_hole.stl")
    
    shaft = _cylinder_mesh(radius=10, height=80)
    
    # Add a cylindrical protrusion to simulate a hole intersection
    hole = _cylinder_mesh(radius=4, height=30)
    hole.apply_transform(trimesh.transformations.rotation_matrix(
        np.pi/2, [1, 0, 0], [0, 0, 0]
    ))
    hole.apply_translation([0, 0, 10])
    
    # Union them for now (since we don't have boolean difference without blender)
    result = trimesh.util.concatenate([shaft, hole])
    
    output_path = OUTPUT_DIR / "shaft_with_cross_hole.stl"
    result.export(output_path)
    return output_path


def generate_shaft_with_groove() -> Path:
    """Generate a shaft with a circumferential groove."""
    print("Generating: shaft_with_groove.stl")
    
    shaft = _cylinder_mesh(radius=10, height=80)
    
    # Create groove by scaling vertices in a ring
    vertices = np.array(shaft.vertices)
    z_center = 0
    z_range = 5
    
    mask = np.abs(vertices[:, 2] - z_center) < z_range
    # Reduce radius in this region
    xy_radius = np.sqrt(vertices[:, 0]**2 + vertices[:, 1]**2)
    new_radius = np.where(mask, xy_radius * 0.7, xy_radius)
    
    angle = np.arctan2(vertices[:, 1], vertices[:, 0])
    vertices[:, 0] = new_radius * np.cos(angle)
    vertices[:, 1] = new_radius * np.sin(angle)
    
    shaft.vertices = vertices
    
    output_path = OUTPUT_DIR / "shaft_with_groove.stl"
    shaft.export(output_path)
    return output_path


def generate_shaft_with_fillet() -> Path:
    """Generate a shaft with stepped sections."""
    print("Generating: shaft_with_fillet.stl")
    
    cyl1 = _cylinder_mesh(radius=10, height=60)
    cyl2 = _cylinder_mesh(radius=6, height=30)
    cyl2.apply_translation([0, 0, 45])
    
    shaft = trimesh.util.concatenate([cyl1, cyl2])
    
    output_path = OUTPUT_DIR / "shaft_with_fillet.stl"
    shaft.export(output_path)
    return output_path


def generate_noisy_shaft_1() -> Path:
    """Generate a plain shaft with added noise."""
    print("Generating: noisy_shaft_1.stl")
    
    shaft = _cylinder_mesh(radius=10, height=100)
    noisy_shaft = _add_noise(shaft, scale=0.1)
    
    output_path = OUTPUT_DIR / "noisy_shaft_1.stl"
    noisy_shaft.export(output_path)
    return output_path


def generate_noisy_shaft_2() -> Path:
    """Generate a stepped shaft with added noise."""
    print("Generating: noisy_shaft_2.stl")
    
    cyl1 = _cylinder_mesh(radius=15, height=30)
    cyl2 = _cylinder_mesh(radius=10, height=40)
    cyl3 = _cylinder_mesh(radius=12.5, height=30)
    
    cyl1.apply_translation([0, 0, -35])
    cyl3.apply_translation([0, 0, 35])
    
    shaft = trimesh.util.concatenate([cyl1, cyl2, cyl3])
    noisy_shaft = _add_noise(shaft, scale=0.15)
    
    output_path = OUTPUT_DIR / "noisy_shaft_2.stl"
    noisy_shaft.export(output_path)
    return output_path


def generate_failure_case() -> Path:
    """Generate an intentionally problematic geometry."""
    print("Generating: failure_case.stl")
    
    # Create a very irregular shape - not cylindrical
    box = trimesh.creation.box(extents=[5, 15, 30])
    box2 = trimesh.creation.box(extents=[8, 10, 20])
    box2.apply_translation([2, 5, 10])
    
    part = trimesh.util.concatenate([box, box2])
    
    output_path = OUTPUT_DIR / "failure_case.stl"
    part.export(output_path)
    return output_path


def generate_all_fixtures():
    """Generate all 10 test fixtures."""
    fixtures = [
        ("plain_shaft", generate_plain_shaft()),
        ("stepped_shaft", generate_stepped_shaft()),
        ("shaft_with_keyway", generate_shaft_with_keyway()),
        ("shaft_with_flat", generate_shaft_with_flat()),
        ("shaft_with_cross_hole", generate_shaft_with_cross_hole()),
        ("shaft_with_groove", generate_shaft_with_groove()),
        ("shaft_with_fillet", generate_shaft_with_fillet()),
        ("noisy_shaft_1", generate_noisy_shaft_1()),
        ("noisy_shaft_2", generate_noisy_shaft_2()),
        ("failure_case", generate_failure_case()),
    ]
    
    return fixtures


if __name__ == "__main__":
    print("=" * 60)
    print("Generating Shaft Test Fixtures")
    print("=" * 60)
    
    fixtures = generate_all_fixtures()
    
    print("\n" + "=" * 60)
    print("Generated Fixtures:")
    print("=" * 60)
    for name, path in fixtures:
        if path.exists():
            size = path.stat().st_size / 1024  # KB
            print(f"  {name}: {path.name} ({size:.1f} KB)")
        else:
            print(f"  {name}: FAILED")
    
    print(f"\nAll fixtures saved to: {OUTPUT_DIR}")
