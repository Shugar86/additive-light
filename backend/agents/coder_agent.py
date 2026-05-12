"""Coder agent for generating parametric CAD code using build123d.

The Coder receives a construction plan from the Coordinator and translates it
into executable Python code using the build123d library (OCP-based parametric CAD).
"""

import logging
import json
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.core.state import CADState, BuildStep, Feature3D, ShaftConstructionPlan
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

    # =============================================================================
    # Shaft MVP: Revolve-based code generation
    # =============================================================================

    def generate_shaft_code(self, state: CADState, output_dir: Optional[str] = None) -> str:
        """Generate build123d code using revolve approach for shafts.
        
        This uses the shaft_construction_plan to generate a revolve-based
        parametric model with proper feature operations.
        
        Args:
            state: CAD state with shaft_construction_plan.
            output_dir: Optional directory for output files.
        
        Returns:
            Python code string using build123d.
        
        Raises:
            ValueError: If no shaft_construction_plan is available.
        """
        if not state.shaft_construction_plan:
            raise ValueError("No shaft construction plan available")
        
        plan = state.shaft_construction_plan
        
        logger.info(f"[CoderAgent] Generating shaft code: {len(plan.segments)} segments, "
                   f"{len(plan.features)} features")
        
        try:
            code = self._generate_shaft_revolve_code(plan, output_dir)
            logger.info(f"[CoderAgent] Generated {len(code)} characters of shaft code")
            return code
        except Exception as e:
            logger.error(f"[CoderAgent] Shaft code generation failed: {e}")
            raise RuntimeError(f"Shaft code generation failed: {e}") from e
    
    def _generate_shaft_revolve_code(
        self,
        plan: ShaftConstructionPlan,
        output_dir: Optional[str] = None
    ) -> str:
        """Generate revolve-based build123d code for a shaft.

        Produces a valid build123d script that:
          1. Builds a closed profile Polyline in Plane.XZ (x = radius, z = height).
          2. Fills it with make_face().
          3. Revolves around Axis.Z to create the solid.
          4. Applies local feature cuts (keyways, holes, etc.).
          5. Exports STEP and STL.

        The generated code has no LLM dependency — it is a deterministic template.
        """
        out_dir_str = output_dir or "output"

        lines: List[str] = [
            '"""Generated parametric shaft model using build123d."""',
            "",
            "# export_step/export_stl are included in build123d's public star-import.",
            "from build123d import *",
            "import pathlib",
            "",
            "# ── Parameters ──────────────────────────────────────────────",
            f"shaft_length = {plan.base_axis.length:.6f}",
        ]

        for i, zone in enumerate(plan.segments):
            lines.append(f"zone{i}_radius = {zone.mean_radius:.6f}")
            lines.append(
                f"zone{i}_length = {zone.end_pos - zone.start_pos:.6f}"
            )

        for i, feat in enumerate(plan.features):
            for key, val in feat.dimensions.items():
                lines.append(f"feature{i}_{key} = {val:.6f}")

        # ── Profile polyline points ────────────────────────────────────
        profile_pts = _build_revolve_polyline(plan)
        pts_repr = ", ".join(f"({r:.6f}, {z:.6f})" for r, z in profile_pts)

        lines.extend([
            "",
            "# ── Build shaft solid ───────────────────────────────────────",
            "with BuildPart() as shaft_part:",
            "    with BuildSketch(Plane.XZ):",
            "        with BuildLine():",
            f"            Polyline({pts_repr}, close=True)",
            "        make_face()",
            "    revolve(axis=Axis.Z)",
        ])

        # ── Local feature cuts ─────────────────────────────────────────
        for i, feature in enumerate(plan.features):
            lines.extend(self._generate_feature_cut(feature, i, "    "))

        lines.extend([
            "",
            "# ── Export ──────────────────────────────────────────────────",
            "part = shaft_part.part",
            f"_out = pathlib.Path('{out_dir_str}')",
            "_out.mkdir(parents=True, exist_ok=True)",
            "export_step(part, str(_out / 'shaft.step'))",
            "export_stl(part, str(_out / 'shaft_preview.stl'))",
            "",
            "if __name__ == '__main__':",
            "    print(f'Generated shaft: {part.volume:.4f} mm^3')",
        ])

        return "\n".join(lines)
    
    def _generate_feature_cut(
        self,
        feature: Any,
        index: int,
        indent: str
    ) -> List[str]:
        """Generate code for cutting a local feature."""
        lines = []
        ftype = feature.feature_type.value
        
        pos = feature.position
        dims = feature.dimensions
        
        if ftype == "keyway":
            width = dims.get("width", 2.0)
            depth = dims.get("depth", 2.0)
            length = dims.get("length", 10.0)
            
            lines.append(f"{indent}# Keyway cut {index}")
            lines.append(f"{indent}with Locations(({pos[0]:.4f}, {pos[1]:.4f})):")
            lines.append(f"{indent}    with BuildSketch() as keyway_{index}:")
            lines.append(f"{indent}        Rectangle(width={width:.4f}, height={depth:.4f})")
            lines.append(f"{indent}    extrude(amount={length:.4f}, mode=Mode.SUBTRACT)")
        
        elif ftype == "flat":
            depth = dims.get("depth", 1.0)
            width = dims.get("width", 10.0)
            length = dims.get("length", 10.0)
            
            lines.append(f"{indent}# Flat cut {index}")
            lines.append(f"{indent}with Locations(({pos[0]:.4f}, {pos[1]:.4f})):")
            lines.append(f"{indent}    with BuildSketch() as flat_{index}:")
            lines.append(f"{indent}        Rectangle(width={width:.4f}, height={depth:.4f})")
            lines.append(f"{indent}    extrude(amount={length:.4f}, mode=Mode.SUBTRACT)")
        
        elif ftype == "cross_hole":
            diameter = dims.get("diameter", 2.0)
            
            lines.append(f"{indent}# Cross hole {index}")
            lines.append(f"{indent}with Locations(({pos[0]:.4f}, {pos[1]:.4f})):")
            lines.append(f"{indent}    with BuildSketch() as hole_{index}:")
            lines.append(f"{indent}        Circle(radius={diameter/2:.4f})")
            lines.append(f"{indent}    extrude(amount={diameter*3:.4f}, mode=Mode.SUBTRACT)")
        
        return lines


def _arc_polyline_points(
    center_r: float,
    center_z: float,
    arc_radius: float,
    start_pos: float,
    end_pos: float,
    start_radius: float,
    end_radius: float,
    n: int = 16,
) -> List[Tuple[float, float]]:
    """Sample ``n`` points on the fitted arc, returned as (radius, z) pairs.

    The arc is parameterised by its centre ``(center_r, center_z)`` in
    profile space and its radius. The two end-points ``(start_radius,
    start_pos)`` and ``(end_radius, end_pos)`` come from the zone spec and
    pin down the angular extent. This is the Sprint 2.4 deterministic
    replacement for the previous linear FILLET / CHAMFER polyline.
    """
    n = max(2, int(n))
    a0 = math.atan2(start_pos - center_z, start_radius - center_r)
    a1 = math.atan2(end_pos - center_z, end_radius - center_r)
    # Pick the shorter angular path around the circle.
    delta = a1 - a0
    if delta > math.pi:
        delta -= 2 * math.pi
    elif delta < -math.pi:
        delta += 2 * math.pi
    pts: List[Tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        ang = a0 + delta * t
        r = center_r + arc_radius * math.cos(ang)
        z = center_z + arc_radius * math.sin(ang)
        pts.append((float(r), float(z)))
    return pts


def _build_revolve_polyline(
    plan: "ShaftConstructionPlan",
    *,
    arc_samples: int = 16,
) -> list:
    """Build ordered (radius, z) points for the Polyline revolve profile.

    The polyline traces the outer boundary of the shaft cross-section in the
    XZ plane from bottom to top, then returns along the revolution axis
    (radius = 0) to form a closed profile suitable for revolve().

    Sprint 2.4: FILLET / CHAMFER zones that carry fitted-arc parameters
    (``arc_center_z``, ``arc_center_r``, ``arc_radius``) are discretised
    along the actual arc instead of approximated with a straight chord.
    The chord behaviour stays as a fallback when the arc parameters are
    absent (legacy zones, non-arc fits) so existing reports keep producing
    the same STEP geometry they did before.

    Args:
        plan: ShaftConstructionPlan with sorted segments.
        arc_samples: Number of polyline samples per fitted arc (default 16).
            Increase for tighter tolerance on small radii; decrease for
            faster build123d execution.

    Returns:
        List of (radius, z_position) tuples in CCW order.
    """
    from backend.core.state import ShaftZoneType

    sorted_segs = sorted(plan.segments, key=lambda s: s.start_pos)

    outer: list = []
    for seg in sorted_segs:
        if seg.zone_type in (ShaftZoneType.CYLINDER, ShaftZoneType.STEP):
            outer.append((seg.mean_radius, seg.start_pos))
            outer.append((seg.mean_radius, seg.end_pos))
        elif seg.zone_type == ShaftZoneType.CONE:
            outer.append((seg.start_radius, seg.start_pos))
            outer.append((seg.end_radius, seg.end_pos))
        elif seg.zone_type in (ShaftZoneType.FILLET, ShaftZoneType.CHAMFER):
            arc_radius = getattr(seg, "arc_radius", None)
            center_z = getattr(seg, "arc_center_z", None)
            center_r = getattr(seg, "arc_center_r", None)
            if (
                arc_radius is not None
                and center_z is not None
                and center_r is not None
                and arc_radius > 1e-6
            ):
                # Adaptive sample count: aim for a polyline step around
                # 0.5 mm along the arc length. ``arc_samples`` becomes a
                # floor — short fillets still get 16 samples, long barrel
                # arcs get tens of points so build123d ``make_face`` can
                # close the wire cleanly.
                arc_len = arc_radius * (
                    abs(seg.end_pos - seg.start_pos) / max(arc_radius, 1e-6)
                )
                n_adaptive = max(arc_samples, int(arc_len / 0.5) + 1)
                # Cap to keep STEP generation fast.
                n_adaptive = min(n_adaptive, 256)
                outer.extend(
                    _arc_polyline_points(
                        center_r=float(center_r),
                        center_z=float(center_z),
                        arc_radius=float(arc_radius),
                        start_pos=float(seg.start_pos),
                        end_pos=float(seg.end_pos),
                        start_radius=float(seg.start_radius),
                        end_radius=float(seg.end_radius),
                        n=n_adaptive,
                    )
                )
            else:
                # Legacy / no-fit fallback: linear chord between endpoints.
                outer.append((seg.start_radius, seg.start_pos))
                outer.append((seg.end_radius, seg.end_pos))
        elif seg.zone_type == ShaftZoneType.GROOVE:
            eps = max(0.05, (seg.end_pos - seg.start_pos) * 0.1)
            outer.append((seg.start_radius, seg.start_pos))
            outer.append((seg.mean_radius, seg.start_pos + eps))
            outer.append((seg.mean_radius, seg.end_pos - eps))
            outer.append((seg.end_radius, seg.end_pos))

    if not outer:
        return []

    # Deduplicate consecutive identical points
    deduped: list = [outer[0]]
    for pt in outer[1:]:
        if abs(pt[0] - deduped[-1][0]) > 1e-6 or abs(pt[1] - deduped[-1][1]) > 1e-6:
            deduped.append(pt)

    z_top = deduped[-1][1]
    z_bot = deduped[0][1]
    # Close through axis: top → axis top → axis bottom (→ polyline close returns to outer[0])
    all_pts = deduped + [(0.0, z_top), (0.0, z_bot)]
    return all_pts


def create_coder_agent(
    llm_client: Optional[Any] = None,
    part_type: str = "generic"
) -> callable:
    """Factory function for creating Coder agent.

    Returns a function that can be used by the LangGraph orchestrator.

    Args:
        llm_client: Optional LLM client.
        part_type: Type of part ("generic" or "shaft").

    Returns:
        Coder function: state -> code string.
    """
    agent = CoderAgent(llm_client=llm_client)
    
    def coder_fn(state: CADState) -> str:
        if part_type == "shaft" and state.shaft_construction_plan:
            return agent.generate_shaft_code(state)
        else:
            return agent.generate_code(state)
    
    return coder_fn