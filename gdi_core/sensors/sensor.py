"""Multi-axis Slicer - Sensor Node 1.

Decomposes 3D mesh into 2D slices for analysis.
"""

import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class SliceMetrics:
    """Metrics for a single slice."""
    z_height: float
    area: float
    centroid: Tuple[float, float]
    bounding_box: Tuple[float, float, float, float]  # minx, miny, maxx, maxy
    perimeter: float
    num_holes: int
    is_valid: bool
    polygon: Optional[Polygon] = None


class Sensor:
    """Multi-axis Slicer - converts 3D mesh to 2D slice data.
    
    This is the first deterministic "sensor" in the pipeline.
    It decomposes 3D chaos into measurable 2D data.
    """
    
    def __init__(self, slice_step: float = 0.1):
        """Initialize sensor.
        
        Args:
            slice_step: Distance between slices in mm (default 0.1)
        """
        self.slice_step = slice_step
        
    def slice_mesh(
        self, 
        mesh: trimesh.Trimesh, 
        axis: str = "Z"
    ) -> List[SliceMetrics]:
        """Slice mesh along specified axis and compute metrics.
        
        Args:
            mesh: Input mesh (should be pre-aligned)
            axis: Axis to slice along ("X", "Y", or "Z")
            
        Returns:
            List of slice metrics sorted by height
        """
        # Get axis index
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
        
        # Calculate slice plane origins
        bounds = mesh.bounds
        min_z = bounds[0, axis_idx]
        max_z = bounds[1, axis_idx]
        
        # Generate slice heights
        heights = np.arange(min_z + self.slice_step, max_z - self.slice_step, self.slice_step)
        
        slices = []
        for z in heights:
            try:
                # Create slicing plane
                if axis == "Z":
                    plane_normal = [0, 0, 1]
                    plane_origin = [0, 0, z]
                elif axis == "Y":
                    plane_normal = [0, 1, 0]
                    plane_origin = [0, z, 0]
                else:  # X
                    plane_normal = [1, 0, 0]
                    plane_origin = [z, 0, 0]
                
                # Perform slice
                slice_result = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)
                
                if slice_result is None:
                    continue
                
                # Convert to 2D polygon
                slice_2d, _ = slice_result.to_planar()
                
                # Compute metrics
                metrics = self._compute_metrics(slice_2d, z)
                slices.append(metrics)
                
            except Exception as e:
                logger.warning(f"Failed to slice at z={z}: {e}")
                continue
        
        return slices
    
    def _compute_metrics(
        self, 
        slice_2d: trimesh.path.Path2D, 
        z_height: float
    ) -> SliceMetrics:
        """Compute metrics from a 2D slice.
        
        Args:
            slice_2d: 2D path from trimesh section
            z_height: Z-height of this slice
            
        Returns:
            SliceMetrics with computed values
        """
        # Extract polygons from slice
        polygons = []
        for entity in slice_2d.entities:
            if hasattr(entity, 'points'):
                points = slice_2d.vertices[entity.points]
                if len(points) >= 3:
                    poly = Polygon(points)
                    if poly.is_valid and poly.area > 1e-6:
                        polygons.append(poly)
        
        if not polygons:
            return SliceMetrics(
                z_height=z_height,
                area=0.0,
                centroid=(0.0, 0.0),
                bounding_box=(0.0, 0.0, 0.0, 0.0),
                perimeter=0.0,
                num_holes=0,
                is_valid=False
            )
        
        # Merge all polygons
        merged = unary_union(polygons)
        
        if isinstance(merged, MultiPolygon):
            # Multiple disconnected regions - take the largest
            main_poly = max(merged.geoms, key=lambda p: p.area)
            num_holes = len([r for r in merged.geoms if not r.exterior.equals(main_poly.exterior)])
        else:
            main_poly = merged
            num_holes = len(main_poly.interiors)
        
        bounds = main_poly.bounds
        
        return SliceMetrics(
            z_height=z_height,
            area=float(main_poly.area),
            centroid=(float(main_poly.centroid.x), float(main_poly.centroid.y)),
            bounding_box=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
            perimeter=float(main_poly.length),
            num_holes=num_holes,
            is_valid=True,
            polygon=main_poly
        )
    
    def detect_axis_of_minimum_variance(self, slices: List[SliceMetrics]) -> str:
        """Detect the axis with minimum variance in cross-section.
        
        For bodies of revolution, this identifies the rotation axis.
        
        Args:
            slices: List of slice metrics from multi-axis slicing
            
        Returns:
            Axis name ("X", "Y", or "Z") with minimum variance
        """
        # This is a placeholder - in full implementation we'd slice
        # along all three axes and compare
        # For now, default to Z as most common for additive
        return "Z"
    
    def export_slices_to_yaml(
        self, 
        slices: List[SliceMetrics],
        source_file: str
    ) -> Dict[str, Any]:
        """Export slice metrics to intermediate format.
        
        This is used by the Approximator for zone detection.
        
        Args:
            slices: List of slice metrics
            source_file: Source STL file path
            
        Returns:
            Dictionary with slice data
        """
        return {
            "source_file": source_file,
            "slice_count": len(slices),
            "slice_step_mm": self.slice_step,
            "slices": [
                {
                    "z": s.z_height,
                    "area": round(s.area, 4),
                    "centroid": [round(c, 4) for c in s.centroid],
                    "bbox": [round(b, 4) for b in s.bounding_box],
                    "perimeter": round(s.perimeter, 4),
                    "holes": s.num_holes
                }
                for s in slices if s.is_valid
            ]
        }
