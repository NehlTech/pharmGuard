"""
Stage 05 — Tokenization with measurement gate.

Pre-tokenizes every Stage 04 split with PubMedBERT so Stage 06's
multi-seed training loop does not re-tokenize per batch. Writes
seven Parquets with `input_ids` and `attention_mask` columns
alongside the metadata columns Stage 06's evaluation slicing needs.

Key decisions (see ``docs/decisions.md``):

* **D55** — Tokenizer is ``microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract``,
  paired with the PubMedBERT encoder (Layer 2 of the four-layer
  PharmGuard architecture, locked by D4).
* **D56** — ``max_length=512`` (PubMedBERT's positional embedding
  limit), right-truncation. The detector reads the start of the
  concatenated CDSS string first; if the input is longer than 512
  tokens, the tail is dropped. This is the BERT-standard choice
  and what published baselines (PromptShield, ProtectAI) use.
  Per-vector truncation rate is measured (see §D61) and reported
  in the run summary; if V2 truncation exceeds 25%, this decision
  is revisited.
* **D57** — Output is PyArrow Parquet with native nested types
  (no JSON stringification). The ``input_ids`` and ``attention_mask``
  columns are ``list[int32]``.
* **D58** — No padding at tokenize time. The training dataloader
  in Stage 06 pads dynamically per batch via
  ``DataCollatorWithPadding``.
* **D59** — All 13 Stage 04 columns are preserved, plus ``input_ids``
  and ``attention_mask``, plus measurement columns
  (``token_count``, ``was_truncated``, ``truncated_token_count``).
* **D60** — Tokenization is deterministic; identical input string
  produces byte-identical output across runs and Python sessions.
* **D61** — Per-vector truncation reporting is part of the manifest,
  not just the log. Future analysis can read the manifest and
  reconstruct the truncation rate per slice without rerunning.

Output layout:

    pharma_data/tokenized/
    ├── train.parquet
    ├── val.parquet
    ├── test_v1.parquet
    ├── test_v2.parquet
    ├── calibration.parquet
    ├── clinical_benign_holdout.parquet
    ├── generic_attack_ood.parquet
    └── stage_05_manifest.json

The manifest records, in addition to the per-file checksums:
``tokenizer_name``, ``max_length``, ``truncation_direction``,
per-split row counts, per-split mean/p95/max token length,
per-vector truncation rate, total truncated tokens lost.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pharmguard.data.splits import (
    SPLIT_NAMES,
    _atomic_write_parquet,
    _file_sha256,
)
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths


# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────

TOKENIZER_NAME = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
MAX_LENGTH = 512
TRUNCATION_DIRECTION = "right"

# Truncation-rate threshold for the measurement gate. If any split's
# V2-row truncation rate exceeds this, Stage 05 prints a prominent
# warning in the run summary. The threshold is informational — Stage 05
# does not block the run — but it surfaces the trigger for revisiting
# D56 (right-truncation vs alternatives) early enough to act on it.
V2_TRUNCATION_WARN_THRESHOLD = 0.25


# ─────────────────────────────────────────────────────────
# Schema — Stage 05 output
# ─────────────────────────────────────────────────────────

def stage_05_schema() -> pa.Schema:
    """
    PyArrow schema for every Stage 05 tokenized Parquet.

    Mirrors Stage 04's schema and adds the tokenization columns.
    `input_ids` and `attention_mask` are unpadded ``list[int32]``;
    padding is applied dynamically by the Stage 06 dataloader.
    """
    return pa.schema([
        # ── Identity ──────────────────────────────────
        pa.field("instance_id", pa.string(), nullable=False),
        pa.field("parent_id", pa.string(), nullable=False),
        pa.field("split", pa.string(), nullable=False),

        # ── Source text (preserved for debug / re-tokenization) ──
        pa.field("input_text", pa.large_string(), nullable=False),
        pa.field("input_text_hash", pa.string(), nullable=False),

        # ── Tokenization output ──────────────────────
        pa.field("input_ids", pa.list_(pa.int32()), nullable=False),
        pa.field("attention_mask", pa.list_(pa.int8()), nullable=False),
        pa.field("token_count", pa.int32(), nullable=False),
        pa.field("was_truncated", pa.bool_(), nullable=False),
        pa.field("truncated_token_count", pa.int32(), nullable=False),

        # ── Training target and slicing metadata ─────
        pa.field("label", pa.int8(), nullable=False),
        pa.field("vector", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("scenario", pa.string(), nullable=True),
        pa.field("severity", pa.int8(), nullable=True),
        pa.field("harm_types", pa.list_(pa.string()), nullable=True),
        pa.field("generation_status", pa.string(), nullable=True),
        pa.field("wrapper_template_id", pa.string(), nullable=True),
    ])


# ─────────────────────────────────────────────────────────
# Tokenizer loading
# ─────────────────────────────────────────────────────────

def load_pubmedbert_tokenizer(cache_dir: Path | None = None):
    """
    Load the PubMedBERT tokenizer.

    Caches to ``paths.hf_cache_dir`` by default so subsequent runs
    on the same Drive do not re-download. Uses the fast (Rust-backed)
    tokenizer when available — substantially faster than the Python
    implementation for the ~19K instances we process.
    """
    # Imported here so the module is importable in sandbox contexts
    # that don't have transformers installed
    from transformers import AutoTokenizer

    cache_dir = cache_dir or paths.hf_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_NAME,
        cache_dir=str(cache_dir),
        use_fast=True,
    )

    # Sanity: confirm the tokenizer matches our locked configuration.
    # If a future PubMedBERT release changes the vocab size or special
    # token IDs, downstream comparison with published baselines breaks
    # silently. Explicit checks here surface the change.
    expected_vocab_size = 30522  # PubMedBERT-base vocab
    if tokenizer.vocab_size != expected_vocab_size:
        # Don't raise — log a warning. Vocab size could legitimately
        # change in a future release, and a hard fail would block work
        # that should otherwise proceed. The result_log will record
        # the discrepancy for the methodology audit.
        import warnings
        warnings.warn(
            f"PubMedBERT tokenizer vocab_size={tokenizer.vocab_size}, "
            f"expected {expected_vocab_size}. This may indicate a model "
            f"version change; verify reproducibility against published "
            f"baselines."
        )

    return tokenizer


# ─────────────────────────────────────────────────────────
# Single-row tokenization
# ─────────────────────────────────────────────────────────

def _tokenize_one(
    text: str,
    tokenizer,
    max_length: int = MAX_LENGTH,
) -> dict[str, Any]:
    """
    Tokenize one input string.

    Returns a dict with:
      input_ids               list[int] (unpadded)
      attention_mask          list[int] (unpadded, all 1s)
      token_count             int — len(input_ids)
      was_truncated           bool
      truncated_token_count   int — tokens dropped from the tail
                              (0 if the input fit in max_length)

    The tokenizer runs twice when truncation is in play: once without
    truncation to measure the full length, once with truncation to
    produce the model input. This costs ~2x tokenizer time per long
    instance but is necessary for honest truncation-rate reporting
    (D61). For instances that fit in max_length the first pass is
    enough; we short-circuit.
    """
    # First pass — measure full length without truncation. Disable
    # attention_mask in this pass since we only need length info.
    untruncated = tokenizer(
        text,
        truncation=False,
        padding=False,
        add_special_tokens=True,
        return_attention_mask=False,
    )
    full_length = len(untruncated["input_ids"])

    if full_length <= max_length:
        # Fits — no second pass needed
        return {
            "input_ids": list(untruncated["input_ids"]),
            "attention_mask": [1] * full_length,
            "token_count": full_length,
            "was_truncated": False,
            "truncated_token_count": 0,
        }

    # Truncate from the right (BERT-standard, D56)
    truncated = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        padding=False,
        add_special_tokens=True,
        return_attention_mask=True,
    )
    return {
        "input_ids": list(truncated["input_ids"]),
        "attention_mask": list(truncated["attention_mask"]),
        "token_count": len(truncated["input_ids"]),
        "was_truncated": True,
        "truncated_token_count": full_length - len(truncated["input_ids"]),
    }


# ─────────────────────────────────────────────────────────
# Per-split tokenization with batched fast-path
# ─────────────────────────────────────────────────────────

def tokenize_split(
    split_name: str,
    splits_dir: Path,
    tokenizer,
    log: Callable[..., None],
    max_length: int = MAX_LENGTH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Tokenize one Stage 04 split.

    Returns the tokenized DataFrame and a stats dict that gets
    rolled into the manifest.

    Two-pass strategy is intentional. PubMedBERT's fast tokenizer
    will batch the first (untruncated) pass over many strings in
    parallel; we then call the truncating pass only on the strings
    that need it. For typical corpora most strings fit, so the
    second pass is small.
    """
    path = splits_dir / f"{split_name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Stage 04 split missing: {path}")

    df = pd.read_parquet(path)
    n_rows = len(df)

    if n_rows == 0:
        log(f"  {split_name}: empty split, skipping")
        return df, {
            "rows": 0,
            "truncated_rows": 0,
            "truncation_rate": 0.0,
            "total_truncated_tokens": 0,
            "mean_token_count": 0,
            "p95_token_count": 0,
            "max_token_count": 0,
            "by_vector": {},
        }

    log(f"  {split_name}: tokenizing {n_rows} rows...")

    # First pass: batched untruncated tokenization (length measurement only)
    # The fast tokenizer batches efficiently when given a list. We chunk to
    # bound memory on the rare long-string-heavy split.
    BATCH = 256
    full_lengths: list[int] = []
    untruncated_ids: list[list[int]] = []
    texts = df["input_text"].tolist()
    for i in range(0, n_rows, BATCH):
        batch_texts = texts[i : i + BATCH]
        out = tokenizer(
            batch_texts,
            truncation=False,
            padding=False,
            add_special_tokens=True,
            return_attention_mask=False,
        )
        for ids in out["input_ids"]:
            untruncated_ids.append(list(ids))
            full_lengths.append(len(ids))

    # Determine which rows need truncation
    needs_trunc = [length > max_length for length in full_lengths]
    n_trunc = sum(needs_trunc)
    log(f"  {split_name}: {n_trunc}/{n_rows} rows need truncation "
        f"({100*n_trunc/n_rows:.1f}%)")

    # Second pass: truncating tokenization only on the rows that need it
    input_ids_col: list[list[int]] = []
    attention_mask_col: list[list[int]] = []
    token_count_col: list[int] = []
    was_truncated_col: list[bool] = []
    truncated_count_col: list[int] = []

    if n_trunc > 0:
        trunc_idxs = [i for i, needs in enumerate(needs_trunc) if needs]
        trunc_texts = [texts[i] for i in trunc_idxs]
        trunc_out = tokenizer(
            trunc_texts,
            truncation=True,
            max_length=max_length,
            padding=False,
            add_special_tokens=True,
            return_attention_mask=True,
        )
        trunc_map = {
            idx: {
                "input_ids": list(trunc_out["input_ids"][k]),
                "attention_mask": list(trunc_out["attention_mask"][k]),
            }
            for k, idx in enumerate(trunc_idxs)
        }
    else:
        trunc_map = {}

    for i in range(n_rows):
        full_len = full_lengths[i]
        if needs_trunc[i]:
            t = trunc_map[i]
            input_ids_col.append(t["input_ids"])
            attention_mask_col.append(t["attention_mask"])
            token_count_col.append(len(t["input_ids"]))
            was_truncated_col.append(True)
            truncated_count_col.append(full_len - len(t["input_ids"]))
        else:
            input_ids_col.append(untruncated_ids[i])
            attention_mask_col.append([1] * full_len)
            token_count_col.append(full_len)
            was_truncated_col.append(False)
            truncated_count_col.append(0)

    df_out = df.copy()
    df_out["input_ids"] = input_ids_col
    df_out["attention_mask"] = attention_mask_col
    df_out["token_count"] = token_count_col
    df_out["was_truncated"] = was_truncated_col
    df_out["truncated_token_count"] = truncated_count_col

    # ── Per-vector stats (the measurement gate) ──
    by_vector: dict[str, dict[str, Any]] = {}
    for v in df_out["vector"].unique():
        sub = df_out[df_out["vector"] == v]
        by_vector[v] = {
            "rows": int(len(sub)),
            "truncated_rows": int(sub["was_truncated"].sum()),
            "truncation_rate": float(sub["was_truncated"].mean()),
            "mean_token_count": float(sub["token_count"].mean()),
            "p95_token_count": int(sub["token_count"].quantile(0.95)),
            "max_token_count": int(sub["token_count"].max()),
        }

    stats = {
        "rows": int(n_rows),
        "truncated_rows": int(sum(was_truncated_col)),
        "truncation_rate": float(sum(was_truncated_col) / n_rows),
        "total_truncated_tokens": int(sum(truncated_count_col)),
        "mean_token_count": float(np.mean(token_count_col)),
        "p95_token_count": int(np.quantile(token_count_col, 0.95)),
        "max_token_count": int(max(token_count_col)),
        "by_vector": by_vector,
    }

    log(f"  {split_name}: mean tokens = {stats['mean_token_count']:.0f}, "
        f"p95 = {stats['p95_token_count']}, max = {stats['max_token_count']}")
    return df_out, stats


# ─────────────────────────────────────────────────────────
# Stage 05 orchestrator
# ─────────────────────────────────────────────────────────

@dataclass
class TokenizationResult:
    artifacts: dict[str, Path]
    manifest_path: Path
    stats_by_split: dict[str, dict[str, Any]]


def write_stage_05_manifest(
    written: dict[str, Path],
    stats_by_split: dict[str, dict[str, Any]],
    out_dir: Path,
    log: Callable[..., None],
) -> Path:
    """
    Write stage_05_manifest.json with checksums + tokenization stats.

    Uses fsync (D51) to ensure the manifest is durable before we
    declare the stage complete.
    """
    # Read pharmguard.__version__ dynamically so the manifest doesn't
    # bake in a stale version string the way Stage 04's v0.5.0 did.
    import pharmguard
    pkg_version = pharmguard.__version__

    manifest = {
        "stage": "stage_05_tokenization",
        "stage_version": "1.0",
        "package_version": pkg_version,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "tokenizer_name": TOKENIZER_NAME,
        "max_length": MAX_LENGTH,
        "truncation_direction": TRUNCATION_DIRECTION,
        "artifacts": {},
        "stats_by_split": stats_by_split,
    }

    for split_name, path in written.items():
        manifest["artifacts"][split_name] = {
            "path": str(path),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
            "row_count": stats_by_split[split_name]["rows"],
        }

    manifest_path = out_dir / "stage_05_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    with open(manifest_path, "rb") as f:
        os.fsync(f.fileno())

    log(f"  Manifest written: {manifest_path.name}")

    # Drive sync verification (added after v0.8.0 data loss event)
    try:
        from pharmguard.data.drive_sync import (
            verify_directory_persisted,
            compute_wait_for_size,
        )

        all_files = list(written.values()) + [manifest_path]
        largest_size = max((p.stat().st_size for p in all_files), default=0)
        wait_s = compute_wait_for_size(largest_size)

        expected_files = [p.name for p in all_files]
        verify_directory_persisted(
            dir_path=out_dir,
            expected_files=expected_files,
            wait_s=wait_s,
        )
        log(f"  ✓ Drive persistence verified for {len(expected_files)} files")
    except Exception as e:
        raise RuntimeError(
            f"Stage 05 artifacts did not persist to Drive: {e}. "
            f"Re-run Stage 05 in a fresh session."
        ) from e

    return manifest_path


def build_tokenized_splits(
    splits_dir: Path | None = None,
    out_dir: Path | None = None,
    log: Callable[..., None] | None = None,
) -> TokenizationResult:
    """
    Run the full Stage 05 pipeline.

    All paths default to the canonical project locations from
    ``pharmguard.paths.paths``.
    """
    if log is None:
        log_file = paths.logs_dir / "stage_05_tokenization.log"
        log = make_logger(log_file)

    splits_dir = splits_dir or paths.splits_dir
    out_dir = out_dir or paths.tokenized_dir
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Verify Stage 04 outputs are present
    missing = [
        s for s in SPLIT_NAMES
        if not (Path(splits_dir) / f"{s}.parquet").exists()
    ]
    if missing:
        raise FileNotFoundError(
            f"Stage 04 outputs missing for splits: {missing}\n"
            f"Run scripts/04_construct_splits.py first."
        )

    section(log, "Stage 05 — Tokenization")

    log(f"\n[1/3] Loading PubMedBERT tokenizer")
    log(f"  Model: {TOKENIZER_NAME}")
    log(f"  Max length: {MAX_LENGTH}")
    log(f"  Truncation direction: {TRUNCATION_DIRECTION}")
    tokenizer = load_pubmedbert_tokenizer()
    log(f"  Vocab size: {tokenizer.vocab_size}")
    log(f"  Special tokens: CLS={tokenizer.cls_token_id} "
        f"SEP={tokenizer.sep_token_id} PAD={tokenizer.pad_token_id}")

    log(f"\n[2/3] Tokenizing seven splits")
    schema = stage_05_schema()
    artifacts: dict[str, Path] = {}
    stats_by_split: dict[str, dict[str, Any]] = {}

    for split_name in SPLIT_NAMES:
        df_tok, stats = tokenize_split(
            split_name=split_name,
            splits_dir=Path(splits_dir),
            tokenizer=tokenizer,
            log=log,
            max_length=MAX_LENGTH,
        )
        stats_by_split[split_name] = stats

        if stats["rows"] == 0:
            log(f"  {split_name}: empty, skipping write")
            continue

        # Atomic write via the helper from splits.py (D51)
        dest = out_dir / f"{split_name}.parquet"
        _atomic_write_parquet(df_tok, dest, schema)
        artifacts[split_name] = dest
        size_kb = dest.stat().st_size // 1024
        log(f"  {split_name}: wrote {dest.name} ({size_kb} KB)")

    log(f"\n[3/3] Writing manifest and final summary")
    manifest_path = write_stage_05_manifest(
        written=artifacts,
        stats_by_split=stats_by_split,
        out_dir=out_dir,
        log=log,
    )

    # ── Final summary with the D56 measurement gate ──
    log(f"\n{'=' * 60}")
    log(f"✓ STAGE 05 COMPLETE")
    log(f"{'=' * 60}")
    log(f"  Artifacts written:      {len(artifacts)}")
    log(f"  Manifest:               {manifest_path}")

    total_rows = sum(s["rows"] for s in stats_by_split.values())
    total_trunc = sum(s["truncated_rows"] for s in stats_by_split.values())
    log(f"  Total rows tokenized:   {total_rows}")
    log(f"  Total truncated:        {total_trunc} ({100*total_trunc/total_rows:.1f}%)")

    log(f"\n  Per-split summary:")
    log(f"    {'split':<32} {'rows':>6} {'trunc%':>7} {'mean':>5} {'p95':>5} {'max':>5}")
    for split_name in SPLIT_NAMES:
        s = stats_by_split[split_name]
        if s["rows"] == 0:
            continue
        log(f"    {split_name:<32} {s['rows']:>6} "
            f"{100*s['truncation_rate']:>6.1f}% "
            f"{s['mean_token_count']:>5.0f} "
            f"{s['p95_token_count']:>5} "
            f"{s['max_token_count']:>5}")

    # ── D56 measurement gate ──
    # Surface per-vector V2 truncation rates and warn if any exceeds
    # the threshold. This is informational, not blocking; Stage 05
    # completes either way and the user decides whether to revisit D56.
    log(f"\n  Per-vector V2 truncation rates (D56 measurement gate):")
    log(f"    threshold = {100*V2_TRUNCATION_WARN_THRESHOLD:.0f}%; "
        f"warns if exceeded")
    any_warned = False
    for split_name in SPLIT_NAMES:
        s = stats_by_split[split_name]
        v2_stats = s["by_vector"].get("V2")
        if v2_stats is None or v2_stats["rows"] == 0:
            continue
        rate = v2_stats["truncation_rate"]
        marker = "⚠ EXCEEDS" if rate > V2_TRUNCATION_WARN_THRESHOLD else "  OK"
        log(f"    {marker:<10} {split_name:<32} V2 truncation rate: "
            f"{100*rate:.1f}% ({v2_stats['truncated_rows']}/{v2_stats['rows']})")
        if rate > V2_TRUNCATION_WARN_THRESHOLD:
            any_warned = True

    if any_warned:
        log(f"\n  ⚠ At least one split exceeded the V2 truncation threshold.")
        log(f"    Consider revisiting D56 (right-truncation vs alternatives).")
        log(f"    Stage 05 completes; decision is left to the user.")
    else:
        log(f"\n  ✓ All V2 truncation rates within threshold.")

    return TokenizationResult(
        artifacts=artifacts,
        manifest_path=manifest_path,
        stats_by_split=stats_by_split,
    )
