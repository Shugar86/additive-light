"""CAD Agent Contracts - Pydantic models for agent specifications.

This module defines the structured contract layer for CAD swarm agents,
adapted from Vibe_contract concepts but focused on CAD/CAM execution.
"""

from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum


class RetryPolicy(BaseModel):
    """Policy for retrying failed operations."""
    max_retries: int = Field(default=3, ge=0)
    backoff_strategy: str = Field(default="exponential", pattern="^(fixed|exponential|linear)$")
    initial_delay_seconds: float = Field(default=1.0, ge=0)
    max_delay_seconds: float = Field(default=60.0, ge=0)
    retryable_errors: List[str] = Field(default_factory=list)


class FailurePolicy(BaseModel):
    """Policy for handling different failure modes."""
    on_execution_error: str = Field(default="retry", pattern="^(retry|escalate|skip|fail)$")
    on_validation_error: str = Field(default="repair", pattern="^(retry|repair|escalate|fail)$")
    on_missing_evidence: str = Field(default="request_more", pattern="^(request_more|infer|skip|fail)$")
    on_timeout: str = Field(default="escalate", pattern="^(retry|escalate|skip|fail)$")


class EscalationPolicy(BaseModel):
    """Policy for escalating issues to higher-level agents."""
    enabled: bool = True
    escalation_target: Optional[str] = None  # agent_id to escalate to
    escalation_conditions: List[str] = Field(default_factory=list)
    max_escalation_depth: int = Field(default=2, ge=0)


class InputContract(BaseModel):
    """Contract for agent inputs."""
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)
    field_types: Dict[str, str] = Field(default_factory=dict)
    preconditions: List[str] = Field(default_factory=list)


class OutputContract(BaseModel):
    """Contract for agent outputs."""
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)
    field_types: Dict[str, str] = Field(default_factory=dict)
    postconditions: List[str] = Field(default_factory=list)


class PromptRule(BaseModel):
    """Rule for prompt assembly."""
    phase: str = Field(..., pattern="^(analysis|planning|coding|repair|validation)$")
    template_key: str
    context_variables: List[str] = Field(default_factory=list)
    priority: int = Field(default=0)


class ToolConfig(BaseModel):
    """Configuration for a tool available to the agent."""
    tool_name: str
    enabled: bool = True
    required_permissions: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[float] = None
    fallback_behavior: str = Field(default="error", pattern="^(error|skip|alternative)$")


class CADAgentSpec(BaseModel):
    """CAD-Adapted Agent Specification.
    
    Inspired by Vibe_contract's PersonaConfig but focused on CAD/CAM execution
    rather than conversational personas.
    """
    agent_id: str = Field(..., description="Unique identifier for the agent")
    role: str = Field(..., description="Agent role (coordinator, coder, sensor, judge, etc.)")
    objective: str = Field(..., description="Primary objective/purpose of the agent")
    planning_style: str = Field(
        default="sequential",
        pattern="^(sequential|parallel|adaptive|hierarchical)$"
    )
    
    # Tool and execution configuration
    allowed_tools: List[str] = Field(default_factory=list)
    tool_configs: Dict[str, ToolConfig] = Field(default_factory=dict)
    
    # Input/Output contracts
    input_contract: InputContract = Field(default_factory=InputContract)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    
    # Policies
    failure_policy: FailurePolicy = Field(default_factory=FailurePolicy)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    
    # Prompt assembly rules
    prompt_rules: List[PromptRule] = Field(default_factory=list)
    
    # Metadata
    version: str = Field(default="1.0.0")
    enabled: bool = True
    tags: List[str] = Field(default_factory=list)


class SwarmPolicy(BaseModel):
    """Policy configuration for the entire agent swarm."""
    
    # Global retry and failure handling
    default_retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    default_failure_policy: FailurePolicy = Field(default_factory=FailurePolicy)
    
    # Pipeline configuration
    max_iterations: int = Field(default=3, ge=1)
    enable_reflection: bool = True
    enable_parallel_sensors: bool = True
    
    # Sensor configuration
    default_sensor_axes: List[str] = Field(default_factory=lambda: ["X", "Y", "Z"])
    required_sensor_coverage: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Validation thresholds
    chamfer_tolerance: float = Field(default=0.1, ge=0.0)
    hausdorff_tolerance: float = Field(default=0.5, ge=0.0)
    
    # Security policy
    allowed_imports: List[str] = Field(default_factory=list)
    forbidden_imports: List[str] = Field(default_factory=list)
    max_code_execution_time: int = Field(default=60, ge=1)
    
    # Agent registry reference
    agent_specs: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of agent roles to spec file paths"
    )


class SensorSpec(BaseModel):
    """Specification for a sensor agent."""
    sensor_id: str
    sensor_type: str = Field(..., pattern="^(axis_slice|surface_probe|feature_detector|custom)$")
    axes: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = Field(default=1)
    dependencies: List[str] = Field(default_factory=list)


class SensorRegistry(BaseModel):
    """Registry of all available sensors."""
    sensors: Dict[str, SensorSpec] = Field(default_factory=dict)
    default_sensors: List[str] = Field(default_factory=list)
    sensor_groups: Dict[str, List[str]] = Field(default_factory=dict)


class ExecutionPolicy(BaseModel):
    """Policy for secure code execution."""
    sandbox_type: str = Field(default="subprocess", pattern="^(subprocess|container|vm)$")
    network_access: bool = False
    filesystem_access: str = Field(default="temp_only", pattern="^(none|temp_only|restricted|full)$")
    allowed_packages: List[str] = Field(default_factory=list)
    forbidden_modules: List[str] = Field(default_factory=list)
    memory_limit_mb: Optional[int] = None
    cpu_time_limit_seconds: Optional[float] = None
