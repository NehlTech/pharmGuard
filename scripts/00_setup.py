"""
Stage 00 — Environment setup.

Run this once per Colab session (or once after any kernel restart).

Responsibilities
----------------
1. Verify Drive is mounted (Colab) and the project root is writable.
2. Rescue any ephemeral data left over from a previous broken run.
3. Verify the runtime can import the packages we need.
4. Install optional packages that Colab does not ship by default.
5. Create the project directory tree on Drive.
6. Persist a configuration fingerprint for reproducibility.

Usage
-----
    !cd /content/pharmguard && python scripts/00_setup.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pharmguard.config import CONFIG
from pharmguard.env import check_environment, install_optional_packages
from pharmguard.paths import paths
from pharmguard.seeds import set_all_seeds


# Locations where a previous broken run might have written ephemeral data.
EPHEMERAL_FALLBACKS = [
    Path("/content/pharmguard/pharmguard_workspace"),
    Path.cwd() / "pharmguard_workspace",
]


def rescue_ephemeral_data() -> int:
    """Move any ephemeral data found at known fallback locations into Drive."""
    n_rescued = 0
    drive_root = paths.root
    drive_root_resolved = drive_root.resolve()

    for src in EPHEMERAL_FALLBACKS:
        if not src.exists():
            continue
        if src.resolve() == drive_root_resolved:
            continue

        print(f"⚠ Found ephemeral data at: {src}")
        print(f"  Moving contents to:        {drive_root}")
        drive_root.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            target = drive_root / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(item), str(target))
            print(f"    ✓ {item.name}")
            n_rescued += 1

        try:
            shutil.rmtree(src)
            print(f"  ✓ Removed ephemeral directory: {src}")
        except Exception as e:
            print(f"  ⚠ Could not remove {src}: {e}")

    return n_rescued


def main() -> int:
    print("=" * 60)
    print("PHARMGUARD STAGE 00 — ENVIRONMENT SETUP")
    print("=" * 60)
    print(f"Timestamp:    {datetime.now().isoformat(timespec='seconds')}")
    print(f"Project root: {paths.root}")
    print()

    # 1. Drive / root writability
    print("─" * 60)
    print("PROJECT ROOT VERIFICATION")
    print("─" * 60)
    ok, msg = paths.verify_root_writable()
    if not ok:
        print(f"✗ {msg}")
        return 1
    print(f"✓ Project root is writable: {paths.root}")

    # 2. Ephemeral rescue
    print()
    print("─" * 60)
    print("EPHEMERAL DATA RESCUE")
    print("─" * 60)
    n_rescued = rescue_ephemeral_data()
    if n_rescued == 0:
        print("✓ No ephemeral data found (good — nothing to rescue)")
    else:
        print(f"✓ Rescued {n_rescued} item(s) to Drive")

    # 3. Environment check
    print()
    print("─" * 60)
    print("ENVIRONMENT CHECK")
    print("─" * 60)
    report = check_environment(verbose=True)

    if report.missing_required:
        print()
        print("✗ Required packages missing:")
        for pkg in report.missing_required:
            print(f"  - {pkg}")
        print()
        print("This is unexpected on Colab. Restart the runtime and re-run.")
        return 1

    # 4. Install optional packages
    if report.missing_optional:
        print()
        print("─" * 60)
        print("INSTALLING OPTIONAL PACKAGES")
        print("─" * 60)
        ok = install_optional_packages(verbose=True)
        if not ok:
            print()
            print("⚠ Some optional packages failed to install.")
            print("  Pipeline will work but some evaluation features may not.")

    # 5. Directory tree
    print()
    print("─" * 60)
    print("PROJECT DIRECTORY TREE")
    print("─" * 60)
    paths.ensure_all()
    n_dirs = len(paths.all_directories())
    print(f"✓ {n_dirs} directories ensured under {paths.root}")

    set_all_seeds(CONFIG.seeds[0])
    print(f"✓ Seed {CONFIG.seeds[0]} applied (deterministic)")

    # 6. Reproducibility artifacts
    fingerprint = {
        "timestamp":         datetime.now().isoformat(),
        "python_version":    report.python_version,
        "platform":          report.platform,
        "required_versions": report.required_versions,
        "optional_versions": report.optional_versions,
        "gpu_info":          report.gpu_info,
        "cuda_available":    report.cuda_available,
        "cuda_smoke_test_passed": report.cuda_smoke_test_passed,
        "config":            CONFIG.to_dict(),
        "project_root":      str(paths.root),
        "n_rescued":         n_rescued,
    }
    fingerprint_path = paths.env_fingerprint_file
    fingerprint_path.parent.mkdir(parents=True, exist_ok=True)
    with fingerprint_path.open("w") as f:
        json.dump(fingerprint, f, indent=2)
    print(f"✓ Fingerprint → {fingerprint_path}")

    config_path = paths.config_file
    with config_path.open("w") as f:
        json.dump(CONFIG.to_dict(), f, indent=2)
    print(f"✓ Config      → {config_path}")

    print()
    print("=" * 60)
    print("✓ SETUP COMPLETE")
    print("=" * 60)
    print("Next: scripts/01_acquire_data.py (clinical benign + generic attacks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
