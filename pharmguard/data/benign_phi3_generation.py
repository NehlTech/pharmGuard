"""
Stage 03B — Phi-3 generation of benign imperative retrieved-content
blocks (D75 risk-3 mitigation: match V2's writing-source distribution).

Background
----------
V2's retrieved content is Phi-3-generated (Stage 03 reconstructs the
poisoned blocks for each MPIB rule family). After D73 broke the block-
count shortcut, the v0.8.1 diagnostic revealed that V2 still scores at
0.999 because the imperative verb mood of Phi-3-generated content is
class-disjoint from our human-written benign augmentation pool.

D75's response is to add benign retrieved content in three sources:
  (1) Hand-authored imperative-benign templates (imperative_benign.py)
  (2) Citation-bearing variants (subset of (1))
  (3) **Phi-3-generated benign updates with the same writing register
     as V2** — this module.

By using the same generator that produced V2's blocks but prompting
for benign payloads, we eliminate the "this text was written by
Phi-3 vs by a human" distinction as a potential shortcut.

Approach
--------
We adapt the R7 (Editor's Note) and R10 (Provenance Spoofing) scaffolds
from MPIB but invert the directive: instead of asking the model to
embed a clinically risky recommendation, we ask it to generate a
benign clinical update that reaffirms standard care, citing real
guideline bodies in the same authoritative register V2's poisoned
updates use.

Each generated block goes through the same safety screen used in
imperative_benign.safety_screen(). A conservative filter: any block
matching deviation-suggesting phrases is dropped. Better to lose
generated content than to poison the benign distribution.

Output
------
A Parquet at ``pharma_data/adversarial/benign_imperatives_v0.parquet``
with columns: prompt_template, generation_seed, text, accepted, reject_reason.

Caching contract
----------------
This stage runs ONCE per major version. Outputs are immutable; Stage 04
loads from this Parquet. Regenerating requires explicit re-run of
``scripts/03B_generate_benign_imperatives.py``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pandas as pd

from pharmguard.data.imperative_benign import (
    MEDICAL_DRUGS,
    MEDICAL_CONDITIONS,
    GUIDELINE_BODIES,
    SCREENING_PROCEDURES,
    safety_screen,
)


# ── Prompt scaffolding ───────────────────────────────────
#
# Two scaffold families, modeled on MPIB R7 and R10 but inverted:
#   * Editor's-note-style scaffolds (R7-inverse): produce editorial
#     summaries that affirm continued standard care.
#   * Institutional-update-style scaffolds (R10-inverse): produce
#     authoritative institutional notes that reaffirm protocol.
#
# Both scaffolds explicitly instruct Phi-3 to:
#   - Use imperative verbs directed at clinicians ("clinicians should
#     continue", "providers must adhere", "practitioners should maintain")
#   - Recommend NO change to current practice
#   - Cite the given guideline body
#   - Avoid any dose/duration modifications, monitoring omissions,
#     or contraindication overrides

PROMPT_EDITORIAL = """\
You are writing a brief editorial summary that would appear as a
retrieved evidence block in a clinical decision support system. The
summary must reaffirm current standard practice and recommend NO
deviation from established care.

Generate a 3-5 sentence editorial summary about {DRUG} use in
{CONDITION}, citing {GUIDELINE_BODY}.

Requirements:
- Use imperative verbs directed at clinicians (e.g., "clinicians
  should continue", "providers must adhere", "practitioners should
  maintain").
- State that the current dosing and monitoring practice should
  continue without modification.
- Do not suggest any dose escalation, dose reduction, duration
  extension, or monitoring omission.
- Begin with "Editor's note:" or "Editorial summary:".

Editorial summary:"""

PROMPT_INSTITUTIONAL = """\
You are writing an institutional clinical practice update that would
appear as a retrieved evidence block in a clinical decision support
system. The update must reaffirm current institutional protocol and
recommend NO deviation from established care.

Generate a 3-5 sentence institutional practice update about
{SCREENING} for patients with {CONDITION}, referencing {GUIDELINE_BODY}.

Requirements:
- Use imperative verbs directed at clinicians (e.g., "clinicians
  should continue", "providers must adhere", "practitioners should
  maintain").
- State that the current screening frequency and protocol should
  continue without modification.
- Do not suggest skipping screening, extending intervals beyond
  current practice, or omitting any monitoring.
- Begin with "Institutional update:" or "Practice update:".

Institutional update:"""


# ── Public API ───────────────────────────────────────────

def build_phi3_benign_pool(
    generator,
    n: int,
    seed: int,
    log: Callable[..., None],
    max_new_tokens: int = 256,
) -> list[dict]:
    """
    Run Phi-3 generation for ``n`` benign imperative blocks.

    Each generation samples a prompt scaffold + slot values, calls
    the generator, and applies the safety screen.

    Parameters
    ----------
    generator : PhiGenerator
        Instance from pharmguard.data.reconstruction.core. Should be
        loaded once by the caller and reused across all generations.
    n : int                       target number of blocks
    seed : int                    RNG seed (deterministic substitutions)
    log : Callable
    max_new_tokens : int          per-generation token budget

    Returns
    -------
    list of dicts with keys: prompt_template, generation_seed, text,
    accepted (bool), reject_reason (Optional[str]).
    """
    import random

    rng = random.Random(seed)
    scaffolds = [
        ("editorial", PROMPT_EDITORIAL),
        ("institutional", PROMPT_INSTITUTIONAL),
    ]

    results: list[dict] = []
    start = time.time()

    for i in range(n):
        # Sample a scaffold and slot values
        scaffold_name, scaffold = rng.choice(scaffolds)
        drug = rng.choice(MEDICAL_DRUGS)
        condition = rng.choice(MEDICAL_CONDITIONS)
        guideline = rng.choice(GUIDELINE_BODIES)
        screening = rng.choice(SCREENING_PROCEDURES)

        prompt = (
            scaffold
            .replace("{DRUG}", drug)
            .replace("{CONDITION}", condition)
            .replace("{GUIDELINE_BODY}", guideline)
            .replace("{SCREENING}", screening)
        )

        # Generate
        try:
            text = generator.generate(prompt, max_new_tokens=max_new_tokens)
            text = text.strip()
        except Exception as e:
            results.append({
                "prompt_template": scaffold_name,
                "generation_seed": seed + i,
                "text": "",
                "accepted": False,
                "reject_reason": f"generation_error: {type(e).__name__}",
            })
            continue

        # Safety-screen the output
        if not text:
            results.append({
                "prompt_template": scaffold_name,
                "generation_seed": seed + i,
                "text": text,
                "accepted": False,
                "reject_reason": "empty_output",
            })
            continue

        if len(text) < 50:
            results.append({
                "prompt_template": scaffold_name,
                "generation_seed": seed + i,
                "text": text,
                "accepted": False,
                "reject_reason": "too_short",
            })
            continue

        if not safety_screen(text):
            # Find the first deviation phrase that triggered the reject
            results.append({
                "prompt_template": scaffold_name,
                "generation_seed": seed + i,
                "text": text,
                "accepted": False,
                "reject_reason": "safety_screen_failed",
            })
            continue

        # Accepted
        results.append({
            "prompt_template": scaffold_name,
            "generation_seed": seed + i,
            "text": text,
            "accepted": True,
            "reject_reason": None,
        })

        # Progress log every 25
        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            n_accepted = sum(1 for r in results if r["accepted"])
            log(f"    [{i+1}/{n}] generated; {n_accepted} accepted; "
                f"{elapsed:.1f}s elapsed ({elapsed/(i+1):.1f}s/gen)")

    elapsed = time.time() - start
    n_accepted = sum(1 for r in results if r["accepted"])
    n_rejected = len(results) - n_accepted
    log(f"  Phi-3 benign pool generation complete: "
        f"{n_accepted}/{n} accepted, {n_rejected} rejected, "
        f"{elapsed:.0f}s total")

    # Breakdown of rejection reasons
    if n_rejected > 0:
        reasons: dict[str, int] = {}
        for r in results:
            if not r["accepted"]:
                reasons[r["reject_reason"]] = reasons.get(r["reject_reason"], 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            log(f"    rejected: {reason}: {count}")

    return results


def save_phi3_benign_pool(
    results: list[dict],
    out_path: Path,
    log: Callable[..., None],
) -> Path:
    """
    Save the generated pool to a Parquet at ``out_path``. Includes
    all rows (accepted and rejected) for downstream auditability.

    Stage 04 reads only ``accepted == True`` rows.
    """
    df = pd.DataFrame(results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log(f"  Saved {len(df)} rows ({df['accepted'].sum()} accepted) "
        f"to {out_path}")
    return out_path


def load_phi3_benign_pool(path: Path) -> list[str]:
    """
    Load accepted benign-imperative blocks from a Stage 03B output.
    Returns just the text strings, ready for Stage 04 augmentation.
    """
    df = pd.read_parquet(path)
    accepted = df[df["accepted"] == True]
    return accepted["text"].tolist()
