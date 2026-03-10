"""Coordinator/Planner agent for aggregating sensor data and creating CAD plans.

The Coordinator is the "Smart LLM" that receives reports from all three sensor
agents (X, Y, Z), correlates the 2D features into 3D features, and creates a
step-by-step construction plan for the Coder agent.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

from backend.core.state import CADState, Axis, SliceReport, Feature3D, BuildStep
from backend.core.state import ShaftConstructionPlan, ShaftZoneSpec, ShaftZoneType, AxisSpec, LocalFeatureSpec, LocalFeatureType, MeasurementLogEntry
from backend.core.config import settings
from backend.core.agent_prompt_compiler import get_prompt_compiler

logger = logging.getLogger(__name__)


class CoordinatorAgent:
    """Smart LLM agent that aggregates sensor data and plans construction.
    
    This agent correlates 2D features from three orthogonal views into 3D
    features, then creates a parametric construction plan (sketch -> extrude -> cut).
    """

    def __init__(self, llm_client: Optional[Any] = None, use_prompt_compiler: bool = True):
        """Initialize the Coordinator agent.

        Args:
            llm_client: LLM client for analysis and planning.
                       If None, uses rule-based coordination.
            use_prompt_compiler: Whether to use the PromptCompiler for prompt assembly.
                               Falls back to legacy prompts if compiler unavailable.
        """
        self.llm_client = llm_client
        self.use_prompt_compiler = use_prompt_compiler
        self._prompt_compiler = None
        
        if use_prompt_compiler:
            try:
                self._prompt_compiler = get_prompt_compiler("coordinator")
                logger.info("[CoordinatorAgent] Initialized with PromptCompiler")
            except Exception as e:
                logger.warning(f"[CoordinatorAgent] PromptCompiler not available: {e}")
                self._prompt_compiler = None
        
        logger.info("[CoordinatorAgent] Initialized")

    def analyze(self, state: CADState) -> Dict[str, Any]:
        """Aggregate sensor reports and create construction plan.

        Args:
            state: Current CAD state with sensor reports.

        Returns:
            Dictionary with 'features' (List[Feature3D]) and 'plan' (List[BuildStep]).
        """
        logger.info("[CoordinatorAgent] Starting analysis")

        if not state.sensor_reports:
            logger.warning("[CoordinatorAgent] No sensor reports to analyze")
            return {"features": [], "plan": []}

        try:
            # Step 1: Aggregate 2D features into 3D features
            features_3d = self._aggregate_features(state.sensor_reports)
            logger.info(f"[CoordinatorAgent] Identified {len(features_3d)} 3D features")

            # Step 2: Create construction plan
            plan = self._create_construction_plan(features_3d, state)
            logger.info(f"[CoordinatorAgent] Created {len(plan)} construction steps")

            return {
                "features": features_3d,
                "plan": plan
            }

        except Exception as e:
            logger.error(f"[CoordinatorAgent] Analysis failed: {e}")
            return {"features": [], "plan": [], "error": str(e)}
    
    def _compile_prompt(self, phase: str, state: CADState) -> Optional[str]:
        """Compile a prompt using the PromptCompiler if available.
        
        Args:
            phase: Pipeline phase (analysis, planning, repair)
            state: Current CAD state
        
        Returns:
            Compiled prompt string or None if compiler unavailable.
        """
        if not self._prompt_compiler:
            return None
        
        try:
            prompt = self._prompt_compiler.compile_prompt(phase, state)
            return prompt
        except Exception as e:
            logger.warning(f"[CoordinatorAgent] Prompt compilation failed: {e}")
            return None
    
    def _maybe_generate_with_llm(self, phase: str, state: CADState) -> Optional[str]:
        """Optionally use LLM if available and prompt compiler is working.
        
        This is a placeholder for future LLM integration. Currently returns None
        to fall back to rule-based processing.
        
        Args:
            phase: Pipeline phase
            state: Current CAD state
        
        Returns:
            LLM-generated content or None to use rule-based fallback.
        """
        if not self.llm_client:
            return None
        
        prompt = self._compile_prompt(phase, state)
        if not prompt:
            return None
        
        # TODO: Implement actual LLM call
        # For now, log that we would use LLM and fall back
        logger.debug(f"[CoordinatorAgent] Would use LLM for {phase} with prompt length {len(prompt)}")
        return None

    def _aggregate_features(
        self,
        sensor_reports: Dict[Axis, SliceReport]
    ) -> List[Feature3D]:
        """Correlate 2D features from all three axes into 3D features.
        
        This is the core spatial reasoning step. We look for features that
        appear consistently across multiple views.
        """
        features: List[Feature3D] = []
        
        # Strategy 1: Find cylindrical features from Z-axis analysis
        if Axis.Z in sensor_reports:
            z_report = sensor_reports[Axis.Z]
            cylinders = self._extract_cylinders_from_z_slices(z_report)
            features.extend(cylinders)
        
        # Strategy 2: Find holes and cutouts from cross-axis analysis
        holes = self._find_holes_from_cross_section(sensor_reports)
        features.extend(holes)
        
        # Strategy 3: Find slots and keyways
        slots = self._find_slots(sensor_reports)
        features.extend(slots)
        
        return features

    def _extract_cylinders_from_z_slices(
        self,
        z_report: SliceReport
    ) -> List[Feature3D]:
        """Extract cylindrical features from Z-axis slice analysis."""
        cylinders: List[Feature3D] = []
        
        # Group circular features by radius
        radius_groups: Dict[float, List[Tuple[float, SliceReport]]] = defaultdict(list)
        
        for slice_key, slice_features in z_report.features_by_slice.items():
            # Parse position from slice key (format: "slice_NNN_pos_X.XXX")
            try:
                pos = float(slice_key.split("_pos_")[1])
            except (IndexError, ValueError):
                continue
            
            for feature in slice_features:
                if feature.feature_type == "circle" and feature.radius:
                    # Round radius to nearest 0.1 for grouping
                    rounded_radius = round(feature.radius, 1)
                    radius_groups[rounded_radius].append((pos, feature))
        
        # Create cylinders from consistent radius groups
        for radius, slice_data in radius_groups.items():
            if len(slice_data) < 3:  # Need at least a few slices
                continue
            
            positions = [p for p, _ in slice_data]
            centers = [f.center for _, f in slice_data]
            
            # Average center position
            avg_center_x = sum(c[0] for c in centers) / len(centers)
            avg_center_y = sum(c[1] for c in centers) / len(centers)
            
            cylinder = Feature3D(
                feature_type="cylinder",
                position=[avg_center_x, avg_center_y, (min(positions) + max(positions)) / 2],
                orientation=[0, 0, 1],  # Along Z-axis
                dimensions={
                    "radius": radius,
                    "height": max(positions) - min(positions)
                },
                evidence=[f"Z-axis: {len(slice_data)} slices"],
                confidence=min(1.0, len(slice_data) / 10.0)
            )
            cylinders.append(cylinder)
        
        logger.debug(f"[CoordinatorAgent] Extracted {len(cylinders)} cylinders from Z-axis")
        return cylinders

    def _find_holes_from_cross_section(
        self,
        sensor_reports: Dict[Axis, SliceReport]
    ) -> List[Feature3D]:
        """Find hole features by looking for circular features in all axes.
        
        P8 Enhancement: Now distinguishes between through-holes and blind holes.
        """
        holes: List[Feature3D] = []
        
        # Collect all small circles with their axis information
        candidate_circles = []
        
        for axis, report in sensor_reports.items():
            for slice_key, features in report.features_by_slice.items():
                # Look for small circles (likely holes)
                small_circles = [
                    f for f in features 
                    if f.feature_type == "circle" and f.radius and f.radius < 5.0
                ]
                
                for circle in small_circles:
                    try:
                        pos = float(slice_key.split("_pos_")[1])
                    except (IndexError, ValueError):
                        continue
                    
                    # Store with axis info for cross-analysis
                    candidate_circles.append({
                        "circle": circle,
                        "axis": axis,
                        "position": pos,
                        "slice_key": slice_key
                    })
        
        # P8: Analyze each axis to find through-holes vs blind holes
        for axis in [Axis.X, Axis.Y, Axis.Z]:
            axis_circles = [c for c in candidate_circles if c["axis"] == axis]
            if not axis_circles:
                continue
            
            # Group by similar position (same hole across slices)
            position_groups = self._group_circles_by_position(axis_circles, tolerance=0.5)
            
            for group in position_groups:
                if len(group) < 2:
                    continue
                
                # Sort by slice position
                group.sort(key=lambda x: x["position"])
                
                # Check if hole goes through entire part or is blind
                min_pos = group[0]["position"]
                max_pos = group[-1]["position"]
                position_span = max_pos - min_pos
                
                # Get bounds from all reports for this axis
                all_positions = []
                if axis in sensor_reports:
                    for slice_key in sensor_reports[axis].features_by_slice.keys():
                        try:
                            pos = float(slice_key.split("_pos_")[1])
                            all_positions.append(pos)
                        except:
                            pass
                
                if all_positions:
                    total_span = max(all_positions) - min(all_positions)
                    
                    # Determine hole type
                    if position_span > 0.8 * total_span:
                        hole_type = "through_hole"
                    else:
                        hole_type = "blind_hole"
                    
                    # Get representative circle
                    rep_circle = group[len(group) // 2]["circle"]
                    rep_pos = group[len(group) // 2]["position"]
                    
                    # 3D position and orientation
                    if axis == Axis.Z:
                        position = [rep_circle.center[0], rep_circle.center[1], rep_pos]
                        orientation = [0, 0, 1]
                    elif axis == Axis.X:
                        position = [rep_pos, rep_circle.center[0], rep_circle.center[1]]
                        orientation = [1, 0, 0]
                    else:  # Y
                        position = [rep_circle.center[0], rep_pos, rep_circle.center[1]]
                        orientation = [0, 1, 0]
                    
                    hole = Feature3D(
                        feature_type=hole_type,
                        position=position,
                        orientation=orientation,
                        dimensions={
                            "radius": rep_circle.radius,
                            "depth": position_span
                        },
                        evidence=[f"{axis.value}-axis: {len(group)} slices"],
                        confidence=rep_circle.confidence * 0.85
                    )
                    holes.append(hole)
        
        # Merge duplicate holes
        merged_holes = self._merge_duplicate_features(holes, tolerance=0.5)
        
        # Count hole types
        through_count = sum(1 for h in merged_holes if h.feature_type == "through_hole")
        blind_count = sum(1 for h in merged_holes if h.feature_type == "blind_hole")
        
        logger.debug(f"[CoordinatorAgent] Found {len(merged_holes)} holes: "
                    f"{through_count} through, {blind_count} blind")
        return merged_holes
    
    def _group_circles_by_position(
        self,
        circles: List[Dict],
        tolerance: float = 0.5
    ) -> List[List[Dict]]:
        """Group circles by similar 2D center position.
        
        P8 Helper: Groups circles that likely belong to the same hole.
        
        Args:
            circles: List of circle dicts with "circle" and "position" keys.
            tolerance: Distance tolerance for grouping.
        
        Returns:
            List of groups (each group is a list of circle dicts).
        """
        if not circles:
            return []
        
        groups: List[List[Dict]] = []
        used = set()
        
        for i, circle_i in enumerate(circles):
            if i in used:
                continue
            
            # Start new group
            group = [circle_i]
            used.add(i)
            
            center_i = np.array(circle_i["circle"].center)
            
            # Find similar circles
            for j, circle_j in enumerate(circles[i+1:], start=i+1):
                if j in used:
                    continue
                
                center_j = np.array(circle_j["circle"].center)
                dist = np.linalg.norm(center_i - center_j)
                
                # Also check if radius is similar
                radius_diff = abs(circle_i["circle"].radius - circle_j["circle"].radius)
                
                if dist < tolerance and radius_diff < 0.2:
                    group.append(circle_j)
                    used.add(j)
            
            groups.append(group)
        
        return groups

    def _find_slots(
        self,
        sensor_reports: Dict[Axis, SliceReport]
    ) -> List[Feature3D]:
        """Find slot/keyway features from rectangular cross-sections."""
        slots: List[Feature3D] = []
        
        for axis, report in sensor_reports.items():
            for slice_key, features in report.features_by_slice.items():
                rectangles = [f for f in features if f.feature_type == "rectangle"]
                
                for rect in rectangles:
                    if not rect.dimensions:
                        continue
                    
                    # Long narrow rectangle suggests a slot
                    aspect = max(rect.dimensions) / (min(rect.dimensions) + 1e-10)
                    if aspect > 2.0:
                        try:
                            pos = float(slice_key.split("_pos_")[1])
                        except (IndexError, ValueError):
                            continue
                        
                        # Position based on axis
                        if axis == Axis.Z:
                            position = [rect.center[0], rect.center[1], pos]
                        elif axis == Axis.X:
                            position = [pos, rect.center[0], rect.center[1]]
                        else:
                            position = [rect.center[0], pos, rect.center[1]]
                        
                        slot = Feature3D(
                            feature_type="slot",
                            position=position,
                            orientation=[0, 0, 1],  # Assume Z-oriented for now
                            dimensions={
                                "width": min(rect.dimensions),
                                "length": max(rect.dimensions)
                                # "depth" is unknown
                            },
                            evidence=[f"{axis.value}-axis rectangular feature"],
                            confidence=0.7
                        )
                        slots.append(slot)
        
        return slots

    def _merge_duplicate_features(
        self,
        features: List[Feature3D],
        tolerance: float = 0.5
    ) -> List[Feature3D]:
        """Merge features that are at approximately the same position."""
        if not features:
            return []
        
        merged: List[Feature3D] = []
        used = set()
        
        for i, feat1 in enumerate(features):
            if i in used:
                continue
            
            # Find similar features
            similar = [feat1]
            for j, feat2 in enumerate(features[i+1:], start=i+1):
                if j in used:
                    continue
                
                # Check position distance
                dist = sum((a - b) ** 2 for a, b in zip(feat1.position, feat2.position)) ** 0.5
                
                if dist < tolerance:
                    similar.append(feat2)
                    used.add(j)
            
            # Merge into single feature
            if len(similar) > 1:
                # Average position
                avg_pos = [
                    sum(f.position[i] for f in similar) / len(similar)
                    for i in range(3)
                ]
                
                # Take max confidence
                max_conf = max(f.confidence for f in similar)
                
                # Combine evidence
                all_evidence = []
                for f in similar:
                    all_evidence.extend(f.evidence)
                
                merged_feat = Feature3D(
                    feature_type=similar[0].feature_type,
                    position=avg_pos,
                    orientation=similar[0].orientation,
                    dimensions=similar[0].dimensions,
                    evidence=list(set(all_evidence)),
                    confidence=min(1.0, max_conf + 0.1)  # Slight boost for confirmation
                )
                merged.append(merged_feat)
            else:
                merged.append(feat1)
            
            used.add(i)
        
        return merged

    def _create_construction_plan(
        self,
        features: List[Feature3D],
        state: CADState
    ) -> List[BuildStep]:
        """Create a step-by-step parametric construction plan.
        
        The plan follows typical CAD workflow:
        1. Base sketch (profile)
        2. Extrude to create solid
        3. Cut features (holes, slots)
        4. Add fillets/chamfers
        """
        plan: List[BuildStep] = []
        step_num = 1
        
        # Step 1: Identify base geometry
        base_cylinders = [f for f in features if f.feature_type == "cylinder"]
        
        if base_cylinders:
            # Use the largest cylinder as the base
            main_cylinder = max(base_cylinders, key=lambda c: c.dimensions.get("radius", 0))
            
            plan.append(BuildStep(
                step_number=step_num,
                operation="base_sketch",
                description=f"Create base circle sketch with radius {main_cylinder.dimensions['radius']:.3f}",
                parameters={
                    "sketch_plane": "XY",
                    "shape": "circle",
                    "radius": main_cylinder.dimensions["radius"],
                    "center": [0, 0]
                },
                dependencies=[]
            ))
            step_num += 1
            base_step = step_num - 1
            
            # Extrude to create main body
            plan.append(BuildStep(
                step_number=step_num,
                operation="extrude",
                description=f"Extrude base to height {main_cylinder.dimensions['height']:.3f}",
                parameters={
                    "distance": main_cylinder.dimensions["height"],
                    "direction": "both"  # Centered extrusion
                },
                dependencies=[base_step]
            ))
            step_num += 1
            body_step = step_num - 1
        else:
            # No cylinders found - use bounding box approach
            plan.append(BuildStep(
                step_number=step_num,
                operation="base_sketch",
                description="Create base rectangular sketch from bounds",
                parameters={
                    "sketch_plane": "XY",
                    "shape": "rectangle",
                    "center": [0, 0],
                    "width": 10.0,  # Placeholder
                    "height": 10.0
                },
                dependencies=[]
            ))
            step_num += 1
            body_step = step_num - 1
        
        # Step 2: Add holes
        holes = [f for f in features if f.feature_type == "hole"]
        for hole in holes:
            plan.append(BuildStep(
                step_number=step_num,
                operation="cut",
                description=f"Cut hole with radius {hole.dimensions['radius']:.3f}",
                parameters={
                    "tool": "cylinder",
                    "radius": hole.dimensions["radius"],
                    "position": hole.position,
                    "orientation": hole.orientation,
                    "depth": hole.dimensions.get("depth", 10.0)
                },
                dependencies=[body_step]
            ))
            step_num += 1
        
        # Step 3: Add slots
        slots = [f for f in features if f.feature_type == "slot"]
        for slot in slots:
            plan.append(BuildStep(
                step_number=step_num,
                operation="cut",
                description=f"Cut slot ({slot.dimensions['width']:.2f} x {slot.dimensions['length']:.2f})",
                parameters={
                    "tool": "extrude",
                    "width": slot.dimensions["width"],
                    "length": slot.dimensions["length"],
                    "position": slot.position,
                    "orientation": slot.orientation
                },
                dependencies=[body_step]
            ))
            step_num += 1
        
        return plan

    # =============================================================================
    # Shaft MVP: Dedicated shaft pipeline
    # =============================================================================

    def analyze_shaft(
        self,
        mesh_path: str,
        state: CADState
    ) -> Dict[str, Any]:
        """Run the dedicated shaft sensor pipeline.
        
        This is the main entry point for shaft reverse engineering.
        Uses hard math (no LLM) to detect axis, profile, zones, and features.
        
        Args:
            mesh_path: Path to the aligned mesh file.
            state: Current CAD state.
        
        Returns:
            Dictionary with:
            - shaft_construction_plan: ShaftConstructionPlan object
            - features: List of Feature3D for compatibility
            - plan: List of BuildStep for compatibility
        """
        import datetime
        from backend.sensors.shaft_axis import detect_main_axis, align_mesh_to_axis
        from backend.sensors.shaft_profile import extract_shaft_segments
        from backend.sensors.shaft_features import detect_keyways_flats_holes
        
        logger.info("[CoordinatorAgent] Starting shaft pipeline analysis")
        
        measurement_log: List[MeasurementLogEntry] = []
        
        try:
            # Step 1: Detect and align to main axis
            logger.info("[ShaftPipeline] Step 1: Detecting main axis")
            axis_info = detect_main_axis(mesh_path)
            
            measurement_log.append(MeasurementLogEntry(
                timestamp=datetime.datetime.now().isoformat(),
                operation="detect_main_axis",
                status="success",
                details=axis_info.to_dict()
            ))
            
            # Align mesh to axis if needed
            aligned_path, aligned_axis_info = align_mesh_to_axis(mesh_path)
            
            # Step 2: Extract shaft profile and segments
            logger.info("[ShaftPipeline] Step 2: Extracting profile and segments")
            profile, zones = extract_shaft_segments(aligned_path, axis="Z", num_samples=100)
            
            measurement_log.append(MeasurementLogEntry(
                timestamp=datetime.datetime.now().isoformat(),
                operation="extract_profile",
                status="success",
                details={
                    "total_length": profile.total_length,
                    "min_radius": profile.min_radius,
                    "max_radius": profile.max_radius,
                    "zone_count": len(zones)
                }
            ))
            
            # Step 3: Detect local features (keyways, flats, holes)
            logger.info("[ShaftPipeline] Step 3: Detecting local features")
            segments_dict = [z.to_dict() for z in zones]
            features = detect_keyways_flats_holes(
                aligned_path,
                axis_info.to_dict(),
                segments_dict
            )
            
            measurement_log.append(MeasurementLogEntry(
                timestamp=datetime.datetime.now().isoformat(),
                operation="detect_features",
                status="success",
                details={"feature_count": len(features)}
            ))
            
            # Step 4: Build construction plan
            logger.info("[ShaftPipeline] Step 4: Building construction plan")
            construction_plan = self._build_shaft_construction_plan(
                axis_info, profile, zones, features, measurement_log
            )
            
            # Validate the plan
            validation_errors = construction_plan.validate_geometry()
            if validation_errors:
                logger.warning(f"[ShaftPipeline] Validation errors: {validation_errors}")
            
            # Convert zones and features to old format for compatibility
            features_3d = self._convert_shaft_to_features3d(zones, features)
            build_steps = self._convert_shaft_to_buildsteps(zones, features)
            
            logger.info(f"[ShaftPipeline] Complete: {len(zones)} zones, {len(features)} features, "
                       f"confidence={construction_plan.confidence:.3f}")
            
            return {
                "shaft_construction_plan": construction_plan,
                "features": features_3d,
                "plan": build_steps
            }
            
        except Exception as e:
            logger.error(f"[ShaftPipeline] Analysis failed: {e}")
            measurement_log.append(MeasurementLogEntry(
                timestamp=datetime.datetime.now().isoformat(),
                operation="shaft_pipeline",
                status="failed",
                details={"error": str(e)}
            ))
            return {
                "shaft_construction_plan": None,
                "features": [],
                "plan": [],
                "error": str(e)
            }
    
    def _build_shaft_construction_plan(
        self,
        axis_info: Any,
        profile: Any,
        zones: List[Any],
        features: List[Any],
        measurement_log: List[MeasurementLogEntry]
    ) -> ShaftConstructionPlan:
        """Build the strict ShaftConstructionPlan from detected data."""
        
        # Build axis spec
        axis_spec = AxisSpec(
            direction=axis_info.direction.tolist(),
            origin=axis_info.origin.tolist(),
            confidence=axis_info.confidence,
            length=axis_info.length
        )
        
        # Build zone specs
        zone_specs = []
        for zone in zones:
            zone_type = ShaftZoneType(zone.zone_type.value)
            
            spec = ShaftZoneSpec(
                zone_type=zone_type,
                start_pos=zone.start_pos,
                end_pos=zone.end_pos,
                start_radius=zone.start_radius,
                end_radius=zone.end_radius,
                mean_radius=zone.mean_radius,
                confidence=zone.confidence
            )
            
            # Add zone-specific metadata
            if zone_type == ShaftZoneType.CHAMFER and "chamfer_angle" in zone.metadata:
                spec.chamfer_angle = zone.metadata["chamfer_angle"]
            elif zone_type == ShaftZoneType.FILLET and "fillet_radius" in zone.metadata:
                spec.fillet_radius = zone.metadata["fillet_radius"]
            
            zone_specs.append(spec)
        
        # Build feature specs
        feature_specs = []
        for feature in features:
            feature_type = LocalFeatureType(feature.feature_type.value)
            
            spec = LocalFeatureSpec(
                feature_type=feature_type,
                position=feature.position.tolist(),
                orientation=feature.orientation.tolist(),
                dimensions=feature.dimensions,
                confidence=feature.confidence,
                zone_index=feature.zone_index
            )
            feature_specs.append(spec)
        
        # Compute overall confidence
        if zone_specs:
            zone_confidences = [z.confidence for z in zone_specs]
            mean_confidence = sum(zone_confidences) / len(zone_confidences)
        else:
            mean_confidence = 0.5
        
        return ShaftConstructionPlan(
            part_type="shaft",
            base_axis=axis_spec,
            segments=zone_specs,
            features=feature_specs,
            fillets=[],  # Extracted from zones if needed
            chamfers=[],  # Extracted from zones if needed
            confidence=mean_confidence * axis_info.confidence,
            measurement_log=measurement_log
        )
    
    def _convert_shaft_to_features3d(
        self,
        zones: List[Any],
        features: List[Any]
    ) -> List[Feature3D]:
        """Convert shaft zones and features to Feature3D format for compatibility."""
        features_3d = []
        
        # Convert zones to cylinders
        for zone in zones:
            if zone.zone_type.value == "cylinder":
                feature = Feature3D(
                    feature_type="cylinder",
                    position=[0, 0, (zone.start_pos + zone.end_pos) / 2],
                    orientation=[0, 0, 1],
                    dimensions={
                        "radius": zone.mean_radius,
                        "height": zone.end_pos - zone.start_pos
                    },
                    confidence=zone.confidence
                )
                features_3d.append(feature)
        
        # Convert local features
        for feature in features:
            feature_3d = Feature3D(
                feature_type=feature.feature_type.value,
                position=feature.position.tolist(),
                orientation=feature.orientation.tolist(),
                dimensions=feature.dimensions,
                confidence=feature.confidence,
                evidence=feature.evidence
            )
            features_3d.append(feature_3d)
        
        return features_3d
    
    def _convert_shaft_to_buildsteps(
        self,
        zones: List[Any],
        features: List[Any]
    ) -> List[BuildStep]:
        """Convert shaft data to BuildStep format for compatibility."""
        steps = []
        step_num = 1
        
        # Find main body (largest cylinder)
        cylinders = [z for z in zones if z.zone_type.value == "cylinder"]
        if cylinders:
            main_cylinder = max(cylinders, key=lambda z: z.mean_radius)
            
            steps.append(BuildStep(
                step_number=step_num,
                operation="base_sketch",
                description=f"Base circle radius={main_cylinder.mean_radius:.3f}",
                parameters={"radius": main_cylinder.mean_radius},
                dependencies=[]
            ))
            step_num += 1
        
        # Add steps for each feature
        for feature in features:
            if feature.feature_type.value in ("keyway", "flat"):
                steps.append(BuildStep(
                    step_number=step_num,
                    operation="cut",
                    description=f"{feature.feature_type.value} cut",
                    parameters=feature.dimensions,
                    dependencies=[1]
                ))
                step_num += 1
        
        return steps


def create_coordinator_agent(
    llm_client: Optional[Any] = None,
    part_type: str = "generic"
) -> callable:
    """Factory function for creating Coordinator agent.

    Returns a function that can be used by the LangGraph orchestrator.

    Args:
        llm_client: Optional LLM client.
        part_type: Type of part to analyze ("generic" or "shaft").

    Returns:
        Coordinator function: state -> dict.
    """
    agent = CoordinatorAgent(llm_client=llm_client)
    
    def coordinator_fn(state: CADState) -> Dict[str, Any]:
        # Route to appropriate analysis method
        if part_type == "shaft":
            if not state.aligned_mesh_path:
                logger.error("[Coordinator] No aligned mesh for shaft analysis")
                return {"shaft_construction_plan": None, "features": [], "plan": []}
            return agent.analyze_shaft(state.aligned_mesh_path, state)
        else:
            # Default generic analysis
            return agent.analyze(state)
    
    return coordinator_fn