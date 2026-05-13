"""
Stage 01 — Pharmaceutical data acquisition.

Pulls four sources of clinical benign text and two sources of generic
attack text. Generic attacks are used ONLY as an out-of-distribution
probe in paper section 6.5; clinical IPI training data comes from
MPIB (stage 02).

Usage
-----
    !cd /content/pharmguard && python scripts/01_acquire_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pharmguard.config import CONFIG
from pharmguard.data.attacks import acquire_all_attacks
from pharmguard.data.benign import acquire_all_benign
from pharmguard.paths import paths


def main() -> int:
    print("=" * 60)
    print("PHARMGUARD STAGE 01 — DATA ACQUISITION")
    print("=" * 60)
    print(f"Project root: {paths.root}")

    ok, msg = paths.verify_root_writable()
    if not ok:
        print(f"\n✗ {msg}")
        print("\nRun scripts/00_setup.py first.")
        return 1

    benign_df, _ = acquire_all_benign(seed=CONFIG.seeds[0])
    print()
    attack_df, _ = acquire_all_attacks(seed=CONFIG.seeds[0])

    print()
    print("=" * 60)
    print("✓ STAGE 01 COMPLETE")
    print("=" * 60)
    print(f"  Benign samples: {len(benign_df):,}")
    print(f"  Attack samples: {len(attack_df):,} (OOD probe)")
    print()
    print("Next: scripts/02_acquire_mpib.py (MPIB pull + EDA)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
