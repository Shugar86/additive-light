"""Coder agent for generating parametric CAD code using build123d.

The Coder receives a construction plan from the Coordinator and translates it
into executable Python code using the build123d library (OCP-based parametric CAD).
"""

import logging
import json
from typing import Dict, Any, List, Optional

from backend.core.state import CADState, BuildStep, Feature3D
from backend.core.config import settings
from backend.core.agent_prompt_compiler import get_prompt_compiler

logger = logging.getLogger(__name__)


class CoderAgent:
    """Smart LLM agent that generates build123d code.
    
    This agent takes a structured construction plan and outputs clean,
    parametric Python code that can be executed to generate a B-Rep model.
    """

    def __init__(self, llm_client: Optional[Any] = None, use_prompt_compiler: bool = True):
        """Initialize the Coder agent.

        Args:
            llm_client: LLM client for code generation.
                       If None, uses template-based generation.
            use_prompt_compiler: Whether to use the PromptCompiler for prompt assembly.
                               Falls back to legacy prompts if compiler unavailable.
        """
        self.llm_client = llm_client
        self.use_prompt_compiler = use_prompt_compiler
        self._prompt_compiler = None
        
        if use_prompt_compiler:
            try:
                self._prompt_compiler = get_prompt_compiler("coder")
                logger.info("[CoderAgent] Initialized with PromptCompiler")
            except Exception as e:
                logger.warning(f"[CoderAgent] PromptCompiler not available: {e}")
                self._prompt_compiler = None
        
        logger.info("[CoderAgent] Initialized")

    def generate_code(self, state: CADState) -> str:
        """Generate build123d code from construction plan.

        Args:
            state: Current CAD state with construction plan.

        Returns:
            Python code string using build123d library.

        Raises:
            ValueError: If no construction plan is available.
        """
        if not state.construction_plan:
            raise ValueError("No construction plan available")

        # Check for previous errors to incorporate in generation
        error_context = ""
        if state.geometric_errors and state.iteration_count > 0:
            error_context = self._format_error_context(state.geometric_errors)
            logger.info(f"[CoderAgent] Incorporating {len(state.geometric_errors)} error corrections")

        try:
            if self.llm_client:
                code = self._generate_with_llm(state, error_context)
            else:
                code = self._generate_template_code(state, error_context)
            
            logger.info(f"[CoderAgent] Generated {len(code)} characters of code")
            return code

        except Exception as e:
            logger.error(f"[CoderAgent] Code generation failed: {e}")
            raise RuntimeError(f"Code generation failed: {e}") from e

    def _generate_template_code(
        self,
        state: CADState,
        error_context: str = ""
    ) -> str:
        """Generate code using templates (deterministic, no LLM).
        
        This is a fallback when LLM is not available. It produces
        working but less sophisticated code.
        """
        lines = [
            '"""Generated parametric CAD model using build123d."""',
            "",
            "from build123d import *",
            "from ocp_vscode import show",
            "",
            "# Parameters",
        ]

        # Extract parameters from features
        params: Dict[str, Any] = {}
        features_3d = state.identified_features
        
        # Find main cylinder parameters
        cylinders = [f for f in features_3d if f.feature_type == "cylinder"]
        if cylinders:
            main_cyl = max(cylinders, key=lambda c: c.dimensions.get("radius", 0))
            params["base_radius"] = main_cyl.dimensions.get("radius", 10.0)
            params["base_height"] = main_cyl.dimensions.get("height", 20.0)
        else:
            params["base_radius"] = 10.0
            params["base_height"] = 20.0

        # Add parameters to code
        for name, value in params.items():
            lines.append(f"{name} = {value}")

        lines.extend([
            "",
            "# Build the model",
            "with BuildPart() as model:",
        ])

        # Generate steps from construction plan
        indent = "    "
        
        for step in state.construction_plan:
            step_lines = self._generate_step_code(step, indent)
            lines.extend(step_lines)

        lines.extend([
            "",
            "# Export",
            "part = model.part",
            "",
            "if __name__ == '__main__':",
            '    print(f"Generated model: {part.volume} mm^3")',
            "    show(part)",
        ])

        return "\n".join(lines)

    def _generate_step_code(self, step: BuildStep, indent: str) -> List[str]:
        """Generate code for a single build step."""
        lines = []
        operation = step.operation
        params = step.parameters

        if operation == "base_sketch":
            shape = params.get("shape", "circle")
            
            if shape == "circle":
                radius = params.get("radius", 10.0)
                lines.append(f"{indent}# Base sketch: circle")
                lines.append(f"{indent}with BuildSketch(Plane.XY) as base:")
                lines.append(f"{indent}    Circle(radius={params.get('radius', 'base_radius')})")
            
            elif shape == "rectangle":
                width = params.get("width", 10.0)
                height = params.get("height", 10.0)
                lines.append(f"{indent}# Base sketch: rectangle")
                lines.append(f"{indent}with BuildSketch(Plane.XY) as base:")
                lines.append(f"{indent}    Rectangle(width={width}, height={height})")

        elif operation == "extrude":
            distance = params.get("distance", params.get("height", "base_height"))
            direction = params.get("direction", "both")
            
            lines.append(f"{indent}# Extrude base")
            if direction == "both":
                lines.append(f"{indent}extrude(amount={distance}/2, both=True)")
            else:
                lines.append(f"{indent}extrude(amount={distance})")

        elif operation == "cut":
            tool = params.get("tool", "cylinder")
            
            if tool == "cylinder":
                radius = params.get("radius", 2.0)
                position = params.get("position", [0, 0, 0])
                depth = params.get("depth", 10.0)
                
                lines.append(f"{indent}# Cut hole")
                lines.append(f"{indent}with Locations(({position[0]}, {position[1]})):")
                lines.append(f"{indent}    with BuildSketch() as hole_profile:")
                lines.append(f"{indent}        Circle(radius={radius})")
                lines.append(f"{indent}    extrude(amount={depth}, mode=Mode.SUBTRACT)")
            
            elif tool == "extrude":
                width = params.get("width", 2.0)
                length = params.get("length", 10.0)
                position = params.get("position", [0, 0, 0])
                
                lines.append(f"{indent}# Cut slot")
                lines.append(f"{indent}with Locations(({position[0]}, {position[1]})):")
                lines.append(f"{indent}    with BuildSketch() as slot_profile:")
                lines.append(f"{indent}        Rectangle(width={width}, height={length})")
                lines.append(f"{indent}    extrude(amount={position[2] if len(position) > 2 else 10.0}, mode=Mode.SUBTRACT)")

        return lines

    def _generate_with_llm(
        self,
        state: CADState,
        error_context: str = ""
    ) -> str:
        """Generate code using LLM (when available).
        
        This produces more sophisticated code that handles edge cases.
        Uses PromptCompiler if available, otherwise falls back to manual prompt building.
        """
        # Try to use PromptCompiler for better prompt assembly
        prompt = None
        if self._prompt_compiler:
            try:
                phase = "repair" if (state.geometric_errors or state.validation_errors) else "coding"
                prompt = self._prompt_compiler.compile_prompt(phase, state)
                logger.debug(f"[CoderAgent] Using compiled prompt for {phase}")
            except Exception as e:
                logger.warning(f"[CoderAgent] Prompt compilation failed: {e}")
        
        # Fallback to manual prompt building
        if not prompt:
            plan_json = json.dumps([s.model_dump() if hasattr(s, 'model_dump') else s for s in state.construction_plan], indent=2)
            features_json = json.dumps([f.model_dump() if hasattr(f, 'model_dump') else f for f in state.identified_features], indent=2)

            prompt = f"""You are an expert CAD programmer using build123d (OCP-based parametric CAD for Python).

Generate Python code to create this 3D model:

Construction Plan:
```json
{plan_json}
```

Identified Features:
```json
{features_json}
```

{error_context}

Requirements:
1. Use build123d import: `from build123d import *`
2. Use context managers: `with BuildPart() as model:`, `with BuildSketch() as sketch:`
3. Include proper parameter variables at the top
4. Add docstring explaining the model
5. Handle all features from the plan
6. Use Mode.SUBTRACT for cuts
7. Export the final part as `part = model.part`
8. No print statements or debug output

YAGNI: Only implement what's in the plan. No "future-proofing".

Generate only the Python code, no markdown formatting."""

        # Placeholder - actual LLM call would go here
        logger.debug("[CoderAgent] LLM code generation requested (using template fallback)")
        return self._generate_template_code(state, error_context)

    def _format_error_context(self, errors: List[Dict[str, Any]]) -> str:
        """Format geometric errors for inclusion in the prompt."""
        if not errors:
            return ""
        
        parts = ["\nPrevious iteration had these geometric errors - FIX THEM:\n"]
        
        for i, error in enumerate(errors, 1):
            desc = error.get("description", "Unknown error")
            location = error.get("location", "Unknown location")
            suggestion = error.get("suggestion", "")
            
            parts.append(f"{i}. {desc}")
            if location:
                parts.append(f"   Location: {location}")
            if suggestion:
                parts.append(f"   Fix: {suggestion}")
        
        return "\n".join(parts)


def create_coder_agent(llm_client: Optional[Any] = None) -> callable:
    """Factory function for creating Coder agent.

    Returns a function that can be used by the LangGraph orchestrator.

    Args:
        llm_client: Optional LLM client.

    Returns:
        Coder function: state -> code string.
    """
    agent = CoderAgent(llm_client=llm_client)
    
    def coder_fn(state: CADState) -> str:
        return agent.generate_code(state)
    
    return coder_fn