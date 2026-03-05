"""Specification Loader - Load and validate YAML agent specifications.

Loads CADAgentSpec, SwarmPolicy, and SensorRegistry from YAML files.
"""

import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union

from backend.core.agent_contracts import (
    CADAgentSpec, SwarmPolicy, SensorRegistry, SensorSpec
)

logger = logging.getLogger(__name__)


class SpecLoader:
    """Loader for YAML agent specifications."""
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """Initialize the spec loader.
        
        Args:
            config_dir: Directory containing YAML config files.
                       Defaults to 'config' in project root.
        """
        if config_dir is None:
            # Find project root (where .git or additive-light.code-workspace exists)
            current = Path.cwd()
            while current != current.parent:
                if (current / ".git").exists() or (current / "additive-light.code-workspace").exists():
                    break
                current = current.parent
            config_dir = current / "config"
        
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
        
        logger.info(f"[SpecLoader] Initialized with config dir: {self.config_dir}")
    
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return data or {}
    
    def load_agent_spec(self, agent_role: str) -> CADAgentSpec:
        """Load agent specification by role.
        
        Args:
            agent_role: Role name (coordinator, coder, judge, etc.)
        
        Returns:
            Validated CADAgentSpec instance.
        """
        cache_key = f"agent:{agent_role}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        spec_path = self.config_dir / "agents" / f"{agent_role}.yaml"
        
        try:
            data = self._load_yaml(spec_path)
            spec = CADAgentSpec(**data)
            self._cache[cache_key] = spec
            logger.info(f"[SpecLoader] Loaded agent spec: {agent_role} (v{spec.version})")
            return spec
        except FileNotFoundError:
            logger.warning(f"[SpecLoader] Spec not found for {agent_role}, using defaults")
            # Return default spec
            spec = CADAgentSpec(
                agent_id=agent_role,
                role=agent_role,
                objective=f"Default {agent_role} agent"
            )
            self._cache[cache_key] = spec
            return spec
        except Exception as e:
            logger.error(f"[SpecLoader] Failed to load spec for {agent_role}: {e}")
            raise
    
    def load_swarm_policy(self) -> SwarmPolicy:
        """Load the swarm policy configuration.
        
        Returns:
            Validated SwarmPolicy instance.
        """
        cache_key = "swarm_policy"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        policy_path = self.config_dir / "swarm_policy.yaml"
        
        try:
            data = self._load_yaml(policy_path)
            policy = SwarmPolicy(**data)
            self._cache[cache_key] = policy
            logger.info(f"[SpecLoader] Loaded swarm policy")
            return policy
        except FileNotFoundError:
            logger.warning(f"[SpecLoader] Swarm policy not found, using defaults")
            policy = SwarmPolicy()
            self._cache[cache_key] = policy
            return policy
        except Exception as e:
            logger.error(f"[SpecLoader] Failed to load swarm policy: {e}")
            raise
    
    def load_sensor_registry(self) -> SensorRegistry:
        """Load the sensor registry.
        
        Returns:
            Validated SensorRegistry instance.
        """
        cache_key = "sensor_registry"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        registry_path = self.config_dir / "sensors" / "registry.yaml"
        
        try:
            data = self._load_yaml(registry_path)
            registry = SensorRegistry(**data)
            self._cache[cache_key] = registry
            logger.info(f"[SpecLoader] Loaded sensor registry with {len(registry.sensors)} sensors")
            return registry
        except FileNotFoundError:
            logger.warning(f"[SpecLoader] Sensor registry not found, using defaults")
            # Create default registry with X/Y/Z sensors
            registry = SensorRegistry(
                sensors={
                    "X": SensorSpec(sensor_id="X", sensor_type="axis_slice", axes=["X"]),
                    "Y": SensorSpec(sensor_id="Y", sensor_type="axis_slice", axes=["Y"]),
                    "Z": SensorSpec(sensor_id="Z", sensor_type="axis_slice", axes=["Z"]),
                },
                default_sensors=["X", "Y", "Z"]
            )
            self._cache[cache_key] = registry
            return registry
        except Exception as e:
            logger.error(f"[SpecLoader] Failed to load sensor registry: {e}")
            raise
    
    def reload(self) -> None:
        """Clear cache and reload all specs."""
        self._cache.clear()
        logger.info("[SpecLoader] Cache cleared, specs will be reloaded")
    
    def get_all_agent_specs(self) -> Dict[str, CADAgentSpec]:
        """Load all available agent specs.
        
        Returns:
            Dictionary mapping agent roles to specs.
        """
        specs = {}
        agents_dir = self.config_dir / "agents"
        
        if not agents_dir.exists():
            return specs
        
        for yaml_file in agents_dir.glob("*.yaml"):
            role = yaml_file.stem
            try:
                specs[role] = self.load_agent_spec(role)
            except Exception as e:
                logger.warning(f"[SpecLoader] Failed to load {role}: {e}")
        
        return specs


# Global loader instance
_spec_loader: Optional[SpecLoader] = None


def get_spec_loader(config_dir: Optional[Union[str, Path]] = None) -> SpecLoader:
    """Get or create the global spec loader instance.
    
    Args:
        config_dir: Optional config directory override.
    
    Returns:
        SpecLoader instance.
    """
    global _spec_loader
    if _spec_loader is None or config_dir is not None:
        _spec_loader = SpecLoader(config_dir)
    return _spec_loader
