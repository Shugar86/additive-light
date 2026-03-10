"""Shaft local feature detection (keyways, flats, holes).

This module detects non-rotational features on shafts:
- Keyways: Axial slots for keys
- Flats: Machined flat surfaces
- Cross holes: Perpendicular drilled holes

Uses Trimesh/Open3D for geometric analysis. Pure math, no LLM.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import numpy.typing as npt

try:
    import trimesh
except ImportError:
    trimesh = None  # type: ignore

try:
    import open3d as o3d
except ImportError:
    o3d = None  # type: ignore

from backend.sensors.slice_trimesh import SliceAnalyzer

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of local features on shafts."""
    KEYWAY = "keyway"              # Axial slot for key
    FLAT = "flat"                  # Machined flat surface
    CROSS_HOLE = "cross_hole"      # Perpendicular hole
    GROOVE = "groove"              # Circumferential groove
    THREAD = "thread"              # Threaded section
    SNAP_RING = "snap_ring"        # Snap ring groove
    OIL_HOLE = "oil_hole"          # Small lubrication hole


@dataclass
class ShaftFeature:
    """A local feature detected on a shaft.
    
    Attributes:
        feature_type: Type of feature.
        position: 3D center position [x, y, z].
        dimensions: Feature dimensions (width, height, depth, diameter, etc.).
        orientation: Principal direction/orientation vector.
        confidence: Detection confidence (0-1).
        zone_index: Which shaft zone this feature belongs to.
        evidence: List of evidence strings describing detection method.
    """
    feature_type: FeatureType
    position: npt.NDArray[np.float64]
    dimensions: Dict[str, float] = field(default_factory=dict)
    orientation: npt.NDArray[np.float64] = field(default_factory=lambda: np.array([0, 0, 1]))
    confidence: float = 0.0
    zone_index: Optional[int] = None
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_type": self.feature_type.value,
            "position": self.position.tolist(),
            "dimensions": self.dimensions,
            "orientation": self.orientation.tolist(),
            "confidence": self.confidence,
            "zone_index": self.zone_index,
            "evidence": self.evidence
        }


def detect_keyways_flats_holes(
    mesh_path: str,
    axis_info: Dict[str, Any],
    segments: List[Dict[str, Any]],
    detection_threshold: float = 0.7
) -> List[ShaftFeature]:
    """Detect keyways, flats, and holes on a shaft mesh.
    
    This is the main entry point for local feature detection.
    It analyzes deviations from perfect rotational symmetry.
    
    Args:
        mesh_path: Path to the aligned mesh file.
        axis_info: Dict with 'direction', 'origin', 'length' from axis detection.
        segments: List of shaft segments/zones from profiling.
        detection_threshold: Minimum confidence for feature detection.
    
    Returns:
        List of detected ShaftFeature objects.
    
    Raises:
        FileNotFoundError: If mesh file doesn't exist.
        RuntimeError: If detection fails.
    
    Example:
        >>> axis_info = detect_main_axis("shaft.stl")
        >>> profile, segments = extract_shaft_segments("shaft.stl")
        >>> features = detect_keyways_flats_holes("shaft.stl", axis_info, [s.to_dict() for s in segments])
    """
    if trimesh is None:
        raise RuntimeError("Trimesh is not installed. Run: pip install trimesh")
    
    mesh_file = Path(mesh_path)
    if not mesh_file.exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")
    
    logger.info(f"[detect_keyways_flats_holes] Analyzing {mesh_path}")
    
    try:
        features = []
        
        # Load mesh
        mesh = trimesh.load(mesh_path, force='mesh')
        
        # Detect keyways (axial slots)
        keyways = _detect_keyways(mesh, axis_info, segments, detection_threshold)
        features.extend(keyways)
        
        # Detect flats (machined flat surfaces)
        flats = _detect_flats(mesh, axis_info, segments, detection_threshold)
        features.extend(flats)
        
        # Detect cross holes (perpendicular drilled holes)
        holes = _detect_cross_holes(mesh, axis_info, segments, detection_threshold)
        features.extend(holes)
        
        # Detect grooves (circumferential)
        grooves = _detect_grooves(mesh, axis_info, segments, detection_threshold)
        features.extend(grooves)
        
        logger.info(f"[detect_keyways_flats_holes] Detected {len(features)} features: "
                   f"{len(keyways)} keyways, {len(flats)} flats, {len(holes)} holes, {len(grooves)} grooves")
        
        return features
        
    except Exception as e:
        logger.error(f"[detect_keyways_flats_holes] Detection failed: {e}")
        raise RuntimeError(f"Feature detection failed: {e}") from e


def _detect_keyways(
    mesh: "trimesh.Trimesh",
    axis_info: Dict[str, Any],
    segments: List[Dict[str, Any]],
    threshold: float
) -> List[ShaftFeature]:
    """Detect keyways by analyzing rectangular deviations in cross-sections.
    
    Keyways appear as rectangular slots in cross-sections perpendicular to the shaft axis.
    """
    keyways = []
    
    try:
        # Get axis direction (assuming aligned to Z)
        axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
        axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
        
        # Analyze cross-sections
        analyzer = SliceAnalyzer(mesh)
        
        # Get bounds along axis
        vertices = np.asarray(mesh.vertices)
        projections = vertices @ axis_direction
        min_pos, max_pos = np.min(projections), np.max(projections)
        
        # Sample positions for keyway detection
        num_samples = 30
        positions = np.linspace(min_pos + 0.1, max_pos - 0.1, num_samples)
        
        # Track rectangular features across slices
        candidate_keyways = []
        
        for pos in positions:
            try:
                # Slice perpendicular to axis
                plane_origin = pos * axis_direction + axis_origin
                slice_result = mesh.section(plane_origin=plane_origin, plane_normal=axis_direction)
                
                if slice_result is None:
                    continue
                
                slice_2d, _ = slice_result.to_planar()
                
                # Analyze polygons for rectangular features
                if hasattr(slice_2d, 'polygons_full'):
                    for poly in slice_2d.polygons_full:
                        from shapely.geometry import Polygon
                        try:
                            shapely_poly = Polygon(poly)
                            if not shapely_poly.is_valid:
                                continue
                            
                            # Check for keyway characteristics:
                            # 1. Small rectangular shape
                            # 2. Close to outer boundary (not center hole)
                            area = shapely_poly.area
                            bounds = shapely_poly.bounds
                            width = bounds[2] - bounds[0]
                            height = bounds[3] - bounds[1]
                            aspect = max(width, height) / (min(width, height) + 1e-10)
                            
                            # Keyway criteria: small area, rectangular (aspect > 1.5), 
                            # but not too elongated (aspect < 5)
                            if 1.5 < aspect < 5.0 and area > 1e-6:
                                # Check if near outer edge
                                # (distance from centroid to main circle center)
                                centroid = np.array(shapely_poly.centroid.coords)[0]
                                distance_from_center = np.linalg.norm(centroid)
                                
                                # Estimate outer radius from area of largest circle
                                outer_poly = max(slice_2d.polygons_full, key=lambda p: Polygon(p).area)
                                outer_area = Polygon(outer_poly).area
                                outer_radius = np.sqrt(outer_area / np.pi)
                                
                                # Keyway should be near outer radius
                                if outer_radius * 0.7 < distance_from_center < outer_radius * 0.95:
                                    candidate_keyways.append({
                                        "position": pos,
                                        "centroid": centroid,
                                        "width": min(width, height),
                                        "height": max(width, height),
                                        "area": area,
                                        "distance_from_center": distance_from_center,
                                        "outer_radius": outer_radius
                                    })
                        except Exception:
                            continue
                            
            except Exception as e:
                logger.debug(f"Keyway slice analysis failed at position {pos}: {e}")
                continue
        
        # Cluster candidates into keyway features
        if candidate_keyways:
            keyways = _cluster_keyway_candidates(candidate_keyways, axis_info)
        
        return keyways
        
    except Exception as e:
        logger.warning(f"[detect_keyways] Detection failed: {e}")
        return []


def _cluster_keyway_candidates(
    candidates: List[Dict[str, Any]],
    axis_info: Dict[str, Any]
) -> List[ShaftFeature]:
    """Cluster keyway candidates into coherent features.
    
    Keyways should span multiple slices in similar positions.
    """
    if not candidates:
        return []
    
    keyways = []
    axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
    axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
    
    # Group by similar angular position
    grouped = {}
    for c in candidates:
        # Compute angle from center
        centroid = c["centroid"]
        angle = np.arctan2(centroid[1], centroid[0])
        # Quantize angle for grouping
        angle_bin = round(np.degrees(angle) / 30) * 30  # 30-degree bins
        
        if angle_bin not in grouped:
            grouped[angle_bin] = []
        grouped[angle_bin].append(c)
    
    # Create features from groups that span multiple positions
    for angle_bin, group in grouped.items():
        if len(group) < 3:  # Need at least 3 slices
            continue
        
        # Sort by position
        group.sort(key=lambda x: x["position"])
        
        # Compute average dimensions
        avg_width = np.mean([c["width"] for c in group])
        avg_height = np.mean([c["height"] for c in group])
        min_pos = min(c["position"] for c in group)
        max_pos = max(c["position"] for c in group)
        
        # Compute 3D position
        avg_centroid = np.mean([c["centroid"] for c in group], axis=0)
        center_pos = (min_pos + max_pos) / 2
        
        # Project to 3D
        position_3d = axis_origin + center_pos * axis_direction
        position_3d[:2] += avg_centroid  # Add offset in perpendicular plane
        
        # Orientation is radial (pointing away from axis)
        orientation = np.array([avg_centroid[0], avg_centroid[1], 0])
        orientation_norm = np.linalg.norm(orientation)
        if orientation_norm > 0:
            orientation = orientation / orientation_norm
        else:
            orientation = np.array([1, 0, 0])
        
        keyway = ShaftFeature(
            feature_type=FeatureType.KEYWAY,
            position=position_3d,
            dimensions={
                "width": float(avg_width),
                "depth": float(avg_height),
                "length": float(max_pos - min_pos)
            },
            orientation=orientation,
            confidence=min(1.0, len(group) / 10),
            evidence=[f"Detected at {len(group)} slices, angular bin {angle_bin}°"]
        )
        keyways.append(keyway)
    
    return keyways


def _detect_flats(
    mesh: "trimesh.Trimesh",
    axis_info: Dict[str, Any],
    segments: List[Dict[str, Any]],
    threshold: float
) -> List[ShaftFeature]:
    """Detect flats by analyzing deviations from circular cross-sections.
    
    Flats appear as chord sections cutting into the circular profile.
    """
    flats = []
    
    try:
        axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
        axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
        
        # Sample positions along shaft
        vertices = np.asarray(mesh.vertices)
        projections = vertices @ axis_direction
        min_pos, max_pos = np.min(projections), np.max(projections)
        
        positions = np.linspace(min_pos + 0.1, max_pos - 0.1, 20)
        
        # Track flat sections
        flat_sections = []
        
        for pos in positions:
            try:
                plane_origin = pos * axis_direction + axis_origin
                slice_result = mesh.section(plane_origin=plane_origin, plane_normal=axis_direction)
                
                if slice_result is None:
                    continue
                
                slice_2d, _ = slice_result.to_planar()
                
                if not hasattr(slice_2d, 'polygons_full') or len(slice_2d.polygons_full) == 0:
                    continue
                
                # Get the outer polygon
                from shapely.geometry import Polygon
                polygons = [Polygon(p) for p in slice_2d.polygons_full]
                polygons = [p for p in polygons if p.is_valid]
                
                if not polygons:
                    continue
                
                outer_poly = max(polygons, key=lambda p: p.area)
                
                # Check circularity
                area = outer_poly.area
                perimeter = outer_poly.length
                circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
                
                # Low circularity suggests flats or other non-circular features
                if circularity < 0.85:
                    # Analyze shape to find flat regions
                    # Simplified: check if min/max radius varies significantly
                    coords = np.array(outer_poly.exterior.coords)
                    centroid = np.array(outer_poly.centroid.coords)[0]
                    
                    # Compute distances from centroid to boundary
                    distances = np.linalg.norm(coords[:, :2] - centroid, axis=1)
                    
                    radius_variation = (np.max(distances) - np.min(distances)) / np.mean(distances)
                    
                    if radius_variation > 0.05:  # More than 5% variation
                        flat_sections.append({
                            "position": pos,
                            "circularity": circularity,
                            "radius_variation": radius_variation,
                            "mean_radius": np.mean(distances),
                            "min_radius": np.min(distances),
                            "centroid": centroid
                        })
                        
            except Exception as e:
                logger.debug(f"Flat detection failed at position {pos}: {e}")
                continue
        
        # Group consecutive flat sections
        if flat_sections:
            flats = _group_flat_sections(flat_sections, axis_info)
        
        return flats
        
    except Exception as e:
        logger.warning(f"[detect_flats] Detection failed: {e}")
        return []


def _group_flat_sections(
    sections: List[Dict[str, Any]],
    axis_info: Dict[str, Any]
) -> List[ShaftFeature]:
    """Group flat sections into coherent flat features."""
    if not sections:
        return []
    
    flats = []
    axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
    axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
    
    # Sort by position
    sections.sort(key=lambda x: x["position"])
    
    # Group consecutive sections
    current_group = [sections[0]]
    
    for section in sections[1:]:
        # Check if this section continues the current flat
        last_pos = current_group[-1]["position"]
        if abs(section["position"] - last_pos) < 2.0:  # Within 2 units
            current_group.append(section)
        else:
            # Process current group
            if len(current_group) >= 2:
                flat = _create_flat_feature(current_group, axis_info)
                if flat:
                    flats.append(flat)
            current_group = [section]
    
    # Process final group
    if len(current_group) >= 2:
        flat = _create_flat_feature(current_group, axis_info)
        if flat:
            flats.append(flat)
    
    return flats


def _create_flat_feature(
    sections: List[Dict[str, Any]],
    axis_info: Dict[str, Any]
) -> Optional[ShaftFeature]:
    """Create a flat feature from grouped sections."""
    axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
    axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
    
    min_pos = min(s["position"] for s in sections)
    max_pos = max(s["position"] for s in sections)
    mean_radius = np.mean([s["mean_radius"] for s in sections])
    min_radius = np.min([s["min_radius"] for s in sections])
    
    # Flat depth is the reduction from mean radius
    flat_depth = mean_radius - min_radius
    
    if flat_depth < 0.1:  # Too shallow to be a meaningful flat
        return None
    
    center_pos = (min_pos + max_pos) / 2
    position_3d = axis_origin + center_pos * axis_direction
    
    # Orientation: flats are typically on one side
    # Simplified: assume flat faces along X axis for now
    orientation = np.array([1, 0, 0])
    
    return ShaftFeature(
        feature_type=FeatureType.FLAT,
        position=position_3d,
        dimensions={
            "depth": float(flat_depth),
            "width": float(mean_radius * 2),  # Approximate
            "length": float(max_pos - min_pos)
        },
        orientation=orientation,
        confidence=min(1.0, len(sections) / 5),
        evidence=[f"Detected at {len(sections)} positions, circularity variation"]
    )


def _detect_cross_holes(
    mesh: "trimesh.Trimesh",
    axis_info: Dict[str, Any],
    segments: List[Dict[str, Any]],
    threshold: float
) -> List[ShaftFeature]:
    """Detect cross holes by analyzing circular features in cross-sections.
    
    Cross holes appear as small circles within the main shaft cross-section.
    """
    holes = []
    
    try:
        axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
        axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
        
        vertices = np.asarray(mesh.vertices)
        projections = vertices @ axis_direction
        min_pos, max_pos = np.min(projections), np.max(projections)
        
        # Sample along axis
        positions = np.linspace(min_pos + 0.1, max_pos - 0.1, 30)
        
        # Track hole candidates
        hole_candidates = []
        
        for pos in positions:
            try:
                plane_origin = pos * axis_direction + axis_origin
                slice_result = mesh.section(plane_origin=plane_origin, plane_normal=axis_direction)
                
                if slice_result is None:
                    continue
                
                slice_2d, _ = slice_result.to_planar()
                
                if not hasattr(slice_2d, 'polygons_full'):
                    continue
                
                from shapely.geometry import Polygon
                polygons = [Polygon(p) for p in slice_2d.polygons_full if Polygon(p).is_valid]
                
                if len(polygons) <= 1:
                    continue  # No holes if only one polygon
                
                # Find main outer polygon
                areas = [p.area for p in polygons]
                main_idx = np.argmax(areas)
                main_poly = polygons[main_idx]
                main_area = main_poly.area
                
                # Check remaining polygons for hole characteristics
                for i, poly in enumerate(polygons):
                    if i == main_idx:
                        continue
                    
                    area = poly.area
                    perimeter = poly.length
                    
                    # Skip if too large (might be a feature, not a hole)
                    if area > main_area * 0.1:
                        continue
                    
                    # Check circularity
                    circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
                    
                    if circularity > 0.7:  # Reasonably circular
                        centroid = np.array(poly.centroid.coords)[0]
                        radius = np.sqrt(area / np.pi)
                        
                        hole_candidates.append({
                            "position": pos,
                            "centroid": centroid,
                            "radius": radius,
                            "area": area,
                            "circularity": circularity
                        })
                        
            except Exception as e:
                logger.debug(f"Hole detection failed at position {pos}: {e}")
                continue
        
        # Cluster hole candidates
        if hole_candidates:
            holes = _cluster_hole_candidates(hole_candidates, axis_info)
        
        return holes
        
    except Exception as e:
        logger.warning(f"[detect_cross_holes] Detection failed: {e}")
        return []


def _cluster_hole_candidates(
    candidates: List[Dict[str, Any]],
    axis_info: Dict[str, Any]
) -> List[ShaftFeature]:
    """Cluster hole candidates into coherent hole features."""
    if not candidates:
        return []
    
    holes = []
    axis_direction = np.array(axis_info.get("direction", [0, 0, 1]))
    axis_origin = np.array(axis_info.get("origin", [0, 0, 0]))
    
    # Group by similar radial position and angle
    # Simplified: group by similar 2D centroid position
    used = set()
    
    for i, c1 in enumerate(candidates):
        if i in used:
            continue
        
        group = [c1]
        used.add(i)
        
        for j, c2 in enumerate(candidates[i+1:], start=i+1):
            if j in used:
                continue
            
            # Check if positions are similar
            pos_diff = abs(c1["position"] - c2["position"])
            centroid_diff = np.linalg.norm(np.array(c1["centroid"]) - np.array(c2["centroid"]))
            
            if pos_diff < 2.0 and centroid_diff < 1.0:  # Similar location
                group.append(c2)
                used.add(j)
        
        # Create hole feature if enough slices
        if len(group) >= 2:
            avg_position = np.mean([c["position"] for c in group])
            avg_centroid = np.mean([c["centroid"] for c in group], axis=0)
            avg_radius = np.mean([c["radius"] for c in group])
            avg_circularity = np.mean([c["circularity"] for c in group])
            
            # 3D position
            position_3d = axis_origin + avg_position * axis_direction
            position_3d[:2] += avg_centroid
            
            # Orientation is perpendicular to shaft axis
            # For cross holes, they're typically perpendicular
            # We'll detect the orientation from the hole path
            orientation = np.array([avg_centroid[0], avg_centroid[1], 0])
            orientation_norm = np.linalg.norm(orientation)
            if orientation_norm > 0:
                orientation = orientation / orientation_norm
            else:
                orientation = np.array([1, 0, 0])
            
            hole = ShaftFeature(
                feature_type=FeatureType.CROSS_HOLE,
                position=position_3d,
                dimensions={
                    "diameter": float(avg_radius * 2),
                    "depth": float(np.max([c["position"] for c in group]) - np.min([c["position"] for c in group]))
                },
                orientation=orientation,
                confidence=min(1.0, len(group) / 5) * avg_circularity,
                evidence=[f"Detected at {len(group)} slices, circularity={avg_circularity:.3f}"]
            )
            holes.append(hole)
    
    return holes


def _detect_grooves(
    mesh: "trimesh.Trimesh",
    axis_info: Dict[str, Any],
    segments: List[Dict[str, Any]],
    threshold: float
) -> List[ShaftFeature]:
    """Detect circumferential grooves from shaft profile.
    
    Grooves are already partially detected in profiling; this refines them.
    """
    grooves = []
    
    # Check segments for groove zones
    for i, segment in enumerate(segments):
        zone_type = segment.get("zone_type", "")
        if zone_type == "groove" or "groove" in zone_type.lower():
            # Create feature from segment data
            position = np.array([
                (segment.get("start_pos", 0) + segment.get("end_pos", 0)) / 2,
                0,
                0
            ])
            
            groove = ShaftFeature(
                feature_type=FeatureType.GROOVE,
                position=position,
                dimensions={
                    "width": segment.get("end_pos", 0) - segment.get("start_pos", 0),
                    "depth": segment.get("metadata", {}).get("depth_reduction", 0) * segment.get("mean_radius", 1),
                    "radius": segment.get("mean_radius", 0)
                },
                orientation=np.array([0, 0, 1]),
                confidence=segment.get("confidence", 0.5),
                zone_index=i,
                evidence=["Detected in profile segmentation as groove zone"]
            )
            grooves.append(groove)
    
    return grooves


def compute_feature_clearances(
    features: List[ShaftFeature],
    profile: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute clearances and verify feature compatibility.
    
    Args:
        features: List of detected features.
        profile: Shaft profile data.
    
    Returns:
        Dictionary with clearance analysis.
    """
    analysis = {
        "feature_count": len(features),
        "interferences": [],
        "clearances": []
    }
    
    # Check for feature-to-feature interferences
    for i, f1 in enumerate(features):
        for f2 in features[i+1:]:
            distance = np.linalg.norm(f1.position - f2.position)
            
            # Get approximate sizes
            size1 = max(f1.dimensions.values()) if f1.dimensions else 1.0
            size2 = max(f2.dimensions.values()) if f2.dimensions else 1.0
            
            if distance < (size1 + size2) * 0.5:
                analysis["interferences"].append({
                    "feature_1": f1.feature_type.value,
                    "feature_2": f2.feature_type.value,
                    "distance": float(distance),
                    "severity": "warning"
                })
    
    return analysis
