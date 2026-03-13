#!/usr/bin/env python3
"""Minimal reproducer for Open3D segfault."""
import open3d as o3d
import numpy as np
from pathlib import Path

stl_path = "tests/fixtures/plain_shaft.stl"
print(f"Loading: {stl_path}")
print(f"Exists: {Path(stl_path).exists()}")

mesh = o3d.io.read_triangle_mesh(stl_path)
print(f"Vertices: {len(mesh.vertices)}")
print(f"Is empty: {mesh.is_empty()}")
print(f"Has vertex colors: {mesh.has_vertex_colors()}")
print(f"Has vertex normals: {mesh.has_vertex_normals()}")

vertices = np.asarray(mesh.vertices)
print(f"Vertices array shape: {vertices.shape}")
print(f"Vertices dtype: {vertices.dtype}")

centroid = np.mean(vertices, axis=0)
print(f"Centroid: {centroid}")
print(f"Centroid dtype: {centroid.dtype}")

print("Testing mesh.translate()...")
mesh.translate((0.0, 0.0, 0.0))
print("OK with tuple (0,0,0)")

mesh2 = o3d.io.read_triangle_mesh(stl_path)
mesh2.translate((-float(centroid[0]), -float(centroid[1]), -float(centroid[2])))
print("OK with negative centroid as tuple")

print("All tests passed!")
