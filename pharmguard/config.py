"""
PharmGuard configuration.

A single frozen dataclass holds every hyperparameter the pipeline needs.
Frozen so that experiment scripts cannot mutate it accidentally, which
would silently invalidate multi-seed comparisons.

If you need to override a setting for an experiment, derive a new
config with `dataclasses.replace(CONFIG, ...)` rather than mutating.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PharmGuardConfig:
    """Single source of truth for hyperparameters."""

    # ── Encoders ──────────────────────────────────────────
    # Must match the tokenizer used in Stage 05 (D55). The "abstract"
    # variant was selected for Stage 05; the "-abstract-fulltext"
    # variant has a different vocabulary and would mismatch tokenization.
    pharmguard_encoder: str = (
        "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
    )
    standard_bert: str = "bert-base-uncased"        # baseline
    distilbert: str = "distilbert-base-uncased"     # ablation

    # ── Off-the-shelf detector baselines (4) ──────────────
    baseline_protectai: str = "protectai/deberta-v3-base-prompt-injection-v2"
    baseline_injecguard: str = "leolee99/InjecGuard"
    baseline_promptguard: str = "meta-llama/Prompt-Guard-86M"
    baseline_fmops: str = "fmops/distilbert-prompt-injection"

    # ── Tokenization ──────────────────────────────────────
    max_length: int = 512

    # ── Architecture ──────────────────────────────────────
    dropout: float = 0.1
    num_classes: int = 2

    # ── Training ──────────────────────────────────────────
    batch_size: int = 16
    num_epochs: int = 3
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    max_grad_norm: float = 1.0

    # ── Class weights (Layer 3 asymmetric harm penalty) ───
    weight_benign: float = 1.0
    weight_attack: float = 3.0

    # ── Layer 4: Confidence-Aware Routing ─────────────────
    routing_tau_low: float = 0.40   # below: route to benign
    routing_tau_high: float = 0.60  # above: route to block
                                    # between: escalate to human

    # ── Default detection threshold ───────────────────────
    detection_threshold: float = 0.5

    # ── Multi-seed reproducibility ────────────────────────
    seeds: tuple = (42, 123, 456, 789, 2024)

    # ── Target FPRs for calibrated reporting ──────────────
    target_fprs: tuple = (0.01, 0.005, 0.001)  # 1%, 0.5%, 0.1%

    def to_dict(self) -> dict:
        return asdict(self)


# Singleton — import this directly
CONFIG = PharmGuardConfig()
N_SEEDS = len(CONFIG.seeds)
