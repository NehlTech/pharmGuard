"""
PharmGuard: A production-grade indirect prompt injection detector for
clinical decision support systems.

This package implements the four-layer PharmGuard architecture:
    Layer 1 (Phi):  Adversarial canonicalization
    Layer 2 (E):    Biomedical encoding (PubMedBERT)
    Layer 3 (D):    Calibrated decision (FPR-targeted thresholds)
    Layer 4 (R):    Confidence-aware human routing

Subpackages:
    data        Acquisition, EDA, payload reconstruction, splits
    model       Architecture components and composed model
    training    Training loop, calibration, drift recalibration
    evaluation  Metrics, adaptive attacks, statistical testing
    baselines   Off-the-shelf detector loaders for comparison
"""

__version__ = "0.10.0"
__author__ = "PharmGuard Contributors"
