"""
Environment verification.

We do NOT pin specific versions of numpy/torch/transformers/etc. — we
work with whatever the host environment ships (Colab in particular).
This module verifies that the running environment can do what
PharmGuard needs: import the core packages, see a GPU, and execute a
trivial CUDA op.

If anything is wrong, the function returns a structured report rather
than crashing, so the caller can decide how to surface the issue.
"""

from __future__ import annotations

import importlib
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# Required imports that the rest of the pipeline cannot work without.
REQUIRED_PACKAGES = [
    "numpy",
    "scipy",
    "pandas",
    "sklearn",
    "torch",
    "transformers",
    "datasets",
    "huggingface_hub",
    "matplotlib",
    "seaborn",
    "tqdm",
    "requests",
]

# Packages that are nice to have but won't block the pipeline.
OPTIONAL_PACKAGES = [
    "bert_score",
    "imblearn",
    "statsmodels",
    "nltk",
    "langdetect",
]


@dataclass
class EnvReport:
    """Structured snapshot of the running environment."""

    python_version: str = ""
    platform: str = ""
    required_versions: dict = field(default_factory=dict)
    optional_versions: dict = field(default_factory=dict)
    missing_required: list = field(default_factory=list)
    missing_optional: list = field(default_factory=list)
    cuda_available: bool = False
    gpu_info: list = field(default_factory=list)
    cuda_smoke_test_passed: Optional[bool] = None
    cuda_smoke_test_error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True if every required package imports and (if needed) CUDA works."""
        return (
            not self.missing_required
            and (not self.cuda_available or self.cuda_smoke_test_passed)
        )


def _try_import(name: str) -> Optional[str]:
    """Return version string if importable, else None."""
    try:
        mod = importlib.import_module(name)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return None


def check_environment(verbose: bool = True) -> EnvReport:
    """
    Inspect the running environment and return a structured report.

    Parameters
    ----------
    verbose : bool
        If True, print a human-readable summary as the check runs.

    Returns
    -------
    report : EnvReport
        Use ``report.ok`` to decide whether to proceed.
    """
    report = EnvReport(
        python_version=sys.version.split()[0],
        platform=platform.platform(),
    )

    if verbose:
        print(f"Python:   {report.python_version}")
        print(f"Platform: {report.platform}")
        print()
        print("Required packages:")

    for pkg in REQUIRED_PACKAGES:
        ver = _try_import(pkg)
        if ver is None:
            report.missing_required.append(pkg)
            if verbose:
                print(f"  ✗ {pkg:<20} not importable")
        else:
            report.required_versions[pkg] = ver
            if verbose:
                print(f"  ✓ {pkg:<20} {ver}")

    if verbose:
        print()
        print("Optional packages:")
    for pkg in OPTIONAL_PACKAGES:
        ver = _try_import(pkg)
        if ver is None:
            report.missing_optional.append(pkg)
            if verbose:
                print(f"  ⚠ {pkg:<20} not importable (will install via pip)")
        else:
            report.optional_versions[pkg] = ver
            if verbose:
                print(f"  ✓ {pkg:<20} {ver}")

    # GPU inventory via nvidia-smi (no torch dependency required)
    if verbose:
        print()
        print("GPU:")
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            for i, line in enumerate(result.stdout.strip().split("\n")):
                report.gpu_info.append(line.strip())
                if verbose:
                    print(f"  ✓ GPU {i}: {line.strip()}")
        else:
            if verbose:
                print("  ⚠ nvidia-smi found no GPUs")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        if verbose:
            print("  ⚠ nvidia-smi unavailable")

    # CUDA smoke test (requires torch)
    if "torch" in report.required_versions:
        try:
            import torch
            report.cuda_available = torch.cuda.is_available()
            if report.cuda_available:
                x = torch.randn(2, 2, device="cuda")
                _ = x @ x
                del x
                torch.cuda.empty_cache()
                report.cuda_smoke_test_passed = True
                if verbose:
                    print("  ✓ CUDA matmul smoke test passed")
            else:
                if verbose:
                    print("  ⚠ torch installed but CUDA not available "
                          "(CPU-only operation)")
        except Exception as e:
            report.cuda_smoke_test_passed = False
            report.cuda_smoke_test_error = str(e)[:200]
            if verbose:
                print(f"  ✗ CUDA smoke test FAILED: {report.cuda_smoke_test_error}")

    return report


def install_optional_packages(verbose: bool = True) -> bool:
    """
    Install the OPTIONAL_PACKAGES via pip if they are missing.

    Returns True if all optional packages are present after the call.
    """
    missing = [
        pkg for pkg in OPTIONAL_PACKAGES if _try_import(pkg) is None
    ]
    if not missing:
        if verbose:
            print("✓ All optional packages already present")
        return True

    # Map import-name → pip-name where they differ
    pip_names = {
        "bert_score": "bert-score",
        "imblearn":   "imbalanced-learn",
    }

    if verbose:
        print(f"Installing optional packages: {missing}")

    for import_name in missing:
        pip_name = pip_names.get(import_name, import_name)
        cmd = [sys.executable, "-m", "pip", "install", "-q", pip_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        ok = result.returncode == 0
        if verbose:
            print(f"  {'✓' if ok else '✗'} {pip_name}")

    # Re-check
    still_missing = [
        pkg for pkg in OPTIONAL_PACKAGES if _try_import(pkg) is None
    ]
    return not still_missing
