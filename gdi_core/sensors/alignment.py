"""Mesh alignment utilities.

Handles the Step 0 (Human-in-the-Loop) alignment where operator
clicks on base plane (Z=0) and center axis.
"""

import numpy as np
import trimesh
from typing import Tuple, Optional


def align_mesh_to_origin(
    mesh: trimesh.Trimesh,
    base_point: Optional[np.ndarray] = None,
    center_point: Optional[np.ndarray] = None,
    target_axis: str = "Z"
) -> trimesh.Trimesh:
    """Align mesh to coordinate system based on human-specified points.
    
    Args:
        mesh: Input mesh (potentially misaligned)
        base_point: Point on the base plane (will become Z=0)
        center_point: Point defining the center axis
        target_axis: Target build axis ("X", "Y", or "Z")
        
    Returns:
        Transformed mesh aligned to coordinate system
    """
    mesh = mesh.copy()
    
    # If no base point provided, use lowest Z point
    if base_point is None:
        base_point = mesh.vertices[mesh.vertices[:, 2].argmin()]
    
    # Translate so base_point is at origin
    mesh.apply_translation(-base_point)
    
    # If center point provided, align it to target axis
    if center_point is not None:
        # Adjust center point for the translation we just did
        adjusted_center = center_point - base_point
        
        # Calculate rotation to align center to target axis
        if target_axis == "Z":
            target = np.array([0, 0, 1])
        elif target_axis == "Y":
            target = np.array([0, 1, 0])
        else:  # X
            target = np.array([1, 0, 0])
        
        # Project adjusted_center onto XY plane for rotation
        center_xy = adjusted_center.copy()
        center_xy[2] = 0  # Zero out Z for XY projection
        
        if np.linalg.norm(center_xy) > 1e-6:
            # Calculate angle to rotate center to target axis projection
            current_angle = np.arctan2(center_xy[1], center_xy[0])
            
            if target_axis == "Z":
                target_angle = 0
            elif target_axis == "Y":
                target_angle = np.pi / 2
            else:
                target_angle = 0
            
            rotation_angle = target_angle - current_angle
            mesh.apply_transform(trimesh.transformations.rotation_matrix(
                rotation_angle, [0, 0, 1], [0, 0, 0]
            ))
    
    # Ensure mesh is centered on XY plane
    centroid = mesh.centroid
    mesh.apply_translation([-centroid[0], -centroid[1], 0])
    
    return mesh


def detect_principal_axis(mesh: trimesh.Trimesh) -> str:
    """Detect the principal build axis based on mesh properties.
    
    Uses inertia analysis to determine the most likely build direction.
    
    Args:
        mesh: Input mesh
        
    Returns:
        Axis name ("X", "Y", or "Z") most suitable for building
    """
    # Calculate inertia properties
    inertia = mesh.moment_inertia
    
    # The principal axis of rotation has smallest moment
    # For additive manufacturing, we typically build along Z
    # But for turned parts, we might detect the rotation axis
    
    # Simple heuristic: axis with largest extent is usually NOT the build axis
    extents = mesh.extents
    
    # For most parts, build along the axis of symmetry or longest dimension
    if extents[2] >= max(extents[0], extents[1]):
        return "Z"
    elif extents[1] >= extents[0]:
        return "Y"
    else:
        return "X"
