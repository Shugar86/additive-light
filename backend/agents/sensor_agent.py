"""Parallel sensor agents for exploring STL geometry along each axis.

Each sensor agent is a Fast LLM (e.g., Gemini Flash) equipped with deterministic
slicing tools. They analyze their assigned axis and produce structured YAML/JSON
reports for the Coordinator.

P5 Refactor: Now supports dynamic sensor configuration from SensorRegistry.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from backend.core.state import Axis, SliceReport, SliceFeature
from backend.core.config import settings
from backend.core.spec_loader import get_spec_loader
from backend.core.agent_contracts import SensorSpec
from backend.sensors.slice_trimesh import SliceAnalyzer

logger = logging.getLogger(__name__)


class SensorAgent:
    """Fast LLM agent for analyzing geometry along one axis.
    
    This agent uses deterministic slicing tools (Trimesh/Shapely) to extract
    features, then uses a Fast LLM to interpret the results and produce
    a structured report.
    """

    def __init__(
        self,
        axis: Axis,
        llm_client: Optional[Any] = None,
        slice_count: int = 20
    ):
        """Initialize a sensor agent for a specific axis.

        Args:
            axis: Which axis this agent explores (X, Y, or Z).
            llm_client: Optional LLM client for interpretation. If None,
                       uses rule-based analysis (deterministic).
            slice_count: Number of slices to create along the axis.
        """
        self.axis = axis
        self.llm_client = llm_client
        self.slice_count = slice_count
        
        logger.info(f"[SensorAgent.{axis.value}] Initialized with {slice_count} slices")

    def analyze(self, mesh_path: str) -> SliceReport:
        """Analyze mesh along assigned axis and produce report.

        Args:
            mesh_path: Path to aligned mesh file.

        Returns:
            SliceReport with detected features and summary.

        Raises:
            FileNotFoundError: If mesh file doesn't exist.
            RuntimeError: If analysis fails.
        """
        logger.info(f"[SensorAgent.{self.axis.value}] Starting analysis of {mesh_path}")

        if not Path(mesh_path).exists():
            raise FileNotFoundError(f"Mesh not found: {mesh_path}")

        try:
            # Step 1: Deterministic slicing using Trimesh
            analyzer = SliceAnalyzer(mesh_path)
            raw_slices = analyzer.slice_along_axis(
                axis=self.axis.value,
                slice_count=self.slice_count
            )

            logger.debug(f"[SensorAgent.{self.axis.value}] Created {len(raw_slices)} raw slices")

            # Step 2: Feature extraction (deterministic)
            features_by_slice: Dict[str, List[SliceFeature]] = {}
            all_anomalies: List[str] = []

            for i, slice_data in enumerate(raw_slices):
                slice_key = f"slice_{i:03d}_pos_{slice_data['position']:.3f}"
                slice_features: List[SliceFeature] = []

                for feature in slice_data.get("features", []):
                    slice_feature = SliceFeature(
                        feature_type=feature["type"],
                        center=feature.get("center", [0.0, 0.0]),
                        radius=feature.get("radius"),
                        dimensions=([
                            feature.get("width"),
                            feature.get("height")
                        ] if feature["type"] == "rectangle" else None),
                        area=feature["area"],
                        perimeter=feature["perimeter"],
                        confidence=feature.get("circle_confidence", 0.8)
                    )
                    slice_features.append(slice_feature)

                features_by_slice[slice_key] = slice_features

                # Detect anomalies
                anomalies = self._detect_anomalies(slice_data, i)
                all_anomalies.extend(anomalies)

            # Step 3: Generate summary
            if self.llm_client:
                summary = self._generate_llm_summary(raw_slices, features_by_slice)
            else:
                summary = self._generate_rule_summary(raw_slices, features_by_slice)

            # Step 4: Compute overall bounds
            bounds = analyzer.mesh.bounds

            report = SliceReport(
                axis=self.axis,
                slice_positions=[s["position"] for s in raw_slices],
                features_by_slice=features_by_slice,
                overall_bounds=bounds.flatten().tolist() if hasattr(bounds, 'flatten') else list(bounds),
                analysis_summary=summary,
                anomalies_detected=list(set(all_anomalies))  # Remove duplicates
            )

            logger.info(f"[SensorAgent.{self.axis.value}] Analysis complete: "
                       f"{len(features_by_slice)} slices, {len(all_anomalies)} anomalies")

            return report

        except Exception as e:
            logger.error(f"[SensorAgent.{self.axis.value}] Analysis failed: {e}")
            raise RuntimeError(f"Sensor analysis failed for axis {self.axis.value}: {e}") from e

    def _detect_anomalies(self, slice_data: Dict[str, Any], slice_index: int) -> List[str]:
        """Detect geometric anomalies in a slice."""
        anomalies = []
        features = slice_data.get("features", [])
        
        # Anomaly 1: Multiple features in one slice (holes, slots)
        circles = [f for f in features if f["type"] == "circle"]
        if len(circles) > 1:
            radii = [c["radius"] for c in circles]
            if max(radii) > 2 * min(radii):  # Significant size difference
                anomalies.append(
                    f"slice_{slice_index}: Multiple circles with varying sizes "
                    f"(possible hole pattern)"
                )
        
        # Anomaly 2: Rectangular features (keyways, slots)
        rectangles = [f for f in features if f["type"] == "rectangle"]
        if rectangles:
            for rect in rectangles:
                aspect = rect.get("aspect_ratio", 1.0)
                if aspect > 3.0:  # Long and narrow
                    anomalies.append(
                        f"slice_{slice_index}: Long rectangular feature "
                        f"(possible keyway or slot)"
                    )
        
        # Anomaly 3: Non-circular outer profile
        if features:
            largest = max(features, key=lambda f: f["area"])
            if largest["type"] == "polygon" and largest.get("circle_confidence", 0) < 0.8:
                anomalies.append(
                    f"slice_{slice_index}: Non-circular outer profile "
                    f"(confidence: {largest.get('circle_confidence', 0):.2f})"
                )
        
        return anomalies

    def _generate_rule_summary(
        self,
        raw_slices: List[Dict[str, Any]],
        features_by_slice: Dict[str, List[SliceFeature]]
    ) -> str:
        """Generate a rule-based summary (no LLM needed).
        
        This provides a deterministic summary for environments without
        LLM access or for testing purposes.
        """
        # Count feature types across all slices
        type_counts: Dict[str, int] = {}
        radius_values: List[float] = []
        position_range = [float('inf'), float('-inf')]
        
        for slice_key, features in features_by_slice.items():
            for feature in features:
                ftype = feature.feature_type
                type_counts[ftype] = type_counts.get(ftype, 0) + 1
                
                if feature.radius:
                    radius_values.append(feature.radius)
        
        for slice_data in raw_slices:
            pos = slice_data["position"]
            position_range[0] = min(position_range[0], pos)
            position_range[1] = max(position_range[1], pos)

        # Build summary
        parts = [f"Analysis along {self.axis.value}-axis:"]
        parts.append(f"  - {len(raw_slices)} slices from {position_range[0]:.3f} to {position_range[1]:.3f}")
        parts.append(f"  - Feature types: {dict(type_counts)}")
        
        if radius_values:
            avg_radius = sum(radius_values) / len(radius_values)
            min_radius = min(radius_values)
            max_radius = max(radius_values)
            parts.append(f"  - Circle radii: avg={avg_radius:.3f}, range=[{min_radius:.3f}, {max_radius:.3f}]")
        
        return "\n".join(parts)

    def _generate_llm_summary(
        self,
        raw_slices: List[Dict[str, Any]],
        features_by_slice: Dict[str, List[SliceFeature]]
    ) -> str:
        """Generate summary using Fast LLM (optional).
        
        If LLM client is available, this produces a more natural language
        summary. Falls back to rule-based if LLM fails.
        """
        if not self.llm_client:
            return self._generate_rule_summary(raw_slices, features_by_slice)

        try:
            # Prepare compact context for LLM
            context = {
                "axis": self.axis.value,
                "slice_count": len(raw_slices),
                "features_by_slice": {
                    k: [
                        {
                            "type": f.feature_type,
                            "radius": f.radius,
                            "area": f.area,
                            "confidence": f.confidence
                        }
                        for f in v
                    ]
                    for k, v in list(features_by_slice.items())[:5]  # Limit context
                }
            }

            prompt = f"""You are a geometric analysis assistant. Analyze this {self.axis.value}-axis slice data:

{json.dumps(context, indent=2)}

Provide a brief summary (2-3 sentences) of:
1. The dominant shape type (cylindrical, rectangular, etc.)
2. Key dimensions if circles are present
3. Any notable patterns or anomalies

Be concise and factual."""

            # Call LLM (implementation depends on client interface)
            # This is a placeholder - actual implementation would use the client
            response = "LLM summary not implemented (rule-based fallback)"
            
            return response

        except Exception as e:
            logger.warning(f"[SensorAgent.{self.axis.value}] LLM summary failed: {e}")
            return self._generate_rule_summary(raw_slices, features_by_slice)


def create_sensor_agent_factory(llm_client: Optional[Any] = None) -> callable:
    """Factory function for creating sensor agents.

    Returns a function that creates SensorAgent instances for specific axes.
    This factory is used by the LangGraph orchestrator.

    Args:
        llm_client: Optional shared LLM client.

    Returns:
        Factory function: axis -> SensorAgent.
    """
    def factory(axis: Axis) -> SensorAgent:
        return SensorAgent(
            axis=axis,
            llm_client=llm_client,
            slice_count=settings.default_slice_count
        )
    
    return factory


class SensorRegistryFactory:
    """Factory for creating sensor agents based on SensorRegistry configuration.
    
    P5 Refactor: Dynamic sensor creation from YAML configuration.
    Replaces the hardcoded X/Y/Z approach with configurable sensor registry.
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """Initialize the factory with sensor registry.
        
        Args:
            llm_client: Optional shared LLM client for all sensors.
        """
        self.llm_client = llm_client
        self._registry = None
        self._sensor_specs: Dict[str, SensorSpec] = {}
        
        try:
            loader = get_spec_loader()
            registry = loader.load_sensor_registry()
            self._registry = registry
            self._sensor_specs = registry.sensors
            logger.info(f"[SensorRegistryFactory] Loaded {len(self._sensor_specs)} sensor specs")
        except Exception as e:
            logger.warning(f"[SensorRegistryFactory] Could not load registry: {e}")
            # Fallback to default X/Y/Z
            self._sensor_specs = {
                "X": SensorSpec(sensor_id="X", sensor_type="axis_slice", axes=["X"]),
                "Y": SensorSpec(sensor_id="Y", sensor_type="axis_slice", axes=["Y"]),
                "Z": SensorSpec(sensor_id="Z", sensor_type="axis_slice", axes=["Z"]),
            }
    
    def get_available_sensors(self) -> List[str]:
        """Get list of available sensor IDs.
        
        Returns:
            List of sensor IDs that are enabled.
        """
        return [
            sensor_id for sensor_id, spec in self._sensor_specs.items()
            if spec.enabled
        ]
    
    def get_default_sensors(self) -> List[str]:
        """Get default sensor IDs for standard analysis.
        
        Returns:
            List of default sensor IDs (typically X, Y, Z).
        """
        if self._registry and self._registry.default_sensors:
            return self._registry.default_sensors
        return ["X", "Y", "Z"]
    
    def create_sensor(self, sensor_id: str) -> Optional[SensorAgent]:
        """Create a sensor agent by ID.
        
        Args:
            sensor_id: ID of the sensor to create.
        
        Returns:
            Configured SensorAgent or None if sensor not found/disabled.
        """
        spec = self._sensor_specs.get(sensor_id)
        if not spec:
            logger.warning(f"[SensorRegistryFactory] Sensor {sensor_id} not found")
            return None
        
        if not spec.enabled:
            logger.info(f"[SensorRegistryFactory] Sensor {sensor_id} is disabled")
            return None
        
        # Map sensor to appropriate Axis
        if spec.sensor_type == "axis_slice" and spec.axes:
            axis_value = spec.axes[0]  # Primary axis
            try:
                axis = Axis(axis_value)
            except ValueError:
                logger.error(f"[SensorRegistryFactory] Invalid axis: {axis_value}")
                return None
        else:
            # For non-axis sensors, default to Z for now
            axis = Axis.Z
        
        # Get slice count from spec parameters or use default
        slice_count = spec.parameters.get("slice_count", settings.default_slice_count)
        
        agent = SensorAgent(
            axis=axis,
            llm_client=self.llm_client,
            slice_count=slice_count
        )
        
        logger.info(f"[SensorRegistryFactory] Created sensor {sensor_id} (axis={axis.value}, slices={slice_count})")
        return agent
    
    def create_all_default_sensors(self) -> Dict[str, SensorAgent]:
        """Create all default sensor agents.
        
        Returns:
            Dictionary mapping sensor IDs to agents.
        """
        sensors = {}
        for sensor_id in self.get_default_sensors():
            agent = self.create_sensor(sensor_id)
            if agent:
                sensors[sensor_id] = agent
        return sensors


def create_dynamic_sensor_factory(llm_client: Optional[Any] = None) -> callable:
    """Create a dynamic sensor factory based on SensorRegistry.
    
    P5 Refactor: This factory uses the YAML sensor registry to create
    configurable sensor agents. Falls back to X/Y/Z if registry unavailable.
    
    Args:
        llm_client: Optional shared LLM client.
    
    Returns:
        Factory function that accepts sensor_id or Axis and returns SensorAgent.
    """
    registry_factory = SensorRegistryFactory(llm_client=llm_client)
    
    def factory(sensor_ref: Union[str, Axis]) -> Optional[SensorAgent]:
        """Create sensor by string ID or Axis enum.
        
        Args:
            sensor_ref: Sensor ID string or Axis enum.
        
        Returns:
            SensorAgent or None.
        """
        if isinstance(sensor_ref, Axis):
            sensor_id = sensor_ref.value
        else:
            sensor_id = sensor_ref
        
        return registry_factory.create_sensor(sensor_id)
    
    # Attach registry factory for advanced usage
    factory._registry = registry_factory
    factory.get_available_sensors = registry_factory.get_available_sensors
    factory.get_default_sensors = registry_factory.get_default_sensors
    
    return factory