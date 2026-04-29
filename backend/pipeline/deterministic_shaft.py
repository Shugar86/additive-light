"""Standalone deterministic reverse engineering pipeline for shaft-like parts.

Converts an STL mesh into a parametric STEP file without any LLM dependency.
The full pipeline is:

    STL → align → detect_axis → align_to_Z → sample_profile →
    segment_zones → fit_primitives → ShaftConstructionPlan →
    generate_revolve_code → execute_build123d → STEP

Usage (CLI)::

    python -m backend.pipeline.deterministic_shaft path/to/shaft.stl -o output/

Usage (API)::

    from backend.pipeline.deterministic_shaft import run_deterministic_pipeline

    result = run_deterministic_pipeline("shaft.stl", output_dir="out/")
    if result.success:
        print("STEP:", result.output_step_path)
        print("Confidence:", result.construction_plan.confidence)
"""

import json
import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class DeterministicResult:
    """Container for all outputs and metadata of the deterministic pipeline.

    Attributes:
        stl_path: Path to the input STL file.
        success: True when a STEP file was successfully generated.
        axis_info: Detected rotation axis (AxisInfo from shaft_axis).
        profile: Sampled radial profile (ShaftProfile from shaft_profile).
        zones: List of detected shaft zones (ShaftZone).
        zone_fits: List of (ShaftZone, FitResult) primitive fits.
        construction_plan: Structured plan (ShaftConstructionPlan from state).
        generated_code: build123d Python script as a string.
        output_step_path: Path to the exported STEP file (if successful).
        output_stl_path: Path to the preview STL file (if successful).
        report: Quality / metadata report dictionary.
        errors: Non-fatal warnings and errors collected during the run.
        duration_s: Wall-clock time for the full pipeline.
    """

    stl_path: str
    success: bool = False

    # Intermediate products
    axis_info: Optional[Any] = None      # AxisInfo
    profile: Optional[Any] = None        # ShaftProfile
    zones: Optional[List[Any]] = None    # List[ShaftZone]
    zone_fits: Optional[List[Any]] = None  # List[Tuple[ShaftZone, FitResult]]
    construction_plan: Optional[Any] = None  # ShaftConstructionPlan

    # Output artefacts
    generated_code: str = ""
    output_step_path: Optional[str] = None
    output_stl_path: Optional[str] = None

    # Quality metadata
    report: Dict[str, Any] = field(default_factory=dict)

    # Execution metadata
    errors: List[str] = field(default_factory=list)
    duration_s: float = 0.0

    def to_report_dict(self) -> Dict[str, Any]:
        """Serialise result to a JSON-compatible dictionary.

        Returns:
            Dictionary with all pipeline metadata and quality metrics.
        """
        axis_dict: Dict[str, Any] = {}
        if self.axis_info is not None:
            try:
                axis_dict = self.axis_info.to_dict()
            except Exception:
                pass

        zones_list: List[Dict[str, Any]] = []
        if self.zones:
            for z in self.zones:
                try:
                    zones_list.append(z.to_dict())
                except Exception:
                    pass

        fits_list: List[Dict[str, Any]] = []
        if self.zone_fits:
            for zone, fit in self.zone_fits:
                fits_list.append(
                    {
                        "zone_type": getattr(zone.zone_type, "value", str(zone.zone_type)),
                        "start_pos": zone.start_pos,
                        "end_pos": zone.end_pos,
                        "fit_primitive": fit.primitive_type,
                        "fit_residual_rms": fit.residual_rms,
                        "fit_confidence": fit.confidence,
                        "fit_params": fit.params,
                    }
                )

        plan_dict: Dict[str, Any] = {}
        if self.construction_plan is not None:
            try:
                plan_dict = self.construction_plan.to_dict()
            except Exception:
                pass

        return {
            "stl_path": self.stl_path,
            "success": self.success,
            "duration_s": self.duration_s,
            "axis": axis_dict,
            "zones": zones_list,
            "zone_fits": fits_list,
            "construction_plan": plan_dict,
            "output_step_path": self.output_step_path,
            "output_stl_path": self.output_stl_path,
            "errors": self.errors,
            **self.report,
        }


# ---------------------------------------------------------------------------
# Zone → ShaftZoneSpec conversion
# ---------------------------------------------------------------------------


def _zones_to_specs(
    zones: List[Any],
) -> List[Any]:
    """Convert ShaftZone list to ShaftZoneSpec list for ShaftConstructionPlan.

    Args:
        zones: List of ShaftZone objects from shaft_profile.

    Returns:
        List of ShaftZoneSpec Pydantic models.
    """
    from backend.core.state import ShaftZoneSpec, ShaftZoneType
    from backend.sensors.shaft_profile import ZoneType as SensorZoneType

    # Mapping from sensor ZoneType to plan ShaftZoneType
    _TYPE_MAP = {
        SensorZoneType.CYLINDER: ShaftZoneType.CYLINDER,
        SensorZoneType.CONE: ShaftZoneType.CONE,
        SensorZoneType.FILLET: ShaftZoneType.FILLET,
        SensorZoneType.CHAMFER: ShaftZoneType.CHAMFER,
        SensorZoneType.GROOVE: ShaftZoneType.GROOVE,
        SensorZoneType.STEP: ShaftZoneType.STEP,
        SensorZoneType.END: ShaftZoneType.STEP,  # map END → STEP as closest
    }

    specs = []
    for z in zones:
        plan_type = _TYPE_MAP.get(z.zone_type, ShaftZoneType.CYLINDER)
        spec = ShaftZoneSpec(
            zone_type=plan_type,
            start_pos=float(z.start_pos),
            end_pos=float(z.end_pos),
            start_radius=float(z.start_radius),
            end_radius=float(z.end_radius),
            mean_radius=float(z.mean_radius),
            confidence=float(z.confidence),
        )
        specs.append(spec)
    return specs


# ---------------------------------------------------------------------------
# Build123d execution
# ---------------------------------------------------------------------------


def _execute_build123d_code(
    code: str,
    output_dir: Path,
    timeout_s: float = 120.0,
) -> Dict[str, Any]:
    """Execute build123d code in a subprocess and collect outputs.

    Writes the code to a temp file then runs it with the current Python
    interpreter.  Waits up to *timeout_s* seconds.

    Args:
        code: build123d Python script source.
        output_dir: Directory that the script will write outputs to.
        timeout_s: Maximum execution time in seconds.

    Returns:
        Dictionary with keys: "success", "stdout", "stderr", "error".
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(output_dir),
        )
        if proc.returncode == 0:
            return {
                "success": True,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "error": None,
            }
        else:
            return {
                "success": False,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "error": f"Process exited with code {proc.returncode}: {proc.stderr[:500]}",
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": f"Execution timed out after {timeout_s}s",
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_deterministic_pipeline(
    stl_path: str,
    output_dir: Optional[str] = None,
    *,
    num_profile_samples: int = 100,
    axis_method: str = "auto",
    execute_build123d: bool = True,
    execution_timeout_s: float = 120.0,
) -> DeterministicResult:
    """Run the complete deterministic reverse engineering pipeline.

    No LLM is required at any stage.  The pipeline is:
      align → axis detect → profile sample → zone segment →
      primitive fit → plan build → code generate → build123d execute

    Args:
        stl_path: Path to the input STL mesh.
        output_dir: Directory for output artefacts.  Defaults to a sibling
            directory named after the stem of *stl_path*.
        num_profile_samples: Number of cross-sections to sample along the
            rotation axis.
        axis_method: Axis detection method — "auto", "symmetry", "slices",
            or "inertia".
        execute_build123d: Whether to execute the generated build123d script
            and produce STEP/STL output.
        execution_timeout_s: Timeout for build123d execution in seconds.

    Returns:
        DeterministicResult with all intermediates and output artefacts.

    Example:
        >>> r = run_deterministic_pipeline("shaft.stl", output_dir="out/")
        >>> print(r.success, r.output_step_path)
    """
    stl_file = Path(stl_path)
    if output_dir is None:
        output_dir = str(stl_file.parent / f"{stl_file.stem}_reng_output")

    # Resolved absolute path so generated export_step(..., cwd=output_dir) writes here,
    # not under nested duplicate paths like ./temp/det_step_run/... inside cwd.
    out_path = Path(output_dir).resolve()
    result = DeterministicResult(stl_path=str(stl_file.absolute()))
    t_start = time.perf_counter()

    if not stl_file.exists():
        result.errors.append(f"STL file not found: {stl_path}")
        result.duration_s = time.perf_counter() - t_start
        return result

    logger.info("[deterministic_pipeline] Starting: %s", stl_path)

    # ── 1. Align and center mesh ────────────────────────────────────────────
    aligned_path: Optional[str] = None
    try:
        from backend.sensors.align_open3d import load_and_center_mesh

        aligned_path_raw, centroid, axes, meta = load_and_center_mesh(
            str(stl_file), output_path=None
        )
        aligned_path = aligned_path_raw
        logger.info("[deterministic_pipeline] Aligned mesh: %s", aligned_path)
    except Exception as exc:
        result.errors.append(f"Alignment failed: {exc}")
        aligned_path = str(stl_file)  # fall through with original

    working_path = aligned_path or str(stl_file)

    # ── 2. Detect rotation axis ─────────────────────────────────────────────
    try:
        from backend.sensors.shaft_axis import (
            align_mesh_to_axis,
            detect_main_axis,
        )

        axis_info = detect_main_axis(working_path, method=axis_method)
        result.axis_info = axis_info
        logger.info(
            "[deterministic_pipeline] Axis detected: dir=%s conf=%.3f method=%s",
            axis_info.direction,
            axis_info.confidence,
            axis_info.method,
        )

        # Align mesh so rotation axis → world Z for consistent profiling
        axis_aligned_path, _ = align_mesh_to_axis(working_path)
        working_path = axis_aligned_path
        logger.info("[deterministic_pipeline] Axis-aligned mesh: %s", working_path)

    except Exception as exc:
        result.errors.append(f"Axis detection failed: {exc}")
        logger.warning("[deterministic_pipeline] Axis detection: %s", exc)

    # ── 3. Sample radial profile ────────────────────────────────────────────
    try:
        from backend.sensors.shaft_profile import (
            sample_radial_profile,
            segment_rotational_zones,
        )

        profile = sample_radial_profile(
            working_path, axis="Z", num_samples=num_profile_samples
        )
        result.profile = profile
        logger.info(
            "[deterministic_pipeline] Profile: length=%.2fmm r=[%.2f, %.2f]mm n=%d",
            profile.total_length,
            profile.min_radius,
            profile.max_radius,
            profile.sample_count,
        )
    except Exception as exc:
        result.errors.append(f"Profile sampling failed: {exc}")
        result.duration_s = time.perf_counter() - t_start
        return result

    # ── 4. Segment zones ────────────────────────────────────────────────────
    try:
        zones = segment_rotational_zones(profile)
        result.zones = zones
        logger.info(
            "[deterministic_pipeline] Zones: %d → %s",
            len(zones),
            [z.zone_type.value for z in zones],
        )
        if not zones:
            result.errors.append("Zone segmentation produced no zones")
            result.duration_s = time.perf_counter() - t_start
            return result
    except Exception as exc:
        result.errors.append(f"Zone segmentation failed: {exc}")
        result.duration_s = time.perf_counter() - t_start
        return result

    # ── 5. Fit primitives per zone ──────────────────────────────────────────
    try:
        from backend.sensors.revolution_fitting import fit_all_zones

        zone_fits = fit_all_zones(zones, profile.samples)
        result.zone_fits = zone_fits
        for zone, fit in zone_fits:
            logger.debug(
                "[deterministic_pipeline] Zone %s → fit=%s rms=%.4f conf=%.3f",
                zone.zone_type.value,
                fit.primitive_type,
                fit.residual_rms,
                fit.confidence,
            )
    except Exception as exc:
        result.errors.append(f"Primitive fitting failed (non-fatal): {exc}")
        zone_fits = []

    # ── 6. Build ShaftConstructionPlan ──────────────────────────────────────
    try:
        from backend.core.state import AxisSpec, ShaftConstructionPlan

        axis_spec = AxisSpec(
            direction=(
                result.axis_info.direction.tolist()
                if result.axis_info is not None
                else [0.0, 0.0, 1.0]
            ),
            origin=(
                result.axis_info.origin.tolist()
                if result.axis_info is not None
                else [0.0, 0.0, 0.0]
            ),
            confidence=(
                float(result.axis_info.confidence)
                if result.axis_info is not None
                else 0.5
            ),
            length=float(profile.total_length),
        )

        zone_specs = _zones_to_specs(zones)
        if not zone_specs:
            result.errors.append("No zone specs could be built from zones")
            result.duration_s = time.perf_counter() - t_start
            return result

        overall_confidence = float(
            np.mean([z.confidence for z in zones]) if zones else 0.5
        )

        plan = ShaftConstructionPlan(
            base_axis=axis_spec,
            segments=zone_specs,
            confidence=overall_confidence,
        )
        result.construction_plan = plan
        logger.info(
            "[deterministic_pipeline] Plan built: %d zones, confidence=%.3f",
            len(zone_specs),
            overall_confidence,
        )
    except Exception as exc:
        result.errors.append(f"Construction plan failed: {exc}")
        result.duration_s = time.perf_counter() - t_start
        return result

    # ── 7. Generate build123d code ──────────────────────────────────────────
    try:
        from backend.agents.coder_agent import CoderAgent
        from backend.core.state import CADState

        coder = CoderAgent(llm_client=None)
        state = CADState(
            stl_path=str(stl_file.absolute()),
            shaft_construction_plan=plan,
        )
        code = coder.generate_shaft_code(state, output_dir=str(out_path))
        result.generated_code = code
        logger.info(
            "[deterministic_pipeline] Code generated: %d chars", len(code)
        )

        # Save generated script
        out_path.mkdir(parents=True, exist_ok=True)
        script_path = out_path / f"{stl_file.stem}_parametric.py"
        script_path.write_text(code, encoding="utf-8")
        logger.info("[deterministic_pipeline] Script saved: %s", script_path)

    except Exception as exc:
        result.errors.append(f"Code generation failed: {exc}")
        result.duration_s = time.perf_counter() - t_start
        return result

    # ── 8. Execute build123d → STEP ─────────────────────────────────────────
    if execute_build123d:
        exec_result = _execute_build123d_code(
            code, out_path, timeout_s=execution_timeout_s
        )
        if exec_result["success"]:
            # Use glob so the pipeline works regardless of the exact filename
            # the generated script chose for its export (flat or nested cwd quirks).
            step_files = (
                list(out_path.glob("*.step"))
                + list(out_path.glob("*.STEP"))
                + list(out_path.rglob("shaft.step"))
                + list(out_path.rglob("shaft.STEP"))
            )
            stl_files = (
                list(out_path.glob("*preview*.stl"))
                or list(out_path.glob("*preview*.STL"))
                or list(out_path.glob("*.stl"))
            )
            result.output_step_path = str(step_files[0]) if step_files else None
            result.output_stl_path = str(stl_files[0]) if stl_files else None
            result.success = result.output_step_path is not None
            logger.info(
                "[deterministic_pipeline] build123d executed OK. STEP: %s",
                result.output_step_path,
            )
        else:
            result.errors.append(
                f"build123d execution failed: {exec_result['error']}"
            )
            logger.warning(
                "[deterministic_pipeline] build123d failed: %s",
                exec_result["error"],
            )
            if exec_result["stderr"]:
                logger.debug(
                    "[deterministic_pipeline] stderr: %s", exec_result["stderr"][:1000]
                )
    else:
        # Code generated but not executed
        result.success = bool(result.generated_code)

    # ── 9. Build report ─────────────────────────────────────────────────────
    result.report = {
        "input_file": str(stl_file),
        "part_type": "revolution_body",
        "zone_count": len(zones),
        "zone_types": [z.zone_type.value for z in zones],
        "overall_confidence": float(plan.confidence),
        "axis_confidence": (
            float(result.axis_info.confidence)
            if result.axis_info is not None
            else None
        ),
        "profile_length_mm": float(profile.total_length),
        "profile_radius_range_mm": [
            float(profile.min_radius),
            float(profile.max_radius),
        ],
    }

    if zone_fits:
        result.report["zone_fits"] = [
            {
                "zone_type": z.zone_type.value,
                "fit_primitive": f.primitive_type,
                "fit_rms_mm": round(f.residual_rms, 4),
                "fit_confidence": round(f.confidence, 3),
            }
            for z, f in zone_fits
        ]

    # ── 9b. Reconstruction quality metrics ──────────────────────────────────
    # Compare the input mesh profile against the reconstructed preview STL.
    # This is a warning signal only — a low-confidence reconstruction is still
    # reported as success=True because the STEP file was produced.
    if result.output_stl_path and Path(result.output_stl_path).exists():
        try:
            from backend.pipeline.profile_metrics import compare_stl_files

            metrics = compare_stl_files(
                working_path, result.output_stl_path, num_samples=100
            )
            result.report["reconstruction_metrics"] = metrics.to_dict()
            logger.info(
                "[deterministic_pipeline] Reconstruction metrics: "
                "rmse=%.3fmm iou=%.4f conf=%.3f",
                metrics.rmse_mm,
                metrics.iou_proxy,
                metrics.confidence,
            )
            if metrics.confidence < 0.3:
                result.errors.append(
                    f"Low reconstruction confidence: {metrics.confidence:.3f} "
                    f"(rmse={metrics.rmse_mm:.3f}mm)"
                )
        except Exception as exc:
            result.errors.append(f"Metrics comparison failed (non-fatal): {exc}")
            logger.debug("[deterministic_pipeline] Metrics comparison: %s", exc)

    # Save report JSON
    report_path = out_path / f"{stl_file.stem}_report.json"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(result.to_report_dict(), fh, indent=2, ensure_ascii=False)
        logger.info("[deterministic_pipeline] Report saved: %s", report_path)
    except Exception as exc:
        result.errors.append(f"Report save failed: {exc}")

    result.duration_s = time.perf_counter() - t_start
    logger.info(
        "[deterministic_pipeline] Done in %.2fs. success=%s errors=%d",
        result.duration_s,
        result.success,
        len(result.errors),
    )
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point.

    Example::

        python -m backend.pipeline.deterministic_shaft shaft.stl -o output/
    """
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Deterministic reverse engineering: STL → STEP (no LLM required)"
    )
    parser.add_argument("stl_file", help="Input STL mesh file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory (default: <stem>_reng_output/ next to the input file)",
    )
    parser.add_argument(
        "-n",
        "--samples",
        type=int,
        default=100,
        help="Number of radial profile samples (default: 100)",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Generate build123d code but do not execute it",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="build123d execution timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable DEBUG logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    result = run_deterministic_pipeline(
        stl_path=args.stl_file,
        output_dir=args.output,
        num_profile_samples=args.samples,
        execute_build123d=not args.no_execute,
        execution_timeout_s=args.timeout,
    )

    print()
    print("=" * 60)
    if result.success:
        print("SUCCESS  — Deterministic Reverse Engineering")
    else:
        print("PARTIAL  — Deterministic Reverse Engineering")
    print("=" * 60)
    print(f"  Input   : {result.stl_path}")
    print(f"  Duration: {result.duration_s:.2f}s")
    print(f"  Zones   : {len(result.zones or [])}")
    if result.construction_plan:
        print(f"  Confidence: {result.construction_plan.confidence:.2%}")
    if result.output_step_path:
        print(f"  STEP    : {result.output_step_path}")
    if result.output_stl_path:
        print(f"  Preview : {result.output_stl_path}")
    if result.errors:
        print(f"  Errors  ({len(result.errors)}):")
        for err in result.errors:
            print(f"    • {err}")
    print("=" * 60)
    print()

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
