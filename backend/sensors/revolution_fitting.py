"""Mathematical primitive fitting for revolution body profile zones.

For each zone of a radial profile r(z), fits the best geometric primitive
(cylinder, cone/frustum, circular arc) using least-squares methods.

All functions are pure math — no LLM, no I/O.

Typical usage::

    from backend.sensors.revolution_fitting import classify_and_fit_zone, FitResult

    positions = [s.position for s in zone_samples]
    radii = [s.radius for s in zone_samples]
    result = classify_and_fit_zone(positions, radii)
    print(result.primitive_type, result.params, result.residual_rms)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


@dataclass
class FitResult:
    """Result of fitting a geometric primitive to an r(z) zone.

    Attributes:
        primitive_type: One of "cylinder", "cone", "arc".
        residual_rms: Root-mean-square fitting error in the same units as radii (mm).
        r_squared: Coefficient of determination (1.0 = perfect fit).
        confidence: Heuristic fit quality score in [0, 1].
        params: Primitive-specific parameters (see per-fit docstrings).
        n_samples: Number of data points used for fitting.
    """

    primitive_type: str
    residual_rms: float
    r_squared: float
    confidence: float
    params: Dict[str, float] = field(default_factory=dict)
    n_samples: int = 0

    def __repr__(self) -> str:
        return (
            f"FitResult(type={self.primitive_type!r}, rms={self.residual_rms:.4f}, "
            f"conf={self.confidence:.3f}, params={self.params})"
        )


def fit_cylinder(
    positions: List[float],
    radii: List[float],
) -> FitResult:
    """Fit a constant-radius cylinder to r(z) data.

    Model: r(z) = R  (constant)

    Args:
        positions: Ordered z-positions of profile samples (mm).
        radii: Radii at each position (mm).

    Returns:
        FitResult with params={"radius": R}.
    """
    pos = np.asarray(positions, dtype=float)
    rad = np.asarray(radii, dtype=float)
    n = len(rad)
    if n == 0:
        return FitResult("cylinder", float("inf"), 0.0, 0.0, {}, 0)

    r_mean = float(np.mean(rad))
    residuals = rad - r_mean
    rms = float(np.sqrt(np.mean(residuals ** 2)))

    ss_tot = float(np.sum((rad - r_mean) ** 2))
    r_squared = 1.0 if ss_tot < 1e-12 else 0.0  # perfect constant fit has r²=1

    # Confidence: penalised by relative radius variation
    r_range = float(np.max(rad) - np.min(rad))
    relative_var = r_range / (r_mean + 1e-10)
    confidence = float(max(0.0, 1.0 - relative_var * 10))

    return FitResult(
        primitive_type="cylinder",
        residual_rms=rms,
        r_squared=r_squared,
        confidence=confidence,
        params={"radius": r_mean},
        n_samples=n,
    )


def fit_cone(
    positions: List[float],
    radii: List[float],
) -> FitResult:
    """Fit a linearly-varying-radius cone/frustum to r(z) data.

    Model: r(z) = a·z + b  (linear regression)

    Args:
        positions: Ordered z-positions of profile samples (mm).
        radii: Radii at each position (mm).

    Returns:
        FitResult with params={"slope": a, "intercept": b,
        "r_start": r(z_min), "r_end": r(z_max), "half_angle_deg": θ}.
    """
    pos = np.asarray(positions, dtype=float)
    rad = np.asarray(radii, dtype=float)
    n = len(rad)
    if n < 2:
        return FitResult("cone", float("inf"), 0.0, 0.0, {}, n)

    # Linear least squares: [z 1] · [a b]^T = r
    A = np.column_stack([pos, np.ones(n)])
    result_lstsq = np.linalg.lstsq(A, rad, rcond=None)
    (a, b) = result_lstsq[0]

    r_fit = a * pos + b
    residuals = rad - r_fit
    rms = float(np.sqrt(np.mean(residuals ** 2)))

    ss_tot = float(np.sum((rad - np.mean(rad)) ** 2))
    ss_res = float(np.sum(residuals ** 2))
    r_squared = float(1.0 - ss_res / (ss_tot + 1e-12))
    r_squared = max(0.0, r_squared)

    confidence = float(max(0.0, r_squared))

    # Half-angle of cone in degrees
    half_angle_deg = float(np.degrees(np.arctan(abs(a))))

    return FitResult(
        primitive_type="cone",
        residual_rms=rms,
        r_squared=r_squared,
        confidence=confidence,
        params={
            "slope": float(a),
            "intercept": float(b),
            "r_start": float(r_fit[0]),
            "r_end": float(r_fit[-1]),
            "half_angle_deg": half_angle_deg,
        },
        n_samples=n,
    )


def fit_arc(
    positions: List[float],
    radii: List[float],
) -> FitResult:
    """Fit a circular arc to r(z) data (fillet / toroidal transition).

    Uses algebraic (Pratt) least-squares circle fitting in the (z, r) plane.
    Model: (z - cz)² + (r - cr)² = R²

    Args:
        positions: Ordered z-positions of profile samples (mm).
        radii: Radii at each position (mm).

    Returns:
        FitResult with params={"center_z": cz, "center_r": cr,
        "arc_radius": R, "arc_span_deg": angular span of the arc}.
    """
    pos = np.asarray(positions, dtype=float)
    rad = np.asarray(radii, dtype=float)
    n = len(rad)
    if n < 3:
        return FitResult("arc", float("inf"), 0.0, 0.0, {}, n)

    # Pratt algebraic circle fit in (z, r) space
    z_c = np.mean(pos)
    r_c = np.mean(rad)
    Z = pos - z_c
    R = rad - r_c

    A_mat = np.column_stack([2.0 * Z, 2.0 * R, np.ones(n)])
    b_vec = Z ** 2 + R ** 2

    try:
        sol, _, _, _ = np.linalg.lstsq(A_mat, b_vec, rcond=None)
        cx = z_c + sol[0]
        cy = r_c + sol[1]
        arc_radius = float(np.sqrt(max(0.0, sol[2] + sol[0] ** 2 + sol[1] ** 2)))
    except np.linalg.LinAlgError as exc:
        logger.debug(f"[fit_arc] lstsq failed: {exc}")
        return FitResult("arc", float("inf"), 0.0, 0.0, {}, n)

    if arc_radius < 1e-6:
        return FitResult("arc", float("inf"), 0.0, 0.0, {}, n)

    # Residuals: distance from each point to the fitted circle minus arc_radius
    distances = np.sqrt((pos - cx) ** 2 + (rad - cy) ** 2)
    residuals = distances - arc_radius
    rms = float(np.sqrt(np.mean(residuals ** 2)))

    # R² against mean-radius baseline
    r_mean = float(np.mean(rad))
    ss_tot = float(np.sum((rad - r_mean) ** 2))
    r_pred = cy + np.sqrt(np.maximum(arc_radius ** 2 - (pos - cx) ** 2, 0.0))
    ss_res = float(np.sum((rad - r_pred) ** 2))
    r_squared = float(max(0.0, 1.0 - ss_res / (ss_tot + 1e-12)))

    # Confidence penalised by rms relative to arc_radius
    confidence = float(max(0.0, 1.0 - rms / (arc_radius * 0.1 + 1e-10)))
    confidence = min(1.0, confidence)

    # Angular span of the arc
    angles = np.degrees(np.arctan2(rad - cy, pos - cx))
    arc_span_deg = float(np.max(angles) - np.min(angles))

    return FitResult(
        primitive_type="arc",
        residual_rms=rms,
        r_squared=r_squared,
        confidence=confidence,
        params={
            "center_z": float(cx),
            "center_r": float(cy),
            "arc_radius": arc_radius,
            "arc_span_deg": arc_span_deg,
        },
        n_samples=n,
    )


def classify_and_fit_zone(
    positions: List[float],
    radii: List[float],
    *,
    cone_slope_threshold: float = 0.005,
    arc_curvature_threshold: float = 0.1,
) -> FitResult:
    """Select the best-fitting primitive for an r(z) zone.

    Tries cylinder, cone, and (when n >= 3) arc fits. Selects the fit with the
    lowest residual RMS, with an Occam-razor bias toward simpler primitives:
    the cylinder is preferred unless a more complex primitive is clearly better.

    Args:
        positions: z-positions of profile samples (mm).
        radii: Radii at each position (mm).
        cone_slope_threshold: Minimum absolute slope (mm/mm) to consider a zone
            conical rather than cylindrical.
        arc_curvature_threshold: Minimum r² improvement for arc over cone to
            justify the more complex model.

    Returns:
        The best FitResult. Falls back to cylinder if all fits fail.
    """
    n = len(positions)
    if n == 0:
        return FitResult("cylinder", 0.0, 1.0, 1.0, {"radius": 0.0}, 0)

    cyl = fit_cylinder(positions, radii)

    if n < 2:
        return cyl

    cone = fit_cone(positions, radii)

    # Arc requires >= 3 points
    arc: Optional[FitResult] = None
    if n >= 3:
        arc = fit_arc(positions, radii)

    # --- selection logic ---
    # 1. If cone slope is negligible, the zone is a cylinder.
    if abs(cone.params.get("slope", 0.0)) < cone_slope_threshold:
        return cyl

    # 2. If there is meaningful slope, compare cone vs cylinder
    # Prefer cone only if it explains the data significantly better
    if cone.residual_rms < cyl.residual_rms * 0.7 and cone.confidence > 0.5:
        best = cone
    else:
        best = cyl

    # 3. Consider arc if it's clearly better than whatever we have so far
    if arc is not None and np.isfinite(arc.residual_rms):
        r_sq_gain = arc.r_squared - best.r_squared
        if r_sq_gain > arc_curvature_threshold and arc.confidence > 0.5:
            best = arc

    logger.debug(
        f"[classify_and_fit_zone] Best fit: {best.primitive_type} "
        f"rms={best.residual_rms:.4f} conf={best.confidence:.3f}"
    )
    return best


def fit_zone_from_profile_samples(
    samples: List[object],
) -> FitResult:
    """Convenience wrapper: fit a zone directly from ProfileSample objects.

    Args:
        samples: List of ProfileSample (must have .position and .radius attributes).

    Returns:
        FitResult for the zone.
    """
    positions = [s.position for s in samples]  # type: ignore[attr-defined]
    radii = [s.radius for s in samples]  # type: ignore[attr-defined]
    return classify_and_fit_zone(positions, radii)


def fit_all_zones(
    zones: List[object],
    profile_samples: List[object],
) -> List[Tuple[object, FitResult]]:
    """Fit primitives for every zone in a shaft profile.

    Args:
        zones: List of ShaftZone objects (with .start_pos, .end_pos).
        profile_samples: List of ProfileSample objects covering the full profile.

    Returns:
        List of (zone, FitResult) pairs in the same order as zones.
    """
    results: List[Tuple[object, FitResult]] = []

    for zone in zones:
        # Collect samples belonging to this zone
        zone_samples = [
            s
            for s in profile_samples
            if zone.start_pos <= s.position <= zone.end_pos  # type: ignore[attr-defined]
        ]

        if not zone_samples:
            logger.warning(
                f"[fit_all_zones] No samples for zone "
                f"{zone.zone_type.value} [{zone.start_pos:.2f}, {zone.end_pos:.2f}]"  # type: ignore[attr-defined]
            )
            fallback = FitResult("cylinder", 0.0, 1.0, 0.5, {}, 0)
            results.append((zone, fallback))
            continue

        fit = fit_zone_from_profile_samples(zone_samples)
        results.append((zone, fit))

    return results
