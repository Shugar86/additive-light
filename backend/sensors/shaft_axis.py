"""Shaft axis detection for rotational parts.

This module provides deterministic, mathematical operations for detecting
the main rotational axis of shaft-like parts using Open3D and Trimesh.
No LLM involvement - pure geometric analysis.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

try:
    import open3d as o3d
except ImportError:
    o3d = None  # type: ignore

try:
    import trimesh
except ImportError:
    trimesh = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class AxisInfo:
    """Information about the detected main axis of a shaft.
    
    Attributes:
        direction: Unit vector of the axis direction.
        origin: Point on the axis (typically centroid).
        confidence: Detection confidence (0.0-1.0).
        length: Estimated length along the axis.
        method: Detection method used.
    """
    direction: npt.NDArray[np.float64]
    origin: npt.NDArray[np.float64]
    confidence: float
    length: float
    method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "direction": self.direction.tolist(),
            "origin": self.origin.tolist(),
            "confidence": self.confidence,
            "length": self.length,
            "method": self.method
        }


def detect_main_axis(
    mesh_path: str,
    method: str = "auto",
    sample_count: int = 50
) -> AxisInfo:
    """Detect the main rotational axis of a shaft-like mesh.
    
    For shafts, the main axis is typically the axis of rotational symmetry.
    This function uses multiple strategies to determine the axis:
    1. Symmetry analysis (for clean, symmetric shafts)
    2. Circular cross-section analysis (for stepped shafts)
    3. Moment of inertia (for asymmetric shafts)
    
    Args:
        mesh_path: Path to the mesh file (STL, OBJ, etc.).
        method: Detection method - "auto", "symmetry", "slices", or "inertia".
        sample_count: Number of cross-section samples for slice-based methods.
    
    Returns:
        AxisInfo with detected axis direction, origin, and confidence.
    
    Raises:
        FileNotFoundError: If mesh file does not exist.
        RuntimeError: If detection fails.
    
    Example:
        >>> axis_info = detect_main_axis("shaft.stl")
        >>> print(f"Axis: {axis_info.direction}, Confidence: {axis_info.confidence}")
    """
    if o3d is None:
        raise RuntimeError("Open3D is not installed. Run: pip install open3d")
    
    mesh_file = Path(mesh_path)
    if not mesh_file.exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")
    
    logger.info(f"[detect_main_axis] Analyzing {mesh_path} (method={method})")
    
    try:
        # Load mesh
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        if len(mesh.vertices) == 0:
            raise ValueError("Mesh has no vertices")
        
        vertices = np.asarray(mesh.vertices)
        centroid = np.mean(vertices, axis=0)
        
        # Method selection
        if method == "auto":
            # Try symmetry first, fall back to inertia
            axis_info = _detect_by_symmetry(mesh, centroid)
            if axis_info.confidence < 0.7:
                logger.debug("[detect_main_axis] Low symmetry confidence, trying slice analysis")
                axis_info = _detect_by_slice_analysis(mesh, centroid, sample_count)
        elif method == "symmetry":
            axis_info = _detect_by_symmetry(mesh, centroid)
        elif method == "slices":
            axis_info = _detect_by_slice_analysis(mesh, centroid, sample_count)
        elif method == "inertia":
            axis_info = _detect_by_inertia(mesh, centroid)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        logger.info(f"[detect_main_axis] Detected axis: method={axis_info.method}, "
                   f"confidence={axis_info.confidence:.3f}, length={axis_info.length:.3f}")
        
        # Task 1.3: Add warning for low confidence
        if axis_info.confidence < 0.5:
            logger.warning(
                f"Low confidence ({axis_info.confidence:.2f}). "
                f"Mesh may not be axis-aligned. "
                f"Consider calling align_mesh_to_axis() before detect_main_axis()."
            )
            axis_info.method += "_low_confidence"
        
        return axis_info
        
    except Exception as e:
        logger.error(f"[detect_main_axis] Detection failed: {e}")
        raise RuntimeError(f"Axis detection failed: {e}") from e


def _detect_by_symmetry(
    mesh: Any,
    centroid: npt.NDArray[np.float64]
) -> AxisInfo:
    """Detect axis by analyzing rotational symmetry.
    
    Strategy: Sample points and test rotation around candidate axes (X, Y, Z).
    The axis with highest rotational symmetry is the shaft axis.
    """
    # Sample points uniformly
    pcd = mesh.sample_points_uniformly(number_of_points=3000)
    points = np.asarray(pcd.points)
    
    # Candidate axes to test
    candidates = [
        (np.array([1, 0, 0]), "X"),
        (np.array([0, 1, 0]), "Y"),
        (np.array([0, 0, 1]), "Z"),
    ]
    
    best_score = 0.0
    best_axis = candidates[2][0]  # Default to Z
    best_method = "symmetry_default"
    
    for axis, name in candidates:
        score = _compute_symmetry_score(points, axis, centroid)
        logger.debug(f"[symmetry] Axis {name}: score={score:.4f}")
        
        if score > best_score:
            best_score = score
            best_axis = axis
            best_method = f"symmetry_{name}"
    
    # Compute length along detected axis
    length = _compute_length_along_axis(mesh, best_axis, centroid)
    
    confidence = min(1.0, best_score * 1.2)  # Scale up slightly
    
    return AxisInfo(
        direction=best_axis,
        origin=centroid,
        confidence=confidence,
        length=length,
        method=best_method
    )


def _compute_symmetry_score(
    points: npt.NDArray[np.float64],
    axis: npt.NDArray[np.float64],
    center: npt.NDArray[np.float64],
    num_angles: int = 12
) -> float:
    """Compute rotational symmetry score around an axis.
    
    Higher score means more symmetric (more shaft-like).
    Uses KDTree for efficient nearest neighbor search.
    """
    from scipy.spatial import KDTree
    
    # Center points
    centered = points - center
    
    # Build KDTree once for efficient nearest neighbor queries
    kdtree = KDTree(centered)
    
    # Test multiple rotation angles
    angles = np.linspace(0, 2 * np.pi, num_angles, endpoint=False)[1:]  # Skip 0
    
    total_score = 0.0
    
    for angle in angles:
        # Rotation matrix around axis using Rodrigues formula
        K = np.array([[0, -axis[2], axis[1]],
                     [axis[2], 0, -axis[0]],
                     [-axis[1], axis[0], 0]])
        R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
        
        # Rotate points
        rotated = centered @ R.T
        
        # Compute Chamfer-like distance using KDTree
        # For efficiency, sample subset
        sample_indices = np.random.choice(len(rotated), min(500, len(rotated)), replace=False)
        rotated_sample = rotated[sample_indices]
        
        # Batch query KDTree for nearest neighbors
        distances, _ = kdtree.query(rotated_sample, k=1)
        mean_distance = np.mean(distances)
        
        # Convert to score (lower distance = higher score)
        score = 1.0 / (1.0 + mean_distance * 10)
        total_score += score
    
    return total_score / len(angles)


def _detect_by_slice_analysis(
    mesh: Any,
    centroid: npt.NDArray[np.float64],
    sample_count: int = 50
) -> AxisInfo:
    """Detect axis by analyzing circularity of cross-sections.
    
    Strategy: For each candidate axis, slice the mesh perpendicular to it
    and measure how circular the cross-sections are.
    """
    from backend.sensors.slice_trimesh import SliceAnalyzer
    
    # Convert to trimesh for slicing
    if trimesh is None:
        raise RuntimeError("Trimesh is required for slice analysis")
    
    # Use trimesh for slicing operations
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)
    
    try:
        tm_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    except Exception as e:
        logger.warning(f"[slice_analysis] Failed to create trimesh: {e}")
        return _detect_by_inertia(mesh, centroid)
    
    candidates = [
        (np.array([1, 0, 0]), "X"),
        (np.array([0, 1, 0]), "Y"),
        (np.array([0, 0, 1]), "Z"),
    ]
    
    best_score = 0.0
    best_axis = candidates[2][0]
    best_method = "slices_default"
    
    for axis, name in candidates:
        score = _compute_slice_circularity_score(tm_mesh, axis, sample_count)
        logger.debug(f"[slices] Axis {name}: circularity score={score:.4f}")
        
        if score > best_score:
            best_score = score
            best_axis = axis
            best_method = f"slices_{name}"
    
    length = _compute_length_along_axis(mesh, best_axis, centroid)
    confidence = min(1.0, best_score)
    
    return AxisInfo(
        direction=best_axis,
        origin=centroid,
        confidence=confidence,
        length=length,
        method=best_method
    )


def _compute_slice_circularity_score(
    mesh: "trimesh.Trimesh",
    axis: npt.NDArray[np.float64],
    sample_count: int
) -> float:
    """Compute circularity score by slicing mesh perpendicular to axis.
    
    Returns average circularity of cross-sections (1.0 = perfect circles).
    Uses Shapely Polygon instead of private _polygon attribute.
    """
    try:
        from shapely.geometry import Polygon as ShapelyPolygon
        
        # Get bounds along axis
        vertices = mesh.vertices
        projections = vertices @ axis
        min_proj, max_proj = np.min(projections), np.max(projections)
        
        if max_proj - min_proj < 0.001:
            return 0.0  # Flat along this axis
        
        # Sample positions along axis
        positions = np.linspace(min_proj + 0.05, max_proj - 0.05, sample_count)
        
        circularities = []
        
        for pos in positions:
            # Create plane perpendicular to axis at position
            plane_origin = pos * axis
            
            # Slice mesh with plane
            slice_result = mesh.section(plane_origin=plane_origin, plane_normal=axis)
            
            if slice_result is None:
                continue
            
            # Compute circularity for each closed loop
            for entity in slice_result.entities:
                if hasattr(entity, 'points') and len(entity.points) >= 3:
                    # Build Shapely Polygon from entity points
                    points = slice_result.vertices[entity.points]
                    
                    # Create Shapely polygon
                    poly = ShapelyPolygon(points)
                    
                    # Skip invalid polygons
                    if not poly.is_valid or poly.is_empty:
                        continue
                    
                    # Compute circularity = 4*pi*Area / Perimeter^2
                    # For a circle, this equals 1.0
                    area = poly.area
                    perimeter = poly.length
                    
                    if perimeter > 0:
                        circularity = (4 * np.pi * area) / (perimeter ** 2)
                        circularities.append(circularity)
        
        if not circularities:
            return 0.0
        
        # Return mean circularity, weighted toward higher values
        return float(np.mean(sorted(circularities, reverse=True)[:len(circularities)//2 + 1]))
        
    except Exception as e:
        logger.debug(f"[circularity] Computation failed: {e}")
        return 0.0


def _detect_by_inertia(
    mesh: Any,
    centroid: npt.NDArray[np.float64]
) -> AxisInfo:
    """Detect axis using moment of inertia (PCA).
    
    For shafts, the axis of rotation typically corresponds to the direction
    with the smallest moment of inertia (mass concentrated around axis).
    """
    vertices = np.asarray(mesh.vertices)
    
    # Compute covariance matrix (moment of inertia approximation)
    centered = vertices - centroid
    covariance = np.cov(centered.T)
    
    # Eigen decomposition
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    
    # Sort by eigenvalue (ascending - smallest first)
    idx = eigenvalues.argsort()
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    # The axis with smallest eigenvalue (smallest spread) is likely the shaft axis
    principal_axes = eigenvectors.T
    
    # Check each axis for shaft-like characteristics
    best_score = 0.0
    best_axis_idx = 0
    
    for i in range(3):
        axis = principal_axes[i]
        length = _compute_length_along_axis(mesh, axis, centroid)
        
        # Score based on aspect ratio (length vs diameter)
        other_eigenvalues = [eigenvalues[j] for j in range(3) if j != i]
        avg_diameter = np.sqrt(np.mean(other_eigenvalues)) * 2
        
        if avg_diameter > 0:
            aspect_ratio = length / avg_diameter
            # Higher aspect ratio = more shaft-like
            score = min(1.0, aspect_ratio / 5.0)  # Normalize
            
            if score > best_score:
                best_score = score
                best_axis_idx = i
    
    detected_axis = principal_axes[best_axis_idx]
    length = _compute_length_along_axis(mesh, detected_axis, centroid)
    
    return AxisInfo(
        direction=detected_axis,
        origin=centroid,
        confidence=best_score,
        length=length,
        method="inertia_pca"
    )


def _compute_length_along_axis(
    mesh: Any,
    axis: npt.NDArray[np.float64],
    center: npt.NDArray[np.float64]
) -> float:
    """Compute the length of the mesh along a given axis."""
    vertices = np.asarray(mesh.vertices)
    centered = vertices - center
    
    # Project onto axis
    projections = centered @ axis
    
    return float(np.max(projections) - np.min(projections))


def align_mesh_to_axis(
    mesh_path: str,
    output_path: Optional[str] = None,
    target_axis: npt.NDArray[np.float64] = np.array([0, 0, 1])
) -> Tuple[str, AxisInfo]:
    """Align a mesh so its main axis aligns with target_axis (default: Z).
    
    Args:
        mesh_path: Path to input mesh.
        output_path: Optional output path. If None, generates temp file.
        target_axis: Target direction for the main axis (default: Z-up).
    
    Returns:
        Tuple of (aligned_mesh_path, axis_info).
    """
    if o3d is None:
        raise RuntimeError("Open3D is not installed")
    
    # Detect main axis
    axis_info = detect_main_axis(mesh_path)
    
    # Load mesh
    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    
    # Center at origin
    mesh.translate(-axis_info.origin)
    
    # Compute rotation to align detected axis with target
    current_axis = axis_info.direction
    
    # Normalize
    current_axis = current_axis / (np.linalg.norm(current_axis) + 1e-10)
    target_axis = target_axis / (np.linalg.norm(target_axis) + 1e-10)
    
    # If already aligned, skip
    if np.dot(current_axis, target_axis) > 0.999:
        logger.info("[align_mesh_to_axis] Axis already aligned")
    else:
        # Compute rotation axis (cross product)
        rotation_axis = np.cross(current_axis, target_axis)
        rotation_axis_norm = np.linalg.norm(rotation_axis)
        
        if rotation_axis_norm > 0.001:
            rotation_axis = rotation_axis / rotation_axis_norm
            angle = np.arccos(np.clip(np.dot(current_axis, target_axis), -1, 1))
            
            # Rodrigues rotation formula
            K = np.array([[0, -rotation_axis[2], rotation_axis[1]],
                         [rotation_axis[2], 0, -rotation_axis[0]],
                         [-rotation_axis[1], rotation_axis[0], 0]])
            R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
            
            mesh.rotate(R.T, center=(0, 0, 0))
            logger.info(f"[align_mesh_to_axis] Rotated by {np.degrees(angle):.2f} degrees")
    
    # Save aligned mesh
    if output_path is None:
        # Task 3.1: Use tempfile instead of hardcoded path
        import tempfile
        import os
        temp_base = Path(os.getenv("TEMP_DIR", tempfile.gettempdir()))
        temp_dir = temp_base / "additive_light_align"
        temp_dir.mkdir(parents=True, exist_ok=True)
        mesh_file = Path(mesh_path)
        output_path = str(temp_dir / f"axis_aligned_{mesh_file.stem}.stl")
    
    o3d.io.write_triangle_mesh(output_path, mesh)
    logger.info(f"[align_mesh_to_axis] Aligned mesh saved to {output_path}")
    
    return output_path, axis_info


def verify_axis_alignment(
    mesh_path: str,
    axis_info: AxisInfo,
    tolerance: float = 0.1
) -> Dict[str, Any]:
    """Verify that detected axis is correct by checking cross-sections.
    
    Returns verification report with metrics.
    """
    try:
        from backend.sensors.slice_trimesh import SliceAnalyzer
        
        analyzer = SliceAnalyzer(mesh_path)
        
        # Sample profile along detected axis
        axis_name = "Z"  # Assume aligned to Z after preprocessing
        profile_samples = analyzer.sample_profile_along_axis(
            axis=axis_name,
            num_samples=20,
            sample_type="radius"
        )
        
        if not profile_samples:
            return {"verified": False, "reason": "no_profile_samples"}
        
        # Analyze profile consistency
        radii = [s["radius"] for s in profile_samples if "radius" in s]
        
        if not radii:
            return {"verified": False, "reason": "no_radius_data"}
        
        # For a shaft, radii should vary smoothly
        radius_variance = np.var(radii)
        radius_range = max(radii) - min(radii)
        
        # Check circularity of cross-sections
        circularities = [s.get("circularity", 0) for s in profile_samples]
        mean_circularity = np.mean(circularities) if circularities else 0
        
        verification = {
            "verified": mean_circularity > 0.7 and radius_variance < 10.0,
            "mean_circularity": float(mean_circularity),
            "radius_variance": float(radius_variance),
            "radius_range": float(radius_range),
            "sample_count": len(profile_samples),
            "detected_confidence": axis_info.confidence
        }
        
        return verification
        
    except Exception as e:
        logger.warning(f"[verify_axis_alignment] Verification failed: {e}")
        # Task 1.4: Enrich return on error
        return {
            "verified": False,
            "error": str(e),
            "exception_type": type(e).__name__,
            "suggestion": "Run align_mesh_to_axis() before verification",
            "fallback_axis": axis_info.to_dict() if axis_info else None
        }
