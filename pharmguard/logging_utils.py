"""
Logging utilities.

A small helper that writes to a per-stage log file and stdout
simultaneously. We avoid Python's logging module because the pipeline
runs as standalone scripts and we want timestamped, append-only logs
that are trivial to read after the fact, with no global state.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable


def make_logger(
    log_path: Path,
    truncate: bool = True,
) -> Callable[..., None]:
    """
    Return a logger function that appends to log_path and prints.

    Parameters
    ----------
    log_path : Path
        Where the log file should live. Parent directory is created.
    truncate : bool
        If True (default), erase any existing log content first so the
        log reflects only the current run.

    Returns
    -------
    log : callable(msg, also_print=True)
        Append the message (with timestamp) to the log file and
        optionally print it to stdout.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if truncate and log_path.exists():
        log_path.unlink()

    def log(msg: str, also_print: bool = True) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
        with log_path.open("a") as f:
            f.write(line)
        if also_print:
            print(msg)

    return log


def section(log_fn: Callable[..., None], title: str) -> None:
    """Pretty section divider for readable logs."""
    log_fn("")
    log_fn("=" * 60)
    log_fn(title)
    log_fn("=" * 60)
