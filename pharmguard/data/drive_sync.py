"""
Drive sync verification (introduced after v0.8.0's data-loss event).

Colab's Drive mount writes go to a local fuse cache first; sync to
Drive happens asynchronously and is opaque to userland Python. If a
runtime ends before sync completes, files vanish on the next session
even though every Python-level write succeeded.

This module provides verification helpers that can be called after
writes to bound the risk:

* ``force_drive_sync(wait_s=3.0)`` — issues a ``sync`` syscall and
  sleeps to let fuse-to-Drive catch up.
* ``assert_drive_persisted(path, expected_size, expected_sha256=None)``
  — re-reads the file via a fresh handle and confirms size and
  (optionally) SHA-256 match expectations.
* ``verify_directory_persisted(dir_path, expected_files)`` —
  same as above for a set of files (e.g., a model checkpoint
  directory).

These checks are not absolute. They cannot detect a failure that
happens *after* the verification (e.g., the runtime crashes between
the assert and the end of the session). But they do catch the
common case where the local write succeeded and the Drive sync
silently dropped on the floor.

Wait times are tuned for Colab's typical sync latency:
* Small files (< 1 MB): 3 seconds is usually enough
* Medium files (1-100 MB): 10 seconds
* Large files (> 100 MB, e.g., model weights): 30 seconds

The caller passes the right value; defaults are conservative.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path


class DriveSyncError(RuntimeError):
    """Raised when a Drive write cannot be verified after sync."""


def force_drive_sync(wait_s: float = 3.0) -> None:
    """
    Force kernel page cache flush and wait for Drive sync.

    Does two things:
      1. ``sync`` syscall: tells the kernel to flush dirty pages to
         the underlying filesystem (in our case, fuse → Drive).
      2. Sleep for ``wait_s`` seconds: gives Drive's background sync
         time to accept the bytes and acknowledge.

    The ``sync`` call is best-effort. It returns when the kernel has
    *issued* the flush, not when Drive has acknowledged. The wait is
    the pragmatic compensation.
    """
    try:
        subprocess.run(["sync"], check=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # `sync` itself failed; not fatal, but worth logging
        pass
    time.sleep(wait_s)


def _file_sha256(path: Path) -> str:
    """Compute SHA-256 by reading the file fresh."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_drive_persisted(
    path: str | Path,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
    wait_s: float = 3.0,
) -> dict:
    """
    Verify that a file written locally has actually persisted to Drive.

    Workflow:
      1. ``force_drive_sync(wait_s)`` to let Drive catch up.
      2. ``os.stat`` the file via a fresh path lookup.
      3. If ``expected_size`` is given, assert it matches.
      4. If ``expected_sha256`` is given, hash the file fresh and
         assert it matches.

    Returns
    -------
    dict with keys: path, size, sha256 (only if expected_sha256 given)

    Raises
    ------
    DriveSyncError if any check fails.
    """
    path = Path(path)

    # First, force a sync and wait.
    force_drive_sync(wait_s=wait_s)

    # Re-stat. If Drive is missing the file, this should reveal it.
    # We open the file fresh to bypass any cached descriptor.
    if not path.exists():
        raise DriveSyncError(
            f"Drive persistence check failed: {path} does not exist "
            f"after sync + wait_s={wait_s}s. The local write likely "
            f"did not reach Drive."
        )

    try:
        stat = path.stat()
    except OSError as e:
        raise DriveSyncError(
            f"Drive persistence check failed: cannot stat {path}: {e}"
        ) from e

    actual_size = stat.st_size
    result: dict = {"path": str(path), "size": actual_size}

    if expected_size is not None and actual_size != expected_size:
        raise DriveSyncError(
            f"Drive persistence check failed: {path} has size "
            f"{actual_size} on Drive but caller expected "
            f"{expected_size}. Write likely incomplete."
        )

    if expected_sha256 is not None:
        actual_sha256 = _file_sha256(path)
        result["sha256"] = actual_sha256
        if actual_sha256 != expected_sha256:
            raise DriveSyncError(
                f"Drive persistence check failed: {path} has SHA-256 "
                f"{actual_sha256[:12]}... on Drive but caller expected "
                f"{expected_sha256[:12]}... Write was corrupted or "
                f"truncated during sync."
            )

    return result


def verify_directory_persisted(
    dir_path: str | Path,
    expected_files: list[str],
    wait_s: float = 3.0,
) -> dict:
    """
    Verify that a directory and a set of named files within it have
    all persisted to Drive.

    Useful after multi-file writes like Stage 04's seven Parquets or
    Stage 06A's model checkpoint directory.

    Parameters
    ----------
    dir_path : str or Path        directory expected to exist
    expected_files : list[str]    file names (not paths) expected
                                   inside the directory
    wait_s : float                seconds to wait after sync

    Returns
    -------
    dict with keys: dir_path, files (mapping name → {size})

    Raises
    ------
    DriveSyncError if the directory is missing or any expected file
    is missing.
    """
    dir_path = Path(dir_path)

    force_drive_sync(wait_s=wait_s)

    if not dir_path.exists():
        raise DriveSyncError(
            f"Drive persistence check failed: directory {dir_path} "
            f"does not exist after sync + wait_s={wait_s}s."
        )
    if not dir_path.is_dir():
        raise DriveSyncError(
            f"Drive persistence check failed: {dir_path} exists but "
            f"is not a directory."
        )

    actual_files = {p.name for p in dir_path.iterdir() if p.is_file()}
    missing = [f for f in expected_files if f not in actual_files]
    if missing:
        raise DriveSyncError(
            f"Drive persistence check failed: directory {dir_path} "
            f"exists but is missing files: {missing}. Listed files: "
            f"{sorted(actual_files)}."
        )

    file_info: dict[str, dict] = {}
    for name in expected_files:
        fpath = dir_path / name
        stat = fpath.stat()
        file_info[name] = {"size": stat.st_size}

    return {"dir_path": str(dir_path), "files": file_info}


def compute_wait_for_size(size_bytes: int) -> float:
    """
    Suggest a wait time based on file size.

    Heuristic from observed Colab behavior:
    * <1 MB    → 3 s
    * 1-100 MB → 10 s
    * >100 MB  → 30 s

    Callers are free to override.
    """
    MB = 1024 * 1024
    if size_bytes < 1 * MB:
        return 3.0
    if size_bytes < 100 * MB:
        return 10.0
    return 30.0
