"""
Stage 06A — single-seed training loop.

Uses HuggingFace's ``Trainer`` (D65) with:

* A ``WeightedTrainer`` subclass that applies class-weighted
  cross-entropy loss (D64; weights from CONFIG.weight_benign /
  weight_attack).
* A ``compute_metrics`` callback computing val AUC (D66) and the
  classification metrics we'll want for sanity-checking.
* Early stopping on best val AUC (D66), checkpointing the best
  weights and discarding the rest.
* Deterministic seeding via ``set_all_seeds`` (D69).

Output artifacts (per (seed, config) combination):

    pharma_models/seed_<seed>_config_<config>/
    ├── pytorch_model.bin       Best-val-AUC weights
    ├── config.json             HuggingFace model config
    ├── tokenizer/              Bundled tokenizer files
    ├── training_log.json       Per-epoch metrics
    ├── calibration.json        Thresholds at target FPRs (D67)
    └── stage_06A_manifest.json SHA-256s of every artifact

The training loop is kept intentionally close to standard HuggingFace
patterns so that switching to BERT-base or DistilBERT for ablations
(Stage 06C) is a single config change rather than a code change.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from pharmguard.config import CONFIG
from pharmguard.logging_utils import make_logger, section
from pharmguard.model.architecture import build_pharmguard_model
from pharmguard.paths import paths
from pharmguard.seeds import set_all_seeds
from pharmguard.training.calibration import calibrate_model
from pharmguard.training.dataset import TokenizedDataset


# ─────────────────────────────────────────────────────────
# Weighted Trainer subclass (D64)
# ─────────────────────────────────────────────────────────

def _build_weighted_trainer_class(class_weights: torch.Tensor):
    """
    Build a Trainer subclass with class-weighted CE loss bound in.

    We define the class lazily inside this factory so that
    `transformers.Trainer` is only imported when actually training,
    not at module-import time (keeps the rest of `pharmguard` import-
    able in environments without transformers).
    """
    from transformers import Trainer

    class WeightedTrainer(Trainer):
        """Trainer with class-weighted cross-entropy loss (D64)."""

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            logits = outputs.logits  # (B, num_labels)

            # F.cross_entropy with weight= applies the class weights
            # along the class dimension. Moves the weight tensor to
            # the logits' device on each call (cheap; same device after
            # the first batch).
            weight = class_weights.to(logits.device)
            loss = F.cross_entropy(logits, labels, weight=weight)

            if return_outputs:
                # Trainer's expected signature when return_outputs=True
                return loss, outputs
            return loss

    return WeightedTrainer


# ─────────────────────────────────────────────────────────
# Eval-time metric computation (D66)
# ─────────────────────────────────────────────────────────

def _compute_metrics(eval_pred) -> dict[str, float]:
    """
    Per-epoch metrics computed on the val split.

    Headline: val_auc (D66 — the metric driving early stopping).
    Also reports accuracy, precision/recall/F1 at the default
    threshold (0.5) for sanity checking.

    Returns
    -------
    dict[str, float]
        Metric names → values. HuggingFace prepends "eval_" to every
        key when used as the early-stopping signal.
    """
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support, roc_auc_score,
    )

    logits, labels = eval_pred
    # logits shape: (N, 2). Apply softmax to get probabilities.
    # NOTE: numpy stable softmax to avoid overflow on extreme logits.
    e = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs = e / e.sum(axis=-1, keepdims=True)
    pos_scores = probs[:, 1]

    predictions = (pos_scores >= 0.5).astype(np.int64)

    # AUC requires both classes present; sklearn raises otherwise.
    # Val should have both per D53/integration check, but be defensive.
    try:
        auc = float(roc_auc_score(labels, pos_scores))
    except ValueError:
        auc = float("nan")

    acc = float(accuracy_score(labels, predictions))
    p, r, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0,
    )

    return {
        "auc": auc,
        "accuracy": acc,
        "precision": float(p),
        "recall": float(r),
        "f1": float(f1),
    }


# ─────────────────────────────────────────────────────────
# Determinism configuration (D69)
# ─────────────────────────────────────────────────────────

def _configure_determinism(seed: int) -> None:
    """
    Set every RNG and enable deterministic CUDA. Called once at the
    start of each training run, before any model or dataloader is
    instantiated.
    """
    set_all_seeds(seed, deterministic=True)
    # set_all_seeds already handles torch.cudnn.{deterministic,benchmark}.
    # We additionally tell PyTorch to use deterministic algorithms where
    # available. CUBLAS_WORKSPACE_CONFIG is required for full determinism
    # on some CUDA ops.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except (AttributeError, RuntimeError):
        # Older PyTorch: signature differs. Best-effort.
        pass


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

@dataclass
class TrainResult:
    """Summary of one training run."""
    seed: int
    config_name: str
    model_dir: Path
    manifest_path: Path
    best_epoch: int
    best_val_auc: float
    final_calibration: dict[str, Any]
    training_log: list[dict[str, Any]] = field(default_factory=list)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_stage_06A_manifest(
    out_dir: Path,
    seed: int,
    config_name: str,
    encoder_name: str,
    training_args: dict[str, Any],
    best_epoch: int,
    best_val_auc: float,
    calibration: dict[str, Any],
    training_log: list[dict[str, Any]],
    artifact_paths: list[Path],
    log: Callable[..., None],
) -> Path:
    """Write the run manifest with SHA-256s of every artifact."""
    import pharmguard

    manifest = {
        "stage": "stage_06A_train_single_seed",
        "stage_version": "1.0",
        "package_version": pharmguard.__version__,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "config_name": config_name,
        "encoder_name": encoder_name,
        "training_args": training_args,
        "best_epoch": best_epoch,
        "best_val_auc": best_val_auc,
        "calibration": calibration,
        "training_log": training_log,
        "artifacts": {},
    }
    for p in artifact_paths:
        if not p.exists():
            continue
        rel = p.name
        manifest["artifacts"][rel] = {
            "path": str(p),
            "sha256": _file_sha256(p),
            "size_bytes": p.stat().st_size,
        }

    manifest_path = out_dir / "stage_06A_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    with open(manifest_path, "rb") as f:
        os.fsync(f.fileno())
    log(f"  Manifest written: {manifest_path.name}")
    return manifest_path


def train_single_seed(
    seed: int = 42,
    config_name: str = "main",
    encoder_name: str | None = None,
    log: Callable[..., None] | None = None,
) -> TrainResult:
    """
    Run one Stage 06A training to completion.

    Parameters
    ----------
    seed : int
        RNG seed for weight init + data shuffling (D69).
    config_name : str
        Label distinguishing this run from ablations. Becomes part of
        the output directory name (D68).
    encoder_name : str, optional
        Override CONFIG.pharmguard_encoder; used by Stage 06C
        ablations (BERT-base, DistilBERT).
    log : Callable, optional
        Logger; defaults to file logger at
        ``logs_dir/stage_06A_train_seed_<seed>_<config>.log``.

    Returns
    -------
    TrainResult
    """
    # Imported here so the module is importable without transformers.
    from transformers import (
        AutoTokenizer, DataCollatorWithPadding,
        EarlyStoppingCallback, TrainingArguments,
    )

    if log is None:
        log_file = (
            paths.logs_dir
            / f"stage_06A_train_seed_{seed}_{config_name}.log"
        )
        log = make_logger(log_file)

    encoder_name = encoder_name or CONFIG.pharmguard_encoder
    out_dir = paths.models_dir / f"seed_{seed}_config_{config_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    section(log, f"Stage 06A — Training (seed={seed}, config={config_name})")
    log(f"\n[1/6] Configuring determinism (seed={seed})")
    _configure_determinism(seed)

    log(f"\n[2/6] Loading tokenized splits")
    train_path = paths.tokenized_dir / "train.parquet"
    val_path = paths.tokenized_dir / "val.parquet"
    cal_path = paths.tokenized_dir / "calibration.parquet"
    for p in [train_path, val_path, cal_path]:
        if not p.exists():
            raise FileNotFoundError(
                f"Stage 05 output missing: {p}. Run Stage 05 first."
            )
    train_ds = TokenizedDataset(train_path)
    val_ds = TokenizedDataset(val_path)
    log(f"  train: {len(train_ds)} rows")
    log(f"  val:   {len(val_ds)} rows")

    log(f"\n[3/6] Building model from {encoder_name}")
    model = build_pharmguard_model(encoder_name=encoder_name)
    n_params = sum(p.numel() for p in model.parameters())
    log(f"  total parameters: {n_params:,}")

    log(f"\n[4/6] Configuring trainer")
    tokenizer = AutoTokenizer.from_pretrained(encoder_name)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    class_weights = torch.tensor(
        [CONFIG.weight_benign, CONFIG.weight_attack], dtype=torch.float
    )
    log(f"  class weights: [benign={CONFIG.weight_benign}, "
        f"attack={CONFIG.weight_attack}]  (D21, D64)")

    training_args = TrainingArguments(
        output_dir=str(out_dir / "_trainer_workdir"),
        num_train_epochs=CONFIG.num_epochs,
        per_device_train_batch_size=CONFIG.batch_size,
        per_device_eval_batch_size=CONFIG.batch_size * 2,
        learning_rate=CONFIG.learning_rate,
        weight_decay=CONFIG.weight_decay,
        warmup_ratio=CONFIG.warmup_ratio,
        max_grad_norm=CONFIG.max_grad_norm,
        # Eval + checkpoint at the end of every epoch
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,           # keep only best per save_strategy
        load_best_model_at_end=True,
        metric_for_best_model="auc",  # D66 — best val AUC
        greater_is_better=True,
        seed=seed,
        data_seed=seed,
        logging_steps=50,
        report_to=[],  # no wandb / tensorboard for v1.0
        disable_tqdm=False,
        fp16=torch.cuda.is_available(),  # mixed-precision on GPU
    )

    WeightedTrainer = _build_weighted_trainer_class(class_weights)
    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        compute_metrics=_compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=1)],
    )

    log(f"  training arguments:")
    log(f"    epochs:               {CONFIG.num_epochs}")
    log(f"    train batch size:     {CONFIG.batch_size}")
    log(f"    learning rate:        {CONFIG.learning_rate}")
    log(f"    weight decay:         {CONFIG.weight_decay}")
    log(f"    warmup ratio:         {CONFIG.warmup_ratio}")
    log(f"    mixed precision:      {training_args.fp16}")
    log(f"    early stopping on:    val_auc (patience=1)")

    log(f"\n[5/6] Training")
    train_output = trainer.train()
    log(f"  training complete")
    log(f"  global_step:     {train_output.global_step}")
    log(f"  training_loss:   {train_output.training_loss:.4f}")

    # Inspect the trainer's log history to record per-epoch metrics
    training_log: list[dict[str, Any]] = []
    best_val_auc = float("-inf")
    best_epoch = -1
    for entry in trainer.state.log_history:
        if "eval_auc" in entry:
            ep = int(entry.get("epoch", -1))
            auc = float(entry["eval_auc"])
            training_log.append({
                "epoch": ep,
                "eval_auc": auc,
                "eval_loss": float(entry.get("eval_loss", float("nan"))),
                "eval_accuracy": float(entry.get("eval_accuracy", float("nan"))),
                "eval_precision": float(entry.get("eval_precision", float("nan"))),
                "eval_recall": float(entry.get("eval_recall", float("nan"))),
                "eval_f1": float(entry.get("eval_f1", float("nan"))),
            })
            if auc > best_val_auc:
                best_val_auc = auc
                best_epoch = ep

    log(f"  best epoch:      {best_epoch}")
    log(f"  best val AUC:    {best_val_auc:.4f}")

    log(f"\n[6/6] Saving best model + calibrating + writing manifest")
    # Save the (already-loaded-best) model to a clean directory next to
    # the Trainer's workdir, so downstream code reads from a clean path.
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    log(f"  best model + tokenizer saved to: {out_dir}")

    # Remove the Trainer's workdir (intermediate checkpoints, optimizer
    # state) — we have what we need. This keeps the per-seed footprint
    # bounded on Drive.
    workdir = out_dir / "_trainer_workdir"
    if workdir.exists():
        shutil.rmtree(workdir)
        log(f"  removed intermediate trainer workdir")

    # Calibrate against held-out benign
    log(f"\n  calibrating against {cal_path.name}...")
    calibration = calibrate_model(
        model=trainer.model,
        calibration_parquet=cal_path,
    )
    cal_path_out = out_dir / "calibration.json"
    cal_path_out.write_text(json.dumps(calibration, indent=2, default=str))
    with open(cal_path_out, "rb") as f:
        os.fsync(f.fileno())
    log(f"  calibration written: {cal_path_out.name}")
    for fpr_key, rec in calibration["thresholds"].items():
        log(f"    {fpr_key:<14} threshold={rec['threshold']:.4f}  "
            f"realized FPR={rec['realized_fpr']:.4f}  "
            f"CI=[{rec['wilson_ci_low']:.4f}, {rec['wilson_ci_high']:.4f}]")

    # Training log
    log_path = out_dir / "training_log.json"
    log_path.write_text(json.dumps(training_log, indent=2, default=str))
    with open(log_path, "rb") as f:
        os.fsync(f.fileno())
    log(f"  training_log written: {log_path.name}")

    # Manifest with checksums for everything in out_dir.
    # We exclude the manifest file itself from artifact_paths — including
    # it would create a self-reference: the manifest contains a SHA-256
    # of every listed artifact, and the manifest containing its own
    # SHA-256 would have a different SHA-256 once written to disk (the
    # file changes when we write into it). The Stage 06A integration
    # check caught this in the v0.7.2 run as a single checksum mismatch.
    artifact_paths = [
        p for p in out_dir.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.name != "stage_06A_manifest.json"
    ]
    manifest_path = _write_stage_06A_manifest(
        out_dir=out_dir,
        seed=seed,
        config_name=config_name,
        encoder_name=encoder_name,
        training_args={
            "num_train_epochs": CONFIG.num_epochs,
            "batch_size": CONFIG.batch_size,
            "learning_rate": CONFIG.learning_rate,
            "weight_decay": CONFIG.weight_decay,
            "warmup_ratio": CONFIG.warmup_ratio,
            "class_weights": [CONFIG.weight_benign, CONFIG.weight_attack],
            "early_stopping_patience": 1,
            "metric_for_best_model": "auc",
            "fp16": training_args.fp16,
        },
        best_epoch=best_epoch,
        best_val_auc=best_val_auc,
        calibration=calibration,
        training_log=training_log,
        artifact_paths=artifact_paths,
        log=log,
    )

    # ── Drive sync verification (added after v0.8.0 data loss) ──
    # The trained model is ~437 MB; Drive's async sync can drop large
    # writes silently if the runtime ends before sync completes. We
    # explicitly force a sync, wait, and re-verify every listed
    # artifact is on Drive before declaring the stage complete.
    log(f"\n  Verifying Drive persistence of Stage 06A artifacts...")
    try:
        from pharmguard.data.drive_sync import (
            verify_directory_persisted,
            compute_wait_for_size,
        )

        # Pick wait time based on the largest artifact (the model
        # safetensors at ~437 MB drives this).
        largest_size = max(
            (p.stat().st_size for p in artifact_paths), default=0
        )
        wait_s = compute_wait_for_size(largest_size)
        log(f"    largest artifact: {largest_size/1024/1024:.1f} MB; "
            f"using wait_s = {wait_s}s")

        expected_files = [p.name for p in artifact_paths] + [
            "stage_06A_manifest.json"
        ]
        verification = verify_directory_persisted(
            dir_path=out_dir,
            expected_files=expected_files,
            wait_s=wait_s,
        )
        log(f"    ✓ All {len(expected_files)} artifacts verified on Drive")
        log(f"    ✓ Directory total: "
            f"{sum(v['size'] for v in verification['files'].values())/1024/1024:.1f} MB")
    except Exception as e:
        # Re-raise with a clearer error message. The trained model
        # is in memory; the caller could decide to retry the save.
        log(f"    ✗ Drive verification failed: {e}")
        raise RuntimeError(
            f"Stage 06A artifacts did not persist to Drive: {e}. "
            f"Model weights may not survive a session restart. "
            f"Retry the save or run Stage 06A again in a fresh session."
        ) from e

    log(f"\n{'=' * 60}")
    log(f"✓ STAGE 06A COMPLETE (seed={seed}, config={config_name})")
    log(f"{'=' * 60}")
    log(f"  Model directory:    {out_dir}")
    log(f"  Best epoch:         {best_epoch}")
    log(f"  Best val AUC:       {best_val_auc:.4f}")
    log(f"  Manifest:           {manifest_path}")

    return TrainResult(
        seed=seed,
        config_name=config_name,
        model_dir=out_dir,
        manifest_path=manifest_path,
        best_epoch=best_epoch,
        best_val_auc=best_val_auc,
        final_calibration=calibration,
        training_log=training_log,
    )
