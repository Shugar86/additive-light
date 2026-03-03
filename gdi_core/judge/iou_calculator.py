"""IoU Calculator for mesh comparison.

Computes Intersection over Union between original STL and generated STEP.
"""

import numpy as np
import trimesh
from typing import List, Dict, Any, Tuple
from shapely.geometry import Polygon
from shapely.ops import unary_union
import logging

logger = logging.getLogger(__name__)


def slice_mesh_at_heights(
    mesh: trimesh.Trimesh,
    heights: List[float],
    axis: str = "Z"
) -> Dict[float, Polygon]:
    """Slice mesh at specific heights and return 2D polygons.
    
    Args:
        mesh: Input mesh
        heights: List of Z-heights to slice at
        axis: Axis to slice along
        
    Returns:
        Dictionary mapping height to 2D polygon
    """
    slices = {}
    axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    
    for z in heights:
        try:
            if axis == "Z":
                plane_origin = [0, 0, z]
                plane_normal = [0, 0, 1]
            elif axis == "Y":
                plane_origin = [0, z, 0]
                plane_normal = [0, 1, 0]
            else:
                plane_origin = [z, 0, 0]
                plane_normal = [1, 0, 0]
            
            slice_result = mesh.section(
                plane_origin=plane_origin,
                plane_normal=plane_normal
            )
            
            if slice_result is None:
                continue
            
            slice_2d, _ = slice_result.to_planar()
            
            # Convert to shapely polygon
            polygons = []
            for entity in slice_2d.entities:
                if hasattr(entity, 'points'):
                    points = slice_2d.vertices[entity.points]
                    if len(points) >= 3:
                        poly = Polygon(points)
                        if poly.is_valid and poly.area > 1e-6:
                            polygons.append(poly)
            
            if polygons:
                merged = unary_union(polygons)
                slices[z] = merged
                
        except Exception as e:
            logger.warning(f"Failed to slice at {z}: {e}")
            continue
    
    return slices


def calculate_slice_iou(
    poly1: Polygon,
    poly2: Polygon
) -> float:
    """Calculate IoU between two 2D polygons.
    
    Args:
        poly1: First polygon
        poly2: Second polygon
        
    Returns:
        IoU score in [0.0, 1.0]
    """
    if not poly1.is_valid or not poly2.is_valid:
        return 0.0
    
    try:
        intersection = poly1.intersection(poly2).area
        union = poly1.union(poly2).area
        
        if union < 1e-10:
            return 0.0
        
        return float(intersection / union)
    except Exception:
        return 0.0


def calculate_iou(
    original_mesh: trimesh.Trimesh,
    generated_mesh: trimesh.Trimesh,
    num_slices: int = 10,
    axis: str = "Z"
) -> Tuple[float, List[Dict[str, Any]]]:
    """Calculate IoU between two meshes by slice comparison.
    
    Args:
        original_mesh: Original STL mesh
        generated_mesh: Generated mesh (from STEP)
        num_slices: Number of slices to compare
        axis: Axis to slice along
        
    Returns:
        (mean_iou, per_slice_details)
    """
    # Get common height range
    orig_bounds = original_mesh.bounds
    gen_bounds = generated_mesh.bounds
    
    axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    
    min_z = max(orig_bounds[0, axis_idx], gen_bounds[0, axis_idx])
    max_z = min(orig_bounds[1, axis_idx], gen_bounds[1, axis_idx])
    
    if max_z <= min_z:
        logger.warning("Meshes don't overlap in height")
        return 0.0, []
    
    # Generate slice heights
    heights = np.linspace(min_z + 0.1, max_z - 0.1, num_slices)
    
    # Slice both meshes
    orig_slices = slice_mesh_at_heights(original_mesh, heights, axis)
    gen_slices = slice_mesh_at_heights(generated_mesh, heights, axis)
    
    # Compare slices
    iou_scores = []
    details = []
    
    for z in heights:
        if z in orig_slices and z in gen_slices:
            iou = calculate_slice_iou(orig_slices[z], gen_slices[z])
            iou_scores.append(iou)
            details.append({
                "height": float(z),
                "iou": float(iou),
                "orig_area": float(orig_slices[z].area),
                "gen_area": float(gen_slices[z].area)
            })
        else:
            # Missing slice = 0 IoU
            details.append({
                "height": float(z),
                "iou": 0.0,
                "orig_area": float(orig_slices[z].area) if z in orig_slices else 0.0,
                "gen_area": float(gen_slices[z].area) if z in gen_slices else 0.0,
                "missing": True
            })
    
    mean_iou = float(np.mean(iou_scores)) if iou_scores else 0.0
    
    logger.info(f"IoU calculation: mean={mean_iou:.4f}, slices={len(iou_scores)}")
    
    return mean_iou, details
