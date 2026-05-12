"""Battery runner for the deterministic revolution-body pipeline.

Walks the configured bench groups (``benchmark_kit/ideal``,
``benchmark_kit/noise``, ``benchmark_kit/corrupt``,
``benchmark_kit/real_scans``, ``tests/fixtures``), invokes
:func:`backend.pipeline.deterministic_shaft.run_deterministic_pipeline`
on every ``*.stl``, and produces:

* ``temp/bench_matrix/<timestamp>/results.json`` – machine-readable matrix.
* ``temp/bench_matrix/<timestamp>/summary.md`` – human-readable table.

The runner is intentionally **read-mostly** about the bench: it neither
creates fixtures nor mutates inputs. Outputs land under ``temp/`` so they
stay outside the source tree.

Typical usage::

    python scripts/run_benchmark_matrix.py
    python scripts/run_benchmark_matrix.py --groups ideal,fixtures
    python scripts/run_benchmark_matrix.py --no-execute  # skip build123d

Design notes (R&D context):
    The matrix is the empirical fuel for every later sprint. Sprint 2 reads
    it to decide which arc-gap fix moves the needle; Sprint 3 reads it to
    calibrate the phi-variance threshold; Sprint 4 surfaces it as the
    Sber500 metrics slide. Keeping the output schema stable across runs is
    therefore more valuable than adding fancy features.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Project import is deferred to ``main`` so ``--help`` works without the venv.

DEFAULT_GROUPS: dict[str, tuple[str, str]] = {
    "ideal": ("benchmark_kit/ideal", "revolution_pure_candidate"),
    "noise": ("benchmark_kit/noise", "noisy_candidate"),
    "corrupt": ("benchmark_kit/corrupt", "corrupt_negative"),
    "real_scans": ("benchmark_kit/real_scans", "real_scan_candidate"),
    "fixtures": ("tests/fixtures", "fixture_or_oo_scope"),
}

logger = logging.getLogger("bench_matrix")


@dataclass
class MatrixEntry:
    """One row of the bench matrix."""

    group: str
    stl_name: str
    stl_path: str
    success: bool
    duration_s: float
    zone_count: int
    zone_types: list[str]
    axis_confidence: float | None
    axis_method: str | None
    overall_confidence: float | None
    rmse_mm: float | None
    iou_proxy: float | None
    max_error_mm: float | None
    reconstruction_confidence: float | None
    n_samples: int | None
    step_path: str | None
    preview_stl_path: str | None
    errors: list[str] = field(default_factory=list)


def _safe_stem(name: str) -> str:
    """Make a filesystem-safe stem out of an arbitrary STL filename.

    Non-ASCII characters (real_scans use Cyrillic) and spaces are mapped to
    ASCII so that downstream tools that pass paths through subprocess
    arguments do not fall over on encoding.
    """
    nfkd = unicodedata.normalize("NFKD", Path(name).stem)
    ascii_only = "".join(c if c.isascii() and c.isalnum() else "_" for c in nfkd)
    while "__" in ascii_only:
        ascii_only = ascii_only.replace("__", "_")
    return ascii_only.strip("_") or "stl"


def _iter_stl_files(group_root: Path) -> Iterable[Path]:
    """Yield ``*.stl`` files sorted by name; ignore other extensions."""
    if not group_root.exists():
        return
    for stl in sorted(group_root.glob("*.stl")):
        yield stl


def _run_one(
    stl_path: Path,
    group: str,
    out_root: Path,
    *,
    num_samples: int,
    execute_build123d: bool,
    timeout_s: float,
) -> MatrixEntry:
    """Run the deterministic pipeline on a single STL and adapt the result."""
    from backend.pipeline.deterministic_shaft import run_deterministic_pipeline

    safe = _safe_stem(stl_path.name)
    out_dir = out_root / group / safe
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    try:
        result = run_deterministic_pipeline(
            stl_path=str(stl_path),
            output_dir=str(out_dir),
            num_profile_samples=num_samples,
            execute_build123d=execute_build123d,
            execution_timeout_s=timeout_s,
        )
        report = result.to_report_dict() if hasattr(result, "to_report_dict") else {}
        rec = report.get("reconstruction_metrics") or {}
        axis = report.get("axis") or {}
        zones = report.get("zones") or []
        return MatrixEntry(
            group=group,
            stl_name=stl_path.name,
            stl_path=str(stl_path),
            success=bool(result.success),
            duration_s=float(result.duration_s),
            zone_count=len(zones),
            zone_types=[z.get("zone_type") for z in zones],
            axis_confidence=axis.get("confidence"),
            axis_method=axis.get("method"),
            overall_confidence=(
                float(result.construction_plan.confidence)
                if result.construction_plan is not None
                else None
            ),
            rmse_mm=rec.get("rmse_mm"),
            iou_proxy=rec.get("iou_proxy"),
            max_error_mm=rec.get("max_error_mm"),
            reconstruction_confidence=rec.get("confidence"),
            n_samples=rec.get("n_samples"),
            step_path=result.output_step_path,
            preview_stl_path=result.output_stl_path,
            errors=list(result.errors or []),
        )
    except Exception as exc:  # noqa: BLE001 — pipeline can raise anything
        # Failing fast on one mesh must not kill the matrix; record and move on.
        logger.exception("Pipeline crashed on %s", stl_path)
        return MatrixEntry(
            group=group,
            stl_name=stl_path.name,
            stl_path=str(stl_path),
            success=False,
            duration_s=time.perf_counter() - t0,
            zone_count=0,
            zone_types=[],
            axis_confidence=None,
            axis_method=None,
            overall_confidence=None,
            rmse_mm=None,
            iou_proxy=None,
            max_error_mm=None,
            reconstruction_confidence=None,
            n_samples=None,
            step_path=None,
            preview_stl_path=None,
            errors=[f"pipeline_crash: {exc}"],
        )


def _format_md_table(entries: list[MatrixEntry]) -> str:
    header = (
        "| group | stl | success | rmse_mm | iou | conf | axis_conf | zones | "
        "duration_s | first_error |\n"
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|\n"
    )
    rows = []
    for e in entries:
        first_err = (e.errors[0][:60] + "...") if e.errors else ""
        rows.append(
            "| {group} | `{stl}` | {success} | {rmse} | {iou} | {conf} | "
            "{axis_conf} | {zones} | {dur:.2f} | {err} |".format(
                group=e.group,
                stl=e.stl_name,
                success="OK" if e.success else "FAIL",
                rmse=f"{e.rmse_mm:.3f}" if e.rmse_mm is not None else "—",
                iou=f"{e.iou_proxy:.3f}" if e.iou_proxy is not None else "—",
                conf=f"{e.reconstruction_confidence:.3f}"
                if e.reconstruction_confidence is not None
                else "—",
                axis_conf=f"{e.axis_confidence:.3f}"
                if e.axis_confidence is not None
                else "—",
                zones=e.zone_count,
                dur=e.duration_s,
                err=first_err,
            )
        )
    return header + "\n".join(rows) + "\n"


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the deterministic revolution-body pipeline over the whole bench."
    )
    parser.add_argument(
        "--groups",
        default=",".join(DEFAULT_GROUPS),
        help=(
            "Comma-separated subset of groups to run. "
            f"Available: {','.join(DEFAULT_GROUPS)}. Default: all."
        ),
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Profile samples per STL (default: 100).",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Skip build123d execution; useful to time the analysis stage alone.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="build123d subprocess timeout in seconds (default: 120).",
    )
    parser.add_argument(
        "--output-root",
        default="temp/bench_matrix",
        help="Where to write the matrix output (default: temp/bench_matrix).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable DEBUG logging."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    )

    selected = [g.strip() for g in args.groups.split(",") if g.strip()]
    unknown = [g for g in selected if g not in DEFAULT_GROUPS]
    if unknown:
        parser.error(f"Unknown groups: {unknown}. Available: {list(DEFAULT_GROUPS)}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = REPO_ROOT / args.output_root / timestamp
    out_root.mkdir(parents=True, exist_ok=True)

    entries: list[MatrixEntry] = []
    for group in selected:
        rel_path, _classification_hint = DEFAULT_GROUPS[group]
        group_root = REPO_ROOT / rel_path
        if not group_root.exists():
            logger.warning("group %s skipped (missing %s)", group, group_root)
            continue
        stls = list(_iter_stl_files(group_root))
        logger.info("group %s: %d STL files", group, len(stls))
        for stl in stls:
            logger.info("  %s/%s", group, stl.name)
            entry = _run_one(
                stl,
                group=group,
                out_root=out_root,
                num_samples=args.samples,
                execute_build123d=not args.no_execute,
                timeout_s=args.timeout,
            )
            entries.append(entry)

    results_json = {
        "schema_version": "sprint1.2.matrix.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": selected,
        "n_samples": args.samples,
        "executed_build123d": not args.no_execute,
        "results": [asdict(e) for e in entries],
    }
    (out_root / "results.json").write_text(
        json.dumps(results_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_root / "summary.md").write_text(
        f"# Bench matrix — {timestamp}\n\n"
        f"Groups: {', '.join(selected)} · samples={args.samples} · "
        f"execute_build123d={not args.no_execute}\n\n"
        + _format_md_table(entries),
        encoding="utf-8",
    )

    n_ok = sum(1 for e in entries if e.success)
    print()
    print(f"Matrix run done: {n_ok}/{len(entries)} STL succeeded")
    print(f"  results.json: {out_root / 'results.json'}")
    print(f"  summary.md  : {out_root / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
