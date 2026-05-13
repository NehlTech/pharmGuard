"""
Generic attack data acquisition.

Pulls two non-clinical attack corpora used purely as an out-of-distribution
probe for paper section 6.5. They are NOT used for training PharmGuard;
clinical IPI training data comes from MPIB (see :mod:`pharmguard.data.mpib`)
and reconstructed payloads (see :mod:`pharmguard.data.reconstruction`).

Sources
-------
* deepset/prompt-injections    — verified IPI patterns
* JailbreakBench/JBB-Behaviors — adversarial behaviors

We deliberately exclude generic mixed-purpose datasets (e.g. xTRam1's
safe-guard) because they conflate jailbreak with prompt injection and
muddy the taxonomy our paper depends on.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

import pandas as pd
from datasets import load_dataset

from pharmguard.config import CONFIG
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths


def acquire_deepset(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """Verified prompt-injection patterns from deepset/prompt-injections."""
    log("\n[1/2] Deepset (prompt injection patterns)")
    name = "deepset"
    stats = {"source": name, "attack_category": "indirect_injection"}

    try:
        ds = load_dataset(
            "deepset/prompt-injections",
            split="train",
            cache_dir=str(paths.hf_cache_dir),
        )
        df = pd.DataFrame(ds)
        if "label" in df.columns:
            df = df[df["label"] == 1]

        text_col = "text" if "text" in df.columns else df.columns[0]

        result = pd.DataFrame({
            "text":        df[text_col].dropna().tolist(),
            "label":       1,
            "source":      name,
            "attack_type": "indirect_injection",
        })
        result = (
            result[result["text"].str.len() > 20]
            .drop_duplicates(subset=["text"])
            .reset_index(drop=True)
        )
        result.to_csv(paths.attack_dir / f"{name}.csv", index=False)

        stats.update({
            "status":      "success",
            "final_count": len(result),
            "mean_length": int(result["text"].str.len().mean()) if len(result) else 0,
        })
        log(f"  ✓ {len(result):,} IPI patterns")
        return result, stats

    except Exception as e:
        stats.update({"status": "failed", "error": str(e)[:200]})
        log(f"  ✗ FAILED: {e}")
        return pd.DataFrame(columns=["text", "label", "source", "attack_type"]), stats


def acquire_jailbreakbench(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """Adversarial behaviors from JailbreakBench."""
    log("\n[2/2] JailbreakBench (adversarial behaviors)")
    name = "jailbreakbench"
    stats = {"source": name, "attack_category": "jailbreak"}

    try:
        ds = load_dataset(
            "JailbreakBench/JBB-Behaviors", "behaviors",
            split="harmful",
            cache_dir=str(paths.hf_cache_dir),
        )
        df = pd.DataFrame(ds)
        text_col = "Goal" if "Goal" in df.columns else df.columns[0]

        result = pd.DataFrame({
            "text":        df[text_col].dropna().tolist(),
            "label":       1,
            "source":      name,
            "attack_type": "jailbreak",
        })
        result = (
            result[result["text"].str.len() > 20]
            .reset_index(drop=True)
        )
        result.to_csv(paths.attack_dir / f"{name}.csv", index=False)

        stats.update({
            "status":      "success",
            "final_count": len(result),
            "mean_length": int(result["text"].str.len().mean()) if len(result) else 0,
        })
        log(f"  ✓ {len(result):,} jailbreak patterns")
        return result, stats

    except Exception as e:
        stats.update({"status": "failed", "error": str(e)[:200]})
        log(f"  ✗ FAILED: {e}")
        return pd.DataFrame(columns=["text", "label", "source", "attack_type"]), stats


def acquire_all_attacks(seed: int = None) -> tuple[pd.DataFrame, dict]:
    """
    Run every attack source, deduplicate, and produce a report.

    Returns
    -------
    (df, report) : tuple
        df      Concatenated attack DataFrame, deduplicated by text.
        report  Per-source and aggregate statistics dict.
    """
    if seed is None:
        seed = CONFIG.seeds[0]

    paths.ensure_all()
    log = make_logger(paths.logs_dir / "attack_acquisition.log")

    section(log, "GENERIC ATTACK DATA ACQUISITION (OOD probe pool)")
    log(f"Seed: {seed}")
    log("")
    log("Note: These attacks are used ONLY as an out-of-distribution")
    log("probe in paper section 6.5. Training data comes from MPIB.")

    report: dict = {
        "started_at": datetime.now().isoformat(),
        "sources":    {},
    }

    parts: list[pd.DataFrame] = []
    for fn in (acquire_deepset, acquire_jailbreakbench):
        df, stats = fn(log)
        report["sources"][stats["source"]] = stats
        if len(df) > 0:
            parts.append(df[["text", "label", "source", "attack_type"]])

    n_succeeded = sum(
        1 for s in report["sources"].values()
        if s.get("status") == "success"
    )
    if n_succeeded < 1:
        log(f"\n⚠ WARNING: all attack sources failed")

    all_attacks = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["text", "label", "source", "attack_type"]
    )
    before_dedup = len(all_attacks)
    all_attacks = (
        all_attacks
        .drop_duplicates(subset=["text"])
        .pipe(lambda d: d[d["text"].str.len() > 20])
        .reset_index(drop=True)
    )
    all_attacks.to_csv(paths.attack_dir / "all_attacks.csv", index=False)

    report["aggregate"] = {
        "before_dedup":       before_dedup,
        "after_dedup":        len(all_attacks),
        "duplicates_removed": before_dedup - len(all_attacks),
        "successful_sources": n_succeeded,
        "mean_length":        int(all_attacks["text"].str.len().mean()) if len(all_attacks) else 0,
        "median_length":      int(all_attacks["text"].str.len().median()) if len(all_attacks) else 0,
        "p95_length":         int(all_attacks["text"].str.len().quantile(0.95)) if len(all_attacks) else 0,
    }
    report["completed_at"] = datetime.now().isoformat()

    report_path = paths.logs_dir / "attack_acquisition_report.json"
    with report_path.open("w") as f:
        json.dump(report, f, indent=2)
    log(f"\n✓ Report → {report_path}")

    section(log, "ATTACK ACQUISITION COMPLETE")
    log(f"Total attack samples: {len(all_attacks):,}")
    log(f"Successful sources:   {n_succeeded}/2")

    return all_attacks, report
