"""GDI Approximator - Zone Detection and Parameter Fitting."""

from .approximator import Approximator, ZoneDetector
from .confidence import compute_zone_confidence, compute_global_confidence

__all__ = ["Approximator", "ZoneDetector", "compute_zone_confidence", "compute_global_confidence"]
