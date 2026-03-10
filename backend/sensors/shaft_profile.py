"""Shaft radial profile sampling and segmentation.

This module provides deterministic operations for:
1. Sampling radial profiles along the shaft axis
2. Segmenting the profile into zones (cylinders, fillets, grooves)
3. Identifying stepped diameters and transitions

Pure math using Open3D/Trimesh, no LLM.
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
    from scipy.signal import find_peaks
    from scipy.ndimage import gaussian_filter1d
except ImportError:
    find_peaks = None  # type: ignore
    gaussian_filter1d = None  # type: ignore

from backend.sensors.slice_trimesh import SliceAnalyzer

logger = logging.getLogger(__name__)


class ZoneType(Enum):
    """Types of zones in a shaft profile."""
    CYLINDER = "cylinder"          # Constant diameter section
    FILLET = "fillet"              # Smooth radius transition
    CHAMFER = "chamfer"            # Angled transition
    GROOVE = "groove"              # Recessed area
    STEP = "step"                  # Sharp diameter change
    END = "end"                    # End of shaft


@dataclass
class ProfileSample:
    """Single sample point in a radial profile.
    
    Attributes:
        position: Position along the shaft axis.
        radius: Estimated radius at this position.
        area: Cross-sectional area.
        circularity: How circular the cross-section is (0-1).
        confidence: Measurement confidence (0-1).
    """
    position: float
    radius: float
    area: float
    circularity: float
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "radius": self.radius,
            "area": self.area,
            "circularity": self.circularity,
            "confidence": self.confidence
        }


@dataclass
class ShaftZone:
    """A zone (segment) of the shaft profile.
    
    Attributes:
        zone_type: Type of zone (cylinder, fillet, etc.).
        start_pos: Start position along axis.
        end_pos: End position along axis.
        start_radius: Radius at start.
        end_radius: Radius at end.
        mean_radius: Average radius in zone.
        confidence: Detection confidence.
        samples: Number of samples in this zone.
    """
    zone_type: ZoneType
    start_pos: float
    end_pos: float
    start_radius: float
    end_radius: float
    mean_radius: float
    confidence: float
    samples: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type": self.zone_type.value,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "start_radius": self.start_radius,
            "end_radius": self.end_radius,
            "mean_radius": self.mean_radius,
            "length": self.end_pos - self.start_pos,
            "confidence": self.confidence,
            "samples": self.samples,
            "metadata": self.metadata
        }


@dataclass
class ShaftProfile:
    """Complete radial profile of a shaft.
    
    Attributes:
        samples: List of profile samples.
        zones: List of identified zones.
        total_length: Total length of the shaft.
        min_radius: Minimum radius.
        max_radius: Maximum radius.
        sample_count: Number of samples.
    """
    samples: List[ProfileSample]
    zones: List[ShaftZone]
    total_length: float
    min_radius: float
    max_radius: float
    sample_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "samples": [s.to_dict() for s in self.samples],
            "zones": [z.to_dict() for z in self.zones],
            "total_length": self.total_length,
            "min_radius": self.min_radius,
            "max_radius": self.max_radius,
            "sample_count": self.sample_count,
            "zone_count": len(self.zones)
        }


def sample_radial_profile(
    mesh_path: str,
    axis: str = "Z",
    num_samples: int = 100,
    circularity_threshold: float = 0.7
) -> ShaftProfile:
    """Sample the radial profile of a shaft along its main axis.
    
    This function slices the mesh perpendicular to the axis at regular
    intervals and measures the cross-sectional radius at each position.
    
    Args:
        mesh_path: Path to the mesh file.
        axis: Axis to sample along ('X', 'Y', or 'Z').
        num_samples: Number of sample positions.
        circularity_threshold: Minimum circularity for valid samples.
    
    Returns:
        ShaftProfile with samples and basic statistics.
    
    Raises:
        FileNotFoundError: If mesh file doesn't exist.
        RuntimeError: If sampling fails.
    
    Example:
        >>> profile = sample_radial_profile("shaft.stl", axis="Z", num_samples=100)
        >>> print(f"Shaft length: {profile.total_length}, Max radius: {profile.max_radius}")
    """
    if trimesh is None:
        raise RuntimeError("Trimesh is not installed. Run: pip install trimesh")
    
    mesh_file = Path(mesh_path)
    if not mesh_file.exists():
        raise FileNotFoundError(f"Mesh file not found: {mesh_path}")
    
    logger.info(f"[sample_radial_profile] Sampling {num_samples} points along {axis}-axis")
    
    try:
        # Use SliceAnalyzer for consistent slicing
        analyzer = SliceAnalyzer(mesh_path)
        
        # Get samples along the axis
        raw_samples = analyzer.sample_profile_along_axis(
            axis=axis,
            num_samples=num_samples,
            sample_type="radius"
        )
        
        if not raw_samples:
            raise RuntimeError("No valid samples could be extracted from mesh")
        
        # Convert to ProfileSample objects
        samples = []
        for rs in raw_samples:
            # Filter by circularity
            circularity = rs.get("circularity", 0)
            confidence = circularity if circularity >= circularity_threshold else circularity * 0.5
            
            sample = ProfileSample(
                position=rs["position"],
                radius=rs["radius"],
                area=rs["area"],
                circularity=circularity,
                confidence=confidence
            )
            samples.append(sample)
        
        # Sort by position
        samples.sort(key=lambda s: s.position)
        
        # Compute statistics
        positions = [s.position for s in samples]
        radii = [s.radius for s in samples]
        
        profile = ShaftProfile(
            samples=samples,
            zones=[],  # Zones identified in separate step
            total_length=max(positions) - min(positions),
            min_radius=min(radii),
            max_radius=max(radii),
            sample_count=len(samples)
        )
        
        logger.info(f"[sample_radial_profile] Sampled {len(samples)} points, "
                   f"length={profile.total_length:.3f}, radius range=[{profile.min_radius:.3f}, {profile.max_radius:.3f}]")
        
        return profile
        
    except Exception as e:
        logger.error(f"[sample_radial_profile] Sampling failed: {e}")
        raise RuntimeError(f"Profile sampling failed: {e}") from e


def segment_rotational_zones(
    profile: ShaftProfile,
    radius_tolerance: float = 0.05,
    slope_threshold: float = 0.5,
    min_zone_length: float = 0.5
) -> List[ShaftZone]:
    """Segment the shaft profile into zones based on geometry.
    
    This function identifies:
    - Cylindrical zones: Constant radius sections
    - Fillet zones: Smooth radius transitions
    - Chamfer zones: Linear (constant slope) transitions
    - Groove zones: Recessed areas
    - Step zones: Sharp diameter changes
    
    Args:
        profile: ShaftProfile with samples.
        radius_tolerance: Relative tolerance for constant radius (0.05 = 5%).
        slope_threshold: Threshold for identifying transitions (radius change per unit length).
        min_zone_length: Minimum zone length to be considered valid.
    
    Returns:
        List of ShaftZone objects describing each segment.
    """
    if not profile.samples:
        logger.warning("[segment_rotational_zones] No samples to segment")
        return []
    
    logger.info(f"[segment_rotational_zones] Segmenting {len(profile.samples)} samples")
    
    # Extract arrays for processing
    positions = np.array([s.position for s in profile.samples])
    radii = np.array([s.radius for s in profile.samples])
    circularities = np.array([s.circularity for s in profile.samples])
    
    # Smooth the radius profile to reduce noise
    if gaussian_filter1d is not None and len(radii) > 5:
        smoothed_radii = gaussian_filter1d(radii, sigma=1.0)
    else:
        smoothed_radii = radii
    
    # Compute derivatives for slope analysis
    if len(positions) > 1:
        dr = np.gradient(smoothed_radii, positions)
        d2r = np.gradient(dr, positions)
    else:
        dr = np.zeros_like(radii)
        d2r = np.zeros_like(radii)
    
    # Identify zone boundaries based on curvature and slope changes
    boundaries = _find_zone_boundaries(positions, smoothed_radii, dr, d2r, radius_tolerance)
    
    # Create zones from boundaries
    zones = []
    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        
        zone_samples = profile.samples[start_idx:end_idx + 1]
        if not zone_samples:
            continue
        
        zone = _classify_zone(
            zone_samples,
            dr[start_idx:end_idx + 1],
            d2r[start_idx:end_idx + 1],
            radius_tolerance,
            slope_threshold
        )
        
        # Filter by minimum length
        zone_length = zone.end_pos - zone.start_pos
        if zone_length >= min_zone_length:
            zones.append(zone)
        else:
            logger.debug(f"[segment_rotational_zones] Skipping short zone ({zone_length:.3f} < {min_zone_length})")
    
    # Merge adjacent cylindrical zones with similar radii
    zones = _merge_similar_cylinders(zones, radius_tolerance)
    
    # Detect grooves (check for local minima in radius)
    zones = _detect_grooves(zones, profile)
    
    logger.info(f"[segment_rotational_zones] Identified {len(zones)} zones")
    for z in zones:
        logger.debug(f"  {z.zone_type.value}: {z.start_pos:.3f}-{z.end_pos:.3f}, "
                    f"r={z.mean_radius:.3f}, confidence={z.confidence:.3f}")
    
    return zones


def _find_zone_boundaries(
    positions: npt.NDArray[np.float64],
    radii: npt.NDArray[np.float64],
    dr: npt.NDArray[np.float64],
    d2r: npt.NDArray[np.float64],
    tolerance: float
) -> List[int]:
    """Find indices where zone type changes."""
    boundaries = [0]  # Always start at first sample
    
    n = len(positions)
    if n < 3:
        return [0, n - 1]
    
    # Detect significant curvature changes
    curvature_threshold = 0.1  # Tunable parameter
    
    for i in range(1, n - 1):
        # Check for sign changes in second derivative (inflection points)
        if np.sign(d2r[i]) != np.sign(d2r[i - 1]) and abs(d2r[i]) > curvature_threshold:
            boundaries.append(i)
            continue
        
        # Check for sudden slope changes
        if i > 0 and i < n - 1:
            slope_change = abs(dr[i] - dr[i - 1])
            if slope_change > 0.5:  # Significant change in slope
                boundaries.append(i)
                continue
        
        # Check for step changes in radius
        if i > 0:
            radius_change = abs(radii[i] - radii[i - 1]) / (radii[i - 1] + 1e-10)
            if radius_change > tolerance * 2:  # Significant step
                boundaries.append(i)
    
    boundaries.append(n - 1)  # Always end at last sample
    
    # Remove duplicates and sort
    boundaries = sorted(set(boundaries))
    
    return boundaries


def _classify_zone(
    samples: List[ProfileSample],
    dr: npt.NDArray[np.float64],
    d2r: npt.NDArray[np.float64],
    radius_tolerance: float,
    slope_threshold: float
) -> ShaftZone:
    """Classify a zone based on its geometric properties."""
    if not samples:
        raise ValueError("Cannot classify empty zone")
    
    positions = [s.position for s in samples]
    radii = [s.radius for s in samples]
    circularities = [s.circularity for s in samples]
    
    start_pos = min(positions)
    end_pos = max(positions)
    start_radius = radii[0]
    end_radius = radii[-1]
    mean_radius = np.mean(radii)
    
    # Compute statistics for classification
    radius_std = np.std(radii)
    max_dr = np.max(np.abs(dr))
    mean_d2r = np.mean(np.abs(d2r))
    mean_circularity = np.mean(circularities)
    
    # Classification logic
    # 1. Cylinder: Nearly constant radius, low slope
    radius_variation = radius_std / (mean_radius + 1e-10)
    
    if radius_variation < radius_tolerance and max_dr < slope_threshold * 0.3:
        zone_type = ZoneType.CYLINDER
        confidence = 1.0 - radius_variation / radius_tolerance
    
    # 2. Step: Sharp radius change at boundary
    elif abs(end_radius - start_radius) / (mean_radius + 1e-10) > radius_tolerance * 2:
        zone_type = ZoneType.STEP
        confidence = 0.8
    
    # 3. Fillet: Smooth curve (high second derivative)
    elif mean_d2r > 0.05 and abs(end_radius - start_radius) > 0.1:
        zone_type = ZoneType.FILLET
        confidence = min(1.0, mean_d2r * 5)
    
    # 4. Chamfer: Linear transition (constant slope)
    elif max_dr > slope_threshold * 0.5 and mean_d2r < 0.05:
        zone_type = ZoneType.CHAMFER
        # Compute chamfer angle
        length = end_pos - start_pos
        if length > 0:
            chamfer_angle = np.degrees(np.arctan2(abs(end_radius - start_radius), length))
        else:
            chamfer_angle = 0
        confidence = 0.7 + 0.3 * (1.0 - abs(chamfer_angle - 45) / 45)  # Higher confidence near 45°
    
    # 5. Default to cylinder if mostly circular
    elif mean_circularity > 0.8:
        zone_type = ZoneType.CYLINDER
        confidence = mean_circularity
    
    # 6. Fallback
    else:
        zone_type = ZoneType.CYLINDER
        confidence = 0.5
    
    # Adjust confidence based on sample count and circularity
    confidence *= (0.5 + 0.5 * mean_circularity)
    confidence = max(0.0, min(1.0, confidence))
    
    metadata = {
        "radius_variation": float(radius_variation),
        "max_slope": float(max_dr),
        "mean_curvature": float(mean_d2r),
        "mean_circularity": float(mean_circularity)
    }
    
    if zone_type == ZoneType.CHAMFER:
        metadata["chamfer_angle_deg"] = chamfer_angle if 'chamfer_angle' in dir() else 0
    
    return ShaftZone(
        zone_type=zone_type,
        start_pos=start_pos,
        end_pos=end_pos,
        start_radius=start_radius,
        end_radius=end_radius,
        mean_radius=mean_radius,
        confidence=confidence,
        samples=len(samples),
        metadata=metadata
    )


def _merge_similar_cylinders(
    zones: List[ShaftZone],
    radius_tolerance: float
) -> List[ShaftZone]:
    """Merge adjacent cylindrical zones with similar radii."""
    if len(zones) < 2:
        return zones
    
    merged = []
    i = 0
    while i < len(zones):
        zone = zones[i]
        
        # If cylinder, try to merge with next cylinders
        if zone.zone_type == ZoneType.CYLINDER:
            while i + 1 < len(zones) and zones[i + 1].zone_type == ZoneType.CYLINDER:
                next_zone = zones[i + 1]
                
                # Check if radii are similar
                radius_diff = abs(zone.mean_radius - next_zone.mean_radius)
                relative_diff = radius_diff / max(zone.mean_radius, next_zone.mean_radius, 1e-10)
                
                if relative_diff < radius_tolerance:
                    # Merge zones
                    zone.end_pos = next_zone.end_pos
                    zone.end_radius = next_zone.end_radius
                    zone.mean_radius = (zone.mean_radius * zone.samples + next_zone.mean_radius * next_zone.samples) / (zone.samples + next_zone.samples)
                    zone.samples += next_zone.samples
                    zone.confidence = min(zone.confidence, next_zone.confidence)
                    i += 1
                else:
                    break
        
        merged.append(zone)
        i += 1
    
    return merged


def _detect_grooves(
    zones: List[ShaftZone],
    profile: ShaftProfile
) -> List[ShaftZone]:
    """Detect groove zones (local minima in radius)."""
    if not profile.samples or len(zones) < 2:
        return zones
    
    # Look for zones that might be grooves
    # A groove is typically a short zone with significantly smaller radius
    updated_zones = []
    
    for i, zone in enumerate(zones):
        is_groove_candidate = False
        
        # Check if this zone has much smaller radius than neighbors
        if 0 < i < len(zones) - 1:
            prev_radius = zones[i - 1].mean_radius
            next_radius = zones[i + 1].mean_radius
            neighbor_avg = (prev_radius + next_radius) / 2
            
            if zone.mean_radius < neighbor_avg * 0.85:  # 15% smaller than neighbors
                is_groove_candidate = True
        
        # Short zone with reduced radius
        zone_length = zone.end_pos - zone.start_pos
        if is_groove_candidate and zone_length < profile.total_length * 0.15:
            zone.zone_type = ZoneType.GROOVE
            zone.confidence = 0.8
            zone.metadata["depth_reduction"] = 1.0 - zone.mean_radius / neighbor_avg if 'neighbor_avg' in dir() else 0
        
        updated_zones.append(zone)
    
    return updated_zones


def extract_shaft_segments(
    mesh_path: str,
    axis: str = "Z",
    num_samples: int = 100,
    radius_tolerance: float = 0.05
) -> Tuple[ShaftProfile, List[ShaftZone]]:
    """Complete pipeline: sample profile and segment into zones.
    
    This is the main entry point for shaft profiling.
    
    Args:
        mesh_path: Path to mesh file.
        axis: Axis to analyze along.
        num_samples: Number of profile samples.
        radius_tolerance: Tolerance for radius matching.
    
    Returns:
        Tuple of (ShaftProfile, list of ShaftZone).
    """
    logger.info(f"[extract_shaft_segments] Processing {mesh_path}")
    
    # Sample the profile
    profile = sample_radial_profile(mesh_path, axis, num_samples)
    
    # Segment into zones
    zones = segment_rotational_zones(profile, radius_tolerance)
    
    # Update profile with zones
    profile.zones = zones
    
    logger.info(f"[extract_shaft_segments] Complete: {len(zones)} zones identified")
    
    return profile, zones


def get_cylindrical_segments(zones: List[ShaftZone]) -> List[ShaftZone]:
    """Filter zones to return only cylindrical segments.
    
    Useful for building the revolve profile - these are the main
    shaft sections that form the base geometry.
    """
    return [z for z in zones if z.zone_type == ZoneType.CYLINDER]


def get_transition_zones(zones: List[ShaftZone]) -> List[ShaftZone]:
    """Filter zones to return only transition features.
    
    These are fillets, chamfers, and steps that need special handling.
    """
    transition_types = {ZoneType.FILLET, ZoneType.CHAMFER, ZoneType.STEP}
    return [z for z in zones if z.zone_type in transition_types]


def build_revolve_profile(
    zones: List[ShaftZone],
    include_transitions: bool = False
) -> List[Tuple[float, float]]:
    """Build a 2D profile for revolution from shaft zones.
    
    Returns list of (position, radius) points suitable for
    creating a build123d revolve sketch.
    
    Args:
        zones: List of shaft zones.
        include_transitions: If True, include fillets/chamfers as approximated steps.
    
    Returns:
        List of (position, radius) tuples.
    """
    if not zones:
        return []
    
    points = []
    
    for zone in zones:
        if zone.zone_type == ZoneType.CYLINDER:
            # Constant radius: start and end points
            points.append((zone.start_pos, zone.mean_radius))
            points.append((zone.end_pos, zone.mean_radius))
        
        elif zone.zone_type in (ZoneType.FILLET, ZoneType.CHAMFER) and include_transitions:
            # Approximate as linear transition
            points.append((zone.start_pos, zone.start_radius))
            # Add midpoint for better approximation
            mid_pos = (zone.start_pos + zone.end_pos) / 2
            mid_radius = (zone.start_radius + zone.end_radius) / 2
            points.append((mid_pos, mid_radius))
            points.append((zone.end_pos, zone.end_radius))
        
        elif zone.zone_type == ZoneType.STEP:
            # Sharp transition: both radii at same position
            points.append((zone.start_pos, zone.start_radius))
            points.append((zone.start_pos, zone.end_radius))
        
        elif zone.zone_type == ZoneType.GROOVE:
            # Groove: reduced radius section
            points.append((zone.start_pos, zone.mean_radius))
            points.append((zone.end_pos, zone.mean_radius))
    
    # Remove duplicates and sort by position
    points = sorted(set(points), key=lambda p: p[0])
    
    return points
