"""Sber500 one-command demo runner.

::

    python -m backend.benchmark                        # default: hero set
    python -m backend.benchmark --groups ideal,noise   # subset of groups
    python -m backend.benchmark --no-previews          # skip matplotlib overlays
    python -m backend.benchmark --output temp/sber500  # custom output root

This module is intentionally thin: it walks ``backend.pipeline.deterministic_shaft``
over the bench, aggregates the per-STL JSON reports into a single
``temp/sber500/<timestamp>/{report.json, summary.md, previews/*.png}``
deliverable, and writes the human-facing markdown table that powers the
Sber500 deck. All the heavy lifting still lives in the deterministic
pipeline; this module just makes the demo reproducible in **one** command.

Design notes:
    * No new dependencies. matplotlib is already pulled in transitively by
      open3d / trimesh, but rendering is gracefully skipped if it is
      missing or if the user passes ``--no-previews``.
    * ``temp/sber500/`` is the canonical output root referenced by
      [docs/sber500_deck.md](../docs/sber500_deck.md); changing it would
      require updating that document.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("backend.benchmark")


# The hero set is what the README quotes and what the Sber500 deck shows.
HERO_SET: Tuple[str, ...] = (
    "benchmark_kit/ideal/ideal_cylinder.stl",
    "benchmark_kit/ideal/ideal_short_disc_shaft.stl",
    "benchmark_kit/ideal/ideal_conical_shaft.stl",
    "benchmark_kit/ideal/ideal_hourglass_shaft.stl",
    "benchmark_kit/ideal/ideal_fillet_shaft.stl",
    "benchmark_kit/ideal/ideal_chamfer_shaft.stl",
    "benchmark_kit/real_scans/Кнопка_2.stl",
    "tests/fixtures/shaft_with_keyway.stl",
)


def _safe_stem(name: str) -> str:
    """Make a filesystem-safe stem out of an arbitrary STL filename."""
    nfkd = unicodedata.normalize("NFKD", Path(name).stem)
    ascii_only = "".join(c if c.isascii() and c.isalnum() else "_" for c in nfkd)
    while "__" in ascii_only:
        ascii_only = ascii_only.replace("__", "_")
    return ascii_only.strip("_") or "stl"


def _render_overlay(
    source_stl: Path,
    reconstructed_stl: Path,
    out_png: Path,
    title: str,
) -> bool:
    """Render an r(z) overlay of source vs reconstructed STL.

    Plots ``boundary_radius`` along the Z axis for both meshes on one
    figure. This is the visual diff that goes into the Sber500 deck.
    Returns ``True`` on success, ``False`` if matplotlib is unavailable or
    if either mesh failed to slice.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from backend.sensors.slice_trimesh import SliceAnalyzer
    except Exception as exc:
        logger.debug("Overlay rendering unavailable: %s", exc)
        return False

    try:
        a_src = SliceAnalyzer(str(source_stl))
        a_rec = SliceAnalyzer(str(reconstructed_stl))
        src_samples = a_src.sample_profile_along_axis(axis="Z", num_samples=80)
        rec_samples = a_rec.sample_profile_along_axis(axis="Z", num_samples=80)
        if not src_samples or not rec_samples:
            return False
        src_z = [s["position"] for s in src_samples]
        src_r = [s.get("boundary_radius", s.get("radius", np.nan)) for s in src_samples]
        rec_z = [s["position"] for s in rec_samples]
        rec_r = [s.get("boundary_radius", s.get("radius", np.nan)) for s in rec_samples]

        fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=110)
        ax.plot(src_z, src_r, label="source r(z)", linewidth=2.0)
        ax.plot(rec_z, rec_r, label="reconstructed r(z)", linewidth=2.0, linestyle="--")
        ax.set_xlabel("z [mm]")
        ax.set_ylabel("boundary radius [mm]")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        out_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_png)
        plt.close(fig)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Overlay failed for %s: %s", source_stl, exc)
        return False


def _summary_md(rows: List[dict]) -> str:
    """Render the markdown summary table consumed by the deck."""
    header = (
        "| STL | RMSE (mm) | IoU | Conf | Axis conf | Zones | Skill requests | Duration (s) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    lines = []
    for r in rows:
        m = r.get("reconstruction_metrics") or {}
        lines.append(
            "| `{stl}` | {rmse} | {iou} | {conf} | {axis} | {zones} | {sk} | {dur:.2f} |".format(
                stl=r["stl_name"],
                rmse=f"{m.get('rmse_mm', float('nan')):.3f}"
                if m.get("rmse_mm") is not None
                else "—",
                iou=f"{m.get('iou_proxy', float('nan')):.3f}"
                if m.get("iou_proxy") is not None
                else "—",
                conf=f"{m.get('confidence', float('nan')):.3f}"
                if m.get("confidence") is not None
                else "—",
                axis=f"{r.get('axis_confidence') or 0.0:.3f}"
                if r.get("axis_confidence") is not None
                else "—",
                zones=r.get("zone_count", 0),
                sk=r.get("skill_request_count", 0),
                dur=r.get("duration_s") or 0.0,
            )
        )
    return header + "\n".join(lines) + "\n"


def _iter_inputs(args: argparse.Namespace) -> Iterable[Path]:
    """Resolve the input STLs for this run.

    Priority: explicit ``--files`` > ``--groups`` (with paths from the
    matrix runner's ``DEFAULT_GROUPS``) > the curated ``HERO_SET``.
    """
    if args.files:
        for raw in args.files:
            p = (REPO_ROOT / raw).resolve()
            if p.exists():
                yield p
            else:
                logger.warning("Skipping missing file: %s", p)
        return

    if args.groups:
        from scripts.run_benchmark_matrix import DEFAULT_GROUPS

        for group in args.groups.split(","):
            group = group.strip()
            if group not in DEFAULT_GROUPS:
                logger.warning("Unknown group %s, ignoring", group)
                continue
            rel, _ = DEFAULT_GROUPS[group]
            group_root = REPO_ROOT / rel
            if not group_root.exists():
                continue
            for stl in sorted(group_root.glob("*.stl")):
                yield stl
        return

    for rel in HERO_SET:
        p = (REPO_ROOT / rel).resolve()
        if p.exists():
            yield p
        else:
            logger.warning("Hero set entry missing: %s", p)


def main() -> int:
    """CLI entry point — see module docstring."""
    parser = argparse.ArgumentParser(
        description="Sber500 demo runner — STL → STEP triple-pack for the bench."
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Specific STL paths (relative to repo root). Overrides --groups.",
    )
    parser.add_argument(
        "--groups",
        default=None,
        help="Comma-separated bench groups (ideal, noise, corrupt, real_scans, fixtures).",
    )
    parser.add_argument(
        "--output",
        default="temp/sber500",
        help="Root output directory (default: temp/sber500).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Profile samples per STL (default: 100).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="build123d subprocess timeout in seconds (default: 120).",
    )
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help="Skip the matplotlib r(z) overlay PNGs.",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Generate parametric scripts but do not run build123d.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="DEBUG logging."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    )

    from backend.pipeline.deterministic_shaft import run_deterministic_pipeline

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = (REPO_ROOT / args.output / timestamp).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    previews_dir = out_root / "previews"

    rows: List[dict] = []
    t0 = time.perf_counter()
    for stl in _iter_inputs(args):
        safe = _safe_stem(stl.name)
        run_dir = out_root / safe
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("running %s", stl.name)
        result = run_deterministic_pipeline(
            stl_path=str(stl),
            output_dir=str(run_dir),
            num_profile_samples=args.samples,
            execute_build123d=not args.no_execute,
            execution_timeout_s=args.timeout,
        )
        report = result.to_report_dict() if hasattr(result, "to_report_dict") else {}
        rec = report.get("reconstruction_metrics") or {}
        axis = report.get("axis") or {}
        zones = report.get("zones") or []
        skill_requests = report.get("skill_requests_generated") or []
        rows.append({
            "stl_name": stl.name,
            "stl_path": str(stl),
            "success": bool(result.success),
            "duration_s": float(result.duration_s),
            "zone_count": len(zones),
            "zone_types": [z.get("zone_type") for z in zones],
            "axis_confidence": axis.get("confidence"),
            "axis_method": axis.get("method"),
            "reconstruction_metrics": rec,
            "skill_request_count": len(skill_requests),
            "skill_requests_generated": skill_requests,
            "step_path": result.output_step_path,
            "preview_stl_path": result.output_stl_path,
            "errors": list(result.errors or []),
        })

        if (
            not args.no_previews
            and result.output_stl_path
            and Path(result.output_stl_path).exists()
        ):
            png_path = previews_dir / f"{safe}_overlay.png"
            ok = _render_overlay(
                source_stl=stl,
                reconstructed_stl=Path(result.output_stl_path),
                out_png=png_path,
                title=f"{stl.name} — RMSE {rec.get('rmse_mm', float('nan')):.3f} mm",
            )
            if ok:
                rows[-1]["overlay_png"] = str(png_path.relative_to(out_root))

    payload = {
        "schema_version": "sprint4.benchmark.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_pipeline": "backend.pipeline.deterministic_shaft",
        "elapsed_total_s": round(time.perf_counter() - t0, 2),
        "results": rows,
    }
    (out_root / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary_md = (
        f"# Sber500 demo — {timestamp}\n\n"
        f"Total parts: **{len(rows)}** · "
        f"successes: **{sum(1 for r in rows if r['success'])}** · "
        f"elapsed: **{payload['elapsed_total_s']}s**\n\n"
        + _summary_md(rows)
    )
    (out_root / "summary.md").write_text(summary_md, encoding="utf-8")

    print()
    print(f"Done. Wrote {len(rows)} runs to {out_root}")
    print(f"  report.json: {out_root / 'report.json'}")
    print(f"  summary.md : {out_root / 'summary.md'}")
    if not args.no_previews:
        print(f"  previews   : {previews_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
