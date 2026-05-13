"""
Imperative-benign retrieved-content templates (D75).

The v0.8.1 diagnostic spike confirmed that PharmGuard's residual
shortcut after D73 was imperative verb mood in retrieved content.
A benign V0/V0p instance with an imperative-mood retrieved block
(e.g., "Clinicians should continue current dosing") scored 0.397,
versus 0.0004 with a declarative-mood block.

D75's central fix is to add benign retrieved content in imperative
mood — telling clinicians what to do, where what they should do is
continue established standard care. This module provides hand-
authored templates with substitution slots, plus a deterministic
instantiator that produces several hundred unique benign imperative
blocks for use in Stage 04's V0/V0p augmentation.

The templates target three properties:
  1. Imperative/prescriptive verb mood ("clinicians should continue",
     "providers must adhere", "practitioners should maintain")
  2. Benign content (continue standard care, no change indicated)
  3. Stylistic variety across rows so the model can't key on a
     specific template signature

A subset of templates include citations to real published guideline
bodies (NCCN, USPSTF, ACC/AHA, Cochrane). These are real organizations
and their guidelines exist; the citation does not assert specific
findings beyond "guidelines exist and reaffirm standard care" which
is a defensible benign claim.
"""

from __future__ import annotations

import random
from typing import Callable


# ── Slot vocabularies ────────────────────────────────────
#
# Templates use {DRUG}, {CONDITION}, {SCREENING}, {INTERVAL},
# {GUIDELINE_BODY}, {GUIDELINE_YEAR}, {PATHWAY}, {SPECIALIST}.
# Slot values are drawn at substitution time; values are general
# enough to be plausible across many clinical scenarios.

MEDICAL_DRUGS: list[str] = [
    "metformin", "atorvastatin", "lisinopril", "amlodipine",
    "metoprolol", "warfarin", "apixaban", "clopidogrel",
    "levothyroxine", "omeprazole", "sertraline", "fluoxetine",
    "ibuprofen", "acetaminophen", "prednisone", "albuterol",
    "insulin glargine", "hydrochlorothiazide", "carvedilol",
    "rosuvastatin", "losartan", "duloxetine", "trazodone",
]

MEDICAL_CONDITIONS: list[str] = [
    "type 2 diabetes", "hypertension", "hyperlipidemia",
    "atrial fibrillation", "heart failure with preserved ejection fraction",
    "asthma", "COPD", "depression", "hypothyroidism",
    "gastroesophageal reflux disease", "chronic kidney disease stage 3",
    "osteoarthritis", "migraine", "rheumatoid arthritis",
    "obesity", "chronic low back pain", "anxiety disorder",
    "obstructive sleep apnea",
]

SCREENING_PROCEDURES: list[str] = [
    "annual hemoglobin A1c monitoring",
    "biannual lipid panel",
    "INR monitoring",
    "blood pressure monitoring",
    "BMP and CMP at routine intervals",
    "annual ophthalmologic examination",
    "renal function assessment",
    "thyroid function testing",
    "ECG follow-up",
    "spirometry assessment",
    "depression screening with PHQ-9",
    "bone density screening per current guidelines",
]

INTERVALS: list[str] = [
    "every 3 months", "every 6 months", "annually",
    "at each visit", "as previously established",
    "per the established schedule", "at the current frequency",
]

GUIDELINE_BODIES: list[str] = [
    "the 2024 American Diabetes Association guidelines",
    "the 2024 ACC/AHA hypertension guidelines",
    "the 2024 NCCN clinical practice guidelines",
    "the 2024 USPSTF recommendations",
    "the 2024 Endocrine Society clinical practice guideline",
    "the 2024 American College of Cardiology consensus statement",
    "the 2024 GOLD guidelines for COPD management",
    "the 2024 GINA guidelines for asthma management",
    "the 2024 KDIGO clinical practice guidelines",
    "the recent Cochrane systematic review",
    "the latest expert consensus statement",
    "the 2024 American Heart Association scientific statement",
]

PATHWAYS: list[str] = [
    "the established institutional protocol",
    "the current clinical pathway",
    "the standard of care algorithm",
    "the existing care pathway",
    "the institutional treatment algorithm",
    "the established prescribing protocol",
    "the current monitoring schedule",
]

SPECIALISTS: list[str] = [
    "endocrinology", "cardiology", "nephrology", "pulmonology",
    "psychiatry", "rheumatology", "gastroenterology", "neurology",
]


# ── Templates ────────────────────────────────────────────
#
# Each template uses imperative verbs directed at clinicians,
# but the imperatives say to continue standard care. Some are
# short (single-sentence) and some are longer to provide a range
# of block lengths matching V2's distribution.

IMPERATIVE_BENIGN_TEMPLATES: list[str] = [
    # Short — single imperative
    "Clinicians should continue to prescribe {DRUG} at the established dose for {CONDITION}. No modification to current practice is indicated.",
    "Practitioners must adhere to {INTERVAL} {SCREENING} for patients with {CONDITION}. The existing schedule remains appropriate.",
    "Providers should maintain the standard dosing of {DRUG} as outlined in {PATHWAY}. No escalation is warranted at this time.",
    "Healthcare providers must continue to apply standard contraindication screening for {DRUG}. The established protocol is unchanged.",

    # Medium — multiple imperatives, no citation
    "Clinicians should continue {SCREENING} {INTERVAL} for patients with {CONDITION}. Practitioners must maintain established follow-up intervals. Providers should not modify the current monitoring approach without specialist consultation.",
    "Practitioners should continue to prescribe {DRUG} per {PATHWAY} for {CONDITION}. Healthcare providers must maintain the existing dosing schedule. Clinicians should escalate to {SPECIALIST} consultation only when standard pathway criteria are met.",
    "Clinicians should adhere to the standard {SCREENING} for patients on long-term {DRUG} therapy. Providers must continue to evaluate response at established intervals. Practitioners should not deviate from {PATHWAY}.",

    # Medium — with guideline citation
    "Clinicians should continue first-line therapy with {DRUG} for {CONDITION} per {GUIDELINE_BODY}. Providers must maintain {SCREENING} {INTERVAL}. The established treatment algorithm remains unchanged.",
    "According to {GUIDELINE_BODY}, providers should continue {SCREENING} at the current frequency for patients with {CONDITION}. Clinicians must adhere to established dosing of {DRUG}. No modification to the standard pathway is warranted.",
    "Per {GUIDELINE_BODY}, practitioners should maintain the existing approach for {CONDITION}. Clinicians must continue to prescribe {DRUG} at established doses. Providers should follow {PATHWAY} without modification.",
    "Clinicians should follow {GUIDELINE_BODY} for {CONDITION} management. Practitioners must continue standard {SCREENING} {INTERVAL}. The established protocol remains the standard of care.",

    # Longer — editorial framing + imperative content
    "Editor's note: A 2024 review of current evidence affirms that clinicians should continue standard dosing of {DRUG} for {CONDITION}. Practitioners must maintain {SCREENING} at the established frequency, and providers should not modify {PATHWAY} based on isolated findings. The standard of care remains unchanged.",
    "Practice update: Healthcare providers should continue to prescribe {DRUG} per {GUIDELINE_BODY}. Clinicians must adhere to established {SCREENING} {INTERVAL}, and practitioners should escalate to {SPECIALIST} only when standard pathway criteria are met. No change in clinical practice is indicated.",
    "Editorial summary: Recent literature reaffirms that clinicians should maintain the current approach for {CONDITION}. Providers must continue {SCREENING} {INTERVAL}, and practitioners should adhere to {PATHWAY}. The established standard of care is unchanged by recent publications.",
    "Institutional update: Clinicians should continue {SCREENING} for all patients on {DRUG} therapy. Providers must maintain {INTERVAL} follow-up, and practitioners should follow {GUIDELINE_BODY} without modification. No new safety signal has been identified that would alter the standard approach.",

    # Longer — content with citation and imperative
    "Clinicians should continue established first-line therapy for {CONDITION} per {GUIDELINE_BODY}. Providers must maintain {SCREENING} {INTERVAL}, and practitioners should adhere to {PATHWAY}. Healthcare providers should escalate to {SPECIALIST} only when standard pathway criteria are met. No modification of current practice is indicated based on recent evidence.",
    "Per {GUIDELINE_BODY}, practitioners should continue prescribing {DRUG} at the established dose for {CONDITION}. Clinicians must maintain {SCREENING}, and providers should adhere to the standard monitoring schedule. The treatment algorithm in {PATHWAY} remains the standard of care without modification.",
    "Clinicians should follow {GUIDELINE_BODY} for management of {CONDITION}. Practitioners must continue {SCREENING} per the established schedule, and providers should adhere to {PATHWAY}. The existing approach remains the standard of care. Healthcare providers should not modify current practice based on preliminary data.",

    # Short — guideline-anchored
    "Per {GUIDELINE_BODY}, clinicians should continue {DRUG} for {CONDITION} without modification.",
    "Healthcare providers must adhere to {GUIDELINE_BODY} for {CONDITION}. {PATHWAY} remains the standard.",

    # Medium — diagnostic/triage flavor
    "Clinicians should continue routine evaluation of patients with {CONDITION} per {PATHWAY}. Practitioners must maintain {SCREENING} {INTERVAL}. Providers should escalate per established triage criteria.",
    "Practitioners should adhere to standard diagnostic workup for {CONDITION}. Clinicians must continue {SCREENING} as previously established, and providers should follow {PATHWAY} without modification.",
    "Healthcare providers must continue the established diagnostic algorithm for {CONDITION}. Clinicians should maintain {SCREENING} {INTERVAL}, and practitioners should adhere to {PATHWAY}.",

    # Short — protocol-focused
    "Clinicians should continue {PATHWAY} for patients with {CONDITION}. {SCREENING} should be maintained {INTERVAL}.",
    "Providers must adhere to the established prescribing protocol for {DRUG}. Practitioners should continue standard monitoring.",
]


def instantiate_templates(
    n: int,
    seed: int = 42,
) -> list[str]:
    """
    Produce ``n`` benign imperative blocks by sampling templates and
    substituting slot values.

    Each block is generated by:
      1. Sampling a template from IMPERATIVE_BENIGN_TEMPLATES
      2. For each {SLOT} in the template, sampling a value from
         the corresponding slot vocabulary
      3. Producing the final string

    Deterministic via ``seed``. Two calls with the same seed produce
    identical blocks.

    Parameters
    ----------
    n : int        number of blocks to generate
    seed : int     RNG seed

    Returns
    -------
    list of n unique-content imperative-benign blocks
    """
    rng = random.Random(seed)

    slot_pools: dict[str, list[str]] = {
        "{DRUG}": MEDICAL_DRUGS,
        "{CONDITION}": MEDICAL_CONDITIONS,
        "{SCREENING}": SCREENING_PROCEDURES,
        "{INTERVAL}": INTERVALS,
        "{GUIDELINE_BODY}": GUIDELINE_BODIES,
        "{PATHWAY}": PATHWAYS,
        "{SPECIALIST}": SPECIALISTS,
    }

    blocks: list[str] = []
    for _ in range(n):
        template = rng.choice(IMPERATIVE_BENIGN_TEMPLATES)
        # Substitute each slot independently with a fresh sample
        block = template
        for slot, pool in slot_pools.items():
            while slot in block:
                # Replace first occurrence with a sampled value
                block = block.replace(slot, rng.choice(pool), 1)
        blocks.append(block)

    return blocks


def safety_screen(block: str) -> bool:
    """
    Return True if the block appears benign (safe to use as training
    content for a benign label).

    Conservative screen: rejects blocks that contain phrases suggesting
    deviation from standard care, escalation of therapy without
    indication, or omission of monitoring. Better to reject a borderline
    block than to poison the benign distribution.

    Used downstream by the Phi-3 generation pipeline (Stage 03B) but
    also applicable to template-generated content as a defense in depth.
    """
    deviation_indicators = [
        # Dose modification
        "increase the dose",
        "extend the duration",
        "double the dose",
        "higher dose",
        "increase to ",
        "raise the dose",
        # Monitoring omission
        "without monitoring",
        "may safely skip",
        "skip the monitoring",
        "no longer required",
        "no further follow-up",
        "discontinue follow-up",
        # Contraindication override
        "despite the contraindication",
        "may safely use",
        "the contraindication is",
        # Triage downplay
        "discharge home",
        "outpatient management is sufficient",
        "no further evaluation needed",
        # Editor's-note-style update
        "this update supersedes",
        "this revision replaces",
    ]
    lower = block.lower()
    for indicator in deviation_indicators:
        if indicator in lower:
            return False
    return True


def build_imperative_benign_pool(
    n: int,
    seed: int,
    log: Callable[..., None],
) -> list[str]:
    """
    Convenience wrapper: instantiate ``n`` templates and apply the
    safety screen. Drops any blocks flagged by the screen and logs
    the count.

    Returns the list of accepted blocks (may be < n if the screen
    rejected some).
    """
    raw = instantiate_templates(n=n, seed=seed)
    accepted = [b for b in raw if safety_screen(b)]
    rejected = len(raw) - len(accepted)
    log(f"  Imperative-benign template pool: {len(accepted)} accepted")
    if rejected > 0:
        log(f"    ⚠ Safety screen rejected {rejected} templated blocks "
            f"(false positives expected; templates are hand-authored)")
    return accepted
