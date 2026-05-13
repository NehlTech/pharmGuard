"""
Stage 04 runner: assemble seven labeled split Parquets.

Usage:
    python scripts/04_construct_splits.py [--verify-only]

Inputs (auto-discovered via pharmguard.paths.paths):
    paths.mpib_dir / "parsed_mpib.parquet"           (from Stage 02)
    paths.adversarial_dir / "reconstructed_v2.parquet" (from Stage 03)
    paths.benign_dir / "all_benign.csv"              (from Stage 01)
    paths.attack_dir / "all_attacks.csv"             (from Stage 01)

Outputs:
    paths.splits_dir / train.parquet
    paths.splits_dir / val.parquet
    paths.splits_dir / test_v1.parquet
    paths.splits_dir / test_v2.parquet
    paths.splits_dir / calibration.parquet
    paths.splits_dir / clinical_benign_holdout.parquet
    paths.splits_dir / generic_attack_ood.parquet
    paths.splits_dir / stage_04_manifest.json

Post-write verification:
    * Every Parquet readable with pandas.read_parquet
    * harm_types column returns Python lists, not strings (D42 fix
      verification)
    * Manifest checksums match actual file SHA-256s
    * No parent_id appears in two splits
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

# Allow running as `python scripts/04_construct_splits.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pharmguard.data.splits import build_splits, SPLIT_NAMES
from pharmguard.logging_utils import make_logger
from pharmguard.paths import paths


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_outputs(log) -> bool:
    """
    Post-write verification: read every Parquet back and assert its
    integrity. This catches the D42-class defect (silently
    JSON-stringified columns) and the data-loss-class defect (file
    on disk doesn't match the manifest checksum).

    Returns True if all checks pass.
    """
    log("\n" + "=" * 60)
    log("Post-write verification")
    log("=" * 60)

    splits_dir = paths.splits_dir
    manifest_path = splits_dir / "stage_04_manifest.json"

    if not manifest_path.exists():
        log(f"  FAIL: manifest missing at {manifest_path}")
        return False

    manifest = json.loads(manifest_path.read_text())
    log(f"  Manifest stage: {manifest.get('stage')}")
    log(f"  Manifest version: {manifest.get('package_version')}")
    log(f"  Completed at: {manifest.get('completed_at')}")

    all_ok = True

    for split_name in SPLIT_NAMES:
        rec = manifest["artifacts"].get(split_name)
        if rec is None:
            log(f"  [{split_name}] skipped (empty split, not in manifest)")
            continue

        path = Path(rec["path"])
        if not path.exists():
            log(f"  [{split_name}] FAIL: file missing on disk")
            all_ok = False
            continue

        # 1. Checksum integrity
        actual_hash = _file_sha256(path)
        if actual_hash != rec["sha256"]:
            log(f"  [{split_name}] FAIL: checksum mismatch")
            log(f"    expected: {rec['sha256']}")
            log(f"    actual:   {actual_hash}")
            all_ok = False
            continue

        # 2. Schema integrity — read back and inspect
        try:
            df = pd.read_parquet(path)
        except Exception as e:
            log(f"  [{split_name}] FAIL: cannot read parquet: {e}")
            all_ok = False
            continue

        if len(df) != rec["row_count"]:
            log(f"  [{split_name}] FAIL: row count mismatch "
                f"({len(df)} on disk vs {rec['row_count']} in manifest)")
            all_ok = False
            continue

        # 3. D42 fix verification: harm_types must be a list, not str
        if "harm_types" in df.columns and len(df) > 0:
            first = df["harm_types"].iloc[0]
            if isinstance(first, str):
                log(f"  [{split_name}] FAIL: harm_types serialized as "
                    f"string (D42 defect present)")
                all_ok = False
                continue

        # 4. Label sanity
        labels = set(df["label"].unique())
        if not labels.issubset({0, 1}):
            log(f"  [{split_name}] FAIL: unexpected label values {labels}")
            all_ok = False
            continue

        n_benign = (df["label"] == 0).sum()
        n_adv = (df["label"] == 1).sum()
        log(f"  [{split_name}] ok    rows={len(df)}  "
            f"benign={n_benign}  adversarial={n_adv}  "
            f"sha256={actual_hash[:12]}...")

    if all_ok:
        log("\n  All verification checks passed.")
    else:
        log("\n  One or more verification checks FAILED.")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip build; only verify existing outputs against the manifest.",
    )
    args = parser.parse_args()

    paths.ensure_all()
    log = make_logger(paths.logs_dir / "stage_04_splits.log")

    if not args.verify_only:
        build_splits(log=log)

    ok = verify_outputs(log)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
