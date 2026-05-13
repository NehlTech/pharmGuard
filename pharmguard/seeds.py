"""
Reproducible seeding for multi-seed experiments.

Critical for Contribution 4 (multi-seed statistical reporting): every
training run must be deterministic given its seed, so that mean ± std
across seeds reflects genuine model variance rather than RNG drift.
"""

from __future__ import annotations

import os
import random


def set_all_seeds(seed: int, deterministic: bool = True) -> None:
    """
    Set every random number generator we use.

    Call this at the very start of each training run, before any model
    or dataloader is created.

    Parameters
    ----------
    seed : int
        The integer seed.
    deterministic : bool
        If True, also set CuDNN to deterministic mode. This makes runs
        reproducible at the cost of some training throughput.
    """
    random.seed(seed)

    # numpy and torch are imported lazily so this module loads cleanly
    # even in environments where one of them is missing (e.g., CI).
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass

    os.environ["PYTHONHASHSEED"] = str(seed)
