"""
Clinical benign data acquisition.

Pulls four sources of clinically realistic benign text:
    1. MTSamples              — clinical transcriptions (broad clinical)
    2. PubMedQA + MedQA       — pharmaceutical literature & QA
    3. OpenFDA                — adverse drug event reports
    4. omi-health clinical    — synthetic doctor-patient dialogues
                                with clinical SOAP summaries

Each source is acquired independently; failures are isolated so a
single broken endpoint does not derail the whole pipeline. Per-source
statistics are written to a JSON report consumed by paper Table 1.

Notes
-----
* MTSamples is pulled in full and tagged with a pharmaceutical-relevance
  flag (rather than filtered) so downstream code can choose its own
  coverage policy.
* PubMedQA is filtered to medical Q&A; the "labeled" config is used
  because it has cleaner provenance.
* OpenFDA is rate-limit-polite (0.5s between drug queries).
* The omi-health dataset replaces the deprecated `medical_dialog`
  loading-script dataset (which newer versions of `datasets` no
  longer support). It is parquet-native and contains 10,000 synthetic
  PMC-Patients-derived dialogues.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime
from typing import Callable

import pandas as pd
import requests
from datasets import load_dataset

from pharmguard.config import CONFIG
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths


# ── Pharmaceutical relevance vocabulary ───────────────────
PHARMA_DRUGS = [
    # Cardiovascular
    "lisinopril", "atorvastatin", "amlodipine", "metoprolol",
    "losartan", "warfarin", "clopidogrel", "simvastatin", "aspirin",
    # Endocrine / metabolic
    "metformin", "insulin", "levothyroxine",
    # Respiratory
    "albuterol",
    # GI / antibiotics
    "omeprazole", "amoxicillin", "azithromycin",
    # Pain / neuro
    "gabapentin", "sertraline",
    # Diuretics / cardiac
    "furosemide", "digoxin", "prednisone",
]

PHARMA_KEYWORDS = [
    "medication", "prescription", "dose", "dosage",
    "adverse", "drug", "pharmac", "therapy",
    "patient", "treatment", "clinical",
]


def _is_pharmaceutical(text: str) -> bool:
    text_lower = text.lower()
    return (
        any(drug in text_lower for drug in PHARMA_DRUGS) or
        any(kw in text_lower for kw in PHARMA_KEYWORDS)
    )


# ─────────────────────────────────────────────────────────
# Source-by-source acquisition functions
# ─────────────────────────────────────────────────────────

def acquire_mtsamples(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """Clinical transcriptions; broad clinical, pharma-tagged subset."""
    log("\n[1/4] MTSamples (clinical transcriptions)")
    name = "mtsamples"
    stats = {"source": name, "hf_path": "harishnair04/mtsamples"}

    try:
        ds = load_dataset(
            "harishnair04/mtsamples",
            split="train",
            cache_dir=str(paths.hf_cache_dir),
        )
        df = pd.DataFrame(ds)

        text_col = next(
            (c for c in ["transcription", "text", "description"] if c in df.columns),
            df.columns[0],
        )
        texts = df[text_col].dropna().astype(str).tolist()
        pharma_flags = [_is_pharmaceutical(t) for t in texts]

        result = pd.DataFrame({
            "text":       texts,
            "label":      0,
            "source":     name,
            "pharma_tag": pharma_flags,
        })
        result = result[result["text"].str.len() > 50].reset_index(drop=True)
        result.to_csv(paths.benign_dir / f"{name}.csv", index=False)

        stats.update({
            "status":        "success",
            "raw_count":     len(texts),
            "final_count":   len(result),
            "pharma_tagged": int(sum(pharma_flags)),
            "mean_length":   int(result["text"].str.len().mean()),
        })
        log(f"  ✓ {len(result):,} samples "
            f"({stats['pharma_tagged']} pharma-tagged), "
            f"mean length {stats['mean_length']} chars")
        return result, stats

    except Exception as e:
        stats.update({"status": "failed", "error": str(e)[:200]})
        log(f"  ✗ FAILED: {e}")
        return pd.DataFrame(columns=["text", "label", "source", "pharma_tag"]), stats


def acquire_pubmed(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """PubMedQA + pharma-filtered MedQA."""
    log("\n[2/4] PubMed (pharmaceutical literature)")
    name = "pubmed"
    stats = {"source": name, "subsources": {}}
    texts: list[str] = []

    # PubMedQA labeled
    try:
        ds = load_dataset(
            "pubmed_qa", "pqa_labeled",
            split="train",
            cache_dir=str(paths.hf_cache_dir),
        )
        n_before = len(texts)
        for row in ds:
            ctx = row.get("context", {})
            contexts = ctx.get("contexts", []) if isinstance(ctx, dict) else []
            question = row.get("question", "")
            text = f"{question} {' '.join(contexts)}".strip()
            if len(text) > 100:
                texts.append(text)
        stats["subsources"]["pubmedqa"] = len(texts) - n_before
        log(f"  → PubMedQA: {stats['subsources']['pubmedqa']} abstracts")
    except Exception as e:
        stats["subsources"]["pubmedqa"] = f"failed: {str(e)[:100]}"
        log(f"  ⚠ PubMedQA failed: {e}")

    # MedQA filtered to pharmaceutical
    try:
        ds2 = load_dataset(
            "medalpaca/medical_meadow_medqa",
            split="train",
            cache_dir=str(paths.hf_cache_dir),
        )
        df2 = pd.DataFrame(ds2)
        combined = (
            df2.get("input", pd.Series()).fillna("") + " " +
            df2.get("output", pd.Series()).fillna("")
        ).tolist()
        pharma_texts = [t for t in combined if _is_pharmaceutical(t)]
        n_before = len(texts)
        texts += pharma_texts[:1500]
        stats["subsources"]["medqa"] = len(texts) - n_before
        log(f"  → MedQA pharmaceutical: {stats['subsources']['medqa']} entries")
    except Exception as e:
        stats["subsources"]["medqa"] = f"failed: {str(e)[:100]}"
        log(f"  ⚠ MedQA failed: {e}")

    result = pd.DataFrame({
        "text":       texts[:3000],
        "label":      0,
        "source":     name,
        "pharma_tag": True,
    })
    result = result[result["text"].str.len() > 100].reset_index(drop=True)
    result.to_csv(paths.benign_dir / f"{name}.csv", index=False)

    stats.update({
        "status":      "success" if len(result) > 0 else "failed",
        "final_count": len(result),
        "mean_length": int(result["text"].str.len().mean()) if len(result) else 0,
    })
    log(f"  ✓ {len(result):,} pharmaceutical samples")
    return result, stats


def acquire_openfda(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """FDA adverse drug event reports across the full PHARMA_DRUGS list."""
    log("\n[3/4] OpenFDA (adverse drug event reports)")
    name = "openfda"
    stats = {"source": name, "drugs_queried": len(PHARMA_DRUGS)}
    reports: list[str] = []
    n_succeeded = 0

    for drug in PHARMA_DRUGS:
        try:
            response = requests.get(
                "https://api.fda.gov/drug/event.json",
                params={
                    "search": f"patient.drug.medicinalproduct:{drug}",
                    "limit": 80,
                },
                timeout=15,
            )
            if response.status_code != 200:
                continue

            data = response.json()
            for event in data.get("results", []):
                patient = event.get("patient", {})
                reactions = patient.get("reaction", [])
                reaction_text = ", ".join(
                    r.get("reactionmeddrapt", "") for r in reactions
                )
                seriousness = event.get("serious", "unknown")
                country = event.get("occurcountry", "unspecified")
                report = (
                    f"Adverse Drug Event Report: Patient receiving {drug} "
                    f"therapy reported {reaction_text}. "
                    f"Reported seriousness: {seriousness}. "
                    f"Country of occurrence: {country}. "
                    f"Event documented in FDA MedWatch system."
                )
                if len(report) > 60:
                    reports.append(report)

            n_succeeded += 1
            time.sleep(0.5)  # rate-limit politeness

        except Exception as e:
            log(f"  ⚠ {drug}: {str(e)[:60]}")

    result = pd.DataFrame({
        "text":       reports[:2500],
        "label":      0,
        "source":     name,
        "pharma_tag": True,
    })
    result.to_csv(paths.benign_dir / f"{name}.csv", index=False)

    stats.update({
        "status":           "success" if len(result) > 0 else "failed",
        "drugs_succeeded":  n_succeeded,
        "final_count":      len(result),
        "mean_length":      int(result["text"].str.len().mean()) if len(result) else 0,
    })
    log(f"  ✓ {len(result):,} FDA reports ({n_succeeded}/{len(PHARMA_DRUGS)} drugs)")
    return result, stats


def acquire_clinical_dialogue(log: Callable[..., None]) -> tuple[pd.DataFrame, dict]:
    """
    Synthetic doctor-patient dialogues (omi-health).

    Replaces the deprecated `medical_dialog` script-based dataset.
    Source: omi-health/medical-dialogue-to-soap-summary (parquet-native,
    10,000 PMC-Patients-derived dialogues with SOAP summaries).
    """
    log("\n[4/4] Clinical dialogue (omi-health/medical-dialogue-to-soap-summary)")
    name = "clinical_dialogue"
    stats = {
        "source": name,
        "hf_path": "omi-health/medical-dialogue-to-soap-summary",
    }

    try:
        ds = load_dataset(
            "omi-health/medical-dialogue-to-soap-summary",
            split="train",
            cache_dir=str(paths.hf_cache_dir),
        )
        df = pd.DataFrame(ds)

        # Schema: 'dialogue' column is the conversation; we use that
        # rather than the SOAP summary because dialogue text is closer
        # to deployment-time clinical query distribution.
        text_col = "dialogue" if "dialogue" in df.columns else df.columns[0]
        texts = df[text_col].dropna().astype(str).tolist()
        pharma_flags = [_is_pharmaceutical(t) for t in texts]

        result = pd.DataFrame({
            "text":       texts,
            "label":      0,
            "source":     name,
            "pharma_tag": pharma_flags,
        })
        result = result[result["text"].str.len() > 100].reset_index(drop=True)
        # Cap to keep the source proportional to the others
        if len(result) > 2500:
            result = result.sample(n=2500, random_state=CONFIG.seeds[0]).reset_index(drop=True)
        result.to_csv(paths.benign_dir / f"{name}.csv", index=False)

        stats.update({
            "status":        "success",
            "final_count":   len(result),
            "pharma_tagged": int(result["pharma_tag"].sum()),
            "mean_length":   int(result["text"].str.len().mean()) if len(result) else 0,
        })
        log(f"  ✓ {len(result):,} dialogues "
            f"({stats['pharma_tagged']} pharma-tagged)")
        return result, stats

    except Exception as e:
        stats.update({"status": "failed", "error": str(e)[:200]})
        log(f"  ✗ FAILED: {e}")
        return pd.DataFrame(columns=["text", "label", "source", "pharma_tag"]), stats


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def acquire_all_benign(seed: int = None) -> tuple[pd.DataFrame, dict]:
    """
    Run every benign source, deduplicate, and produce a report.

    Returns
    -------
    (df, report) : tuple
        df      Concatenated benign DataFrame, deduplicated by text.
        report  Per-source and aggregate statistics dict.
    """
    if seed is None:
        seed = CONFIG.seeds[0]
    random.seed(seed)

    paths.ensure_all()
    log = make_logger(paths.logs_dir / "benign_acquisition.log")

    section(log, "CLINICAL BENIGN DATA ACQUISITION")
    log(f"Seed: {seed}")

    report: dict = {
        "started_at": datetime.now().isoformat(),
        "sources":    {},
    }

    parts: list[pd.DataFrame] = []
    for fn in (acquire_mtsamples, acquire_pubmed,
               acquire_openfda, acquire_clinical_dialogue):
        df, stats = fn(log)
        report["sources"][stats["source"]] = stats
        if len(df) > 0:
            parts.append(df[["text", "label", "source", "pharma_tag"]])

    n_succeeded = sum(
        1 for s in report["sources"].values()
        if s.get("status") == "success"
    )
    if n_succeeded < 3:
        log(f"\n⚠ WARNING: only {n_succeeded}/4 benign sources succeeded")

    all_benign = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["text", "label", "source", "pharma_tag"]
    )
    before_dedup = len(all_benign)
    all_benign = (
        all_benign
        .drop_duplicates(subset=["text"])
        .pipe(lambda d: d[d["text"].str.len() > 50])
        .reset_index(drop=True)
    )
    all_benign_path = paths.benign_dir / "all_benign.csv"
    all_benign.to_csv(all_benign_path, index=False)

    # ── Drive sync verification (added after v0.8.0 data loss) ──
    try:
        from pharmguard.data.drive_sync import (
            assert_drive_persisted,
            compute_wait_for_size,
        )

        size = all_benign_path.stat().st_size
        wait_s = compute_wait_for_size(size)
        assert_drive_persisted(
            path=all_benign_path,
            expected_size=size,
            wait_s=wait_s,
        )
        log(f"✓ Drive persistence verified for all_benign.csv "
            f"({size/1024/1024:.1f} MB)")
    except Exception as e:
        raise RuntimeError(
            f"Stage 01 all_benign.csv did not persist to Drive: {e}. "
            f"D73 augmentation depends on this file; re-run Stage 01."
        ) from e

    report["aggregate"] = {
        "before_dedup":         before_dedup,
        "after_dedup":          len(all_benign),
        "duplicates_removed":   before_dedup - len(all_benign),
        "successful_sources":   n_succeeded,
        "pharma_tagged":        int(all_benign["pharma_tag"].sum()),
        "mean_length":          int(all_benign["text"].str.len().mean()) if len(all_benign) else 0,
        "median_length":        int(all_benign["text"].str.len().median()) if len(all_benign) else 0,
        "p95_length":           int(all_benign["text"].str.len().quantile(0.95)) if len(all_benign) else 0,
    }
    report["completed_at"] = datetime.now().isoformat()

    report_path = paths.logs_dir / "benign_acquisition_report.json"
    with report_path.open("w") as f:
        json.dump(report, f, indent=2)
    log(f"\n✓ Report → {report_path}")

    section(log, "BENIGN ACQUISITION COMPLETE")
    log(f"Total benign samples: {len(all_benign):,}")
    log(f"Successful sources:   {n_succeeded}/4")

    return all_benign, report
