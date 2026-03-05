"""Open3D-based mesh alignment and centering utilities.

P8 Refactor: Enhanced alignment with RANSAC plane detection and ICP refinement
for mechanical reverse engineering.

This module provides deterministic, mathematical operations for preparing
STL meshes for analysis. All functions are pure computation with no LLM involvement.
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import numpy as np
import numpy.typing as npt

try:
    import open3d as o3d
except ImportError:
    o3d = None  # type: ignore

logger = logging.getLogger(__name__)


def detect_principal_axes_ransac(
    mesh: o3d.geometry.TriangleMesh,
    min_plane_points: int = 100,
    ransac_threshold: float = 0.01
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Detect principal axes using RANSAC plane detection.
    
    P8 Enhancement: For mechanical parts, detecting dominant planes
    (flat faces) is often more reliable than PCA for asymmetric parts.
    
    Args:
        mesh: Open3D triangle mesh.
        min_plane_points: Minimum points to consider a valid plane.
        ransac_threshold: Distance threshold for plane inliers.
    
    Returns:
        Tuple of (rotation_matrix, metadata dict).
    """
    # Sample points from mesh surface
    pcd = mesh.sample_points_uniformly(number_of_points=5000)
    points = np.asarray(pcd.points)
    
    if len(points) < min_plane_points:
        # Fall back to PCA if not enough points
        vertices = np.asarray(mesh.vertices)
        covariance = np.cov(vertices.T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        idx = eigenvalues.argsort()[::-1]
        return eigenvectors[:, idx].T, {"method": "pca_fallback"}
    
    # Detect up to 3 orthogonal planes using RANSAC
    planes = []
    remaining_pcd = pcd
    
    for i in range(3):
        if len(remaining_pcd.points) < min_plane_points:
            break
        
        # Detect plane
        plane_model, inliers = remaining_pcd.segment_plane(
            distance_threshold=ransac_threshold,
            ransac_n=3,
            num_iterations=1000
        )
        
        if len(inliers) < min_plane_points:
            break
        
        # Plane equation: ax + by + cz + d = 0
        # Normal is (a, b, c)
        normal = np.array(plane_model[:3])
        normal = normal / (np.linalg.norm(normal) + 1e-10)
        
        planes.append({
            "normal": normal,
            "inlier_count": len(inliers),
            "equation": plane_model
        })
        
        # Remove inliers for next iteration
        remaining_pcd = remaining_pcd.select_by_index(inliers, invert=True)
    
    if len(planes) >= 2:
        # Use detected planes to build coordinate system
        # Primary axis: normal of plane with most inliers
        primary = planes[0]["normal"]
        
        # Secondary axis: project second plane normal onto plane perpendicular to primary
        if len(planes) >= 2:
            secondary = planes[1]["normal"]
            # Make orthogonal to primary
            secondary = secondary - np.dot(secondary, primary) * primary
            secondary_norm = np.linalg.norm(secondary)
            if secondary_norm > 0.1:
                secondary = secondary / secondary_norm
            else:
                # Create arbitrary orthogonal vector
                secondary = np.cross(primary, [1, 0, 0])
                if np.linalg.norm(secondary) < 0.1:
                    secondary = np.cross(primary, [0, 1, 0])
                secondary = secondary / np.linalg.norm(secondary)
        else:
            secondary = np.cross(primary, [1, 0, 0])
            if np.linalg.norm(secondary) < 0.1:
                secondary = np.cross(primary, [0, 1, 0])
            secondary = secondary / np.linalg.norm(secondary)
        
        # Tertiary axis: cross product
        tertiary = np.cross(primary, secondary)
        
        rotation_matrix = np.vstack([primary, secondary, tertiary])
        
        metadata = {
            "method": "ransac_planes",
            "plane_count": len(planes),
            "inliers": [p["inlier_count"] for p in planes]
        }
        
        logger.info(f"[RANSAC] Detected {len(planes)} planes, using {planes[0]['inlier_count']} inliers for primary axis")
        
        return rotation_matrix, metadata
    
    # Fall back to PCA if not enough planes detected
    vertices = np.asarray(mesh.vertices)
    covariance = np.cov(vertices.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    idx = eigenvalues.argsort()[::-1]
    
    return eigenvectors[:, idx].T, {"method": "pca_fallback", "planes_found": len(planes)}


def refine_alignment_icp(
    source_mesh: o3d.geometry.TriangleMesh,
    target_points: np.ndarray,
    max_iterations: int = 30,
    convergence_threshold: float = 1e-6
) -> Tuple[o3d.geometry.TriangleMesh, np.ndarray]:
    """Refine mesh alignment using Iterative Closest Point (ICP).
    
    P8 Enhancement: ICP refinement for precise alignment when a reference
    point cloud is available (e.g., from previous scan).
    
    Args:
        source_mesh: Mesh to refine.
        target_points: Target point cloud as numpy array.
        max_iterations: Maximum ICP iterations.
        convergence_threshold: Convergence threshold.
    
    Returns:
        Tuple of (refined_mesh, transformation_matrix).
    """
    # Convert target points to point cloud
    target_pcd = o3d.geometry.PointCloud()
    target_pcd.points = o3d.utility.Vector3dVector(target_points)
    
    # Sample points from source mesh
    source_pcd = source_mesh.sample_points_uniformly(number_of_points=len(target_points))
    
    # Run ICP
    result = o3d.pipelines.registration.registration_icp(
        source_pcd, target_pcd,
        max_correspondence_distance=0.05,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(
            max_iteration=max_iterations,
            relative_fitness=convergence_threshold,
            relative_rmse=convergence_threshold
        )
    )
    
    # Apply transformation to mesh
    refined_mesh = source_mesh.transform(result.transformation)
    
    logger.info(f"[ICP] Refinement converged with fitness={result.fitness:.4f}, RMSE={result.inlier_rmse:.4f}")
    
    return refined_mesh, result.transformation


def load_and_center_mesh(
    stl_path: str,
    output_path: Optional[str] = None,
    use_ransac: bool = True,
    symmetry_check: bool = True
) -> Tuple[str, np.ndarray, np.ndarray, Dict[str, Any]]:
    """Load STL, center at origin, and align to principal axes.
    
    P8 Refactor: Enhanced alignment with RANSAC plane detection and symmetry analysis.

    This is the foundation operation that prepares any input mesh
    for consistent multi-axis analysis.

    Args:
        stl_path: Path to input STL file.
        output_path: Optional path to save aligned mesh. If None, uses temp.
        use_ransac: Whether to use RANSAC plane detection for alignment.
        symmetry_check: Whether to analyze and report rotational symmetry.

    Returns:
        Tuple of (aligned_mesh_path, centroid, principal_axes, metadata).
        Principal axes is a 3x3 matrix where each row is a principal axis.

    Raises:
        FileNotFoundError: If STL file does not exist.
        RuntimeError: If Open3D operations fail.
        ValueError: If mesh has zero vertices or is degenerate.

    Example:
        >>> path, center, axes, meta = load_and_center_mesh("input.stl")
        >>> print(f"Center: {center}, Method: {meta['alignment_method']}")
    """
    if o3d is None:
        raise RuntimeError("Open3D is not installed. Run: pip install open3d")

    stl_file = Path(stl_path)
    if not stl_file.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    metadata: Dict[str, Any] = {
        "alignment_method": "unknown",
        "symmetry": None
    }

    try:
        logger.info(f"Loading mesh from {stl_path}")
        mesh = o3d.io.read_triangle_mesh(str(stl_path))
        
        if len(mesh.vertices) == 0:
            raise ValueError("Mesh has no vertices - file may be corrupted")

        # Compute centroid
        vertices = np.asarray(mesh.vertices)
        centroid = np.mean(vertices, axis=0)
        logger.debug(f"Original centroid: {centroid}")

        # Center the mesh at origin
        mesh.translate(-centroid)
        centered_vertices = np.asarray(mesh.vertices)

        # P8: Enhanced alignment method selection
        if use_ransac and len(mesh.vertices) > 100:
            # Use RANSAC for parts with clear flat faces
            rotation_matrix, align_meta = detect_principal_axes_ransac(mesh)
            metadata["alignment_method"] = align_meta.get("method", "ransac")
            metadata["ransac_info"] = align_meta
        else:
            # Use PCA for smooth/organic shapes
            covariance = np.cov(centered_vertices.T)
            eigenvalues, eigenvectors = np.linalg.eigh(covariance)
            
            # Sort by eigenvalue (descending)
            idx = eigenvalues.argsort()[::-1]
            rotation_matrix = eigenvectors[:, idx].T
            
            metadata["alignment_method"] = "pca"
            metadata["eigenvalues"] = eigenvalues[idx].tolist()
        
        logger.debug(f"Principal axes matrix shape: {rotation_matrix.shape}")
        
        # P8: Symmetry analysis for mechanical parts
        if symmetry_check:
            symmetry_info = analyze_rotational_symmetry(mesh)
            metadata["symmetry"] = symmetry_info
            
            # If cylindrical symmetry detected, ensure Z is rotation axis
            if symmetry_info.get("is_cylindrical", False):
                logger.info("[Alignment] Cylindrical symmetry detected, aligning Z axis")
                # Adjust rotation to put symmetry axis along Z
                sym_axis = symmetry_info.get("symmetry_axis", [0, 0, 1])
                # Realign so sym_axis becomes Z
                current_z = rotation_matrix[2]
                if np.dot(current_z, sym_axis) < 0.9:  # Not already aligned
                    # Create rotation to align sym_axis with Z
                    target = np.array([0, 0, 1])
                    axis = np.cross(sym_axis, target)
                    if np.linalg.norm(axis) > 0.01:
                        angle = np.arccos(np.clip(np.dot(sym_axis, target), -1, 1))
                        axis = axis / np.linalg.norm(axis)
                        # Rodrigues rotation formula
                        K = np.array([[0, -axis[2], axis[1]],
                                     [axis[2], 0, -axis[0]],
                                     [-axis[1], axis[0], 0]])
                        R_align = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
                        rotation_matrix = R_align @ rotation_matrix

        # Rotate mesh to align with principal axes
        mesh.rotate(rotation_matrix.T, center=(0, 0, 0))

        # Determine output path
        if output_path is None:
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            output_path = str(temp_dir / f"aligned_{stl_file.stem}.stl")

        # Save aligned mesh
        success = o3d.io.write_triangle_mesh(output_path, mesh)
        if not success:
            raise RuntimeError(f"Failed to write aligned mesh to {output_path}")

        logger.info(f"Aligned mesh saved to {output_path} (method: {metadata['alignment_method']})")
        
        return output_path, centroid, rotation_matrix, metadata

    except np.linalg.LinAlgError as e:
        logger.error(f"Linear algebra error during PCA: {e}")
        raise RuntimeError(f"Failed to compute principal axes: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during mesh alignment: {e}")
        raise RuntimeError(f"Mesh alignment failed: {e}") from e


def analyze_rotational_symmetry(
    mesh: o3d.geometry.TriangleMesh,
    num_angles: int = 36
) -> Dict[str, Any]:
    """Analyze rotational symmetry of a mesh.
    
    P8 Enhancement: Detect if part is cylindrical/rotationally symmetric,
    which affects how we align and analyze it.
    
    Args:
        mesh: Open3D triangle mesh.
        num_angles: Number of angles to test for symmetry.
    
    Returns:
        Dictionary with symmetry analysis results.
    """
    # Sample points uniformly
    pcd = mesh.sample_points_uniformly(number_of_points=2000)
    points = np.asarray(pcd.points)
    
    if len(points) < 100:
        return {"is_cylindrical": False, "reason": "insufficient_points"}
    
    # Try different potential rotation axes (Z is most common for mechanical parts)
    candidate_axes = [
        np.array([0, 0, 1]),  # Z axis
        np.array([0, 1, 0]),  # Y axis  
        np.array([1, 0, 0]),  # X axis
    ]
    
    best_symmetry = {"score": 0, "axis": None}
    
    for axis in candidate_axes:
        symmetry_score = 0
        
        # Test rotation at multiple angles
        angles = np.linspace(0, 2 * np.pi, num_angles, endpoint=False)
        
        for angle in angles[1:]:  # Skip 0
            # Rotation matrix around axis
            K = np.array([[0, -axis[2], axis[1]],
                         [axis[2], 0, -axis[0]],
                         [-axis[1], axis[0], 0]])
            R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
            
            # Rotate points
            rotated = points @ R.T
            
            # Compute nearest neighbor distances
            distances = []
            for p in rotated:
                dists = np.sqrt(np.sum((points - p) ** 2, axis=1))
                distances.append(np.min(dists))
            
            mean_distance = np.mean(distances)
            # Lower distance = better symmetry
            symmetry_score += 1.0 / (1.0 + mean_distance)
        
        avg_score = symmetry_score / (num_angles - 1)
        
        if avg_score > best_symmetry["score"]:
            best_symmetry = {
                "score": avg_score,
                "axis": axis.tolist(),
                "is_cylindrical": avg_score > 0.8  # Threshold
            }
    
    return {
        "is_cylindrical": best_symmetry.get("is_cylindrical", False),
        "symmetry_axis": best_symmetry.get("axis"),
        "symmetry_score": best_symmetry.get("score", 0),
        "num_test_angles": num_angles
    }


def get_mesh_bounds(mesh_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Get axis-aligned bounding box of a mesh.

    Args:
        mesh_path: Path to mesh file.

    Returns:
        Tuple of (min_bounds, max_bounds) as numpy arrays [x, y, z].

    Raises:
        FileNotFoundError: If mesh file does not exist.
        RuntimeError: If Open3D fails to load mesh.
    """
    if o3d is None:
        raise RuntimeError("Open3D is not installed")

    if not Path(mesh_path).exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

    try:
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        vertices = np.asarray(mesh.vertices)
        
        if len(vertices) == 0:
            raise ValueError("Mesh has no vertices")

        min_bounds = np.min(vertices, axis=0)
        max_bounds = np.max(vertices, axis=0)
        
        logger.debug(f"Bounds: min={min_bounds}, max={max_bounds}")
        return min_bounds, max_bounds

    except Exception as e:
        logger.error(f"Failed to get mesh bounds: {e}")
        raise RuntimeError(f"Failed to get mesh bounds: {e}") from e


def get_alignment_metadata(mesh_path: str) -> Dict[str, Any]:
    """Get alignment metadata for an already-aligned mesh.
    
    P8: Helper function to retrieve alignment information without re-aligning.
    
    Args:
        mesh_path: Path to aligned mesh file.
    
    Returns:
        Metadata dictionary.
    """
    if not Path(mesh_path).exists():
        return {"error": "Mesh file not found"}
    
    try:
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        
        # Compute basic properties
        vertices = np.asarray(mesh.vertices)
        properties = {
            "vertex_count": len(vertices),
            "centroid": np.mean(vertices, axis=0).tolist(),
            "bounds": {
                "min": np.min(vertices, axis=0).tolist(),
                "max": np.max(vertices, axis=0).tolist()
            }
        }
        
        # Analyze symmetry
        symmetry = analyze_rotational_symmetry(mesh)
        properties["symmetry"] = symmetry
        
        return properties
        
    except Exception as e:
        logger.error(f"Failed to get alignment metadata: {e}")
        return {"error": str(e)}


def compute_mesh_properties(mesh_path: str) -> dict:
    """Compute basic geometric properties of a mesh.

    Args:
        mesh_path: Path to mesh file.

    Returns:
        Dictionary with keys: volume, surface_area, centroid, bounds, is_watertight.

    Raises:
        FileNotFoundError: If mesh file does not exist.
        RuntimeError: If computation fails.
    """
    if o3d is None:
        raise RuntimeError("Open3D is not installed")

    if not Path(mesh_path).exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

    try:
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        
        # Compute properties
        volume = mesh.get_volume()
        surface_area = mesh.get_surface_area()
        
        vertices = np.asarray(mesh.vertices)
        centroid = np.mean(vertices, axis=0)
        min_bounds = np.min(vertices, axis=0)
        max_bounds = np.max(vertices, axis=0)
        
        # Check if watertight (simplified check)
        is_watertight = mesh.is_watertight()
        
        properties = {
            "volume": float(volume),
            "surface_area": float(surface_area),
            "centroid": centroid.tolist(),
            "bounds": {
                "min": min_bounds.tolist(),
                "max": max_bounds.tolist(),
                "size": (max_bounds - min_bounds).tolist()
            },
            "is_watertight": bool(is_watertight),
            "vertex_count": len(vertices),
            "triangle_count": len(mesh.triangles)
        }
        
        logger.info(f"Mesh properties computed: volume={volume:.4f}, area={surface_area:.4f}")
        return properties

    except Exception as e:
        logger.error(f"Failed to compute mesh properties: {e}")
        raise RuntimeError(f"Property computation failed: {e}") from e