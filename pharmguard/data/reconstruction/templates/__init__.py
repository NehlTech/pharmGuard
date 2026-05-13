"""
Rule-family-specific template strategies for V2 payload reconstruction.

Each rule family (R1–R10 from the MPIB paper) gets its own strategy
module that knows how to build a generation prompt for that family
and a fallback skeleton for cases where LLM generation fails.

The dispatcher ``get_strategy(rule_family_id)`` returns the right
strategy object. A rule family without a registered strategy raises
NotImplementedError, which the orchestrator translates into a
"family-not-implemented" status flag rather than crashing.

Implemented:
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
"""

from __future__ import annotations

from .base import TemplateStrategy
from .r1_exaggeration import R1_EvidenceExaggeration
from .r2_masking import R2_ContraindicationMasking
from .r3_generalization import R3_SubgroupGeneralization
from .r4_outdated import R4_OutdatedAsLatest
from .r5_citation import R5_FabricatedCitation
from .r6_warning_demotion import R6_WarningDemotion
from .r7_editorial import R7_EditorialNote
from .r8_triage_downplay import R8_TriageDownplay
from .r9_dose_tweak import R9_DoseTweak
from .r10_provenance import R10_ProvenanceSpoofing


_STRATEGIES: dict[str, TemplateStrategy] = {
    "R1":  R1_EvidenceExaggeration(),
    "R2":  R2_ContraindicationMasking(),
    "R3":  R3_SubgroupGeneralization(),
    "R4":  R4_OutdatedAsLatest(),
    "R5":  R5_FabricatedCitation(),
    "R6":  R6_WarningDemotion(),
    "R7":  R7_EditorialNote(),
    "R8":  R8_TriageDownplay(),
    "R9":  R9_DoseTweak(),
    "R10": R10_ProvenanceSpoofing(),
}


def get_strategy(rule_family_id: str) -> TemplateStrategy:
    """Return the registered strategy for a rule family."""
    if rule_family_id not in _STRATEGIES:
        raise NotImplementedError(
            f"No template strategy registered for rule family "
            f"{rule_family_id!r}. Implemented families: "
            f"{sorted(_STRATEGIES.keys())}"
        )
    return _STRATEGIES[rule_family_id]


def implemented_families() -> list[str]:
    """Return the rule family IDs that currently have a strategy."""
    return sorted(_STRATEGIES.keys())
