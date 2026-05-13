#!/usr/bin/env python3
"""
Stage 03B — Generate benign imperative retrieved-content blocks
with Phi-3-mini for D75 augmentation pool.

Produces ``pharma_data/adversarial/benign_imperatives_v0.parquet``
with ~250 accepted blocks (after safety screening).

This stage runs ONCE per major version. Output is loaded by Stage 04.
Re-running this script regenerates the pool, but Stage 04 will
otherwise read the cached parquet without invoking Phi-3.

Estimated wall-clock on L4 GPU:
  - Phi-3-mini load: ~30 sec
  - Generation: ~5 sec × 250 generations = ~21 min
  - Save + verify: ~5 sec
  Total: ~22 min

Usage:
    python scripts/03B_generate_benign_imperatives.py
    python scripts/03B_generate_benign_imperatives.py --n 250 --seed 42
"""

import argparse
import sys
from pathlib import Path

# Ensure pharmguard is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pharmguard.data.benign_phi3_generation import (
    build_phi3_benign_pool,
    save_phi3_benign_pool,
)
from pharmguard.data.reconstruction.core import PhiGenerator
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=250,
                        help="number of generations to attempt "
                             "(some will be rejected by safety screen)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None,
                        help="output parquet path")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    out_path = Path(
        args.out
        or (paths.adversarial_dir / "benign_imperatives_v0.parquet")
    )

    log = make_logger(paths.logs_dir / "stage_03B_benign_imperatives.log")
    section(log, "Stage 03B — Phi-3 Benign-Imperative Generation")

    log(f"  Target generations:  {args.n}")
    log(f"  Seed:                {args.seed}")
    log(f"  Output path:         {out_path}")
    log(f"  Max new tokens:      {args.max_new_tokens}")

    log(f"\n[1/3] Loading Phi-3-mini")
    generator = PhiGenerator()
    log(f"  Phi-3-mini loaded onto device: {generator.model.device}")

    log(f"\n[2/3] Generating benign imperative blocks")
    results = build_phi3_benign_pool(
        generator=generator,
        n=args.n,
        seed=args.seed,
        log=log,
        max_new_tokens=args.max_new_tokens,
    )

    log(f"\n[3/3] Saving + verifying Drive persistence")
    save_phi3_benign_pool(results, out_path, log)

    # Verify on Drive (D74 drive_sync infrastructure)
    try:
        from pharmguard.data.drive_sync import (
            assert_drive_persisted,
            compute_wait_for_size,
        )

        expected_size = out_path.stat().st_size
        wait_s = compute_wait_for_size(expected_size)
        log(f"  Verifying Drive persistence (size={expected_size/1024:.1f} KB, "
            f"wait_s={wait_s}s)")
        verification = assert_drive_persisted(
            path=out_path,
            expected_size=expected_size,
            wait_s=wait_s,
        )
        log(f"  ✓ Verified on Drive at {verification['path']}")
    except Exception as e:
        log(f"  ⚠ Drive verification failed: {e}")
        log(f"  ⚠ Local write succeeded but persistence not confirmed; "
            f"rerun Stage 03B before relying on the output.")

    log(f"\n{'=' * 60}")
    log(f"✓ STAGE 03B COMPLETE")
    log(f"{'=' * 60}")

    n_accepted = sum(1 for r in results if r["accepted"])
    log(f"  Total attempts:     {len(results)}")
    log(f"  Accepted:           {n_accepted}")
    log(f"  Output:             {out_path}")


if __name__ == "__main__":
    main()
