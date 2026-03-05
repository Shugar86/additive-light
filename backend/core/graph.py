"""LangGraph orchestrator for the CAD-Recode multi-agent system.

This module defines the state graph that coordinates all agents:
- Parallel sensor agents (X, Y, Z axis explorers)
- Coordinator/Planner agent
- Coder agent
- Validator agents
- VibeGuard judge
- Reflection loop for refinement

P4 Refactor: Patch-based orchestration with SwarmPolicy integration.
"""

import logging
from typing import Dict, Any, List, Callable, Optional
from functools import partial

try:
    from langgraph.graph import StateGraph, END
    from langgraph.constants import START
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    StateGraph = END = START = None  # type: ignore

from backend.core.state import CADState, Axis, SliceReport
from backend.core.spec_loader import get_spec_loader
from backend.core.agent_contracts import SwarmPolicy, SensorRegistry

logger = logging.getLogger(__name__)


def _create_sensor_node_function(sensor_id: str, sensor_agent_factory: Callable) -> Callable:
    """Create a sensor node function for a specific sensor ID.
    
    P5 Refactor: Dynamic sensor node creation based on SensorRegistry.
    
    Args:
        sensor_id: ID of the sensor (e.g., "X", "Y", "Z", or custom).
        sensor_agent_factory: Factory function to create sensor agents.
    
    Returns:
        Node function for the sensor.
    """
    def sensor_node(state: CADState) -> Dict[str, Any]:
        """Sensor node exploring along configured axis."""
        logger.info(f"[sensor_{sensor_id}_node] {sensor_id} sensor exploring")
        
        updates: Dict[str, Any] = {}
        
        if not state.aligned_mesh_path:
            logger.warning(f"[sensor_{sensor_id}_node] No aligned mesh available")
            return updates
        
        try:
            # Create agent using factory
            agent = sensor_agent_factory(sensor_id)
            if agent is None:
                logger.warning(f"[sensor_{sensor_id}_node] Could not create agent")
                return updates
            
            report = agent.analyze(state.aligned_mesh_path)
            
            # Merge with existing sensor reports
            new_reports = dict(state.sensor_reports)
            # Map sensor_id to appropriate Axis
            try:
                axis = Axis(sensor_id)
            except ValueError:
                axis = Axis.Z  # Default to Z for non-standard sensors
            new_reports[axis] = report
            updates["sensor_reports"] = new_reports
            
            logger.info(f"[sensor_{sensor_id}_node] {sensor_id} analysis complete: "
                       f"{len(report.features_by_slice)} slices")
        except Exception as e:
            logger.error(f"[sensor_{sensor_id}_node] {sensor_id} analysis failed: {e}")
        
        return updates
    
    # Set function name for better traceability
    sensor_node.__name__ = f"sensor_{sensor_id}_node"
    return sensor_node


def _get_sensor_registry(swarm_policy: SwarmPolicy) -> SensorRegistry:
    """Get sensor registry from policy or load default.
    
    Args:
        swarm_policy: SwarmPolicy with sensor configuration.
    
    Returns:
        SensorRegistry instance.
    """
    try:
        loader = get_spec_loader()
        registry = loader.load_sensor_registry()
        logger.info(f"[_get_sensor_registry] Loaded {len(registry.sensors)} sensors")
        return registry
    except Exception as e:
        logger.warning(f"[_get_sensor_registry] Could not load registry: {e}")
        # Return default with X/Y/Z
        from backend.core.agent_contracts import SensorSpec
        return SensorRegistry(
            sensors={
                "X": SensorSpec(sensor_id="X", sensor_type="axis_slice", axes=["X"]),
                "Y": SensorSpec(sensor_id="Y", sensor_type="axis_slice", axes=["Y"]),
                "Z": SensorSpec(sensor_id="Z", sensor_type="axis_slice", axes=["Z"]),
            },
            default_sensors=["X", "Y", "Z"]
        )


def create_cad_recode_graph(
    sensor_agent_factory: Callable,
    coordinator_agent: Callable,
    coder_agent: Callable,
    validator_agent: Callable,
    executor_agent: Callable,
    vibeguard_agent: Callable,
    swarm_policy: Optional[SwarmPolicy] = None
) -> Any:
    """Create the complete LangGraph for CAD reverse engineering.

    Args:
        sensor_agent_factory: Function that creates a sensor agent for an axis.
        coordinator_agent: Coordinator/Planner agent function.
        coder_agent: Code generation agent function.
        validator_agent: AST/Safety validation agent function.
        executor_agent: Secure code execution agent function.
        vibeguard_agent: Geometric comparison judge agent function.
        swarm_policy: Optional SwarmPolicy for policy-driven decisions.

    Returns:
        Compiled LangGraph ready for execution.

    Raises:
        RuntimeError: If LangGraph is not installed.
    """
    if not HAS_LANGGRAPH:
        raise RuntimeError("LangGraph is not installed. Run: pip install langgraph")

    # Load swarm policy if not provided
    if swarm_policy is None:
        try:
            loader = get_spec_loader()
            swarm_policy = loader.load_swarm_policy()
            logger.info("[create_cad_recode_graph] Loaded swarm policy")
        except Exception as e:
            logger.warning(f"[create_cad_recode_graph] Could not load swarm policy: {e}")
            swarm_policy = SwarmPolicy()  # Use defaults

    # Initialize the graph with our state type
    workflow = StateGraph(CADState)

    # Define node functions
    def align_mesh_node(state: CADState) -> Dict[str, Any]:
        """Initial node: align and center the input mesh.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[align_mesh_node] Aligning input mesh")
        
        updates: Dict[str, Any] = {}
        
        try:
            from backend.sensors.align_open3d import load_and_center_mesh
            
            if not state.stl_path:
                raise ValueError("No STL path provided in state")
            
            aligned_path, centroid, axes = load_and_center_mesh(state.stl_path)
            updates["aligned_mesh_path"] = aligned_path
            
            logger.info(f"[align_mesh_node] Mesh aligned: {aligned_path}")
            
        except Exception as e:
            logger.error(f"[align_mesh_node] Alignment failed: {e}")
            updates["validation_errors"] = state.validation_errors + [f"Mesh alignment failed: {e}"]
        
        return updates

    def sensor_x_node(state: CADState) -> Dict[str, Any]:
        """Sensor agent exploring X-axis.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[sensor_x_node] X-axis sensor exploring")
        
        updates: Dict[str, Any] = {}
        
        if not state.aligned_mesh_path:
            logger.warning("[sensor_x_node] No aligned mesh available")
            return updates
        
        try:
            agent = sensor_agent_factory(Axis.X)
            report = agent.analyze(state.aligned_mesh_path)
            
            # Merge with existing sensor reports
            new_reports = dict(state.sensor_reports)
            new_reports[Axis.X] = report
            updates["sensor_reports"] = new_reports
            
            logger.info(f"[sensor_x_node] X-axis analysis complete: {len(report.features_by_slice)} slices")
        except Exception as e:
            logger.error(f"[sensor_x_node] X-axis analysis failed: {e}")
        
        return updates

    def sensor_y_node(state: CADState) -> Dict[str, Any]:
        """Sensor agent exploring Y-axis.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[sensor_y_node] Y-axis sensor exploring")
        
        updates: Dict[str, Any] = {}
        
        if not state.aligned_mesh_path:
            logger.warning("[sensor_y_node] No aligned mesh available")
            return updates
        
        try:
            agent = sensor_agent_factory(Axis.Y)
            report = agent.analyze(state.aligned_mesh_path)
            
            # Merge with existing sensor reports
            new_reports = dict(state.sensor_reports)
            new_reports[Axis.Y] = report
            updates["sensor_reports"] = new_reports
            
            logger.info(f"[sensor_y_node] Y-axis analysis complete: {len(report.features_by_slice)} slices")
        except Exception as e:
            logger.error(f"[sensor_y_node] Y-axis analysis failed: {e}")
        
        return updates

    def sensor_z_node(state: CADState) -> Dict[str, Any]:
        """Sensor agent exploring Z-axis.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[sensor_z_node] Z-axis sensor exploring")
        
        updates: Dict[str, Any] = {}
        
        if not state.aligned_mesh_path:
            logger.warning("[sensor_z_node] No aligned mesh available")
            return updates
        
        try:
            agent = sensor_agent_factory(Axis.Z)
            report = agent.analyze(state.aligned_mesh_path)
            
            # Merge with existing sensor reports
            new_reports = dict(state.sensor_reports)
            new_reports[Axis.Z] = report
            updates["sensor_reports"] = new_reports
            
            logger.info(f"[sensor_z_node] Z-axis analysis complete: {len(report.features_by_slice)} slices")
        except Exception as e:
            logger.error(f"[sensor_z_node] Z-axis analysis failed: {e}")
        
        return updates

    def coordinator_node(state: CADState) -> Dict[str, Any]:
        """Coordinator agent: aggregate sensor data and plan construction.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[coordinator_node] Coordinator analyzing sensor reports")
        
        updates: Dict[str, Any] = {}
        
        if not state.sensor_reports:
            logger.warning("[coordinator_node] No sensor reports available")
            return updates
        
        try:
            result = coordinator_agent(state)
            updates["identified_features"] = result.get("features", [])
            updates["construction_plan"] = result.get("plan", [])
            logger.info(f"[coordinator_node] Plan created: {len(updates.get('construction_plan', []))} steps")
        except Exception as e:
            logger.error(f"[coordinator_node] Planning failed: {e}")
        
        return updates

    def coder_node(state: CADState) -> Dict[str, Any]:
        """Coder agent: generate build123d code from plan.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[coder_node] Generating CAD code")
        
        updates: Dict[str, Any] = {}
        
        if not state.construction_plan:
            logger.warning("[coder_node] No construction plan available")
            return updates
        
        try:
            code = coder_agent(state)
            updates["generated_code"] = code
            logger.info(f"[coder_node] Code generated: {len(code)} characters")
        except Exception as e:
            logger.error(f"[coder_node] Code generation failed: {e}")
        
        return updates

    def validator_node(state: CADState) -> Dict[str, Any]:
        """Validator agent: check code safety and syntax.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[validator_node] Validating generated code")
        
        updates: Dict[str, Any] = {}
        
        if not state.generated_code:
            logger.warning("[validator_node] No code to validate")
            return updates
        
        try:
            errors = validator_agent(state.generated_code)
            updates["validation_errors"] = errors
            
            if errors:
                logger.warning(f"[validator_node] Validation found {len(errors)} issues")
            else:
                logger.info("[validator_node] Code validation passed")
        except Exception as e:
            logger.error(f"[validator_node] Validation error: {e}")
            updates["validation_errors"] = state.validation_errors + [f"Validator exception: {e}"]
        
        return updates

    def executor_node(state: CADState) -> Dict[str, Any]:
        """Executor agent: run the generated code and produce output.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[executor_node] Executing CAD code")
        
        updates: Dict[str, Any] = {}
        
        if state.validation_errors:
            logger.warning("[executor_node] Skipping execution due to validation errors")
            return updates
        
        if not state.generated_code:
            logger.warning("[executor_node] No code to execute")
            return updates
        
        try:
            result = executor_agent(state)
            updates["final_mesh_path"] = result.get("output_path")
            
            if result.get("error"):
                updates["execution_errors"] = state.execution_errors + [result["error"]]
                logger.error(f"[executor_node] Execution failed: {result['error']}")
            else:
                logger.info(f"[executor_node] Execution successful: {result.get('output_path')}")
        except Exception as e:
            logger.error(f"[executor_node] Execution exception: {e}")
            updates["execution_errors"] = state.execution_errors + [f"Executor exception: {e}"]
        
        return updates

    def vibeguard_node(state: CADState) -> Dict[str, Any]:
        """VibeGuard agent: compare generated mesh with original.
        
        Returns:
            Patch dict with updates to apply to state.
        """
        logger.info("[vibeguard_node] Comparing meshes with VibeGuard")
        
        updates: Dict[str, Any] = {}
        
        if not state.final_mesh_path or not state.stl_path:
            logger.warning("[vibeguard_node] Missing mesh paths for comparison")
            return updates
        
        try:
            result = vibeguard_agent(state)
            
            updates["chamfer_distance"] = result.get("chamfer_distance")
            updates["hausdorff_distance"] = result.get("hausdorff_distance")
            
            if result.get("errors"):
                updates["geometric_errors"] = result["errors"]
                logger.warning(f"[vibeguard_node] Found {len(result['errors'])} geometric errors")
            else:
                logger.info("[vibeguard_node] Geometric validation passed")
                
            # Store final output if successful
            chamfer = result.get("chamfer_distance")
            if not result.get("errors") and chamfer is not None:
                if chamfer < swarm_policy.chamfer_tolerance:
                    updates["final_output"] = state.generated_code
        except Exception as e:
            logger.error(f"[vibeguard_node] VibeGuard error: {e}")
        
        return updates

    # P5 Refactor: Dynamic sensor node creation from SensorRegistry
    # Get sensor registry (from policy or default)
    sensor_registry = _get_sensor_registry(swarm_policy)
    
    # Determine which sensors to use
    if swarm_policy.enable_parallel_sensors:
        active_sensor_ids = sensor_registry.default_sensors
    else:
        # Sequential mode - use only first sensor
        active_sensor_ids = sensor_registry.default_sensors[:1] if sensor_registry.default_sensors else ["Z"]
    
    logger.info(f"[create_cad_recode_graph] Configuring {len(active_sensor_ids)} sensors: {active_sensor_ids}")
    
    # Add nodes to graph
    workflow.add_node("align_mesh", align_mesh_node)
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("vibeguard", vibeguard_node)
    
    # Add dynamic sensor nodes
    sensor_nodes = []
    for sensor_id in active_sensor_ids:
        node_name = f"sensor_{sensor_id.lower()}"
        node_func = _create_sensor_node_function(sensor_id, sensor_agent_factory)
        workflow.add_node(node_name, node_func)
        sensor_nodes.append(node_name)
        logger.debug(f"[create_cad_recode_graph] Added sensor node: {node_name}")

    # Define edges
    workflow.add_edge(START, "align_mesh")
    
    # Connect align_mesh to all sensor nodes
    for node_name in sensor_nodes:
        workflow.add_edge("align_mesh", node_name)
    
    # Parallel sensors -> coordinator (all must complete)
    for node_name in sensor_nodes:
        workflow.add_edge(node_name, "coordinator")
    
    # Coordinator -> Coder -> Validator -> Executor -> VibeGuard
    workflow.add_edge("coordinator", "coder")
    workflow.add_edge("coder", "validator")
    workflow.add_edge("validator", "executor")
    workflow.add_edge("executor", "vibeguard")
    
    # Conditional edge: VibeGuard -> END or back to Coder (reflection)
    def reflection_router(state: CADState) -> str:
        """Policy-driven reflection router.
        
        Uses SwarmPolicy to determine routing decisions:
        - Success criteria based on policy tolerances
        - Max iterations from policy
        - Failure policy for error handling
        """
        state.iteration_count += 1
        
        logger.info(f"[reflection_router] Iteration {state.iteration_count}/{swarm_policy.max_iterations}")
        
        # Check success criteria using policy tolerances
        chamfer_ok = (state.chamfer_distance is None or 
                      state.chamfer_distance < swarm_policy.chamfer_tolerance)
        hausdorff_ok = (state.hausdorff_distance is None or 
                        state.hausdorff_distance < swarm_policy.hausdorff_tolerance)
        no_geometric_errors = not state.geometric_errors
        has_output = state.final_output is not None
        
        # Success case: all criteria met
        if has_output and no_geometric_errors and chamfer_ok and hausdorff_ok:
            logger.info(f"[reflection_router] Success after {state.iteration_count} iterations")
            return END
        
        # Max iterations reached - check policy
        if state.iteration_count >= swarm_policy.max_iterations:
            logger.warning(f"[reflection_router] Max iterations ({swarm_policy.max_iterations}) reached")
            
            # Apply failure policy
            if swarm_policy.default_failure_policy.on_validation_error == "fail":
                logger.error("[reflection_router] Aborting due to failure policy")
                return END
            elif swarm_policy.enable_reflection:
                logger.info("[reflection_router] One final attempt with reflection")
                return "coder"
            else:
                return END
        
        # Check if reflection is enabled in policy
        if not swarm_policy.enable_reflection:
            logger.warning("[reflection_router] Reflection disabled in policy, ending")
            return END
        
        # Need refinement
        logger.info(f"[reflection_router] Geometric errors: {len(state.geometric_errors)}, "
                     f"Chamfer: {state.chamfer_distance}, Hausdorff: {state.hausdorff_distance}")
        logger.info(f"[reflection_router] Routing to coder for refinement")
        return "coder"
    
    workflow.add_conditional_edges(
        "vibeguard",
        reflection_router,
        {
            "coder": "coder",
            END: END
        }
    )

    # Compile the graph
    compiled_graph = workflow.compile()
    logger.info("[create_cad_recode_graph] Graph compiled successfully")
    
    return compiled_graph


def run_cad_recode(
    stl_path: str,
    agent_factories: Dict[str, Callable],
    max_iterations: int = 3,
    swarm_policy: Optional[SwarmPolicy] = None
) -> CADState:
    """Run the complete CAD-Recode pipeline on an STL file.

    Args:
        stl_path: Path to input STL file.
        agent_factories: Dictionary mapping agent names to factory functions.
            Required keys: 'sensor', 'coordinator', 'coder', 'validator', 
                          'executor', 'vibeguard'
        max_iterations: Maximum refinement iterations (overrides policy if set).
        swarm_policy: Optional SwarmPolicy configuration.

    Returns:
        Final CADState with results.

    Raises:
        RuntimeError: If LangGraph not available or pipeline fails.
    """
    if not HAS_LANGGRAPH:
        raise RuntimeError("LangGraph is not installed")

    # Load swarm policy if not provided
    if swarm_policy is None:
        try:
            loader = get_spec_loader()
            swarm_policy = loader.load_swarm_policy()
        except Exception as e:
            logger.warning(f"[run_cad_recode] Could not load swarm policy: {e}")
            swarm_policy = SwarmPolicy()
    
    # Override max_iterations if explicitly provided
    if max_iterations != 3:  # Default value was changed
        swarm_policy.max_iterations = max_iterations

    # Create the graph with policy
    graph = create_cad_recode_graph(
        sensor_agent_factory=agent_factories['sensor'],
        coordinator_agent=agent_factories['coordinator'],
        coder_agent=agent_factories['coder'],
        validator_agent=agent_factories['validator'],
        executor_agent=agent_factories['executor'],
        vibeguard_agent=agent_factories['vibeguard'],
        swarm_policy=swarm_policy
    )

    # Initialize state
    initial_state = CADState(
        stl_path=stl_path,
        max_iterations=swarm_policy.max_iterations
    )

    # Run the graph
    logger.info(f"[run_cad_recode] Starting pipeline for {stl_path} "
                 f"(max_iterations={swarm_policy.max_iterations})")
    
    try:
        final_state = graph.invoke(initial_state)
        logger.info("[run_cad_recode] Pipeline complete")
        return final_state
    except Exception as e:
        logger.error(f"[run_cad_recode] Pipeline failed: {e}")
        raise RuntimeError(f"CAD-Recode pipeline failed: {e}") from e