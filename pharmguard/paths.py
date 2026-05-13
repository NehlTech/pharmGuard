"""
Project paths.

All paths in PharmGuard derive from a single project root. The root
is resolved with the following precedence (highest priority first):

    1. PHARMGUARD_ROOT environment variable (always wins)
    2. /content/drive/MyDrive/pharmguard if running on Colab
       (detected by the existence of /content)
    3. ./pharmguard_workspace under the current working directory
       (local fallback only)

CRITICAL: On Colab we always commit to the Drive path, regardless of
whether Drive is actually mounted at the moment paths.py is imported.
This is intentional. If Drive is not mounted, downstream operations
will fail visibly with a clear "directory does not exist" error,
which is far better than silently writing to ephemeral storage that
disappears on session restart.

Usage:
    from pharmguard.paths import paths
    paths.benign_dir        # -> .../pharma_data/raw/benign
    paths.ensure_all()      # creates every directory if missing
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _is_colab() -> bool:
    """
    Detect whether we are running on Google Colab.

    The /content directory is created at boot on every Colab runtime
    and does not exist on local machines. This is more reliable than
    inspecting Drive-mount state at import time.
    """
    return Path("/content").is_dir()


def _default_project_root() -> Path:
    """
    Resolve the project root.

    Precedence:
      1. PHARMGUARD_ROOT environment variable
      2. /content/drive/MyDrive/pharmguard if on Colab
      3. ./pharmguard_workspace otherwise (local fallback)
    """
    env_root = os.environ.get("PHARMGUARD_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    if _is_colab():
        # Always commit to the Drive path on Colab. Whether Drive is
        # actually mounted is a separate concern that Stage 00 verifies.
        return Path("/content/drive/MyDrive/pharmguard")

    # True local fallback — only reached off-Colab without env override
    return Path.cwd() / "pharmguard_workspace"


@dataclass(frozen=True)
class ProjectPaths:
    """All filesystem paths used by PharmGuard, derived from a root."""

    root: Path

    # ── Data ──────────────────────────────────────────────
    @property
    def data_dir(self) -> Path:
        return self.root / "pharma_data"

    @property
    def benign_dir(self) -> Path:
        return self.data_dir / "raw" / "benign"

    @property
    def attack_dir(self) -> Path:
        return self.data_dir / "raw" / "attacks"

    @property
    def mpib_dir(self) -> Path:
        return self.data_dir / "raw" / "mpib"

    @property
    def adversarial_dir(self) -> Path:
        return self.data_dir / "adversarial"

    @property
    def splits_dir(self) -> Path:
        """Stage 04 output — seven labeled, split-tagged Parquets."""
        return self.data_dir / "splits"

    @property
    def tokenized_dir(self) -> Path:
        """Stage 05 output — pre-tokenized seven splits, ready for Stage 06."""
        return self.data_dir / "tokenized"

    @property
    def models_dir(self) -> Path:
        """Stage 06+ output — trained model checkpoints, one dir per (seed, config)."""
        return self.root / "pharma_models"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def hf_cache_dir(self) -> Path:
        return self.root / "hf_cache"

    # ── Results (organized by paper contribution) ─────────
    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    @property
    def results_main(self) -> Path:
        return self.results_dir / "main"

    @property
    def results_baselines(self) -> Path:
        return self.results_dir / "baselines"

    @property
    def results_ablations(self) -> Path:
        return self.results_dir / "ablations"

    @property
    def results_clinical_fp(self) -> Path:
        return self.results_dir / "clinical_fp"  # C1

    @property
    def results_adaptive(self) -> Path:
        return self.results_dir / "adaptive"

    @property
    def results_difficulty(self) -> Path:
        return self.results_dir / "difficulty"  # C4 part 1

    @property
    def results_drift(self) -> Path:
        return self.results_dir / "drift"  # C4 part 2

    @property
    def results_ood(self) -> Path:
        return self.results_dir / "ood"

    @property
    def figures_dir(self) -> Path:
        return self.results_dir / "figures"

    @property
    def tables_dir(self) -> Path:
        return self.results_dir / "tables"

    # ── Checkpoints ───────────────────────────────────────
    @property
    def ckpt_dir(self) -> Path:
        return self.root / "checkpoints"

    @property
    def ckpt_seeds_dir(self) -> Path:
        return self.ckpt_dir / "seeds"

    # ── Logs ──────────────────────────────────────────────
    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def mpib_eda_dir(self) -> Path:
        return self.logs_dir / "mpib_eda"

    @property
    def mpib_figures_dir(self) -> Path:
        return self.mpib_eda_dir / "figures"

    # ── Files ─────────────────────────────────────────────
    @property
    def hf_token_file(self) -> Path:
        return self.root / ".hf_token"

    @property
    def config_file(self) -> Path:
        return self.root / "pharmguard_config.json"

    @property
    def env_fingerprint_file(self) -> Path:
        return self.root / "environment_fingerprint.json"

    # ── Operations ────────────────────────────────────────
    def all_directories(self) -> list[Path]:
        """Return every directory used by the pipeline."""
        return [
            self.root,
            self.data_dir, self.benign_dir, self.attack_dir,
            self.mpib_dir, self.adversarial_dir, self.splits_dir,
            self.tokenized_dir, self.models_dir,
            self.processed_dir,
            self.hf_cache_dir,
            self.results_dir, self.results_main, self.results_baselines,
            self.results_ablations, self.results_clinical_fp,
            self.results_adaptive, self.results_difficulty,
            self.results_drift, self.results_ood,
            self.figures_dir, self.tables_dir,
            self.ckpt_dir, self.ckpt_seeds_dir,
            self.logs_dir, self.mpib_eda_dir, self.mpib_figures_dir,
        ]

    def ensure_all(self) -> None:
        """Create every directory if missing. Idempotent."""
        for d in self.all_directories():
            d.mkdir(parents=True, exist_ok=True)

    def verify_root_writable(self) -> tuple[bool, str]:
        """
        Confirm we can actually write to the project root.

        On Colab this fails clearly if Drive is not mounted, instead of
        silently falling back to ephemeral storage.

        Returns
        -------
        (ok, message) : tuple
            ok       True if the root exists and is writable.
            message  Human-readable explanation; empty string if ok.
        """
        if _is_colab() and "drive" in str(self.root).lower():
            drive_mount = Path("/content/drive/MyDrive")
            if not drive_mount.is_dir():
                return False, (
                    "Project root is set to a Drive path but Drive is "
                    "not mounted. In a Colab cell, run:\n"
                    "    from google.colab import drive\n"
                    "    drive.mount('/content/drive')"
                )

        try:
            self.root.mkdir(parents=True, exist_ok=True)
            test_file = self.root / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            return True, ""
        except Exception as e:
            return False, f"Cannot write to project root {self.root}: {e}"


# Singleton — import this directly
paths = ProjectPaths(root=_default_project_root())
