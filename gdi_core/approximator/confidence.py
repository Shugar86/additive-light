"""Confidence scoring for Approximator.

Implements robust confidence metrics for zone detection.
"""

import numpy as np
from typing import List


def compute_zone_confidence(
    measurements: np.ndarray,
    inliers: np.ndarray,
    has_holes: bool = False
) -> float:
    """Compute confidence score for a single zone.
    
    Factors:
    - RANSAC inlier ratio (how well data fits model)
    - Measurement variance (lower variance = higher confidence)
    - Hole detection certainty (if applicable)
    
    Args:
        measurements: Array of measurements (e.g., radii)
        inliers: Boolean mask of RANSAC inliers
        has_holes: Whether holes were detected
        
    Returns:
        Confidence score in [0.0, 1.0]
    """
    if len(measurements) == 0:
        return 0.0
    
    # Base confidence from inlier ratio
    inlier_ratio = np.sum(inliers) / len(inliers) if len(inliers) > 0 else 0
    
    # Variance penalty (normalized)
    if np.sum(inliers) > 1:
        variance = np.var(measurements[inliers])
        # Normalize: variance of 0.5mm is considered high
        variance_penalty = min(1.0, variance / 0.5)
    else:
        variance_penalty = 1.0  # Max penalty if no inliers
    
    # Combine factors
    base_confidence = inlier_ratio * (1.0 - variance_penalty * 0.3)
    
    # Hole penalty (hole detection adds uncertainty)
    if has_holes:
        base_confidence *= 0.9  # 10% penalty for hole complexity
    
    # Ensure in valid range
    return float(np.clip(base_confidence, 0.0, 1.0))


def compute_global_confidence(zone_confidences: List[float]) -> float:
    """Compute global confidence from zone confidences.
    
    Uses a conservative approach: global confidence is weighted
    toward the lowest zone confidence (weakest link principle).
    
    Args:
        zone_confidences: List of per-zone confidence scores
        
    Returns:
        Global confidence score in [0.0, 1.0]
    """
    if not zone_confidences:
        return 0.0
    
    if len(zone_confidences) == 1:
        return zone_confidences[0]
    
    # Weighted combination favoring minimum
    min_conf = min(zone_confidences)
    mean_conf = np.mean(zone_confidences)
    
    # 60% weight on minimum, 40% on mean
    # This ensures one bad zone significantly impacts global score
    global_conf = 0.6 * min_conf + 0.4 * mean_conf
    
    return float(np.clip(global_conf, 0.0, 1.0))


def compute_iou_confidence(iou_score: float) -> float:
    """Convert IoU score to confidence metric.
    
    Args:
        iou_score: Intersection over Union score in [0.0, 1.0]
        
    Returns:
        Confidence based on IoU
    """
    # IoU >= 0.98 is considered "perfect" (confidence 1.0)
    # IoU < 0.70 is considered "failed" (confidence 0.0)
    
    if iou_score >= 0.98:
        return 1.0
    elif iou_score < 0.70:
        return 0.0
    else:
        # Linear interpolation between 0.70 and 0.98
        return (iou_score - 0.70) / (0.98 - 0.70)
