"""
Stage 06A runner — single-seed training.

Usage:
    python scripts/06A_train_single_seed.py [--seed 42] [--config main]

Inputs (auto-discovered):
    paths.tokenized_dir / train.parquet
    paths.tokenized_dir / val.parquet
    paths.tokenized_dir / calibration.parquet

Outputs:
    paths.models_dir / seed_<seed>_config_<config>/
        ├── pytorch_model.bin       (or model.safetensors)
        ├── config.json
        ├── tokenizer files
        ├── training_log.json
        ├── calibration.json
        └── stage_06A_manifest.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pharmguard.logging_utils import make_logger
from pharmguard.paths import paths
from pharmguard.training.loop import train_single_seed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for weight init and data shuffling (default: 42).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="main",
        help=(
            "Config name suffix for the output directory. "
            "'main' for the headline detector; 'noweight' / 'bertbase' / "
            "'distilbert' for ablations (Stage 06C)."
        ),
    )
    parser.add_argument(
        "--encoder",
        type=str,
        default=None,
        help="Override encoder model name (for ablations).",
    )
    args = parser.parse_args()

    paths.ensure_all()
    log = make_logger(
        paths.logs_dir
        / f"stage_06A_train_seed_{args.seed}_{args.config}.log"
    )

    result = train_single_seed(
        seed=args.seed,
        config_name=args.config,
        encoder_name=args.encoder,
        log=log,
    )

    log(
        f"\nTrainResult summary: "
        f"seed={result.seed} config={result.config_name} "
        f"best_epoch={result.best_epoch} best_val_auc={result.best_val_auc:.4f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
