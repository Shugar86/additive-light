import trimesh
import numpy as np
import os

def generate_cylinder(radius=20.0, height=40.0):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=64)
    # Align bottom to Z=0
    mesh.apply_translation([0, 0, height/2])
    return mesh

def generate_flange(radius_outer=30.0, height=10.0, hole_radius=3.0, hole_pitch_radius=22.0, num_holes=4):
    base = trimesh.creation.cylinder(radius=radius_outer, height=height, sections=64)
    base.apply_translation([0, 0, height/2])
    
    holes = []
    for i in range(num_holes):
        angle = 2 * np.pi * i / num_holes
        x = hole_pitch_radius * np.cos(angle)
        y = hole_pitch_radius * np.sin(angle)
        hole = trimesh.creation.cylinder(radius=hole_radius, height=height * 1.5, sections=32)
        hole.apply_translation([x, y, height/2])
        holes.append(hole)
    
    # trimesh boolean operations
    for h in holes:
        base = base.difference(h)
    
    return base

def generate_stepped_shaft(r1=15.0, h1=20.0, r2=10.0, h2=30.0):
    sec1 = trimesh.creation.cylinder(radius=r1, height=h1, sections=64)
    sec1.apply_translation([0, 0, h1/2])
    
    sec2 = trimesh.creation.cylinder(radius=r2, height=h2, sections=64)
    sec2.apply_translation([0, 0, h1 + h2/2])
    
    # merge meshes
    shaft = trimesh.util.concatenate([sec1, sec2])
    return shaft

def generate_bracket_2d(width=60.0, depth=40.0, height=10.0, hole_radius=5.0, pocket_radius=15.0, pocket_depth=5.0):
    base = trimesh.creation.box(extents=[width, depth, height])
    base.apply_translation([0, 0, height/2])
    
    # 2 corner holes
    h1 = trimesh.creation.cylinder(radius=hole_radius, height=height * 1.5, sections=32)
    h1.apply_translation([width/2 - 10, depth/2 - 10, height/2])
    
    h2 = trimesh.creation.cylinder(radius=hole_radius, height=height * 1.5, sections=32)
    h2.apply_translation([-width/2 + 10, -depth/2 + 10, height/2])
    
    # central pocket
    pocket = trimesh.creation.cylinder(radius=pocket_radius, height=pocket_depth, sections=64)
    pocket.apply_translation([0, 0, height - pocket_depth/2 + 0.1])
    
    res = base.difference(h1).difference(h2).difference(pocket)
    return res

if __name__ == "__main__":
    output_dir = "benchmark_kit/ideal"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating ideal_cylinder.stl...")
    generate_cylinder().export(os.path.join(output_dir, "ideal_cylinder.stl"))
    
    print("Generating ideal_flange.stl...")
    generate_flange().export(os.path.join(output_dir, "ideal_flange.stl"))
    
    print("Generating ideal_stepped_shaft.stl...")
    generate_stepped_shaft().export(os.path.join(output_dir, "ideal_stepped_shaft.stl"))
    
    print("Generating ideal_bracket_2.5d.stl...")
    generate_bracket_2d().export(os.path.join(output_dir, "ideal_bracket_2.5d.stl"))
    
    print(f"Done! Ideal dataset generated in {output_dir}")
