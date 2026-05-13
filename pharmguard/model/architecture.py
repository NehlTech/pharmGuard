"""
PharmGuard model architecture (Layers 1 + 2 + 3 of the four-layer
architecture locked in D4).

For v1.0 (D63):
* Layer 1 (Φ): identity. The adversarial canonicalization stub is
  documented in methodology §4.1; non-trivial Φ is reserved for a
  later ablation.
* Layer 2 (E_θ): PubMedBERT encoder (config.pharmguard_encoder),
  fine-tuned on the binary classification objective.
* Layer 3 (D_τ): linear classification head over the [CLS] pooled
  output, num_labels=2. The threshold τ is selected post-training
  by the calibration module against target FPRs.
* Layer 4 (R): inference-time routing logic — not part of the
  trainable model, applied in Stage 07 evaluation.

This module returns the standard HuggingFace
`AutoModelForSequenceClassification` instance, which already implements
the encoder + classification head pattern. We keep it intentionally
thin so that ablations (BERT-base, DistilBERT) can use the same
`build_pharmguard_model(encoder_name=...)` entry point.
"""

from __future__ import annotations

from pharmguard.config import CONFIG


def build_pharmguard_model(
    encoder_name: str | None = None,
    num_labels: int | None = None,
    dropout: float | None = None,
):
    """
    Build the trainable PharmGuard model.

    Parameters
    ----------
    encoder_name : str, optional
        HuggingFace model identifier for the encoder. Defaults to
        ``CONFIG.pharmguard_encoder``.
    num_labels : int, optional
        Number of output classes. Defaults to ``CONFIG.num_classes``.
    dropout : float, optional
        Classification-head dropout. Defaults to ``CONFIG.dropout``.

    Returns
    -------
    transformers.PreTrainedModel
        A model ready for training. Its ``.config.num_labels`` is set
        to ``num_labels``; its ``.config.problem_type`` is
        ``"single_label_classification"``.

    Notes
    -----
    The encoder weights are loaded with ``from_pretrained``, which
    downloads them on first run and caches them in ``hf_cache_dir``.
    The classification head is randomly initialized; the seeding (D69)
    governs its initial weights.
    """
    # Imported here to keep this module importable in environments
    # without transformers (e.g., during AST or doc tooling).
    from transformers import AutoModelForSequenceClassification

    encoder_name = encoder_name or CONFIG.pharmguard_encoder
    num_labels = num_labels or CONFIG.num_classes
    dropout = dropout if dropout is not None else CONFIG.dropout

    model = AutoModelForSequenceClassification.from_pretrained(
        encoder_name,
        num_labels=num_labels,
        problem_type="single_label_classification",
        hidden_dropout_prob=dropout,
        attention_probs_dropout_prob=dropout,
    )
    return model
