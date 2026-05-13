"""
FPR-targeted threshold calibration (D20, D67).

After training, we evaluate the model on the held-out
`calibration.parquet` (455 pure-benign rows; D47) and select the
threshold τ*(β) that produces each target FPR β. This is the
PromptShield methodology applied to a clinical-safety detector.

For each target β ∈ {0.01, 0.005, 0.001}:

    τ*(β) = inf{ τ : empirical_fpr(scores >= τ) ≤ β }

The "smallest threshold producing FPR ≤ target" definition means we
prefer recall: among thresholds that meet the FPR bound, we pick the
one with the most positive predictions. This matches the deployment
intent — operate as sensitively as the FPR budget allows.

We additionally report the Wilson 95 % CI on the realized FPR at
each threshold. At β = 0.001 with n = 455, the threshold is set by
the top ~5 benign scores, so its calibration uncertainty is wide;
we surface this honestly rather than reporting point estimates only.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from pharmguard.config import CONFIG
from pharmguard.training.dataset import TokenizedDataset


def _wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson 95 % CI for a binomial proportion.

    More accurate than normal approximation for small n or extreme p,
    which is exactly the regime we are in for FPR calibration at the
    0.1 % target.

    Parameters
    ----------
    k : int   number of successes (positive predictions on benign)
    n : int   total trials (benign calibration rows)
    z : float critical value (1.96 for 95 % CI)

    Returns
    -------
    (lower, upper) : tuple[float, float]
    """
    if n == 0:
        return (0.0, 0.0)
    p_hat = k / n
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def find_threshold_at_fpr(
    benign_scores: np.ndarray,
    target_fpr: float,
) -> dict[str, Any]:
    """
    Find the smallest threshold τ producing empirical FPR ≤ target_fpr
    on a pure-benign score array.

    Parameters
    ----------
    benign_scores : np.ndarray of shape (n_benign,)
        Per-instance positive-class probabilities (in [0, 1]) on
        benign calibration data.
    target_fpr : float
        The target FPR β (e.g., 0.001 for 0.1 %).

    Returns
    -------
    dict with:
        target_fpr        the input target
        threshold         the selected τ*(β)
        realized_fpr      k/n at threshold
        wilson_ci_low     Wilson 95 % CI lower bound
        wilson_ci_high    Wilson 95 % CI upper bound
        n_calibration     n (rows used)
        n_false_positives k (benign rows scoring >= threshold)

    Notes
    -----
    The "smallest τ" rule means: sort scores descending; walk from the
    top until the prefix's size as a fraction of n exceeds target_fpr;
    the threshold is the score at the last position that still
    satisfied the bound (one above where it broke).

    If target_fpr * n < 1, the bound cannot be satisfied with any
    threshold below the strict max + epsilon (we'd need fewer than
    one false positive, but with discrete data the next-lowest is one).
    In that case we return τ = max(scores) + epsilon, which trivially
    produces FPR = 0 (no false positives at all), and the CI reflects
    the discreteness.
    """
    n = len(benign_scores)
    if n == 0:
        raise ValueError("Cannot calibrate on empty benign scores.")

    sorted_desc = np.sort(benign_scores)[::-1]

    # k_max = max integer k such that k/n ≤ target_fpr
    # i.e., the largest number of false positives we can afford
    k_max = int(np.floor(target_fpr * n))

    if k_max == 0:
        # Cannot afford any false positives at this target.
        # Threshold = max score + small epsilon so no benign row scores >= τ.
        threshold = float(sorted_desc[0]) + 1e-9
        k_actual = 0
    else:
        # The threshold is the (k_max + 1)-th highest score, i.e., the
        # score immediately *below* the k_max-th highest. We set τ such
        # that exactly the top k_max benign rows score >= τ.
        # Using the score at index k_max-1 (0-indexed top-k_max) as τ
        # means k_actual = k_max (everything with score >= τ counts).
        threshold = float(sorted_desc[k_max - 1])
        k_actual = int((benign_scores >= threshold).sum())

    realized_fpr = k_actual / n
    ci_low, ci_high = _wilson_interval(k_actual, n)

    return {
        "target_fpr": target_fpr,
        "threshold": threshold,
        "realized_fpr": realized_fpr,
        "wilson_ci_low": ci_low,
        "wilson_ci_high": ci_high,
        "n_calibration": n,
        "n_false_positives": k_actual,
    }


@torch.inference_mode()
def score_split(
    model,
    parquet_path: Path,
    device: str = "cuda",
    batch_size: int = 32,
) -> dict[str, np.ndarray]:
    """
    Run the trained model on a Stage 05 tokenized split.

    Returns probability of the positive class (label == 1) for every
    row, alongside the true labels. Used by calibration (benign-only
    split) and by evaluation (any split).

    Parameters
    ----------
    model : transformers.PreTrainedModel  in eval mode
    parquet_path : Path                   tokenized split to score
    device : str                          "cuda" or "cpu"
    batch_size : int                      inference batch size; can be
                                          larger than training since
                                          no gradients are tracked.

    Returns
    -------
    {
        "scores": np.ndarray of shape (n,) — positive-class probabilities,
        "labels": np.ndarray of shape (n,) — ground-truth labels,
    }
    """
    from transformers import DataCollatorWithPadding, AutoTokenizer

    dataset = TokenizedDataset(parquet_path)
    tokenizer = AutoTokenizer.from_pretrained(CONFIG.pharmguard_encoder)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=False,
        collate_fn=collator,
    )

    model.eval()
    model.to(device)

    all_scores: list[np.ndarray] = []
    all_labels: list[np.ndarray] = []

    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
        )
        # logits shape (B, 2); take softmax then column 1 (positive class)
        probs = torch.softmax(outputs.logits, dim=-1)
        all_scores.append(probs[:, 1].detach().cpu().numpy())
        all_labels.append(batch["labels"].detach().cpu().numpy())

    return {
        "scores": np.concatenate(all_scores),
        "labels": np.concatenate(all_labels),
    }


def calibrate_model(
    model,
    calibration_parquet: Path,
    target_fprs: tuple[float, ...] = CONFIG.target_fprs,
    device: str = "cuda",
) -> dict[str, Any]:
    """
    Calibrate the model's decision threshold against a held-out
    pure-benign split at each target FPR.

    Parameters
    ----------
    model : transformers.PreTrainedModel
        Trained model in any state (will be put in eval mode).
    calibration_parquet : Path
        Stage 05 calibration split (pure benign by D47).
    target_fprs : tuple[float, ...]
        Target FPRs to calibrate against. Defaults to
        ``CONFIG.target_fprs`` = (0.01, 0.005, 0.001).
    device : str
        "cuda" or "cpu".

    Returns
    -------
    dict with:
        target_fprs          list[float]
        thresholds           dict[str -> threshold_record]  keys formatted as 'fpr_0.001'
        score_distribution   dict with min/max/p50/p90/p99 of benign scores
        n_calibration        int
    """
    out = score_split(model, calibration_parquet, device=device)
    scores = out["scores"]
    labels = out["labels"]

    # Calibration split must be pure benign — assert this loudly
    n_positive = int((labels == 1).sum())
    if n_positive != 0:
        raise ValueError(
            f"calibration_parquet contains {n_positive} positive labels; "
            f"expected pure-benign (label=0 only). Check Stage 04 (D47)."
        )

    thresholds: dict[str, Any] = {}
    for beta in target_fprs:
        key = f"fpr_{beta:g}"
        thresholds[key] = find_threshold_at_fpr(scores, beta)

    return {
        "target_fprs": list(target_fprs),
        "thresholds": thresholds,
        "score_distribution": {
            "min": float(scores.min()),
            "p50": float(np.median(scores)),
            "p90": float(np.quantile(scores, 0.90)),
            "p99": float(np.quantile(scores, 0.99)),
            "max": float(scores.max()),
            "mean": float(scores.mean()),
            "std": float(scores.std()),
        },
        "n_calibration": int(len(scores)),
    }
