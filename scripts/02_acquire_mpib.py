"""
Stage 02 — MPIB acquisition and EDA.

Pulls the Medical Prompt Injection Benchmark from Hugging Face and
runs the ten-pass EDA that informs every downstream stage.

Prerequisites
-------------
* You have signed in at huggingface.co
* You have visited the dataset page and clicked
  "Agree and access repository":
      https://huggingface.co/datasets/jhlee0619/mpib
* Your HF read token is saved at:
      /content/drive/MyDrive/pharmguard/.hf_token

Usage
-----
    !cd /content/pharmguard && python scripts/02_acquire_mpib.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pharmguard.config import CONFIG
from pharmguard.data.mpib import acquire_mpib
from pharmguard.paths import paths


def main() -> int:
    print("=" * 60)
    print("PHARMGUARD STAGE 02 — MPIB ACQUISITION + EDA")
    print("=" * 60)
    print(f"Project root: {paths.root}")

    ok, msg = paths.verify_root_writable()
    if not ok:
        print(f"\n✗ {msg}")
        print("\nRun scripts/00_setup.py first.")
        return 1

    try:
        df, eda = acquire_mpib(seed=CONFIG.seeds[0])
    except FileNotFoundError as e:
        print(str(e))
        return 1

    print()
    print("=" * 60)
    print("✓ STAGE 02 COMPLETE")
    print("=" * 60)
    print(f"  Total instances:    {eda['n_total']:,}")
    print(f"  Vector counts:      {eda['vector_distribution']}")
    redaction_rate = eda["v2_redaction_audit"]["fraction_redacted"] * 100
    print(f"  V2 redaction rate:  {redaction_rate:.1f}%")
    print()
    print("Next: scripts/03_reconstruct_payloads.py")
    print("  (will be added after we review the EDA findings together)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
