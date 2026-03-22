"""Quality metrics for revolution body reconstruction.

Compares the r(z) radial profile of an original STL mesh against a
reconstructed (reverse-engineered) STL, producing quantitative accuracy
metrics suitable for benchmarking and the Sber500 demo report.

All functions are pure math — no LLM, no build123d, no I/O except for
the convenience ``compare_stl_files`` entry point.

Typical usage::

    from backend.pipeline.profile_metrics import compare_stl_files

    metrics = compare_stl_files("original.stl", "reconstructed.stl")
    print(metrics.rmse_mm, metrics.iou_proxy, metrics.confidence)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------


@dataclass
class ProfileMetrics:
    """Quantitative comparison of two revolution body profiles.

    Attributes:
        rmse_mm: Root-mean-square error of r(z) in millimetres.
        max_error_mm: Maximum absolute error of r(z) in millimetres.
        mean_abs_error_mm: Mean absolute error of r(z) in millimetres.
        iou_proxy: Approximate volumetric IoU (1.0 = perfect overlap).
            Computed as 1 – mean(|r_orig – r_recon| / max(r_orig, r_recon)).
        confidence: Overall reconstruction quality score in [0, 1].
            Aggregates axis confidence, zone count accuracy, and profile error.
        n_samples: Number of evaluation positions used.
        details: Per-position breakdown and per-zone metrics.
    """

    rmse_mm: float
    max_error_mm: float
    mean_abs_error_mm: float
    iou_proxy: float
    confidence: float
    n_samples: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict.

        Returns:
            Dictionary of all metric fields.
        """
        return {
            "rmse_mm": round(self.rmse_mm, 4),
            "max_error_mm": round(self.max_error_mm, 4),
            "mean_abs_error_mm": round(self.mean_abs_error_mm, 4),
            "iou_proxy": round(self.iou_proxy, 4),
            "confidence": round(self.confidence, 4),
            "n_samples": self.n_samples,
            **self.details,
        }

    def __repr__(self) -> str:
        return (
            f"ProfileMetrics("
            f"rmse={self.rmse_mm:.4f}mm "
            f"max_err={self.max_error_mm:.4f}mm "
            f"iou={self.iou_proxy:.4f} "
            f"conf={self.confidence:.3f} "
            f"n={self.n_samples})"
        )


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------


def profile_rmse(
    r_orig: npt.NDArray[np.float64],
    r_recon: npt.NDArray[np.float64],
) -> float:
    """Root-mean-square error between two radius profiles at the same positions.

    Args:
        r_orig: Radii from the original mesh at each evaluation position (mm).
        r_recon: Radii from the reconstructed mesh at the same positions (mm).

    Returns:
        RMSE in mm.
    """
    if len(r_orig) == 0:
        return 0.0
    return float(np.sqrt(np.mean((r_orig - r_recon) ** 2)))


def profile_max_error(
    r_orig: npt.NDArray[np.float64],
    r_recon: npt.NDArray[np.float64],
) -> float:
    """Maximum absolute error between two radius profiles.

    Args:
        r_orig: Radii from the original mesh (mm).
        r_recon: Radii from the reconstructed mesh (mm).

    Returns:
        Maximum absolute error in mm.
    """
    if len(r_orig) == 0:
        return 0.0
    return float(np.max(np.abs(r_orig - r_recon)))


def profile_mean_abs_error(
    r_orig: npt.NDArray[np.float64],
    r_recon: npt.NDArray[np.float64],
) -> float:
    """Mean absolute error between two radius profiles.

    Args:
        r_orig: Radii from the original mesh (mm).
        r_recon: Radii from the reconstructed mesh (mm).

    Returns:
        MAE in mm.
    """
    if len(r_orig) == 0:
        return 0.0
    return float(np.mean(np.abs(r_orig - r_recon)))


def iou_proxy(
    r_orig: npt.NDArray[np.float64],
    r_recon: npt.NDArray[np.float64],
) -> float:
    """Approximate volumetric IoU for two revolution bodies with the same axis.

    For revolution bodies, the exact 3-D IoU is expensive.  This approximation
    computes a cross-sectional overlap metric at each evaluation position:

        IoU_proxy = 1 – mean( |r_orig – r_recon| / max(r_orig, r_recon) )

    For perfect reconstruction (r_orig == r_recon at every point), IoU_proxy = 1.
    When one body is 20% larger everywhere, IoU_proxy ≈ 0.8.

    Args:
        r_orig: Radii from the original mesh (mm).
        r_recon: Radii from the reconstructed mesh (mm).

    Returns:
        IoU proxy score in [0, 1].
    """
    if len(r_orig) == 0:
        return 0.0
    r_max = np.maximum(r_orig, r_recon)
    # Avoid division by zero where both radii are zero
    mask = r_max > 1e-6
    if not np.any(mask):
        return 1.0
    relative_error = np.abs(r_orig[mask] - r_recon[mask]) / r_max[mask]
    return float(max(0.0, 1.0 - np.mean(relative_error)))


def compute_confidence(
    rmse_mm: float,
    max_error_mm: float,
    iou: float,
    *,
    rmse_target_mm: float = 0.5,
    max_error_target_mm: float = 2.0,
) -> float:
    """Aggregate a single confidence score from profile error metrics.

    Penalises scores exponentially as RMSE and max error grow past their
    target thresholds.

    Args:
        rmse_mm: Profile RMSE in mm.
        max_error_mm: Profile max error in mm.
        iou: IoU proxy score.
        rmse_target_mm: RMSE budget (score = 1 when below this).
        max_error_target_mm: Max-error budget (score = 1 when below this).

    Returns:
        Confidence score in [0, 1].
    """
    rmse_score = float(np.exp(-rmse_mm / max(rmse_target_mm, 1e-6)))
    max_err_score = float(np.exp(-max_error_mm / max(max_error_target_mm, 1e-6)))
    confidence = 0.4 * rmse_score + 0.3 * max_err_score + 0.3 * iou
    return float(max(0.0, min(1.0, confidence)))


# ---------------------------------------------------------------------------
# Profile sampling utility
# ---------------------------------------------------------------------------


def _sample_radius_along_z(
    stl_path: str,
    z_positions: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Sample the radial profile of an STL mesh at specified z-positions.

    Uses slice_trimesh to cut the mesh at each z position and extracts the
    boundary-based radius of the largest cross-sectional polygon.

    Args:
        stl_path: Path to the STL file.
        z_positions: Array of z-positions at which to sample the radius.

    Returns:
        Array of radii (mm) at each requested z-position.  Positions where
        sampling fails produce NaN values.
    """
    from backend.sensors.slice_trimesh import SliceAnalyzer

    analyzer = SliceAnalyzer(stl_path)
    radii = np.full(len(z_positions), np.nan)

    for idx, z in enumerate(z_positions):
        try:
            sample = analyzer.sample_at_position(float(z), axis="Z")
            if sample is not None:
                radii[idx] = sample.get("boundary_radius", sample.get("radius", np.nan))
        except Exception as exc:
            logger.debug("Sampling failed at z=%.3f: %s", z, exc)

    return radii


# ---------------------------------------------------------------------------
# Per-zone IoU
# ---------------------------------------------------------------------------


def zone_iou_proxy(
    zones_orig: List[Any],
    zones_recon: List[Any],
) -> float:
    """Compute IoU proxy by comparing zone-level r(z) intervals.

    Matches original zones to reconstructed zones by closest mean_radius,
    then computes per-zone radius overlap.

    Args:
        zones_orig: List of ShaftZone from the original STL (with
            .start_pos, .end_pos, .mean_radius).
        zones_recon: List of ShaftZone from the reconstructed STL.

    Returns:
        Mean zone IoU proxy score in [0, 1].
    """
    if not zones_orig or not zones_recon:
        return 0.0

    per_zone_scores: List[float] = []
    for oz in zones_orig:
        # Find closest reconstructed zone by mean radius
        best = min(
            zones_recon,
            key=lambda rz: abs(rz.mean_radius - oz.mean_radius),
        )
        r_max = max(oz.mean_radius, best.mean_radius)
        if r_max < 1e-6:
            per_zone_scores.append(1.0)
            continue
        relative_err = abs(oz.mean_radius - best.mean_radius) / r_max
        per_zone_scores.append(max(0.0, 1.0 - relative_err))

    return float(np.mean(per_zone_scores))


# ---------------------------------------------------------------------------
# High-level comparison API
# ---------------------------------------------------------------------------


def compare_profiles(
    r_orig: npt.NDArray[np.float64],
    r_recon: npt.NDArray[np.float64],
    positions: npt.NDArray[np.float64],
) -> ProfileMetrics:
    """Compute full metric suite for two already-sampled profiles.

    Both arrays must be sampled at the same positions.  NaN values in either
    array are dropped before computing metrics.

    Args:
        r_orig: Original radii at each position (mm).
        r_recon: Reconstructed radii at each position (mm).
        positions: z-positions for annotation in details.

    Returns:
        ProfileMetrics with all computed scores.
    """
    valid = np.isfinite(r_orig) & np.isfinite(r_recon)
    r_o = r_orig[valid]
    r_r = r_recon[valid]
    pos_valid = positions[valid]
    n = int(np.sum(valid))

    if n == 0:
        logger.warning("[compare_profiles] No valid (non-NaN) sample pairs")
        return ProfileMetrics(
            rmse_mm=float("inf"),
            max_error_mm=float("inf"),
            mean_abs_error_mm=float("inf"),
            iou_proxy=0.0,
            confidence=0.0,
            n_samples=0,
        )

    rmse = profile_rmse(r_o, r_r)
    max_err = profile_max_error(r_o, r_r)
    mae = profile_mean_abs_error(r_o, r_r)
    iou = iou_proxy(r_o, r_r)
    conf = compute_confidence(rmse, max_err, iou)

    errors = (r_o - r_r).tolist()
    details: Dict[str, Any] = {
        "n_valid": n,
        "n_nan": int(len(r_orig) - n),
        "r_orig_mean_mm": round(float(np.mean(r_o)), 4),
        "r_recon_mean_mm": round(float(np.mean(r_r)), 4),
        "r_orig_max_mm": round(float(np.max(r_o)), 4),
        "r_recon_max_mm": round(float(np.max(r_r)), 4),
        "per_position_error_sample": [
            {"z": round(float(p), 3), "error_mm": round(float(e), 4)}
            for p, e in zip(
                pos_valid[::max(1, n // 10)].tolist(),
                np.array(errors)[::max(1, n // 10)].tolist(),
            )
        ],
    }

    return ProfileMetrics(
        rmse_mm=rmse,
        max_error_mm=max_err,
        mean_abs_error_mm=mae,
        iou_proxy=iou,
        confidence=conf,
        n_samples=n,
        details=details,
    )


def compare_stl_files(
    original_stl: str,
    reconstructed_stl: str,
    *,
    num_samples: int = 200,
    z_start: Optional[float] = None,
    z_end: Optional[float] = None,
) -> ProfileMetrics:
    """Compare the r(z) profiles of an original and a reconstructed STL.

    Both STLs are sliced at the same set of evenly-spaced z-positions within
    the overlapping z-extent.  The resulting radius arrays are compared with
    the full metric suite.

    Args:
        original_stl: Path to the original STL mesh.
        reconstructed_stl: Path to the reconstructed STL mesh.
        num_samples: Number of z-positions for evaluation.
        z_start: Override start of the z evaluation range.
        z_end: Override end of the z evaluation range.

    Returns:
        ProfileMetrics for the pair.
    """
    import trimesh

    try:
        mesh_orig = trimesh.load_mesh(original_stl)
        mesh_recon = trimesh.load_mesh(reconstructed_stl)
    except Exception as exc:
        logger.error("[compare_stl_files] Failed to load meshes: %s", exc)
        raise

    # Determine overlapping z extent
    z_min_orig = float(mesh_orig.bounds[0][2])
    z_max_orig = float(mesh_orig.bounds[1][2])
    z_min_recon = float(mesh_recon.bounds[0][2])
    z_max_recon = float(mesh_recon.bounds[1][2])

    z_lo = max(z_min_orig, z_min_recon) if z_start is None else z_start
    z_hi = min(z_max_orig, z_max_recon) if z_end is None else z_end

    if z_lo >= z_hi:
        logger.error(
            "[compare_stl_files] Z ranges do not overlap: "
            "orig=[%.2f, %.2f] recon=[%.2f, %.2f]",
            z_min_orig, z_max_orig, z_min_recon, z_max_recon,
        )
        return ProfileMetrics(
            rmse_mm=float("inf"),
            max_error_mm=float("inf"),
            mean_abs_error_mm=float("inf"),
            iou_proxy=0.0,
            confidence=0.0,
            n_samples=0,
        )

    # Add a small inset to avoid boundary slicing artifacts
    inset = (z_hi - z_lo) * 0.02
    positions = np.linspace(z_lo + inset, z_hi - inset, num_samples)

    logger.info(
        "[compare_stl_files] Sampling %d positions z=[%.2f, %.2f]",
        num_samples, z_lo, z_hi,
    )

    r_orig = _sample_radius_along_z(original_stl, positions)
    r_recon = _sample_radius_along_z(reconstructed_stl, positions)

    return compare_profiles(r_orig, r_recon, positions)


def compare_profile_vs_zones(
    original_stl: str,
    reconstructed_zones: List[Any],
    *,
    num_samples: int = 200,
) -> ProfileMetrics:
    """Compare an original STL profile against reconstructed zone definitions.

    Instead of requiring a reconstructed STL, this uses the
    ShaftConstructionPlan zones as the "reconstructed" radius model:
    each zone contributes its mean_radius at positions within [start_pos, end_pos].

    Args:
        original_stl: Path to the original STL mesh.
        reconstructed_zones: List of ShaftZone objects with .start_pos,
            .end_pos, and .mean_radius attributes.
        num_samples: Number of positions for evaluation.

    Returns:
        ProfileMetrics comparing original vs. zone-level reconstruction.
    """
    from backend.sensors.shaft_profile import (
        sample_radial_profile,
        segment_rotational_zones,
    )

    profile = sample_radial_profile(
        original_stl, axis="Z", num_samples=num_samples
    )

    positions = np.array([s.position for s in profile.samples])
    r_orig = np.array([s.radius for s in profile.samples])

    # Build reconstructed radius array from zones
    r_recon = np.full_like(r_orig, np.nan)
    for zone in reconstructed_zones:
        mask = (positions >= zone.start_pos) & (positions <= zone.end_pos)
        if hasattr(zone, "start_radius") and abs(zone.start_radius - zone.end_radius) > 0.1:
            # Linear interpolation for cone zones
            t = np.where(
                (zone.end_pos - zone.start_pos) > 0,
                (positions[mask] - zone.start_pos) / (zone.end_pos - zone.start_pos),
                0.5,
            )
            r_recon[mask] = zone.start_radius + t * (zone.end_radius - zone.start_radius)
        else:
            r_recon[mask] = zone.mean_radius

    return compare_profiles(r_orig, r_recon, positions)
