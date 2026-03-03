import trimesh
import numpy as np
import os
import glob

def apply_noise(mesh, magnitude=0.2):
    """Adds random Gaussian noise to vertices."""
    noise = np.random.normal(0, magnitude, mesh.vertices.shape)
    mesh.vertices += noise
    return mesh

def apply_tilt(mesh, max_angle_deg=10):
    """Applies a random tilt (rotation) to the mesh."""
    angles = np.radians(np.random.uniform(-max_angle_deg, max_angle_deg, 3))
    transform = trimesh.transformations.euler_matrix(*angles)
    mesh.apply_transform(transform)
    # Also add a small translation offset
    offset = np.random.uniform(-5, 5, 3)
    mesh.apply_translation(offset)
    return mesh

def apply_holes(mesh, num_holes=3, hole_radius=8.0):
    """Simulates scanning holes by deleting faces within a sphere."""
    if len(mesh.faces) == 0:
        return mesh
        
    for _ in range(num_holes):
        # Pick a random point on the mesh surface
        samples, face_indices = trimesh.sample.sample_surface(mesh, 1)
        center = samples[0]
        
        # Find vertices within distance
        distances = np.linalg.norm(mesh.vertices - center, axis=1)
        mask_v = distances < hole_radius
        
        # Find faces that use these vertices
        # This is a simple way to create a hole: delete any face that has at least one vertex in the sphere
        faces_to_remove = np.any(mask_v[mesh.faces], axis=1)
        
        # Invert mask to keep
        faces_to_keep = ~faces_to_remove
        mesh.update_faces(faces_to_keep)
        
    mesh.remove_unreferenced_vertices()
    return mesh

def process_files():
    input_dir = "benchmark_kit/ideal"
    output_dir = "benchmark_kit/noise"
    os.makedirs(output_dir, exist_ok=True)
    
    files = glob.glob(os.path.join(input_dir, "*.stl"))
    
    if not files:
        print(f"No STL files found in {input_dir}")
        return

    for fpath in files:
        fname = os.path.basename(fpath)
        print(f"Corrupting {fname}...")
        
        try:
            mesh = trimesh.load(fpath)
            
            # 1. Apply Tilt (simulates poor alignment)
            mesh = apply_tilt(mesh, max_angle_deg=15)
            
            # 2. Apply Noise (simulates sensor jitter)
            mesh = apply_noise(mesh, magnitude=0.3)
            
            # 3. Apply Holes (simulates missing scan data)
            # More holes for more complex parts
            num_holes = 5 if "lattice" in fname or "gear" in fname else 2
            mesh = apply_holes(mesh, num_holes=num_holes, hole_radius=6.0)
            
            output_path = os.path.join(output_dir, fname.replace("ideal_", "noise_"))
            mesh.export(output_path)
            print(f"Saved to {output_path}")
            
        except Exception as e:
            print(f"Error processing {fname}: {e}")

if __name__ == "__main__":
    process_files()
