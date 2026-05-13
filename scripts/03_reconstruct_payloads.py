"""
Stage 03 — Reconstruct redacted V2 payloads.

Reads parsed_mpib.parquet, generates synthetic poisoned payloads for
V2 instances using rule-family-aware templates backed by Phi-3-mini,
and writes the result to data/adversarial/reconstructed_v2.parquet.

All ten rule families (R1–R10) are implemented. Default behavior
generates payloads for every V2 instance.

Outputs
-------
* data/adversarial/reconstructed_v2.parquet
* logs/reconstruction.log
* logs/reconstruction_report.json    aggregate per-family statistics
* logs/reconstruction_samples.json   first-5 generated payloads for review

Usage
-----
    !cd /content/pharmguard && python scripts/03_reconstruct_payloads.py
    !cd /content/pharmguard && python scripts/03_reconstruct_payloads.py --no-llm
    !cd /content/pharmguard && python scripts/03_reconstruct_payloads.py --families R7,R8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pharmguard.data.reconstruction import run_reconstruction
from pharmguard.data.reconstruction.templates import implemented_families
from pharmguard.paths import paths


def main() -> int:
    p = argparse.ArgumentParser(
        description="Reconstruct redacted V2 payloads in MPIB."
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Phi-3-mini and use only deterministic skeletons "
             "(faster; useful for smoke-testing the pipeline).",
    )
    p.add_argument(
        "--all-families",
        action="store_true",
        help="Reconstruct every rule family registered. Default is to "
             "restrict to currently implemented families (R1–R10).",
    )
    p.add_argument(
        "--families",
        type=str,
        default=None,
        help="Comma-separated rule families to include (e.g. 'R7,R8'). "
             "Overrides --all-families.",
    )
    args = p.parse_args()

    print("=" * 60)
    print("PHARMGUARD STAGE 03 — V2 PAYLOAD RECONSTRUCTION")
    print("=" * 60)
    print(f"Project root: {paths.root}")

    ok, msg = paths.verify_root_writable()
    if not ok:
        print(f"\n✗ {msg}")
        print("\nRun scripts/00_setup.py first.")
        return 1

    parsed_path = paths.mpib_dir / "parsed_mpib.parquet"
    if not parsed_path.exists():
        print(f"\n✗ Parsed MPIB not found at {parsed_path}")
        print(f"  Run scripts/02_acquire_mpib.py first.")
        return 1

    if args.families:
        families = [f.strip() for f in args.families.split(",") if f.strip()]
    elif args.all_families:
        families = None
    else:
        families = implemented_families()
        print(f"Restricting to implemented families: {families}")
        print(f"  (use --all-families to attempt every family)")

    df, report = run_reconstruction(
        use_llm=not args.no_llm,
        rule_families=families,
    )

    print()
    print("=" * 60)
    print("✓ STAGE 03 COMPLETE")
    print("=" * 60)
    print(f"  V2 instances reconstructed: {report['n_total']:,}")
    print(f"  Status distribution:")
    for status, n in report.get("status_counts", {}).items():
        print(f"    {status:<25} {n:>5,}")
    if report["n_total"] > 0:
        print(f"  Time per instance: "
              f"{report.get('elapsed_per_instance_s', 0):.2f}s")
    print()
    print("Inspect the generated samples at:")
    print(f"  {paths.logs_dir / 'reconstruction_samples.json'}")
    print()
    print("Next: review samples to spot-check quality, then proceed to")
    print("Stage 04 (seven-variant dataset construction).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
