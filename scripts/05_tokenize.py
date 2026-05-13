"""
Stage 05 runner: tokenize all seven Stage 04 splits with PubMedBERT.

Usage:
    python scripts/05_tokenize.py [--verify-only]

Inputs (auto-discovered):
    paths.splits_dir / *.parquet     (seven Stage 04 outputs)

Outputs:
    paths.tokenized_dir / train.parquet
    paths.tokenized_dir / val.parquet
    paths.tokenized_dir / test_v1.parquet
    paths.tokenized_dir / test_v2.parquet
    paths.tokenized_dir / calibration.parquet
    paths.tokenized_dir / clinical_benign_holdout.parquet
    paths.tokenized_dir / generic_attack_ood.parquet
    paths.tokenized_dir / stage_05_manifest.json

Post-write verification:
    * Every Parquet readable
    * input_ids and attention_mask are list[int], not strings (D42 fix verified)
    * input_ids length == attention_mask length per row
    * token_count == len(input_ids) per row
    * Manifest checksums match files on disk
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

# Allow running as `python scripts/05_tokenize.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pharmguard.data.splits import SPLIT_NAMES
from pharmguard.data.tokenization import (
    MAX_LENGTH,
    TOKENIZER_NAME,
    build_tokenized_splits,
)
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
    Post-write verification: read every tokenized Parquet back and
    assert structural integrity. Catches D42-class regressions and
    schema corruption.
    """
    log("\n" + "=" * 60)
    log("Post-write verification")
    log("=" * 60)

    out_dir = paths.tokenized_dir
    manifest_path = out_dir / "stage_05_manifest.json"

    if not manifest_path.exists():
        log(f"  FAIL: manifest missing at {manifest_path}")
        return False

    manifest = json.loads(manifest_path.read_text())
    log(f"  Manifest stage:           {manifest.get('stage')}")
    log(f"  Package version:          {manifest.get('package_version')}")
    log(f"  Tokenizer:                {manifest.get('tokenizer_name')}")
    log(f"  Max length:               {manifest.get('max_length')}")
    log(f"  Truncation direction:     {manifest.get('truncation_direction')}")
    log(f"  Completed at:             {manifest.get('completed_at')}")
    log("")

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

        # Checksum
        actual = _file_sha256(path)
        if actual != rec["sha256"]:
            log(f"  [{split_name}] FAIL: checksum mismatch")
            log(f"    expected: {rec['sha256']}")
            log(f"    actual:   {actual}")
            all_ok = False
            continue

        # Schema integrity
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

        # D42 fix verification: input_ids and attention_mask must be
        # list-like, not strings.
        first_ids = df["input_ids"].iloc[0]
        first_mask = df["attention_mask"].iloc[0]
        if isinstance(first_ids, str) or isinstance(first_mask, str):
            log(f"  [{split_name}] FAIL: input_ids/attention_mask serialized as string")
            all_ok = False
            continue

        # Per-row structural consistency: len(input_ids) == len(attention_mask)
        # and token_count matches both.
        lengths_ok = (
            df["input_ids"].apply(len)
            == df["attention_mask"].apply(len)
        ).all()
        if not lengths_ok:
            log(f"  [{split_name}] FAIL: input_ids/attention_mask lengths inconsistent")
            all_ok = False
            continue

        token_count_ok = (
            df["input_ids"].apply(len) == df["token_count"]
        ).all()
        if not token_count_ok:
            log(f"  [{split_name}] FAIL: token_count does not match len(input_ids)")
            all_ok = False
            continue

        # Token-count cap: every input_ids length <= MAX_LENGTH
        max_obs = int(df["token_count"].max())
        if max_obs > MAX_LENGTH:
            log(f"  [{split_name}] FAIL: max token_count={max_obs} > MAX_LENGTH={MAX_LENGTH}")
            all_ok = False
            continue

        n_trunc = int(df["was_truncated"].sum())
        log(f"  [{split_name}] ok    rows={len(df)}  "
            f"truncated={n_trunc} ({100*n_trunc/len(df):.1f}%)  "
            f"sha256={actual[:12]}...")

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
        help="Skip tokenization; only verify existing outputs against the manifest.",
    )
    args = parser.parse_args()

    paths.ensure_all()
    log = make_logger(paths.logs_dir / "stage_05_tokenization.log")

    if not args.verify_only:
        build_tokenized_splits(log=log)

    ok = verify_outputs(log)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
