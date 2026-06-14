"""Open3D-based mesh alignment and centering utilities.

P8 Refactor: Enhanced alignment with RANSAC plane detection and ICP refinement
for mechanical reverse engineering.

Sprint 2.1-2.2 rescue: ``ransac_plane_axes`` lifted from the dropped P8-P9
commit ``f6b25652`` and adapted to operate on a NumPy point sample so the
loader can keep using ``trimesh`` (which is the stable path on WSL2 mounts
where ``open3d.io.read_triangle_mesh`` occasionally returns an empty mesh).

This module provides deterministic, mathematical operations for preparing
STL meshes for analysis. All functions are pure computation with no LLM involvement.
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import numpy as np
import numpy.typing as npt

try:
    import open3d as o3d
except ImportError:
    o3d = None  # type: ignore

logger = logging.getLogger(__name__)


def ransac_plane_axes(
    points: np.ndarray,
    *,
    min_plane_points: int = 100,
    ransac_threshold: float = 0.01,
    max_planes: int = 3,
    num_iterations: int = 1000,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Compute a principal-axes rotation from RANSAC plane detection on a point cloud.

    Mechanical parts are typically dominated by a small set of mutually
    perpendicular flat faces (top, bottom, side). RANSAC finds those faces
    far more reliably than PCA when the part has an obvious "ground" face
    (think machined flange, bracket, NEMA mount, etc.).

    The function returns a 3x3 rotation matrix whose rows are an orthonormal
    basis aligned with the dominant detected planes, ordered from largest to
    smallest plane inlier count. When fewer than two planes are detected, or
    open3d is unavailable, the function falls back to PCA on the input
    points and reports it through the metadata.

    Args:
        points: ``(N, 3)`` numpy array of points to fit planes to.
        min_plane_points: Minimum inliers required to accept a plane.
        ransac_threshold: Distance threshold for inliers in source units (mm).
        max_planes: Up to how many orthogonal planes to extract.
        num_iterations: RANSAC iterations per plane.

    Returns:
        Tuple of ``(rotation_matrix, metadata)``. ``rotation_matrix`` is
        a ``(3, 3)`` array, each row a unit basis vector. ``metadata``
        carries ``method`` (``"ransac_planes"`` or ``"pca_fallback"``),
        ``plane_count``, ``inliers``, and any fallback reason.

    Raises:
        ValueError: If ``points`` is not an ``(N, 3)`` array.
    """
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"Expected (N, 3) points, got shape {points.shape}")

    def _pca_fallback(reason: str, planes_found: int = 0) -> Tuple[np.ndarray, Dict[str, Any]]:
        centered = points - points.mean(axis=0)
        cov = np.cov(centered.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = eigvals.argsort()[::-1]
        rot = eigvecs[:, order].T
        return rot, {
            "method": "pca_fallback",
            "reason": reason,
            "planes_found": planes_found,
            "eigenvalues": eigvals[order].tolist(),
        }

    if o3d is None:
        return _pca_fallback("open3d_missing")
    if len(points) < min_plane_points:
        return _pca_fallback("too_few_points")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))

    detected: List[Dict[str, Any]] = []
    remaining = pcd
    for _ in range(max_planes):
        if len(remaining.points) < min_plane_points:
            break
        plane_model, inliers = remaining.segment_plane(
            distance_threshold=ransac_threshold,
            ransac_n=3,
            num_iterations=num_iterations,
        )
        if len(inliers) < min_plane_points:
            break
        normal = np.array(plane_model[:3], dtype=np.float64)
        norm = np.linalg.norm(normal)
        if norm < 1e-9:
            break
        normal = normal / norm
        detected.append({"normal": normal, "inliers": int(len(inliers))})
        remaining = remaining.select_by_index(inliers, invert=True)

    if len(detected) < 2:
        return _pca_fallback("too_few_planes", planes_found=len(detected))

    # Primary = normal of the largest plane (RANSAC sorts by inlier count
    # implicitly because we extract iteratively from the residual cloud).
    primary = detected[0]["normal"]

    # Pick the first subsequent plane whose normal is genuinely non-parallel
    # to ``primary`` (cos(angle) < 0.9). For a disc-shaped part (top + bottom
    # caps) the RANSAC pass returns two parallel normals — adopting one as
    # ``secondary`` would collapse the basis. Falling back to PCA for the
    # tangential axes preserves the diametral information we need.
    secondary_normal: Optional[np.ndarray] = None
    for cand in detected[1:]:
        if abs(float(np.dot(cand["normal"], primary))) < 0.9:
            secondary_normal = cand["normal"]
            break
    if secondary_normal is None:
        # No transverse plane detected. Use PCA on the input points to build
        # an orthogonal basis perpendicular to ``primary``.
        residual = points - points.mean(axis=0)
        proj = residual - np.outer(residual @ primary, primary)
        cov = np.cov(proj.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = eigvals.argsort()[::-1]
        secondary_normal = eigvecs[:, order[0]]
        method = "ransac_primary_pca_tangent"
    else:
        method = "ransac_planes"

    secondary = secondary_normal - np.dot(secondary_normal, primary) * primary
    sec_norm = np.linalg.norm(secondary)
    if sec_norm < 1e-6:
        helper = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(primary, helper)) > 0.95:
            helper = np.array([0.0, 1.0, 0.0])
        secondary = np.cross(primary, helper)
        sec_norm = np.linalg.norm(secondary)
    secondary = secondary / sec_norm
    tertiary = np.cross(primary, secondary)
    tertiary = tertiary / max(np.linalg.norm(tertiary), 1e-12)

    # Stack so that the primary plane normal becomes the **Z** axis after
    # ``apply_transform(rotation.T)``. PCA's convention is "longest dim → X",
    # so for a shaft we want the rotational axis to land on Z. The two
    # tangent vectors fill X and Y in arbitrary order.
    rotation = np.vstack([secondary, tertiary, primary])
    return rotation, {
        "method": method,
        "plane_count": len(detected),
        "inliers": [p["inliers"] for p in detected],
    }


def detect_principal_axes_ransac(
    mesh: "o3d.geometry.TriangleMesh",
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
        # WSL2/Open3D workaround: use trimesh which is stable on WSL2 mounts
        import trimesh
        
        logger.info(f"Loading mesh from {stl_path}")
        mesh = trimesh.load(stl_path, force='mesh')
        
        if len(mesh.vertices) == 0:
            raise ValueError("Mesh has no vertices - file may be corrupted")

        # Compute centroid
        centroid = mesh.centroid.copy()
        logger.debug(f"Original centroid: {centroid}")

        # Center the mesh at origin (in-place translation)
        mesh.apply_translation(-centroid)
        centered_vertices = mesh.vertices.copy()

        # PCA baseline. Sprint 2.1-2.2 adds RANSAC refinement on top: PCA is
        # cheap and reliable for "long" parts, RANSAC catches near-degenerate
        # cases (L ≈ D, heavy flange, hourglass) where PCA's primary axis
        # becomes ambiguous.
        covariance = np.cov(centered_vertices.T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        idx = eigenvalues.argsort()[::-1]
        rotation_matrix = eigenvectors[:, idx].T
        sorted_eig = eigenvalues[idx]

        metadata["alignment_method"] = "pca"
        metadata["eigenvalues"] = sorted_eig.tolist()
        logger.debug(f"Principal axes matrix shape: {rotation_matrix.shape}")

        # Engage RANSAC when PCA is suspect (small spread between the top
        # two eigenvalues) and open3d is available. Spread is the relative
        # gap (λ1 − λ2) / λ1 — values below ~0.2 mean PCA cannot tell long
        # from medium axis reliably.
        eig_spread = (
            float((sorted_eig[0] - sorted_eig[1]) / sorted_eig[0])
            if sorted_eig[0] > 1e-12
            else 0.0
        )
        metadata["pca_spread"] = round(eig_spread, 6)
        ransac_meta: Dict[str, Any] = {"activated": False, "reason": "not_engaged"}
        if use_ransac and o3d is not None and len(centered_vertices) >= 200:
            sample_size = min(5000, len(centered_vertices))
            rng = np.random.default_rng(seed=42)
            idx_sample = rng.choice(len(centered_vertices), sample_size, replace=False)
            sample_pts = centered_vertices[idx_sample]
            # Pick a RANSAC threshold proportional to the part size (1% of bbox span).
            bbox_span = float(np.max(np.ptp(sample_pts, axis=0)))
            threshold = max(bbox_span * 0.01, 0.05)
            try:
                ransac_rot, ransac_info = ransac_plane_axes(
                    sample_pts, ransac_threshold=threshold
                )
                ransac_meta = {
                    "activated": True,
                    "threshold_mm": round(threshold, 4),
                    **ransac_info,
                }
                # Adopt RANSAC only when PCA is ambiguous AND RANSAC genuinely
                # discovered at least one strong plane (not its full PCA
                # fallback). Both ``ransac_planes`` (two non-parallel planes)
                # and ``ransac_primary_pca_tangent`` (one plane + PCA tangent
                # basis) count as a real win — the second mode is exactly
                # what disc-like parts need.
                if eig_spread < 0.2 and ransac_info.get("method", "").startswith("ransac"):
                    rotation_matrix = ransac_rot
                    metadata["alignment_method"] = ransac_info.get("method")
                    logger.info(
                        "[align] RANSAC engaged: spread=%.3f, method=%s, planes=%d, threshold=%.3fmm",
                        eig_spread,
                        ransac_info.get("method"),
                        ransac_info.get("plane_count"),
                        threshold,
                    )
            except Exception as exc:  # noqa: BLE001 — RANSAC must never fail the load
                ransac_meta = {"activated": True, "error": str(exc)}
                logger.warning("[align] RANSAC refinement failed: %s", exc)
        metadata["ransac"] = ransac_meta

        # Rotate mesh to align with principal axes
        mesh.apply_transform(np.vstack([
            np.hstack([rotation_matrix.T, [[0], [0], [0]]]),
            [0, 0, 0, 1]
        ]))

        # Determine output path
        if output_path is None:
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            output_path = str(temp_dir / f"aligned_{stl_file.stem}.stl")

        # Save aligned mesh
        mesh.export(output_path)

        logger.info(f"Aligned mesh saved to {output_path} (method: {metadata['alignment_method']})")
        
        return output_path, centroid, rotation_matrix, metadata

    except ImportError:
        raise RuntimeError("Trimesh is not installed. Run: pip install trimesh")
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
        RuntimeError: If trimesh fails to load mesh.
    """
    if not Path(mesh_path).exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

    try:
        import trimesh
        mesh = trimesh.load(mesh_path, force='mesh')
        
        if len(mesh.vertices) == 0:
            raise ValueError("Mesh has no vertices")

        min_bounds = mesh.bounds[0]
        max_bounds = mesh.bounds[1]
        
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