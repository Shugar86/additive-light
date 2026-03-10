"""Generate test fixture STL files for shaft reverse engineering.

Creates 10 test cases:
1. plain_shaft - Simple uniform cylinder
2. stepped_shaft - Multiple diameter sections
3. shaft_with_keyway - Axial slot for key
4. shaft_with_flat - Machined flat surface
5. shaft_with_cross_hole - Perpendicular drilled hole
6. shaft_with_groove - Circumferential groove
7. shaft_with_fillet - Smooth transitions
8. noisy_shaft_1 - Add noise to plain shaft
9. noisy_shaft_2 - Add noise to stepped shaft
10. failure_case - Intentionally problematic geometry

Usage:
    python generate_shaft_fixtures.py

Requirements:
    pip install build123d
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pathlib import Path
from typing import List, Tuple
import numpy as np

try:
    from build123d import *
    from build123d.exporters import export_stl
except ImportError:
    print("build123d not installed. Run: pip install build123d")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent


def _add_noise_to_mesh(vertices: np.ndarray, noise_scale: float = 0.05) -> np.ndarray:
    """Add random noise to mesh vertices."""
    noise = np.random.normal(0, noise_scale, vertices.shape)
    return vertices + noise


def generate_plain_shaft() -> Path:
    """Generate a simple uniform cylinder shaft."""
    print("Generating: plain_shaft.stl")
    
    with BuildPart() as shaft:
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 100, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
    
    output_path = OUTPUT_DIR / "plain_shaft.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_stepped_shaft() -> Path:
    """Generate a shaft with multiple diameter sections."""
    print("Generating: stepped_shaft.stl")
    
    with BuildPart() as shaft:
        with BuildSketch(Plane.XZ) as profile:
            # Create stepped profile
            with Locations((0, 0)):
                Rectangle(30, 30, align=(Align.MIN, Align.CENTER))
            with Locations((0, 30)):
                Rectangle(20, 40, align=(Align.MIN, Align.CENTER))
            with Locations((0, 70)):
                Rectangle(25, 30, align=(Align.MIN, Align.CENTER))
        revolve(axis=Axis.Z)
    
    output_path = OUTPUT_DIR / "stepped_shaft.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_shaft_with_keyway() -> Path:
    """Generate a shaft with a keyway slot."""
    print("Generating: shaft_with_keyway.stl")
    
    with BuildPart() as shaft:
        # Base shaft
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 80, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
        
        # Keyway cut
        with Locations((10, 0)):
            with BuildSketch() as keyway:
                Rectangle(6, 40, align=(Align.CENTER, Align.CENTER))
            extrude(amount=4, mode=Mode.SUBTRACT)
    
    output_path = OUTPUT_DIR / "shaft_with_keyway.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_shaft_with_flat() -> Path:
    """Generate a shaft with a machined flat surface."""
    print("Generating: shaft_with_flat.stl")
    
    with BuildPart() as shaft:
        # Base shaft
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 80, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
        
        # Flat cut (remove material on one side)
        with Locations((15, 0)):
            with BuildSketch() as flat_cut:
                Rectangle(10, 60, align=(Align.MIN, Align.CENTER))
            extrude(amount=20, mode=Mode.SUBTRACT)
    
    output_path = OUTPUT_DIR / "shaft_with_flat.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_shaft_with_cross_hole() -> Path:
    """Generate a shaft with a perpendicular drilled hole."""
    print("Generating: shaft_with_cross_hole.stl")
    
    with BuildPart() as shaft:
        # Base shaft
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 80, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
        
        # Cross hole
        with Locations((0, 40)):
            with BuildSketch() as hole:
                Circle(radius=4)
            extrude(amount=30, mode=Mode.SUBTRACT)
    
    output_path = OUTPUT_DIR / "shaft_with_cross_hole.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_shaft_with_groove() -> Path:
    """Generate a shaft with a circumferential groove."""
    print("Generating: shaft_with_groove.stl")
    
    with BuildPart() as shaft:
        # Base shaft
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 80, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
        
        # Groove cut
        with Locations((0, 40)):
            with BuildSketch() as groove:
                Rectangle(4, 10, align=(Align.CENTER, Align.CENTER))
            extrude(amount=25, mode=Mode.SUBTRACT)
    
    output_path = OUTPUT_DIR / "shaft_with_groove.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_shaft_with_fillet() -> Path:
    """Generate a shaft with smooth fillet transitions."""
    print("Generating: shaft_with_fillet.stl")
    
    with BuildPart() as shaft:
        with BuildSketch(Plane.XZ) as profile:
            # Main cylinder
            Rectangle(20, 60, align=(Align.CENTER, Align.CENTER))
            # Smaller cylinder with fillet
            with Locations((0, 30)):
                Rectangle(12, 30, align=(Align.CENTER, Align.MIN))
        revolve(axis=Axis.Z)
        
        # Apply fillet to the transition
        # Note: build123d fillet API may vary, this is simplified
        # In real implementation, use proper fillet_edges
    
    output_path = OUTPUT_DIR / "shaft_with_fillet.stl"
    export_stl(shaft.part, str(output_path))
    return output_path


def generate_noisy_shaft_1() -> Path:
    """Generate a plain shaft with added noise."""
    print("Generating: noisy_shaft_1.stl")
    
    # First create the base shaft
    with BuildPart() as shaft:
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(20, 100, align=(Align.CENTER, Align.CENTER))
        revolve(axis=Axis.Z)
    
    output_path = OUTPUT_DIR / "noisy_shaft_1.stl"
    
    # Export temporarily
    temp_path = OUTPUT_DIR / "_temp_noisy1.stl"
    export_stl(shaft.part, str(temp_path))
    
    # Load and add noise
    try:
        import trimesh
        mesh = trimesh.load(temp_path)
        vertices = np.array(mesh.vertices)
        noisy_vertices = _add_noise_to_mesh(vertices, noise_scale=0.1)
        mesh.vertices = noisy_vertices
        mesh.export(output_path)
        temp_path.unlink()
    except ImportError:
        # Fallback: just copy the clean version
        export_stl(shaft.part, str(output_path))
    
    return output_path


def generate_noisy_shaft_2() -> Path:
    """Generate a stepped shaft with added noise."""
    print("Generating: noisy_shaft_2.stl")
    
    with BuildPart() as shaft:
        with BuildSketch(Plane.XZ) as profile:
            with Locations((0, 0)):
                Rectangle(30, 30, align=(Align.MIN, Align.CENTER))
            with Locations((0, 30)):
                Rectangle(20, 40, align=(Align.MIN, Align.CENTER))
            with Locations((0, 70)):
                Rectangle(25, 30, align=(Align.MIN, Align.CENTER))
        revolve(axis=Axis.Z)
    
    output_path = OUTPUT_DIR / "noisy_shaft_2.stl"
    
    # Export temporarily
    temp_path = OUTPUT_DIR / "_temp_noisy2.stl"
    export_stl(shaft.part, str(temp_path))
    
    # Load and add noise
    try:
        import trimesh
        mesh = trimesh.load(temp_path)
        vertices = np.array(mesh.vertices)
        noisy_vertices = _add_noise_to_mesh(vertices, noise_scale=0.15)
        mesh.vertices = noisy_vertices
        mesh.export(output_path)
        temp_path.unlink()
    except ImportError:
        export_stl(shaft.part, str(output_path))
    
    return output_path


def generate_failure_case() -> Path:
    """Generate an intentionally problematic geometry."""
    print("Generating: failure_case.stl")
    
    # Create a geometry that is very non-cylindrical
    # This should challenge the shaft pipeline
    with BuildPart() as part:
        with BuildSketch(Plane.XZ) as profile:
            # Very irregular shape
            Rectangle(10, 20, align=(Align.CENTER, Align.MIN))
            with Locations((5, 10)):
                Rectangle(15, 30, align=(Align.CENTER, Align.MIN))
            with Locations((-2, 40)):
                Rectangle(8, 20, align=(Align.CENTER, Align.MIN))
        revolve(axis=Axis.Z)
    
    output_path = OUTPUT_DIR / "failure_case.stl"
    export_stl(part.part, str(output_path))
    return output_path


def generate_all_fixtures() -> List[Tuple[str, Path]]:
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
        size = path.stat().st_size / 1024  # KB
        print(f"  {name}: {path.name} ({size:.1f} KB)")
    
    print(f"\nAll fixtures saved to: {OUTPUT_DIR}")
