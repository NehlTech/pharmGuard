"""
MPIB acquisition and exploratory data analysis.

Pulls the Medical Prompt Injection Benchmark (jhlee0619/mpib) from
Hugging Face, parses every instance into a unified DataFrame, runs a
ten-pass EDA, and writes artifacts that downstream stages consume.

Authentication
--------------
The HF token is read from the file at ``paths.hf_token_file``. The
dataset is gated; you must accept its conditions in your HF account
before download will succeed (see README for the one-time setup).

Artifacts produced
------------------
* parsed_mpib.parquet         — single source of truth for downstream
* mpib_eda_report.json        — quantitative findings
* schema_issues.json          — sanity-check flags
* redaction_audit.json        — V2 redaction prevalence and roles
* mpib_eda/figures/*.pdf      — distribution plots (4 figures)
"""

from __future__ import annotations

import gc
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from pharmguard.config import CONFIG
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths


DATASET_NAME = "jhlee0619/mpib"
REDACTION_TOKEN = "[REDACTED_PAYLOAD]"


# ─────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────

def load_hf_token() -> str:
    """Read the HF token from disk."""
    token_path = paths.hf_token_file

    if not token_path.exists():
        raise FileNotFoundError(
            f"\nHF token not found at {token_path}\n\n"
            f"One-time setup:\n"
            f"  1. Sign in/up at https://huggingface.co\n"
            f"  2. Visit https://huggingface.co/datasets/{DATASET_NAME}\n"
            f"     and click 'Agree and access repository'\n"
            f"  3. Create a Read token at\n"
            f"     https://huggingface.co/settings/tokens\n"
            f"  4. Save it to {token_path}\n"
        )

    token = token_path.read_text().strip()
    if not token.startswith("hf_"):
        raise ValueError(
            f"Token at {token_path} does not look like an HF token "
            f"(should start with 'hf_'). Re-create it."
        )
    return token


def authenticate(token: str) -> None:
    """Authenticate the HuggingFace Hub session with the given token."""
    from huggingface_hub import login as hf_login
    hf_login(token=token, add_to_git_credential=False)


# ─────────────────────────────────────────────────────────
# Defensive parsing helpers
# ─────────────────────────────────────────────────────────

def _safe_get(d, *keys, default=None):
    """Nested-dict access that survives missing or malformed keys."""
    cur = d
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k, None)
        else:
            return default
    return cur if cur is not None else default


def _normalize_contexts(contexts_field):
    """
    Normalize MPIB contexts to a list of dicts.

    Preserves MPIB's full struct schema where present:
        role, text, doc_id, rule_family_id, template_id,
        reconstruction_hook, hash_commitment

    The rule_family_id and reconstruction_hook fields are MPIB's
    payload-reconstruction metadata (R1-R10 rule families). Stage 03
    uses these to reconstruct redacted V2 payloads, so we do NOT
    drop them during parsing.
    """
    if contexts_field is None:
        return []

    if isinstance(contexts_field, str):
        try:
            return _normalize_contexts(json.loads(contexts_field))
        except (json.JSONDecodeError, TypeError):
            return [{"role": "context", "text": contexts_field}]

    if isinstance(contexts_field, list):
        out = []
        for item in contexts_field:
            if isinstance(item, dict):
                # Preserve every key MPIB provides; default common ones
                normalized = {
                    "role": item.get("role", "context"),
                    "text": item.get("text", "") or "",
                }
                # Attach optional MPIB metadata if present
                for opt_key in (
                    "doc_id",
                    "rule_family_id",
                    "template_id",
                    "reconstruction_hook",
                    "hash_commitment",
                ):
                    if opt_key in item and item[opt_key] is not None:
                        normalized[opt_key] = item[opt_key]
                out.append(normalized)
            elif isinstance(item, str):
                out.append({"role": "context", "text": item})
        return out

    return []


def _ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        return [x]
    return []


def _parse_split(hf_split, split_name: str) -> list[dict]:
    """Convert one HF split into a list of normalized records."""
    records = []
    for row in hf_split:
        rec = {
            "sample_id": row.get("sample_id", row.get("id", None)),
            "parent_sample_id": row.get(
                "parent_sample_id",
                row.get("parent_id", row.get("sample_id", None)),
            ),
            "scenario": row.get("scenario", None),
            "vector":   row.get("vector", None),
            "user_query": row.get("user_query", row.get("query", "")),
            "contexts": _normalize_contexts(row.get("contexts", None)),
            "expected_safe_behavior": (
                _safe_get(row, "labels", "expected_safe_behavior", default="")
                or row.get("expected_safe_behavior", "")
            ),
            "severity": _safe_get(row, "labels", "severity", default=None),
            "harm_types": (
                _safe_get(row, "labels", "h_type", default=None)
                or _safe_get(row, "labels", "harm_types", default=[])
            ),
            "source": _safe_get(row, "metadata", "source", default="unknown"),
            "mpib_split": split_name,
        }
        records.append(rec)
    return records


# ─────────────────────────────────────────────────────────
# Schema sanity
# ─────────────────────────────────────────────────────────

def schema_check(df: pd.DataFrame, log) -> list[str]:
    """Flag anything in the parsed DataFrame that violates expectations."""
    issues: list[str] = []

    for col in ("sample_id", "scenario", "vector", "user_query"):
        n_missing = df[col].isna().sum()
        if n_missing > 0:
            issues.append(f"{col}: {n_missing} missing values")
            log(f"    ⚠ {col}: {n_missing} missing")
        else:
            log(f"    ✓ {col}: complete")

    expected_vectors = {"V0", "V0'", "V1", "V2", "V2-S", "V2-B"}
    observed_v = set(df["vector"].dropna().unique())
    unexpected_v = observed_v - expected_vectors
    if unexpected_v:
        issues.append(f"unexpected vector values: {unexpected_v}")
        log(f"    ⚠ Unexpected vector values: {unexpected_v}")
    else:
        log(f"    ✓ Vectors in expected set: {sorted(observed_v)}")

    expected_scenarios = {"S1", "S2", "S3", "S4"}
    observed_s = set(df["scenario"].dropna().unique())
    unexpected_s = observed_s - expected_scenarios
    if unexpected_s:
        issues.append(f"unexpected scenario values: {unexpected_s}")
        log(f"    ⚠ Unexpected scenario values: {unexpected_s}")
    else:
        log(f"    ✓ Scenarios in expected set: {sorted(observed_s)}")

    n_with_parent = df["parent_sample_id"].notna().sum()
    log(f"    Parent-id coverage: {n_with_parent:,} / {len(df):,} "
        f"({n_with_parent/len(df)*100:.1f}%)")
    if n_with_parent < len(df) * 0.95:
        issues.append(
            f"only {n_with_parent}/{len(df)} rows have parent_sample_id; "
            "leakage-safe splits may be partial"
        )

    n_unique = df["sample_id"].nunique()
    if n_unique != len(df):
        n_dups = len(df) - n_unique
        issues.append(f"{n_dups} duplicate sample_ids")
        log(f"    ⚠ {n_dups} duplicate sample_ids detected")
    else:
        log(f"    ✓ All {len(df):,} sample_ids unique")

    return issues


# ─────────────────────────────────────────────────────────
# EDA passes
# ─────────────────────────────────────────────────────────

def _redaction_count(contexts) -> tuple[int, list[str]]:
    """Count REDACTION_TOKEN occurrences and which roles they live in."""
    n = 0
    roles: list[str] = []
    for c in contexts:
        text = c.get("text", "") or ""
        cnt = text.count(REDACTION_TOKEN)
        if cnt > 0:
            n += cnt
            roles.append(c.get("role", "unknown"))
    return n, roles


def run_eda(df: pd.DataFrame, log) -> dict:
    """Run all EDA passes and return a report dict."""
    eda: dict = {
        "timestamp": datetime.now().isoformat(),
        "dataset":   DATASET_NAME,
        "n_total":   int(len(df)),
    }

    # 5.1 Vector distribution
    log("\n  [5.1] Vector distribution")
    vc = df["vector"].value_counts().to_dict()
    eda["vector_distribution"] = {str(k): int(v) for k, v in vc.items()}
    for vec, n in sorted(vc.items(), key=lambda x: -x[1]):
        log(f"    {str(vec):<6} {n:>6,}  ({n/len(df)*100:>5.1f}%)")

    # 5.2 Scenario distribution
    log("\n  [5.2] Scenario distribution")
    sc = df["scenario"].value_counts().to_dict()
    eda["scenario_distribution"] = {str(k): int(v) for k, v in sc.items()}
    for scn, n in sorted(sc.items()):
        log(f"    {str(scn):<6} {n:>6,}  ({n/len(df)*100:>5.1f}%)")

    # 5.3 Vector × Scenario crosstab
    log("\n  [5.3] Vector × Scenario crosstab")
    ctab = pd.crosstab(df["vector"], df["scenario"],
                       margins=True, margins_name="Total")
    log(f"\n{ctab.to_string()}\n")
    eda["crosstab_vector_scenario"] = ctab.to_dict()

    # 5.4 Length distributions
    log("  [5.4] Length distributions (chars)")
    eda["length_stats_by_vector"] = {}
    for vec in sorted(df["vector"].dropna().unique()):
        sub = df[df["vector"] == vec]
        qlen = sub["query_length_chars"]
        clen = sub["context_length_chars"]
        log(
            f"    {vec:<6} query: med={int(qlen.median()):>5} "
            f"p95={int(qlen.quantile(0.95)):>5} | "
            f"context: med={int(clen.median()):>5} "
            f"p95={int(clen.quantile(0.95)):>5}"
        )
        eda["length_stats_by_vector"][str(vec)] = {
            "query": {
                "mean":   float(qlen.mean()),
                "median": float(qlen.median()),
                "p95":    float(qlen.quantile(0.95)),
                "max":    int(qlen.max()),
            },
            "context": {
                "mean":   float(clen.mean()),
                "median": float(clen.median()),
                "p95":    float(clen.quantile(0.95)),
                "max":    int(clen.max()),
            },
        }

    # 5.5 V2 redaction audit
    log("\n  [5.5] V2 redaction audit (drives payload reconstruction)")
    v2_mask = df["vector"].str.startswith("V2", na=False)
    v2 = df[v2_mask].copy()
    v2["n_redactions"] = v2["contexts"].apply(lambda c: _redaction_count(c)[0])
    v2["redaction_roles"] = v2["contexts"].apply(lambda c: _redaction_count(c)[1])

    n_v2 = len(v2)
    n_v2_red = int((v2["n_redactions"] > 0).sum())
    role_flat = [r for roles in v2["redaction_roles"] for r in roles]
    role_counts = Counter(role_flat)

    log(f"    V2 instances total:                {n_v2:,}")
    log(f"    V2 with at least one redaction:    {n_v2_red:,} "
        f"({n_v2_red/max(1,n_v2)*100:.1f}%)")
    log(f"    V2 with NO redaction:              {n_v2 - n_v2_red:,}")
    log(f"    Mean redactions per V2 instance:   "
        f"{float(v2['n_redactions'].mean()) if n_v2 else 0:.2f}")
    log(f"    Redaction-bearing roles:")
    for role, count in role_counts.most_common():
        log(f"      {role:<30} {count:>5,}")

    eda["v2_redaction_audit"] = {
        "n_v2_total":             n_v2,
        "n_v2_with_redaction":    n_v2_red,
        "n_v2_without_redaction": n_v2 - n_v2_red,
        "fraction_redacted":      float(n_v2_red / max(1, n_v2)),
        "mean_redactions_per_v2": float(v2["n_redactions"].mean()) if n_v2 else 0.0,
        "redaction_role_counts":  dict(role_counts),
    }

    # 5.6 Severity distribution
    log("\n  [5.6] Severity distribution")
    sev_counts = df["severity"].value_counts(dropna=False).sort_index().to_dict()
    log("    Severity  Count")
    for sev, n in sev_counts.items():
        sev_label = "missing" if pd.isna(sev) else f"  {sev}"
        log(f"    {str(sev_label):<8}  {n:>6,}")
    eda["severity_distribution"] = {str(k): int(v) for k, v in sev_counts.items()}

    # 5.7 Harm-type distribution
    log("\n  [5.7] Harm-type distribution (multi-label)")
    harm_flat = [h for harms in df["harm_types"] for h in harms]
    harm_counts = Counter(harm_flat)
    log("    Type  Count")
    for h, n in harm_counts.most_common():
        log(f"    {h:<6}  {n:>6,}")
    eda["harm_type_distribution"] = dict(harm_counts)

    # 5.8 Source provenance
    log("\n  [5.8] Source provenance")
    src_counts = df["source"].value_counts(dropna=False).to_dict()
    for src, n in sorted(src_counts.items(), key=lambda x: -x[1]):
        log(f"    {str(src):<25} {n:>6,}")
    eda["source_distribution"] = {str(k): int(v) for k, v in src_counts.items()}

    # 5.9 MPIB published splits
    log("\n  [5.9] MPIB-published splits")
    split_counts = df["mpib_split"].value_counts().to_dict()
    for sp, n in split_counts.items():
        log(f"    {sp:<10} {n:>6,}")
    eda["mpib_published_splits"] = {str(k): int(v) for k, v in split_counts.items()}

    # 5.10 Parent-id leakage check
    log("\n  [5.10] Parent-id leakage across MPIB splits")
    if df["parent_sample_id"].notna().sum() > 0:
        ptos = (
            df.dropna(subset=["parent_sample_id"])
              .groupby("parent_sample_id")["mpib_split"]
              .nunique()
        )
        n_leaky = int((ptos > 1).sum())
        log(f"    Parents spanning multiple splits: {n_leaky}")
        if n_leaky > 0:
            log(f"    ⚠ Group-by-parent leakage exists in published splits")
        else:
            log(f"    ✓ Splits are leakage-safe at parent_sample_id level")
        eda["parent_leakage_across_splits"] = n_leaky
    else:
        log(f"    (skipped — parent_sample_id missing)")
        eda["parent_leakage_across_splits"] = None

    return eda


# ─────────────────────────────────────────────────────────
# Figures
# ─────────────────────────────────────────────────────────

def render_figures(df: pd.DataFrame, eda: dict, log) -> None:
    """Write four EDA figures to mpib_figures_dir."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig_dir = paths.mpib_figures_dir
    fig_dir.mkdir(parents=True, exist_ok=True)

    # F1: vector distribution
    fig, ax = plt.subplots(figsize=(8, 4))
    vec = df["vector"].value_counts()
    ax.bar(vec.index.astype(str), vec.values, color="steelblue")
    ax.set_xlabel("Threat vector")
    ax.set_ylabel("Number of instances")
    ax.set_title("MPIB instance distribution by threat vector")
    for i, v in enumerate(vec.values):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig1_vector_distribution.pdf")
    plt.close(fig)

    # F2: length distributions
    v2_mask = df["vector"].str.startswith("V2", na=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    v0 = df.loc[df["vector"].isin(["V0", "V0'"]), "query_length_chars"]
    v1 = df.loc[df["vector"] == "V1", "query_length_chars"]
    v2 = df.loc[v2_mask, "query_length_chars"]
    axes[0].hist([v0, v1, v2], bins=40, label=["V0/V0'", "V1", "V2"])
    axes[0].set_xlabel("Query length (chars)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Query length by vector")
    axes[0].legend()
    v2c = df.loc[v2_mask, "context_length_chars"]
    axes[1].hist(v2c[v2c > 0], bins=40, color="darkorange")
    axes[1].set_xlabel("Context length (chars)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("V2 context length distribution")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig2_length_distributions.pdf")
    plt.close(fig)

    # F3: vector × scenario heatmap
    fig, ax = plt.subplots(figsize=(7, 5))
    ctab_no_total = pd.crosstab(df["vector"], df["scenario"])
    sns.heatmap(ctab_no_total, annot=True, fmt="d", cmap="Blues", ax=ax,
                cbar_kws={"label": "Instance count"})
    ax.set_title("MPIB vector × scenario crosstab")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig3_vector_scenario_heatmap.pdf")
    plt.close(fig)

    # F4: severity by vector
    fig, ax = plt.subplots(figsize=(8, 4))
    sev_by_vec = (
        df.dropna(subset=["severity"])
          .groupby(["vector", "severity"])
          .size()
          .unstack(fill_value=0)
    )
    if len(sev_by_vec) > 0:
        sev_by_vec.plot(kind="bar", stacked=True, ax=ax, colormap="RdYlGn_r")
        ax.set_xlabel("Vector")
        ax.set_ylabel("Number of instances")
        ax.set_title("Severity distribution by threat vector")
        ax.legend(title="Severity", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig4_severity_by_vector.pdf")
    plt.close(fig)

    log(f"  ✓ 4 figures saved → {fig_dir}/")


# ─────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────

def save_dataframe(df: pd.DataFrame) -> Path:
    """Save the parsed MPIB DataFrame to parquet, JSON-encoding list cols."""
    out_path = paths.mpib_dir / "parsed_mpib.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_save = df.copy()
    df_save["contexts"]  = df_save["contexts"].apply(json.dumps)
    df_save["harm_types"] = df_save["harm_types"].apply(json.dumps)
    df_save.to_parquet(out_path, index=False)
    return out_path


def load_parsed_mpib() -> pd.DataFrame:
    """Reload the parsed MPIB DataFrame for downstream stages."""
    parsed_path = paths.mpib_dir / "parsed_mpib.parquet"
    df = pd.read_parquet(parsed_path)
    df["contexts"]   = df["contexts"].apply(json.loads)
    df["harm_types"] = df["harm_types"].apply(json.loads)
    return df


# ─────────────────────────────────────────────────────────
# Direct JSONL download and reading
# ─────────────────────────────────────────────────────────
#
# We download MPIB's JSONL files directly and parse them ourselves
# rather than going through `datasets.load_dataset()`. The reason is
# that MPIB's `contexts` column is heterogeneous: V0/V1 rows have
# `null` while V2 rows have a rich struct. HuggingFace's Arrow schema
# inference picks `null` from the first batch and then chokes when
# it encounters the struct, raising a TypeError before our code runs.
#
# Reading JSONL with pandas avoids the inference step entirely.

# MPIB's published file names (relative to the repo root on the Hub).
MPIB_JSONL_FILES = {
    "train":      "data/train.jsonl",
    "validation": "data/validation.jsonl",
    "test":       "data/test.jsonl",
}


def _download_mpib_jsonl(token: str, log) -> dict:
    """
    Download every MPIB JSONL split as a raw file via huggingface_hub.

    Returns
    -------
    paths_by_split : dict[str, Path]
        Mapping from split name to local file path. Files are cached in
        ``paths.hf_cache_dir`` so subsequent runs are instant.
    """
    from huggingface_hub import hf_hub_download

    paths_by_split: dict[str, Path] = {}
    for split_name, hub_path in MPIB_JSONL_FILES.items():
        try:
            local = hf_hub_download(
                repo_id=DATASET_NAME,
                filename=hub_path,
                repo_type="dataset",
                token=token,
                cache_dir=str(paths.hf_cache_dir),
            )
            paths_by_split[split_name] = Path(local)
            size_mb = Path(local).stat().st_size / (1024 * 1024)
            log(f"      {split_name:<10} → {local} ({size_mb:.1f} MB)")
        except Exception as e:
            log(f"      ✗ {split_name:<10} failed: {e}")
            raise
    return paths_by_split


def _read_jsonl(path: Path):
    """Yield dicts from a JSONL file, skipping malformed lines."""
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                # MPIB hasn't shipped malformed lines historically,
                # but we tolerate them rather than crash the pipeline.
                continue


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def acquire_mpib(seed: int = None) -> tuple[pd.DataFrame, dict]:
    """Pull MPIB, parse, run EDA, and persist artifacts."""
    if seed is None:
        seed = CONFIG.seeds[0]

    paths.ensure_all()
    log = make_logger(paths.logs_dir / "mpib_acquisition.log")

    section(log, "MPIB ACQUISITION + EDA")

    log("\n[1/6] Hugging Face authentication")
    token = load_hf_token()
    log(f"  ✓ Token loaded ({len(token)} chars; contents masked)")
    authenticate(token)
    log("  ✓ Authenticated")

    log(f"\n[2/6] Downloading {DATASET_NAME} (raw JSONL)")
    paths_by_split = _download_mpib_jsonl(token, log)
    log(f"  ✓ {len(paths_by_split)} files cached locally")

    log("\n[3/6] Parsing to unified DataFrame")
    all_records: list[dict] = []
    for split_name, jsonl_path in paths_by_split.items():
        rows_iter = _read_jsonl(jsonl_path)
        recs = _parse_split(rows_iter, split_name)
        all_records.extend(recs)
        log(f"    Parsed {split_name:<10} → {len(recs):,} records")

    df = pd.DataFrame(all_records)
    df["harm_types"] = df["harm_types"].apply(_ensure_list)
    df["severity"]   = pd.to_numeric(df["severity"], errors="coerce").astype("Int64")
    df["n_contexts"] = df["contexts"].apply(len)
    df["query_length_chars"]   = df["user_query"].astype(str).str.len()
    df["context_length_chars"] = df["contexts"].apply(
        lambda ctxs: sum(len(c.get("text", "")) for c in ctxs)
    )
    log(f"\n  ✓ Total records: {len(df):,}")

    gc.collect()

    log("\n[4/6] Schema sanity checks")
    issues = schema_check(df, log)

    log("\n[5/6] Exploratory data analysis")
    eda = run_eda(df, log)

    log("\n[6/6] Writing artifacts")
    parsed_path = save_dataframe(df)
    log(f"  ✓ Parsed DataFrame → {parsed_path}")

    eda_path = paths.mpib_eda_dir / "mpib_eda_report.json"
    with eda_path.open("w") as f:
        json.dump(eda, f, indent=2, default=str)
    log(f"  ✓ EDA report      → {eda_path}")

    schema_path = paths.mpib_eda_dir / "schema_issues.json"
    with schema_path.open("w") as f:
        json.dump({
            "n_issues":   len(issues),
            "issues":     issues,
            "checked_at": datetime.now().isoformat(),
        }, f, indent=2)
    log(f"  ✓ Schema issues   → {schema_path}")

    redaction_path = paths.mpib_eda_dir / "redaction_audit.json"
    with redaction_path.open("w") as f:
        json.dump(eda["v2_redaction_audit"], f, indent=2)
    log(f"  ✓ Redaction audit → {redaction_path}")

    render_figures(df, eda, log)

    section(log, "MPIB ACQUISITION COMPLETE")
    log(f"  Total instances:   {len(df):,}")
    log(f"  Schema issues:     {len(issues)}")
    log(f"  V2 redaction rate: "
        f"{eda['v2_redaction_audit']['fraction_redacted']*100:.1f}%")

    return df, eda
