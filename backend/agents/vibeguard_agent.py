"""VibeGuard (Judge) agent for geometric comparison and validation.

P8 Refactor: Enhanced judging with SDF-based metrics and improved error localization.

VibeGuard compares the generated B-Rep model with the original STL mesh
using Chamfer Distance, Hausdorff distance, and Signed Distance Field (SDF) metrics.
It generates a Failure Density Report that drives the reflection loop.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger(__name__)


class VibeGuardAgent:
    """Geometric judge that validates CAD output against input mesh.
    
    VibeGuard is the final gatekeeper. It determines if the generated
    parametric model accurately represents the original STL. If not,
    it provides detailed error reports for the reflection loop.
    """

    def __init__(
        self,
        sample_count: Optional[int] = None,
        chamfer_tolerance: Optional[float] = None,
        hausdorff_tolerance: Optional[float] = None
    ):
        """Initialize the VibeGuard agent.

        Args:
            sample_count: Number of points to sample for comparison.
            chamfer_tolerance: Maximum acceptable Chamfer distance.
            hausdorff_tolerance: Maximum acceptable Hausdorff distance.
        """
        self.sample_count = sample_count or settings.sample_point_count
        self.chamfer_tolerance = chamfer_tolerance or settings.chamfer_tolerance
        self.hausdorff_tolerance = hausdorff_tolerance or settings.hausdorff_tolerance
        
        logger.info(f"[VibeGuardAgent] Initialized (samples={self.sample_count}, "
                   f"chamfer_tol={self.chamfer_tolerance})")

    def compare(self, state: Any) -> Dict[str, Any]:
        """Compare generated mesh with original and produce error report.
        
        P8 Refactor: Now includes SDF metrics and improved error localization.

        Args:
            state: CADState with paths to both meshes.

        Returns:
            Dictionary with:
            - chamfer_distance: Computed Chamfer distance
            - hausdorff_distance: Computed Hausdorff distance
            - sdf_metrics: SDF-based volumetric metrics
            - errors: List of detected errors with locations
            - passed: Boolean indicating if model passes validation
        """
        original_path = state.stl_path
        generated_path = state.final_mesh_path

        if not original_path or not generated_path:
            logger.warning("[VibeGuardAgent] Missing mesh paths for comparison")
            return {
                "chamfer_distance": None,
                "hausdorff_distance": None,
                "sdf_metrics": None,
                "errors": [{"description": "Missing mesh paths"}],
                "passed": False
            }

        if not Path(original_path).exists():
            return {
                "chamfer_distance": None,
                "hausdorff_distance": None,
                "sdf_metrics": None,
                "errors": [{"description": f"Original mesh not found: {original_path}"}],
                "passed": False
            }

        if not Path(generated_path).exists():
            return {
                "chamfer_distance": None,
                "hausdorff_distance": None,
                "sdf_metrics": None,
                "errors": [{"description": f"Generated mesh not found: {generated_path}"}],
                "passed": False
            }

        try:
            # Load both meshes
            original_points = self._sample_mesh_points(original_path)
            generated_points = self._sample_mesh_points(generated_path)
            
            logger.debug(f"[VibeGuardAgent] Sampled {len(original_points)} points from original, "
                        f"{len(generated_points)} from generated")

            # Compute distances
            chamfer_dist = self._compute_chamfer_distance(original_points, generated_points)
            hausdorff_dist = self._compute_hausdorff_distance(original_points, generated_points)
            
            # P8: Compute SDF metrics
            sdf_metrics = self._compute_sdf_metric(original_points, generated_points)
            
            logger.info(f"[VibeGuardAgent] Distances: Chamfer={chamfer_dist:.4f}, "
                       f"Hausdorff={hausdorff_dist:.4f}, "
                       f"SDF_mean={sdf_metrics.get('sdf_mean', 0):.4f}")

            # P8: Enhanced error report
            errors = self._generate_error_report(
                original_points, generated_points,
                chamfer_dist, hausdorff_dist
            )
            
            # Add SDF-based volume error
            if abs(sdf_metrics.get("volume_error", 0)) > 0.1:
                vol_error = sdf_metrics["volume_error"]
                errors.append({
                    "type": "volume_mismatch",
                    "description": f"Volume error: {vol_error:.4f} (SDF metric)",
                    "severity": "high" if abs(vol_error) > 0.3 else "medium",
                    "location": "Global",
                    "suggestion": "Check overall dimensions and extrusion depths"
                })

            # Determine pass/fail with SDF consideration
            passed = (chamfer_dist < self.chamfer_tolerance and 
                     hausdorff_dist < self.hausdorff_tolerance and
                     sdf_metrics.get("sdf_mean", 0) < self.chamfer_tolerance and
                     abs(sdf_metrics.get("volume_error", 0)) < 0.2 and
                     len(errors) == 0)

            return {
                "chamfer_distance": float(chamfer_dist),
                "hausdorff_distance": float(hausdorff_dist),
                "sdf_metrics": sdf_metrics,
                "errors": errors,
                "passed": passed
            }

        except Exception as e:
            logger.error(f"[VibeGuardAgent] Comparison failed: {e}")
            return {
                "chamfer_distance": None,
                "hausdorff_distance": None,
                "sdf_metrics": None,
                "errors": [{"description": f"Comparison error: {e}"}],
                "passed": False
            }

    def _sample_mesh_points(self, mesh_path: str) -> np.ndarray:
        """Sample points from a mesh surface.
        
        Uses Trimesh or Open3D depending on availability.
        """
        # Try Trimesh first
        try:
            import trimesh
            mesh = trimesh.load(mesh_path)
            
            if hasattr(mesh, 'sample'):
                points = mesh.sample(self.sample_count)
                return np.array(points)
            else:
                # Fallback: sample from vertices
                vertices = np.array(mesh.vertices)
                if len(vertices) > self.sample_count:
                    indices = np.random.choice(len(vertices), self.sample_count, replace=False)
                    return vertices[indices]
                return vertices
                
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[VibeGuardAgent] Trimesh sampling failed: {e}")

        # Try Open3D
        try:
            import open3d as o3d
            mesh = o3d.io.read_triangle_mesh(mesh_path)
            
            # Sample points using Poisson disk or uniform
            pcd = mesh.sample_points_uniformly(number_of_points=self.sample_count)
            points = np.asarray(pcd.points)
            return points
            
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[VibeGuardAgent] Open3D sampling failed: {e}")

        raise RuntimeError("No mesh library available for point sampling")

    def _compute_chamfer_distance(
        self,
        points_a: np.ndarray,
        points_b: np.ndarray
    ) -> float:
        """Compute Chamfer distance between two point clouds.
        
        Chamfer distance is the mean of nearest-neighbor distances
        from A to B and from B to A.
        """
        # A to B
        dist_a_to_b = self._nearest_neighbor_distances(points_a, points_b)
        mean_a_to_b = np.mean(dist_a_to_b)
        
        # B to A
        dist_b_to_a = self._nearest_neighbor_distances(points_b, points_a)
        mean_b_to_a = np.mean(dist_b_to_a)
        
        # Symmetric Chamfer distance
        chamfer = (mean_a_to_b + mean_b_to_a) / 2.0
        
        return float(chamfer)

    def _compute_hausdorff_distance(
        self,
        points_a: np.ndarray,
        points_b: np.ndarray
    ) -> float:
        """Compute Hausdorff distance between two point clouds.
        
        Hausdorff distance is the maximum of nearest-neighbor distances.
        """
        # A to B
        dist_a_to_b = self._nearest_neighbor_distances(points_a, points_b)
        max_a_to_b = np.max(dist_a_to_b)
        
        # B to A
        dist_b_to_a = self._nearest_neighbor_distances(points_b, points_a)
        max_b_to_a = np.max(dist_b_to_a)
        
        # Symmetric Hausdorff distance
        hausdorff = max(max_a_to_b, max_b_to_a)
        
        return float(hausdorff)

    def _nearest_neighbor_distances(
        self,
        points_from: np.ndarray,
        points_to: np.ndarray
    ) -> np.ndarray:
        """Compute nearest neighbor distance from each point in points_from to points_to."""
        # Brute force for simplicity (could use KD-tree for large datasets)
        distances = []
        
        for p in points_from:
            # Distance to all points in points_to
            dists = np.sqrt(np.sum((points_to - p) ** 2, axis=1))
            min_dist = np.min(dists)
            distances.append(min_dist)
        
        return np.array(distances)

    def _compute_sdf_metric(
        self,
        original_points: np.ndarray,
        generated_points: np.ndarray,
        grid_resolution: int = 32
    ) -> Dict[str, float]:
        """Compute Signed Distance Field (SDF) based metrics.
        
        P8 Enhancement: SDF measures volumetric deviation, not just surface distance.
        This is crucial for detecting missing internal features or volume errors.
        
        Args:
            original_points: Point cloud of original mesh.
            generated_points: Point cloud of generated mesh.
            grid_resolution: Resolution of SDF grid.
        
        Returns:
            Dictionary with SDF metrics.
        """
        if len(original_points) == 0 or len(generated_points) == 0:
            return {"sdf_mean": 0, "sdf_max": 0, "volume_error": 0}
        
        try:
            # Compute bounding box
            all_points = np.vstack([original_points, generated_points])
            bb_min = np.min(all_points, axis=0)
            bb_max = np.max(all_points, axis=0)
            bb_size = bb_max - bb_min
            
            # Create grid
            x = np.linspace(bb_min[0], bb_max[0], grid_resolution)
            y = np.linspace(bb_min[1], bb_max[1], grid_resolution)
            z = np.linspace(bb_min[2], bb_max[2], grid_resolution)
            
            xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
            grid_points = np.stack([xx.ravel(), yy.ravel(), zz.ravel()], axis=1)
            
            # Compute SDF for original (simplified: distance to nearest point)
            sdf_original = self._approximate_sdf(grid_points, original_points)
            
            # Compute SDF for generated
            sdf_generated = self._approximate_sdf(grid_points, generated_points)
            
            # Difference
            sdf_diff = sdf_generated - sdf_original
            
            # Metrics
            metrics = {
                "sdf_mean": float(np.mean(np.abs(sdf_diff))),
                "sdf_max": float(np.max(np.abs(sdf_diff))),
                "sdf_rms": float(np.sqrt(np.mean(sdf_diff ** 2))),
                "volume_error": float(np.sum(sdf_diff) * np.prod(bb_size) / (grid_resolution ** 3)),
                "grid_resolution": grid_resolution
            }
            
            logger.info(f"[VibeGuard] SDF metrics: mean={metrics['sdf_mean']:.4f}, "
                       f"max={metrics['sdf_max']:.4f}")
            
            return metrics
            
        except Exception as e:
            logger.warning(f"[VibeGuard] SDF computation failed: {e}")
            return {"sdf_mean": 0, "sdf_max": 0, "volume_error": 0, "error": str(e)}
    
    def _approximate_sdf(
        self,
        query_points: np.ndarray,
        surface_points: np.ndarray
    ) -> np.ndarray:
        """Approximate SDF at query points using nearest surface point.
        
        This is a simplified SDF approximation. Full SDF would require
        watertight mesh and proper inside/outside classification.
        
        Args:
            query_points: Points where to compute SDF.
            surface_points: Points on the surface.
        
        Returns:
            Array of signed distances (negative inside, positive outside).
        """
        # Compute unsigned distance to nearest surface point
        distances = []
        
        for qp in query_points:
            dists = np.sqrt(np.sum((surface_points - qp) ** 2, axis=1))
            min_dist = np.min(dists)
            distances.append(min_dist)
        
        distances = np.array(distances)
        
        # Simple inside/outside test using ray casting approximation
        # Count how many surface points are in each octant
        # This is a heuristic - not rigorous but fast
        inside_mask = self._approximate_inside_test(query_points, surface_points)
        
        # Negative inside, positive outside
        signed_distances = distances * (1 - 2 * inside_mask)
        
        return signed_distances
    
    def _approximate_inside_test(
        self,
        query_points: np.ndarray,
        surface_points: np.ndarray,
        num_rays: int = 6
    ) -> np.ndarray:
        """Approximate inside/outside test using ray casting.
        
        Args:
            query_points: Points to test.
            surface_points: Surface points.
            num_rays: Number of rays to cast per point.
        
        Returns:
            Boolean array (True = inside).
        """
        inside = np.zeros(len(query_points), dtype=bool)
        
        # Ray directions (6 cardinal directions)
        directions = np.array([
            [1, 0, 0], [-1, 0, 0],
            [0, 1, 0], [0, -1, 0],
            [0, 0, 1], [0, 0, -1]
        ])
        
        for i, qp in enumerate(query_points):
            intersections = 0
            
            for direction in directions:
                # Ray: qp + t * direction
                # Find intersections with surface points
                # Simplified: count surface points that could be intersected
                to_surface = surface_points - qp
                
                # Check if point is in front of ray
                proj = np.dot(to_surface, direction)
                
                # Count potential intersections (simplified)
                close_points = np.sum((np.abs(proj) < 0.1) & (np.linalg.norm(to_surface, axis=1) < 1.0))
                intersections += close_points > 0
            
            # Odd number of intersections = inside
            inside[i] = (intersections % 2) == 1
        
        return inside
    
    def _compute_detailed_error_regions(
        self,
        original_points: np.ndarray,
        generated_points: np.ndarray,
        distances: np.ndarray,
        num_regions: int = 8
    ) -> List[Dict[str, Any]]:
        """Identify specific regions with high errors.
        
        P8 Enhancement: Better error localization for targeted repair.
        
        Args:
            original_points: Original point cloud.
            generated_points: Generated point cloud.
            distances: Per-point distances.
            num_regions: Number of spatial regions to analyze.
        
        Returns:
            List of error region descriptions.
        """
        errors = []
        
        if len(distances) == 0:
            return errors
        
        # Define spatial regions based on octants
        centroid = np.mean(original_points, axis=0)
        
        for i, point in enumerate(original_points):
            dist = distances[i]
            
            # Only consider high-error points
            if dist < np.mean(distances) + np.std(distances):
                continue
            
            # Determine octant
            octant = ""
            if point[0] > centroid[0]:
                octant += "+X"
            else:
                octant += "-X"
            if point[1] > centroid[1]:
                octant += "+Y"
            else:
                octant += "-Y"
            if point[2] > centroid[2]:
                octant += "+Z"
            else:
                octant += "-Z"
            
            # Create error entry
            error = {
                "type": "surface_deviation",
                "description": f"High deviation ({dist:.3f}) in {octant} region",
                "location": point.tolist(),
                "distance": float(dist),
                "octant": octant,
                "severity": "high" if dist > 2 * np.mean(distances) else "medium",
                "suggestion": f"Check geometry in {octant} region near ({point[0]:.1f}, {point[1]:.1f}, {point[2]:.1f})"
            }
            
            errors.append(error)
            
            # Limit number of reported errors
            if len(errors) >= 20:
                break
        
        return errors

    def _generate_error_report(
        self,
        original_points: np.ndarray,
        generated_points: np.ndarray,
        chamfer_dist: float,
        hausdorff_dist: float
    ) -> List[Dict[str, Any]]:
        """Generate detailed error report with locations.
        
        P8 Refactor: Enhanced error localization with detailed region analysis.
        Identifies regions where the generated model deviates significantly
        from the original.
        """
        errors: List[Dict[str, Any]] = []
        
        # Error 1: Overall distance too high
        if chamfer_dist > self.chamfer_tolerance:
            errors.append({
                "type": "global_chamfer",
                "description": f"Chamfer distance ({chamfer_dist:.4f}) exceeds tolerance ({self.chamfer_tolerance})",
                "severity": "high" if chamfer_dist > 2 * self.chamfer_tolerance else "medium",
                "location": "Global",
                "suggestion": "Check base dimensions and feature positions in the construction plan"
            })
        
        # Error 2: Local deviations (P8: enhanced with detailed regions)
        if len(original_points) > 0 and len(generated_points) > 0:
            # Compute distances for detailed analysis
            distances = self._nearest_neighbor_distances(original_points, generated_points)
            
            # Basic local deviations
            local_errors = self._find_local_deviations(original_points, generated_points)
            errors.extend(local_errors)
            
            # P8: Detailed error regions
            if chamfer_dist > 0.5 * self.chamfer_tolerance:
                detailed_errors = self._compute_detailed_error_regions(
                    original_points, generated_points, distances
                )
                errors.extend(detailed_errors)
        
        # Error 3: Volume comparison (rough check)
        volume_error = self._check_volume_conservation(original_points, generated_points)
        if volume_error:
            errors.append(volume_error)
        
        return errors

    def _find_local_deviations(
        self,
        original_points: np.ndarray,
        generated_points: np.ndarray,
        threshold_factor: float = 3.0
    ) -> List[Dict[str, Any]]:
        """Find regions with high local deviation."""
        errors: List[Dict[str, Any]] = []
        
        # Compute distances from original to generated
        distances = self._nearest_neighbor_distances(original_points, generated_points)
        
        # Find points with distance > threshold * mean
        mean_dist = np.mean(distances)
        threshold = threshold_factor * mean_dist
        
        bad_points = original_points[distances > threshold]
        bad_distances = distances[distances > threshold]
        
        if len(bad_points) > 0:
            # Cluster bad points to identify regions
            # Simple approach: just report the centroid of bad points
            error_center = np.mean(bad_points, axis=0)
            max_error = np.max(bad_distances)
            
            errors.append({
                "type": "local_deviation",
                "description": f"Found {len(bad_points)} points with high deviation (max: {max_error:.4f})",
                "severity": "high" if max_error > 5 * mean_dist else "medium",
                "location": [float(x) for x in error_center],
                "suggestion": f"Check geometry near coordinates ({error_center[0]:.2f}, {error_center[1]:.2f}, {error_center[2]:.2f})"
            })
        
        return errors

    def _check_volume_conservation(
        self,
        original_points: np.ndarray,
        generated_points: np.ndarray,
        tolerance: float = 0.2
    ) -> Optional[Dict[str, Any]]:
        """Check if volumes are approximately conserved.
        
        Uses bounding box as a rough volume proxy.
        """
        if len(original_points) == 0 or len(generated_points) == 0:
            return None
        
        # Compute bounding boxes
        orig_min = np.min(original_points, axis=0)
        orig_max = np.max(original_points, axis=0)
        orig_size = orig_max - orig_min
        orig_volume = np.prod(orig_size)
        
        gen_min = np.min(generated_points, axis=0)
        gen_max = np.max(generated_points, axis=0)
        gen_size = gen_max - gen_min
        gen_volume = np.prod(gen_size)
        
        if orig_volume > 0:
            volume_ratio = gen_volume / orig_volume
            
            if abs(volume_ratio - 1.0) > tolerance:
                return {
                    "type": "volume_mismatch",
                    "description": f"Volume ratio is {volume_ratio:.2f} (expected ~1.0)",
                    "severity": "medium",
                    "location": "Global",
                    "suggestion": "Check extrusion heights and cut depths in the construction plan"
                }
        
        return None


def create_vibeguard_agent() -> callable:
    """Factory function for creating VibeGuard agent.

    Returns:
        VibeGuard function: state -> comparison result dict.
    """
    agent = VibeGuardAgent()
    
    def vibeguard_fn(state: Any) -> Dict[str, Any]:
        return agent.compare(state)
    
    return vibeguard_fn