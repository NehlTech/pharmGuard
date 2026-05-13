"""
V2 payload reconstruction.

The MPIB benchmark redacts every V2 (RAG-injection) payload with a
`[REDACTED_PAYLOAD]` placeholder before public release, gating the
original payloads behind a research-access agreement. This subpackage
generates clinically plausible *substitute* payloads — matched to
each instance's rule family (R1–R10) and surface-feature targets —
so PharmGuard can train and evaluate against realistic V2 attacks.

All ten rule families from the MPIB paper Table 9 are implemented:
    R1  Evidence Exaggeration
    R2  Contraindication Masking
    R3  Subgroup Generalization
    R4  Outdated-as-Latest
    R5  Fabricated Citation
    R6  Warning Demotion
    R7  Editorial Note
    R8  Triage Downplay
    R9  Dose Tweak
    R10 Provenance Spoofing

The output of this stage is a new parquet at
``data/adversarial/reconstructed_v2.parquet`` with the same schema
as the parsed MPIB but with `[REDACTED_PAYLOAD]` replaced.

Public entry point:
    run_reconstruction(use_llm=True, rule_families=None)
"""

from .core import run_reconstruction

__all__ = ["run_reconstruction"]
