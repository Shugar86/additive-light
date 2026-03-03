"""Approximator - Sensor Node 2.

Vector regression for zone detection using SciPy + RANSAC.
"""

import numpy as np
from scipy.optimize import least_squares
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import logging

from ..sensors.sensor import SliceMetrics
from ..models.yaml_contract import (
    GlobalState,
    ZoneParameters,
    TopologicalZone,
    AgentTask,
    SensorTelemetry,
    ApproximationResult,
    GeometryType,
    CrossSectionType,
)
from .confidence import compute_zone_confidence, compute_global_confidence

logger = logging.getLogger(__name__)


@dataclass
class DetectedZone:
    """Internal representation of a detected zone before YAML conversion."""
    start_z: float
    end_z: float
    geometry: GeometryType
    cross_section: CrossSectionType
    params: Dict[str, Any]
    confidence: float
    sensor_hint: str


class ZoneDetector:
    """Detects geometric zones from slice metrics using RANSAC."""
    
    def __init__(self, ransac_threshold: float = 0.5):
        """Initialize zone detector.
        
        Args:
            ransac_threshold: RANSAC outlier threshold in mm
        """
        self.ransac_threshold = ransac_threshold
        
    def detect_zones(
        self, 
        slices: List[SliceMetrics]
    ) -> List[DetectedZone]:
        """Detect topological zones from slice data.
        
        Args:
            slices: List of slice metrics from Sensor
            
        Returns:
            List of detected zones with parameters
        """
        if not slices:
            return []
        
        # Sort by Z
        slices = sorted(slices, key=lambda s: s.z_height)
        
        zones = []
        current_zone_start = 0
        
        # Analyze slice evolution to detect zone boundaries
        for i in range(1, len(slices)):
            prev_slice = slices[i - 1]
            curr_slice = slices[i]
            
            # Check for zone boundary conditions
            is_boundary = self._is_zone_boundary(prev_slice, curr_slice)
            
            if is_boundary or i == len(slices) - 1:
                # End current zone
                zone_slices = slices[current_zone_start:i]
                if zone_slices:
                    zone = self._analyze_zone(zone_slices)
                    if zone:
                        zones.append(zone)
                
                current_zone_start = i
        
        # Handle last zone
        if current_zone_start < len(slices):
            zone_slices = slices[current_zone_start:]
            zone = self._analyze_zone(zone_slices)
            if zone:
                zones.append(zone)
        
        return zones
    
    def _is_zone_boundary(
        self, 
        prev: SliceMetrics, 
        curr: SliceMetrics
    ) -> bool:
        """Detect if there's a geometric discontinuity between slices.
        
        Args:
            prev: Previous slice
            curr: Current slice
            
        Returns:
            True if this is a zone boundary
        """
        # Check for sudden area change (>20%)
        if prev.area > 0 and curr.area > 0:
            area_change = abs(curr.area - prev.area) / prev.area
            if area_change > 0.2:
                return True
        
        # Check for hole count change
        if prev.num_holes != curr.num_holes:
            return True
        
        # Check for centroid jump
        centroid_dist = np.sqrt(
            (curr.centroid[0] - prev.centroid[0])**2 +
            (curr.centroid[1] - prev.centroid[1])**2
        )
        if centroid_dist > 5.0:  # 5mm threshold
            return True
        
        return False
    
    def _analyze_zone(
        self, 
        slices: List[SliceMetrics]
    ) -> Optional[DetectedZone]:
        """Analyze a zone to determine its geometry and parameters.
        
        Uses RANSAC for robust fitting on noisy data.
        Detects cross-section type via circularity before fitting.
        
        Args:
            slices: Slices belonging to this zone
            
        Returns:
            DetectedZone or None if analysis fails
        """
        if len(slices) < 2:
            return None
        
        z_vals = np.array([s.z_height for s in slices])
        zone_height = float(z_vals[-1] - z_vals[0])
        
        # --- Cross-section type detection via circularity ---
        # circularity = 4π·A/P²; perfect circle = 1.0, square ≈ 0.785
        valid_slices = [s for s in slices if s.is_valid]
        if valid_slices:
            mean_circularity = float(np.mean([s.circularity for s in valid_slices]))
        else:
            mean_circularity = 1.0  # fallback to circular path
        
        CIRCULARITY_THRESHOLD = 0.85
        
        if mean_circularity <= CIRCULARITY_THRESHOLD:
            # ---- RECTANGLE / POLYGON cross-section ----
            # Use bounding-box dimensions averaged over zone slices
            widths = np.array([s.bounding_box[2] - s.bounding_box[0] for s in valid_slices])
            depths = np.array([s.bounding_box[3] - s.bounding_box[1] for s in valid_slices])
            
            mean_width = float(np.mean(widths))
            mean_depth = float(np.mean(depths))
            max_holes = max(s.num_holes for s in slices)
            
            if max_holes > 0:
                geom = GeometryType.CONSTANT_PROFILE_WITH_HOLES
                hint = (
                    f"Rectangle cross-section detected (circularity={mean_circularity:.2f}). "
                    f"Dims: {mean_width:.1f}x{mean_depth:.1f}mm, {max_holes} holes. "
                    f"Use Box(width, depth, height) with PolarArray for holes."
                )
            else:
                geom = GeometryType.CONSTANT_PROFILE
                hint = (
                    f"Rectangle cross-section detected (circularity={mean_circularity:.2f}). "
                    f"Dims: {mean_width:.1f}x{mean_depth:.1f}mm. "
                    f"Use Box(width, depth, height)."
                )
            
            params = {
                "width": mean_width,
                "depth": mean_depth,
                "height": zone_height,
            }
            if max_holes > 0:
                params["hole_count"] = max_holes
                
            inliers = np.ones(len(widths), dtype=bool)
            conf = compute_zone_confidence(widths, inliers, has_holes=max_holes > 0)
            
            return DetectedZone(
                start_z=float(z_vals[0]),
                end_z=float(z_vals[-1]),
                geometry=geom,
                cross_section=CrossSectionType.RECTANGLE,
                params=params,
                confidence=conf,
                sensor_hint=hint
            )

        
        # ---- CIRCLE / body-of-revolution path ----
        # Estimate radius from bounding box (for circular approximation)
        radii = np.array([
            (s.bounding_box[2] - s.bounding_box[0] + 
             s.bounding_box[3] - s.bounding_box[1]) / 4.0
            for s in slices
        ])
        
        # Check if it's constant radius (cylinder)
        radius_variance = np.var(radii)
        
        if radius_variance < 0.5:  # Low variance = cylinder
            # RANSAC for robust radius estimation
            inliers = self._ransac_fit_constant(radii)
            mean_radius = float(np.mean(radii[inliers]))
            
            # Check for holes
            max_holes = max(s.num_holes for s in slices)
            
            if max_holes > 0:
                geometry = GeometryType.CONSTANT_PROFILE_WITH_HOLES
                hint = f"Detected {max_holes} internal contours in polar array. " \
                       f"Stable RANSAC fit: R={mean_radius:.2f}mm. Suggest beautification."
            else:
                geometry = GeometryType.CONSTANT_PROFILE
                hint = f"Stable RANSAC fit. Probably a base cylinder. " \
                       f"Suggest beautification to R={round(mean_radius, 0)}."
            
            params = {
                "radius": mean_radius,
                "height": zone_height,
                "hole_count": max_holes if max_holes > 0 else None,
                "center": [0.0, 0.0]
            }
            
            return DetectedZone(
                start_z=float(z_vals[0]),
                end_z=float(z_vals[-1]),
                geometry=geometry,
                cross_section=CrossSectionType.CIRCLE,
                params={k: v for k, v in params.items() if v is not None},
                confidence=compute_zone_confidence(radii, inliers, has_holes=max_holes>0),
                sensor_hint=hint
            )
        
        else:
            # Check for linear transition (chamfer/cone)
            slope, intercept, is_linear = self._fit_linear_transition(z_vals, radii)
            
            if is_linear and abs(slope) > 0.1:
                geometry = GeometryType.LINEAR_REGRESSION
                hint = f"Radius decreases linearly from {radii[0]:.2f} to {radii[-1]:.2f}. " \
                       f"Build as Chamfer or Loft."
                
                params = {
                    "radius_start": float(radii[0]),
                    "radius_end": float(radii[-1]),
                    "center": [0.0, 0.0]
                }
                
                return DetectedZone(
                    start_z=float(z_vals[0]),
                    end_z=float(z_vals[-1]),
                    geometry=geometry,
                    cross_section=CrossSectionType.CIRCLE,
                    params=params,
                    confidence=0.75,  # Linear is less confident than constant
                    sensor_hint=hint
                )
            else:
                # Complex shape - low confidence
                geometry = GeometryType.COMPLEX
                hint = f"Complex geometry detected. Variance in radius: {radius_variance:.2f}. " \
                       f"2.7D slicer may not fully capture this shape. Recommend manual review."
                
                return DetectedZone(
                    start_z=float(z_vals[0]),
                    end_z=float(z_vals[-1]),
                    geometry=geometry,
                    cross_section=CrossSectionType.POLYGON,
                    params={"bounding_radius": float(np.mean(radii))},
                    confidence=0.5,  # Low confidence for complex
                    sensor_hint=hint
                )
    
    def _ransac_fit_constant(
        self, 
        values: np.ndarray,
        max_iterations: int = 100
    ) -> np.ndarray:
        """RANSAC fit for constant value.
        
        Args:
            values: Array of values to fit
            max_iterations: Max RANSAC iterations
            
        Returns:
            Boolean mask of inliers
        """
        best_inliers = np.ones(len(values), dtype=bool)
        best_score = 0
        
        for _ in range(max_iterations):
            # Sample random subset
            sample_size = max(2, len(values) // 4)
            sample_idx = np.random.choice(len(values), sample_size, replace=False)
            sample_mean = np.mean(values[sample_idx])
            
            # Find inliers
            residuals = np.abs(values - sample_mean)
            inliers = residuals < self.ransac_threshold
            
            score = np.sum(inliers)
            if score > best_score:
                best_score = score
                best_inliers = inliers
        
        return best_inliers
    
    def _fit_linear_transition(
        self, 
        z_vals: np.ndarray, 
        radii: np.ndarray
    ) -> Tuple[float, float, bool]:
        """Fit linear transition model.
        
        Args:
            z_vals: Z positions
            radii: Corresponding radii
            
        Returns:
            (slope, intercept, is_linear_valid)
        """
        try:
            # Linear regression
            A = np.vstack([z_vals, np.ones(len(z_vals))]).T
            slope, intercept = np.linalg.lstsq(A, radii, rcond=None)[0]
            
            # Check fit quality
            predicted = slope * z_vals + intercept
            residuals = np.abs(radii - predicted)
            
            is_linear = np.mean(residuals) < self.ransac_threshold * 2
            
            return slope, intercept, is_linear
        except Exception:
            return 0.0, 0.0, False


class Approximator:
    """Main Approximator class - converts slices to YAML telemetry."""
    
    def __init__(
        self, 
        confidence_threshold: float = 0.7,
        ransac_threshold: float = 0.5
    ):
        """Initialize approximator.
        
        Args:
            confidence_threshold: Minimum confidence before fallback to manual review
            ransac_threshold: RANSAC outlier threshold
        """
        self.confidence_threshold = confidence_threshold
        self.detector = ZoneDetector(ransac_threshold)
    
    def approximate(
        self,
        slices: List[SliceMetrics],
        source_file: str,
        base_axis: str = "Z"
    ) -> ApproximationResult:
        """Convert slice metrics to YAML telemetry payload.
        
        Args:
            slices: Slice metrics from Sensor
            source_file: Source STL file path
            base_axis: Build axis
            
        Returns:
            ApproximationResult with telemetry and confidence
        """
        # Detect zones
        detected_zones = self.detector.detect_zones(slices)
        
        if not detected_zones:
            return self._create_fallback_result(source_file, "No zones detected")
        
        # Convert to YAML models
        topological_zones = []
        for i, zone in enumerate(detected_zones, 1):
            tz = TopologicalZone(
                zone_id=i,
                span_z=[zone.start_z, zone.end_z],
                geometry=zone.geometry,
                cross_section=zone.cross_section,
                parameters=ZoneParameters(**zone.params),
                sensor_hint=zone.sensor_hint,
                confidence=zone.confidence
            )
            topological_zones.append(tz)
        
        # Compute global confidence
        global_confidence = compute_global_confidence([z.confidence for z in detected_zones])
        
        # Determine if fallback needed
        fallback_required = global_confidence < self.confidence_threshold
        fallback_reason = None
        if fallback_required:
            low_confidence_zones = [z for z in detected_zones if z.confidence < 0.6]
            if low_confidence_zones:
                fallback_reason = f"Low confidence zones detected: {[z.geometry.value for z in low_confidence_zones]}"
            else:
                fallback_reason = f"Global confidence {global_confidence:.2f} below threshold {self.confidence_threshold}"
        
        # Create telemetry
        telemetry = SensorTelemetry(
            global_state=GlobalState(
                base_axis=base_axis,
                total_height=float(max(z.end_z for z in detected_zones))
            ),
            topological_zones=topological_zones,
            agent_task=AgentTask(
                thought_process=self._generate_thought_process(detected_zones)
            ),
            source_file=source_file
        )
        
        return ApproximationResult(
            telemetry=telemetry,
            global_confidence=global_confidence,
            fallback_required=fallback_required,
            fallback_reason=fallback_reason
        )
    
    def _generate_thought_process(
        self, 
        zones: List[DetectedZone]
    ) -> str:
        """Generate structured thought process for LLM.
        
        Args:
            zones: Detected zones
            
        Returns:
            Thought process string
        """
        lines = ["# Approximator Analysis:"]
        
        for i, zone in enumerate(zones, 1):
            lines.append(f"# Zone {i} ({zone.start_z:.1f} to {zone.end_z:.1f} mm):")
            lines.append(f"#   - Geometry: {zone.geometry.value}")
            lines.append(f"#   - Cross-section: {zone.cross_section.value}")
            lines.append(f"#   - Confidence: {zone.confidence:.2f}")
            
            if "radius" in zone.params:
                lines.append(f"#   - Radius: {zone.params['radius']:.2f} mm")
            if "hole_count" in zone.params:
                lines.append(f"#   - Holes: {zone.params['hole_count']}")
        
        lines.append("#")
        lines.append("# Build strategy:")
        for i, zone in enumerate(zones, 1):
            if zone.geometry == GeometryType.CONSTANT_PROFILE:
                r = zone.params.get("radius", 10.0)
                h = zone.end_z - zone.start_z
                lines.append(f"# {i}. Zone {i}: Cylinder R={r:.1f}, H={h:.1f}")
            elif zone.geometry == GeometryType.LINEAR_REGRESSION:
                rs = zone.params.get("radius_start", 10.0)
                re = zone.params.get("radius_end", 5.0)
                lines.append(f"# {i}. Zone {i}: Chamfer/Cone {rs:.1f} -> {re:.1f}")
            elif zone.geometry == GeometryType.CONSTANT_PROFILE_WITH_HOLES:
                r = zone.params.get("radius", 10.0)
                hc = zone.params.get("hole_count", 0)
                lines.append(f"# {i}. Zone {i}: Cylinder R={r:.1f} with {hc} holes")
        
        return "\n".join(lines)
    
    def _create_fallback_result(
        self, 
        source_file: str, 
        reason: str
    ) -> ApproximationResult:
        """Create a fallback result when approximation fails.
        
        Args:
            source_file: Source file path
            reason: Reason for fallback
            
        Returns:
            Fallback ApproximationResult
        """
        telemetry = SensorTelemetry(
            global_state=GlobalState(
                base_axis="Z",
                total_height=10.0
            ),
            topological_zones=[],
            agent_task=AgentTask(
                thought_process=f"# FALLBACK REQUIRED: {reason}\n# Manual review needed."
            ),
            source_file=source_file
        )
        
        return ApproximationResult(
            telemetry=telemetry,
            global_confidence=0.0,
            fallback_required=True,
            fallback_reason=reason
        )
