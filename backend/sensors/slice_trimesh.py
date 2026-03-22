"""Trimesh-based mesh slicing and 2D geometric analysis.

This module provides deterministic slicing operations using Trimesh
and Shapely for 2D feature extraction. Pure math, no LLM magic.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import numpy.typing as npt

try:
    import trimesh
except ImportError:
    trimesh = None  # type: ignore

try:
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import unary_union
    from shapely.errors import TopologicalError
except ImportError:
    Polygon = Point = LineString = unary_union = None  # type: ignore
    TopologicalError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class SliceAnalyzer:
    """Analyzes 2D cross-sections of 3D meshes."""

    def __init__(self, mesh_path: str):
        """Initialize analyzer with a mesh file.

        Args:
            mesh_path: Path to STL/OBJ mesh file.

        Raises:
            FileNotFoundError: If mesh file doesn't exist.
            RuntimeError: If Trimesh fails to load mesh.
        """
        if trimesh is None:
            raise RuntimeError("Trimesh is not installed. Run: pip install trimesh")

        self.mesh_path = mesh_path
        if not Path(mesh_path).exists():
            raise FileNotFoundError(f"Mesh file not found: {mesh_path}")

        try:
            self.mesh = trimesh.load(mesh_path, force='mesh')
            logger.info(f"Loaded mesh: {len(self.mesh.vertices)} vertices, "
                       f"{len(self.mesh.faces)} faces")
        except Exception as e:
            logger.error(f"Failed to load mesh: {e}")
            raise RuntimeError(f"Mesh loading failed: {e}") from e

    def slice_along_axis(
        self,
        axis: str,
        slice_count: int = 20,
        slice_range: Optional[Tuple[float, float]] = None
    ) -> List[Dict[str, Any]]:
        """Create multiple parallel slices along specified axis.

        Args:
            axis: Axis to slice along ('X', 'Y', or 'Z').
            slice_count: Number of slices to create.
            slice_range: Optional (min, max) range. If None, uses mesh bounds.

        Returns:
            List of slice data dictionaries. Each contains:
            - position: float, slice position along axis
            - axis: str, which axis was sliced
            - polygons: list of Shapely polygons
            - area: float, total slice area
            - centroid: [x, y], slice centroid in 2D
            - features: detected geometric features

        Raises:
            ValueError: If axis is invalid or slice_count <= 0.
        """
        if axis.upper() not in ['X', 'Y', 'Z']:
            raise ValueError(f"Axis must be 'X', 'Y', or 'Z', got: {axis}")
        
        if slice_count <= 0:
            raise ValueError(f"slice_count must be positive, got: {slice_count}")

        axis_map = {'X': 0, 'Y': 1, 'Z': 2}
        axis_idx = axis_map[axis.upper()]

        # Determine slice positions
        bounds = self.mesh.bounds
        if slice_range:
            min_pos, max_pos = slice_range
        else:
            min_pos = bounds[0][axis_idx]
            max_pos = bounds[1][axis_idx]

        # Create slice planes
        positions = np.linspace(min_pos, max_pos, slice_count)
        logger.debug(f"Slicing {axis}-axis at {slice_count} positions from {min_pos:.3f} to {max_pos:.3f}")

        slices = []
        for pos in positions:
            try:
                slice_data = self._slice_at_position(axis_idx, pos, axis)
                if slice_data:
                    slices.append(slice_data)
            except Exception as e:
                logger.warning(f"Failed to slice at position {pos}: {e}")
                continue

        logger.info(f"Created {len(slices)} valid slices")
        return slices

    def _slice_at_position(
        self,
        axis_idx: int,
        position: float,
        axis_name: str
    ) -> Optional[Dict[str, Any]]:
        """Create a single slice at specified position."""
        # Create plane normal (e.g., for Z-slice, normal is [0, 0, 1])
        plane_normal = [0.0, 0.0, 0.0]
        plane_normal[axis_idx] = 1.0
        plane_origin = [0.0, 0.0, 0.0]
        plane_origin[axis_idx] = position

        try:
            # Get cross-section
            slice_3d = self.mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)
            
            if slice_3d is None:
                logger.debug(f"No geometry at position {position} on axis {axis_name}")
                return None

            # Convert to 2D
            # to_2D replaces the deprecated to_planar (removed in trimesh ≥ 4.x)
            try:
                slice_2d, _ = slice_3d.to_2D()
            except (AttributeError, TypeError):
                slice_2d, _ = slice_3d.to_planar()  # legacy fallback
            
            # Extract polygons
            polygons = []
            total_area = 0.0
            
            if hasattr(slice_2d, 'polygons_full'):
                for poly in slice_2d.polygons_full:
                    try:
                        shapely_poly = Polygon(poly)
                        if shapely_poly.is_valid and shapely_poly.area > 0:
                            polygons.append(shapely_poly)
                            total_area += shapely_poly.area
                    except Exception as e:
                        logger.debug(f"Invalid polygon at {position}: {e}")
                        continue

            if not polygons:
                return None

            # Compute combined properties
            try:
                combined = unary_union(polygons)
                centroid = list(combined.centroid.coords)[0] if hasattr(combined.centroid, 'coords') else [0.0, 0.0]
            except TopologicalError:
                # Fall back to largest polygon
                largest = max(polygons, key=lambda p: p.area)
                centroid = list(largest.centroid.coords)[0]

            # Detect features
            features = self._analyze_slice_features(polygons)

            return {
                "position": float(position),
                "axis": axis_name,
                "area": float(total_area),
                "centroid": list(centroid),
                "polygon_count": len(polygons),
                "features": features,
                "bounds": [
                    [float(combined.bounds[0]), float(combined.bounds[1])],
                    [float(combined.bounds[2]), float(combined.bounds[3])]
                ] if polygons else None
            }

        except Exception as e:
            logger.warning(f"Slice at {position} failed: {e}")
            return None

    def _analyze_slice_features(self, polygons: List[Polygon]) -> List[Dict[str, Any]]:
        """Analyze 2D polygons for geometric features.

        Detects circles, rectangles, and other primitives by comparing
        polygon properties to ideal shapes.

        Args:
            polygons: List of Shapely polygons from slice.

        Returns:
            List of detected feature dictionaries.
        """
        features = []

        for poly in polygons:
            try:
                if not poly.is_valid or poly.area < 1e-6:
                    continue

                feature = self._classify_polygon(poly)
                if feature:
                    features.append(feature)

            except Exception as e:
                logger.debug(f"Feature analysis failed for polygon: {e}")
                continue

        return features

    def _classify_polygon(self, poly: Polygon) -> Optional[Dict[str, Any]]:
        """Classify a single polygon by shape type."""
        try:
            area = poly.area
            perimeter = poly.length
            
            # Skip degenerate polygons
            if area < 1e-8 or perimeter < 1e-8:
                return None

            # Circle test: isoperimetric quotient (4*pi*A / P^2)
            # Perfect circle = 1.0, square = ~0.785
            circle_quotient = (4 * np.pi * area) / (perimeter ** 2)
            
            centroid = list(poly.centroid.coords)[0]
            bounds = poly.bounds  # minx, miny, maxx, maxy
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            aspect_ratio = max(width, height) / (min(width, height) + 1e-10)

            # Classify as circle if quotient is close to 1 and aspect ratio is close to 1
            if circle_quotient > 0.9 and aspect_ratio < 1.1:
                # Estimate radius from area: A = pi*r^2
                radius = np.sqrt(area / np.pi)
                return {
                    "type": "circle",
                    "center": list(centroid),
                    "radius": float(radius),
                    "area": float(area),
                    "perimeter": float(perimeter),
                    "circle_confidence": float(circle_quotient)
                }

            # Rectangle test: check if area approx equals width * height
            # and if the polygon has 4 vertices
            bbox_area = width * height
            fill_ratio = area / bbox_area if bbox_area > 0 else 0
            
            # Get exterior coordinates
            exterior = list(poly.exterior.coords)[:-1]  # Remove duplicate closing point
            vertex_count = len(exterior)
            
            if fill_ratio > 0.9 and aspect_ratio > 1.01 and vertex_count <= 8:
                return {
                    "type": "rectangle",
                    "center": list(centroid),
                    "width": float(width),
                    "height": float(height),
                    "area": float(area),
                    "aspect_ratio": float(aspect_ratio),
                    "vertex_count": vertex_count
                }

            # Generic polygon
            return {
                "type": "polygon",
                "center": list(centroid),
                "area": float(area),
                "perimeter": float(perimeter),
                "vertex_count": vertex_count,
                "circle_confidence": float(circle_quotient)
            }

        except Exception as e:
            logger.debug(f"Polygon classification failed: {e}")
            return None

    def find_cylindrical_features(
        self,
        axis: str = 'Z',
        tolerance: float = 0.05
    ) -> List[Dict[str, Any]]:
        """Find cylindrical features by analyzing circular cross-sections.

        Args:
            axis: Primary axis to analyze along.
            tolerance: Tolerance for radius consistency.

        Returns:
            List of detected cylinders with position, radius, and length.
        """
        slices = self.slice_along_axis(axis, slice_count=30)
        
        # Group consecutive circular slices
        cylinders = []
        current_cylinder = None
        
        for slice_data in slices:
            circles = [f for f in slice_data.get('features', []) if f['type'] == 'circle']
            
            if not circles:
                if current_cylinder:
                    cylinders.append(current_cylinder)
                    current_cylinder = None
                continue

            # Use the largest circle
            largest_circle = max(circles, key=lambda c: c['radius'])
            radius = largest_circle['radius']
            position = slice_data['position']
            
            if current_cylinder is None:
                current_cylinder = {
                    'start_position': position,
                    'end_position': position,
                    'radius': radius,
                    'center_xy': largest_circle['center'],
                    'positions': [position]
                }
            else:
                # Check if this slice continues the cylinder
                radius_diff = abs(radius - current_cylinder['radius'])
                if radius_diff < tolerance * current_cylinder['radius']:
                    current_cylinder['end_position'] = position
                    current_cylinder['positions'].append(position)
                else:
                    cylinders.append(current_cylinder)
                    current_cylinder = {
                        'start_position': position,
                        'end_position': position,
                        'radius': radius,
                        'center_xy': largest_circle['center'],
                        'positions': [position]
                    }

        if current_cylinder:
            cylinders.append(current_cylinder)

        # Filter out short cylinders (likely just small features)
        valid_cylinders = [
            c for c in cylinders 
            if len(c['positions']) >= 3  # At least 3 consecutive slices
        ]

        logger.info(f"Found {len(valid_cylinders)} cylindrical features along {axis}-axis")
        return valid_cylinders

    def sample_profile_along_axis(
        self,
        axis: str = 'Z',
        num_samples: int = 50,
        sample_type: str = "radius"
    ) -> List[Dict[str, Any]]:
        """Sample radial profile along the specified axis.

        This is the core function for shaft profiling. It slices the mesh
        perpendicular to the axis and measures the cross-section properties.

        Args:
            axis: Axis to sample along ('X', 'Y', or 'Z').
            num_samples: Number of sample positions along the axis.
            sample_type: Type of measurement - "radius", "area", or "full".

        Returns:
            List of sample dictionaries with keys:
            - position: float, position along axis
            - radius: float, estimated radius (for circular sections)
            - area: float, cross-sectional area
            - circularity: float, how circular the section is (0-1)
            - centroid: [x, y], 2D centroid of cross-section
            - bounds: [[min_x, min_y], [max_x, max_y]], bounding box
        """
        if axis.upper() not in ['X', 'Y', 'Z']:
            raise ValueError(f"Axis must be 'X', 'Y', or 'Z', got: {axis}")

        axis_map = {'X': 0, 'Y': 1, 'Z': 2}
        axis_idx = axis_map[axis.upper()]

        # Get bounds along axis
        bounds = self.mesh.bounds
        min_pos = bounds[0][axis_idx]
        max_pos = bounds[1][axis_idx]

        # Create sample positions
        positions = np.linspace(min_pos, max_pos, num_samples)
        logger.debug(f"Sampling {num_samples} positions along {axis}-axis from {min_pos:.3f} to {max_pos:.3f}")

        samples = []
        for pos in positions:
            try:
                sample = self._sample_at_position(axis_idx, pos, axis, sample_type)
                if sample:
                    samples.append(sample)
            except Exception as e:
                logger.debug(f"Failed to sample at position {pos}: {e}")
                continue

        logger.info(f"Collected {len(samples)} profile samples along {axis}-axis")
        return samples

    def _sample_at_position(
        self,
        axis_idx: int,
        position: float,
        axis_name: str,
        sample_type: str
    ) -> Optional[Dict[str, Any]]:
        """Sample cross-section at a single position."""
        plane_normal = [0.0, 0.0, 0.0]
        plane_normal[axis_idx] = 1.0
        plane_origin = [0.0, 0.0, 0.0]
        plane_origin[axis_idx] = position

        try:
            slice_3d = self.mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)
            if slice_3d is None:
                return None

            # to_2D replaces the deprecated to_planar (removed in trimesh ≥ 4.x)
            try:
                slice_2d, _ = slice_3d.to_2D()
            except (AttributeError, TypeError):
                slice_2d, _ = slice_3d.to_planar()  # legacy fallback

            # Extract polygons
            polygons = []
            if hasattr(slice_2d, 'polygons_full'):
                for poly in slice_2d.polygons_full:
                    try:
                        shapely_poly = Polygon(poly)
                        if shapely_poly.is_valid and shapely_poly.area > 0:
                            polygons.append(shapely_poly)
                    except Exception:
                        continue

            if not polygons:
                return None

            # Find the largest polygon (outer profile)
            largest_poly = max(polygons, key=lambda p: p.area)

            area = largest_poly.area
            perimeter = largest_poly.length
            centroid = list(largest_poly.centroid.coords)[0] if hasattr(largest_poly.centroid, 'coords') else [0.0, 0.0]
            bounds = largest_poly.bounds

            # Compute circularity
            circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0

            # Area-based radius estimate (backward compatible)
            radius = np.sqrt(area / np.pi)

            # Boundary-based radius: mean distance from centroid to all boundary
            # vertices. For a perfect circle this equals the true radius. For
            # slightly non-circular sections (mesh approximation) it gives a more
            # physically meaningful estimate than the area-based one.
            try:
                coords = np.array(largest_poly.exterior.coords)[:-1]  # drop duplicate
                centroid_xy = np.array([centroid[0], centroid[1]])
                boundary_distances = np.linalg.norm(coords - centroid_xy, axis=1)
                boundary_radius = float(np.mean(boundary_distances))
            except Exception:
                boundary_radius = radius  # fallback to area-based

            result = {
                "position": float(position),
                "axis": axis_name,
                "area": float(area),
                "perimeter": float(perimeter),
                "circularity": float(circularity),
                "radius": float(radius),           # area-based (backward compat)
                "boundary_radius": float(boundary_radius),  # mean boundary distance
                "centroid": list(centroid),
                "bounds": [[float(bounds[0]), float(bounds[1])], [float(bounds[2]), float(bounds[3])]]
            }

            return result

        except Exception as e:
            logger.debug(f"Sample at position {position} failed: {e}")
            return None