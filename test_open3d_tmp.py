#!/usr/bin/env python3
import open3d as o3d
import shutil
from pathlib import Path

# Copy to native Linux filesystem
src = "/mnt/c/additive-light _dev/tests/fixtures/plain_shaft.stl"
dst = "/tmp/test.stl"
shutil.copy(src, dst)
print(f"Copied to {dst}")

# Try loading from /tmp
mesh = o3d.io.read_triangle_mesh(dst)
print(f"Loaded from /tmp: {len(mesh.vertices)} vertices")
print("SUCCESS!")
