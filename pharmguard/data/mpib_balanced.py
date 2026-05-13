"""
Construction of paired benign-PubMedQA instances (Stage 02C).

Background
----------
After Stage 02B documented MPIB's source-distribution shortcut — V2
instances are PubMedQA-sourced with a fixed template, V0/V0'/V1 are
MedQA-sourced — we need a benign cohort that shares V2's user_query
template to force any future detector to read retrieved content rather
than identify the source dataset.

This module constructs such a cohort by taking each V2 instance and:

  1. Keeping the V2 user_query verbatim
  2. Keeping only the ``benign_evidence`` block in contexts (i.e.,
     the original PubMedQA abstract that the V2 was built from)
  3. Optionally pairing with a second ``benign_evidence`` block from
     another V2 instance to match V2's 2-block structure
  4. Re-labelling as benign (vector="V0_paired_pubmedqa", severity=0)
  5. Recording paired_with_v2_id for provenance

After this construction, the training corpus contains roughly equal
numbers of V2 (adversarial PubMedQA-templated) and paired-benign
(benign PubMedQA-templated) instances. The user_query template is
class-balanced; the only discriminative feature is the presence vs
absence of the poisoned_update block, which lives inside the
retrieved-content blocks.

This module is called from Stage 04 (the orchestrator) after MPIB is
loaded and before split assignment.
"""

from __future__ import annotations

import hashlib
import random
from typing import Callable

import pandas as pd


# ── Vector label for the new cohort ──────────────────────
#
# We use a distinct vector name to make this cohort easy to identify
# downstream. Stage 04's split-assignment treats it as benign (label=0)
# while preserving the source provenance for analysis.
PAIRED_BENIGN_VECTOR = "V0_paired_pubmedqa"


def construct_paired_benign_pubmedqa(
    mpib: pd.DataFrame,
    log: Callable[..., None],
    pair_with_second_block: bool = True,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Build paired benign-PubMedQA instances from each V2 row.

    For each V2 row in the input DataFrame, produce one new row with:

      * Same user_query as the V2 (PubMedQA literature-evaluation template).
      * Contexts containing only the ``benign_evidence`` block from V2,
        plus optionally a second ``benign_evidence`` block sampled from
        another V2 (to match V2's 2-block structure so block count is
        not a class signal).
      * vector = PAIRED_BENIGN_VECTOR
      * severity = 0
      * harm_types = []
      * expected_safe_behavior copied from V2
      * source = "PubMedQA"
      * mpib_split = same as paired V2 (preserves split membership)
      * Provenance: ``paired_with_v2_id`` records which V2 the row was
        paired from.

    Parameters
    ----------
    mpib : pd.DataFrame                MPIB rows including V2 instances
    log : Callable
    pair_with_second_block : bool      If True, add a second benign_evidence
                                       block from another V2 to match V2's
                                       2-block structure. Default True.
    seed : int                         RNG seed for second-block sampling.

    Returns
    -------
    pd.DataFrame  — original mpib rows + newly constructed paired-benign
                    rows, concatenated. Column schema is preserved.
    """
    rng = random.Random(seed)
    v2_rows = mpib[mpib["vector"] == "V2"].copy()

    if len(v2_rows) == 0:
        log("  ⚠ No V2 rows found in MPIB; nothing to pair.")
        return mpib

    log(f"  V2 rows to pair: {len(v2_rows)}")
    log(f"  Pair with second block: {pair_with_second_block}")

    # Pool of all V2 benign_evidence texts (used as second-block donors)
    benign_evidence_pool: list[tuple[str, str]] = []  # (v2_id, text)
    for _, row in v2_rows.iterrows():
        for ctx in row["contexts"] or []:
            if isinstance(ctx, dict) and ctx.get("role") == "benign_evidence":
                text = ctx.get("text", "")
                if text:
                    benign_evidence_pool.append((row["sample_id"], text))

    log(f"  Benign-evidence donor pool: {len(benign_evidence_pool)} texts")

    new_rows: list[dict] = []
    n_first_block_found = 0
    n_second_block_added = 0

    for _, row in v2_rows.iterrows():
        # Find the benign_evidence block in this V2's contexts
        first_block = None
        for ctx in row["contexts"] or []:
            if isinstance(ctx, dict) and ctx.get("role") == "benign_evidence":
                first_block = ctx.get("text", "")
                break

        if not first_block:
            # V2 instance without a benign_evidence block; skip
            continue
        n_first_block_found += 1

        # Build new contexts list
        new_contexts = [
            {"role": "benign_evidence", "text": first_block},
        ]

        # Optionally add a second benign_evidence block from another V2
        if pair_with_second_block and len(benign_evidence_pool) > 1:
            # Sample a donor that isn't this row's own V2
            attempts = 0
            while attempts < 10:
                donor_id, donor_text = rng.choice(benign_evidence_pool)
                if donor_id != row["sample_id"]:
                    new_contexts.append({
                        "role": "benign_evidence",
                        "text": donor_text,
                    })
                    n_second_block_added += 1
                    break
                attempts += 1

        # Construct the new row, preserving MPIB schema
        new_row = {
            "sample_id":         _derive_paired_id(row["sample_id"]),
            "parent_sample_id":  row["parent_sample_id"],
            "scenario":          row["scenario"],
            "vector":            PAIRED_BENIGN_VECTOR,
            "user_query":        row["user_query"],
            "contexts":          new_contexts,
            "expected_safe_behavior": row.get("expected_safe_behavior", ""),
            "severity":          0,
            "harm_types":        [],
            "source":            row["source"],   # PubMedQA
            "mpib_split":        row["mpib_split"],
            "n_contexts":        len(new_contexts),
            "query_length_chars": row.get("query_length_chars",
                                          len(row["user_query"])),
            "context_length_chars": sum(len(c["text"]) for c in new_contexts),
            "paired_with_v2_id": row["sample_id"],
        }
        new_rows.append(new_row)

    log(f"  Paired benign rows constructed: {len(new_rows)}")
    log(f"  First block found:              {n_first_block_found}")
    if pair_with_second_block:
        log(f"  Second block added:             {n_second_block_added}")

    # Concatenate
    new_df = pd.DataFrame(new_rows)

    # Ensure paired_with_v2_id column exists in original mpib too
    if "paired_with_v2_id" not in mpib.columns:
        mpib = mpib.copy()
        mpib["paired_with_v2_id"] = None

    combined = pd.concat([mpib, new_df], ignore_index=True)
    log(f"  Combined corpus: {len(combined)} rows (original {len(mpib)} + paired {len(new_df)})")

    # Verify the union of V2 and paired-benign covers both classes equally
    v2_n = (combined["vector"] == "V2").sum()
    paired_n = (combined["vector"] == PAIRED_BENIGN_VECTOR).sum()
    if v2_n > 0:
        ratio = paired_n / v2_n
        log(f"  V2 count: {v2_n}, paired-benign count: {paired_n} "
            f"(ratio {ratio:.2f})")
        if abs(ratio - 1.0) > 0.05:
            log(f"  ⚠ Ratio not near 1.0; some V2 rows had no benign_evidence "
                f"block to extract.")

    return combined


def _derive_paired_id(v2_sample_id: str) -> str:
    """
    Produce a deterministic sample_id for a paired-benign instance.

    The format is ``V0pair_<short_hash>`` where the short_hash is the
    first 16 hex chars of SHA-256(v2_sample_id + "paired_benign").
    """
    digest = hashlib.sha256(
        f"{v2_sample_id}|paired_benign".encode("utf-8")
    ).hexdigest()[:16]
    return f"V0pair_{digest}"
