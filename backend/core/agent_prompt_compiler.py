"""Agent Prompt Compiler - Assemble system prompts from CADAgentSpec + runtime context.

Adapted from Vibe_contract's PromptCompiler but focused on CAD/CAM context:
- Uses CADAgentSpec instead of VibePersona
- Considers pipeline phase (analysis/planning/coding/repair)
- Incorporates tool/sensor status and errors
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pathlib import Path

from backend.core.agent_contracts import CADAgentSpec, PromptRule
from backend.core.spec_loader import get_spec_loader

if TYPE_CHECKING:
    from backend.core.state import CADState

logger = logging.getLogger(__name__)


# Default prompt templates (fallback when no spec or YAML template available)
DEFAULT_TEMPLATES = {
    "coordinator_analysis": """You are the Coordinator agent for a CAD reverse engineering system.

Your task: Analyze sensor reports and identify 3D geometric features.

Input:
- Sensor reports from X, Y, Z axes
- Slice positions and detected 2D features

Output format:
Return a JSON-like structure with:
- "features": List of 3D features (cylinders, holes, slots)
- "plan": Step-by-step construction plan

Guidelines:
1. Correlate 2D circles across slices to identify cylinders
2. Small circles (<5mm radius) are likely holes
3. Rectangular features may indicate slots
4. Each feature needs: position, orientation, dimensions, confidence

Current context:
{context}
""",

    "coordinator_planning": """Create a parametric construction plan.

Given these 3D features:
{features}

Create a build plan with operations in this order:
1. base_sketch - Create the main profile
2. extrude - Create solid from sketch
3. cut - Subtract holes and slots
4. fillet/chamfer - Edge treatments (if needed)

Each step needs:
- operation: string
- description: human-readable
- parameters: dict with operation-specific values
- dependencies: list of step numbers this depends on
""",

    "coordinator_repair": """The previous construction plan had issues.

Errors from previous iteration:
{errors}

Iteration: {iteration_count} of {max_iterations}

Please revise the plan to fix these issues while maintaining
feature integrity. Focus on:
1. Dimensional accuracy
2. Feature relationships
3. Manufacturing feasibility
""",

    "coder_generation": """You are a CAD code generator using build123d.

Generate Python code to create this 3D model:

Construction Plan:
{plan}

Identified Features:
{features}

Requirements:
1. Use: from build123d import *
2. Use context managers: with BuildPart() as model:
3. Define parameters at the top
4. Follow the plan steps exactly
5. Use Mode.SUBTRACT for cuts
6. Export as: part = model.part

YAGNI: Only implement what's in the plan.
""",

    "coder_repair": """Fix the generated CAD code.

Previous code had these errors:
{errors}

Geometric discrepancies:
{geometric_errors}

Iteration: {iteration_count}

Fix the code while maintaining:
1. Build123d API compatibility
2. Parametric design principles
3. Clean, readable structure
""",
}


class AgentPromptCompiler:
    """Compiles system prompts from agent spec + runtime context.
    
    Supports dual-path operation:
    - If compiled spec available -> use spec + templates
    - Otherwise -> fallback to legacy hardcoded prompts
    """
    
    def __init__(self, agent_role: str, spec: Optional[CADAgentSpec] = None):
        """Initialize the compiler for an agent.
        
        Args:
            agent_role: Role identifier (coordinator, coder, judge, etc.)
            spec: Optional pre-loaded agent spec. If None, will try to load.
        """
        self.agent_role = agent_role
        self.spec = spec
        self._templates: Dict[str, str] = {}
        
        if spec is None:
            try:
                loader = get_spec_loader()
                self.spec = loader.load_agent_spec(agent_role)
                logger.info(f"[PromptCompiler] Loaded spec for {agent_role}")
            except Exception as e:
                logger.warning(f"[PromptCompiler] Could not load spec for {agent_role}: {e}")
                self.spec = None
        
        # Load default templates as fallback
        self._templates.update(DEFAULT_TEMPLATES)
    
    def compile_prompt(
        self,
        phase: str,
        state: Optional["CADState"] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Compile a prompt for the given phase.
        
        Args:
            phase: Pipeline phase (analysis, planning, coding, repair, validation)
            state: Current CAD state for context
            extra_context: Additional context variables
        
        Returns:
            Compiled prompt string.
        """
        context = self._build_context(state, extra_context)
        
        # Try to find template from spec
        template = None
        if self.spec:
            template = self._get_template_from_spec(phase, context)
        
        # Fallback to default templates
        if template is None:
            template_key = f"{self.agent_role}_{phase}"
            template = self._templates.get(template_key)
            logger.debug(f"[PromptCompiler] Using fallback template: {template_key}")
        
        # Last resort: generic template
        if template is None:
            template = self._generate_generic_template(phase)
            logger.warning(f"[PromptCompiler] No template found for {self.agent_role}/{phase}, using generic")
        
        # Render template with context
        try:
            rendered = template.format(**context)
            return rendered
        except KeyError as e:
            logger.error(f"[PromptCompiler] Missing context variable {e} in template")
            # Return unrendered template as fallback
            return template
    
    def _build_context(
        self,
        state: Optional["CADState"],
        extra: Optional[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Build the context dictionary for template rendering."""
        context: Dict[str, str] = {}
        
        # Add state information if available
        if state:
            import json
            
            # Sensor reports summary
            if state.sensor_reports:
                reports = []
                for axis, report in state.sensor_reports.items():
                    reports.append(f"{axis.value}: {len(report.features_by_slice)} slices")
                context["sensor_reports"] = "\n".join(reports)
            else:
                context["sensor_reports"] = "No sensor reports available"
            
            # Features
            if state.identified_features:
                features = []
                for f in state.identified_features:
                    features.append(f"- {f.feature_type} at {f.position}")
                context["features"] = "\n".join(features)
            else:
                context["features"] = "No features identified yet"
            
            # Construction plan
            if state.construction_plan:
                plan = []
                for step in state.construction_plan:
                    plan.append(f"{step.step_number}. {step.operation}: {step.description}")
                context["plan"] = "\n".join(plan)
            else:
                context["plan"] = "No construction plan available"
            
            # Errors
            if state.geometric_errors:
                errors = []
                for e in state.geometric_errors:
                    desc = e.get("description", "Unknown error")
                    errors.append(f"- {desc}")
                context["geometric_errors"] = "\n".join(errors)
            else:
                context["geometric_errors"] = "None"
            
            if state.validation_errors:
                context["validation_errors"] = "\n".join(f"- {e}" for e in state.validation_errors)
            else:
                context["validation_errors"] = "None"
            
            if state.execution_errors:
                context["execution_errors"] = "\n".join(f"- {e}" for e in state.execution_errors)
            else:
                context["execution_errors"] = "None"
            
            # Iteration info
            context["iteration_count"] = str(state.iteration_count)
            context["max_iterations"] = str(state.max_iterations)
            
            # Metrics
            if state.chamfer_distance is not None:
                context["chamfer_distance"] = f"{state.chamfer_distance:.4f}"
            else:
                context["chamfer_distance"] = "N/A"
            
            if state.hausdorff_distance is not None:
                context["hausdorff_distance"] = f"{state.hausdorff_distance:.4f}"
            else:
                context["hausdorff_distance"] = "N/A"
        
        # Add extra context
        if extra:
            for key, value in extra.items():
                if isinstance(value, (list, dict)):
                    import json
                    context[key] = json.dumps(value, indent=2)
                else:
                    context[key] = str(value)
        
        return context
    
    def _get_template_from_spec(self, phase: str, context: Dict[str, str]) -> Optional[str]:
        """Get template from agent spec if available."""
        if not self.spec:
            return None
        
        # Find matching prompt rule
        for rule in self.spec.prompt_rules:
            if rule.phase == phase:
                template_key = rule.template_key
                # Try to load from external template file
                template_path = Path("config/templates") / f"{template_key}.txt"
                if template_path.exists():
                    return template_path.read_text(encoding='utf-8')
                
                # Try default templates
                if template_key in self._templates:
                    return self._templates[template_key]
        
        return None
    
    def _generate_generic_template(self, phase: str) -> str:
        """Generate a generic template when no specific one is found."""
        return f"""You are the {self.agent_role} agent in a CAD reverse engineering system.

Current phase: {phase}

Context:
{{context}}

Please perform your assigned task based on the available information.
"""
    
    def has_spec(self) -> bool:
        """Check if a valid spec is loaded."""
        return self.spec is not None
    
    def get_fallback_status(self) -> Dict[str, Any]:
        """Get information about fallback status."""
        return {
            "agent_role": self.agent_role,
            "has_spec": self.spec is not None,
            "spec_version": self.spec.version if self.spec else None,
            "available_templates": list(self._templates.keys()),
        }


class PromptCompilerRegistry:
    """Registry for managing multiple prompt compilers."""
    
    def __init__(self):
        self._compilers: Dict[str, AgentPromptCompiler] = {}
    
    def get_compiler(self, agent_role: str) -> AgentPromptCompiler:
        """Get or create a compiler for an agent role."""
        if agent_role not in self._compilers:
            self._compilers[agent_role] = AgentPromptCompiler(agent_role)
        return self._compilers[agent_role]
    
    def reload_all(self) -> None:
        """Reload all compilers (e.g., after config changes)."""
        self._compilers.clear()
        # Also reload spec loader cache
        from backend.core.spec_loader import get_spec_loader
        loader = get_spec_loader()
        loader.reload()


# Global registry
_compiler_registry: Optional[PromptCompilerRegistry] = None


def get_prompt_compiler(agent_role: str) -> AgentPromptCompiler:
    """Get a prompt compiler for the given agent role.
    
    Args:
        agent_role: Agent role identifier.
    
    Returns:
        Configured AgentPromptCompiler instance.
    """
    global _compiler_registry
    if _compiler_registry is None:
        _compiler_registry = PromptCompilerRegistry()
    return _compiler_registry.get_compiler(agent_role)


def compile_prompt(
    agent_role: str,
    phase: str,
    state: Optional["CADState"] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to compile a prompt in one call.
    
    Args:
        agent_role: Agent role identifier.
        phase: Pipeline phase.
        state: Current CAD state.
        extra_context: Additional context variables.
    
    Returns:
        Compiled prompt string.
    """
    compiler = get_prompt_compiler(agent_role)
    return compiler.compile_prompt(phase, state, extra_context)
