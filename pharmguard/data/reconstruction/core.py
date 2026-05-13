"""
V2 payload reconstruction orchestrator.

Loads MPIB V2 instances, generates a synthetic payload for each one
using the rule-family-appropriate template strategy backed by an
instruction-tuned LLM, and writes a new parquet with the redacted
payloads replaced.

LLM choice: Phi-3-mini-4k-instruct (3.8B params, fp16). Greedy
decoding for reproducibility. We disable sampling, set temperature
to 0.0, and use a per-instance seed for any randomness in the
template strategy (preamble selection, etc.).

Quality control:
* Every generation is wrapped in try/except — failures fall back to
  the strategy's deterministic skeleton.
* Empty/garbage outputs (< 20 words, or matches a refusal pattern)
  are detected and replaced with the fallback.
* Surface features are counted and deviation from target is recorded.
* Per-family success counts are reported at the end.

Output schema (data/adversarial/reconstructed_v2.parquet):
* All columns from parsed_mpib for V2 rows
* contexts: same structure but poisoned_update.text replaced
* original_redacted_text: '[REDACTED_PAYLOAD]' (for audit)
* generation_status: 'success' | 'fallback' | 'deviated' | 'family_not_implemented' | 'no_poisoned_context'
* generation_seed: per-instance seed
* actual_features: dict of counted lines/words/headers/formatting
* feature_deviation: dict of fractional deviations from target
"""

from __future__ import annotations

import gc
import hashlib
import json
import re
from datetime import datetime
from typing import Optional

import pandas as pd

from pharmguard.config import CONFIG
from pharmguard.logging_utils import make_logger, section
from pharmguard.paths import paths

from .surface_features import (
    SurfaceFeatures,
    count_features,
    feature_deviation,
    is_within_tolerance,
    trim_to_word_target,
)
from .templates import get_strategy, implemented_families
from .templates.base import GenerationContext


# Phi-3-mini ID. Pinned because we need to know what generation
# behavior we are validating against in this stage's QC report.
LLM_MODEL_ID = "microsoft/Phi-3-mini-4k-instruct"

# Heuristic patterns that flag refusals / non-output garbage.
REFUSAL_PATTERNS = [
    r"i\s+can(no|')t",
    r"i\s+cannot",
    r"i'?m\s+sorry",
    r"i\s+won't",
    r"i\s+will\s+not",
    r"as an ai",
    r"i\s+am\s+unable",
    r"as a (?:language model|llm)",
]
_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS), re.IGNORECASE)


def _seed_for_sample_id(sample_id: str) -> int:
    """Deterministic 32-bit seed derived from sample_id."""
    h = hashlib.sha256(sample_id.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2 ** 32)


def _looks_like_refusal_or_garbage(text: str, min_words: int = 20) -> bool:
    """True if text is empty, very short, or contains refusal markers."""
    if not text or len(text.split()) < min_words:
        return True
    if _REFUSAL_RE.search(text[:300]):
        return True
    return False


def _strip_llm_artifacts(text: str, collapse_paragraphs: bool = True) -> str:
    """
    Remove common LLM output artifacts.

    * Strips wrapping triple backticks (` ``` `) and quotes.
    * If ``collapse_paragraphs`` is True (default), collapses runs of
      blank lines to a single space, so that families targeting a
      single dense paragraph (R7, R8) don't get falsely flagged as
      multi-line. Multi-paragraph families (R4, R5, R10) call this
      with ``collapse_paragraphs=False`` to preserve structure.
    """
    text = text.strip()

    # Drop wrapping triple-backticks
    if text.startswith("```"):
        text = re.sub(r"^```\w*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Drop wrapping straight or curly quotes
    if len(text) >= 2 and text[0] in '"\u201c' and text[-1] in '"\u201d':
        text = text[1:-1].strip()

    # Collapse paragraph breaks for single-paragraph families
    if collapse_paragraphs:
        # Multiple blank lines or single blank line → one space
        text = re.sub(r"\n\s*\n", " ", text)
        # Single newlines mid-paragraph → space (since single-paragraph)
        text = re.sub(r"\n+", " ", text)
        # Collapse consecutive whitespace
        text = re.sub(r"\s+", " ", text).strip()

    return text


# ─────────────────────────────────────────────────────────
# Phi-3-mini wrapper
# ─────────────────────────────────────────────────────────

class PhiGenerator:
    """
    Thin wrapper around Phi-3-mini-4k-instruct.

    We avoid the ``transformers`` ``pipeline`` API because it makes
    it harder to set deterministic decoding and read the prompt
    template correctly for chat models. Instead we call the model
    directly with a constructed chat prompt.
    """

    def __init__(self, model_id: str = LLM_MODEL_ID):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=str(paths.hf_cache_dir),
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            device_map="cuda",
            cache_dir=str(paths.hf_cache_dir),
        )
        self.model.eval()
        # No pad token on Phi by default; use eos_token to silence warnings
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
    ) -> str:
        """
        Run greedy decoding on the prompt.

        Returns the model's text output with the prompt stripped off.
        """
        import torch

        # Phi-3 uses an instruction-style chat template
        messages = [{"role": "user", "content": prompt}]
        chat_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(
            chat_prompt,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,                  # deterministic
                temperature=1.0,                  # ignored when sampling off
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Strip the prompt tokens
        new_tokens = output_ids[0, inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return text


# ─────────────────────────────────────────────────────────
# Per-instance reconstruction
# ─────────────────────────────────────────────────────────

def _reconstruct_one(
    row: pd.Series,
    generator: Optional[PhiGenerator],
    log,
    log_progress_every: int,
    progress_idx: int,
) -> dict:
    """
    Reconstruct the redacted payload in a single V2 row.

    Returns a dict with the new poisoned text and quality metadata.
    Does NOT mutate the row.
    """
    sample_id = row["sample_id"]
    contexts = row["contexts"]

    # Find the poisoned_update context with reconstruction_hook metadata
    poisoned_idx = None
    for i, c in enumerate(contexts):
        if c.get("role") == "poisoned_update":
            poisoned_idx = i
            break

    if poisoned_idx is None:
        return {
            "generation_status":  "no_poisoned_context",
            "new_text":           None,
            "actual_features":    None,
            "feature_deviation":  None,
            "generation_seed":    0,
        }

    poisoned = contexts[poisoned_idx]
    rule_family = poisoned.get("rule_family_id")
    hook = poisoned.get("reconstruction_hook", {}) or {}
    features = hook.get("features", {}) or {}

    # Find the benign_evidence context as topic anchor (any non-poisoned)
    benign_text = ""
    for c in contexts:
        if c.get("role") != "poisoned_update":
            benign_text = c.get("text", "") or ""
            break

    # Build the generation context
    seed = _seed_for_sample_id(sample_id)
    ctx = GenerationContext(
        sample_id=sample_id,
        rule_family_id=rule_family or "",
        benign_evidence=benign_text,
        target_lines=int(features.get("lines", 1)),
        target_words=int(features.get("words", 100)),
        target_headers=int(features.get("headers", 0)),
        target_formatting=int(features.get("formatting", 0)),
        seed=seed,
    )

    # Get the strategy for this rule family
    if rule_family not in implemented_families():
        return {
            "generation_status":  "family_not_implemented",
            "new_text":           None,
            "actual_features":    None,
            "feature_deviation":  None,
            "generation_seed":    seed,
        }

    strategy = get_strategy(rule_family)

    # Try LLM generation first, fall back to skeleton on any failure
    generated_text = None
    used_fallback = False
    if generator is not None:
        try:
            prompt = strategy.build_prompt(ctx)
            raw_output = generator.generate(prompt, max_new_tokens=512)
            cleaned = _strip_llm_artifacts(
                raw_output,
                collapse_paragraphs=not strategy.preserves_paragraphs,
            )
            if _looks_like_refusal_or_garbage(cleaned):
                used_fallback = True
            else:
                generated_text = cleaned
        except Exception as e:
            log(f"    ⚠ LLM exception on {sample_id}: {str(e)[:120]}")
            used_fallback = True
    else:
        used_fallback = True

    if generated_text is None:
        generated_text = strategy.fallback_skeleton(ctx)

    # Trim if greatly oversized
    generated_text = trim_to_word_target(
        generated_text,
        target_words=ctx.target_words,
        overshoot_factor=1.30,
    )

    # Count features and compute deviation
    actual = count_features(generated_text)
    target_dict = {
        "lines":      ctx.target_lines,
        "words":      ctx.target_words,
        "headers":    ctx.target_headers,
        "formatting": ctx.target_formatting,
    }
    deviation = feature_deviation(actual, target_dict)
    within = is_within_tolerance(deviation, tolerance=0.50)

    if used_fallback:
        status = "fallback"
    elif not within:
        status = "deviated"
    else:
        status = "success"

    if (progress_idx % log_progress_every) == 0:
        log(
            f"    [{progress_idx:>4d}] {sample_id:<40} "
            f"rf={rule_family:<3} status={status:<10} "
            f"words={actual.words:>3}/{ctx.target_words:<3}"
        )

    return {
        "generation_status":  status,
        "new_text":           generated_text,
        "actual_features":    actual.to_dict(),
        "feature_deviation":  deviation,
        "generation_seed":    seed,
    }


# ─────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────

def run_reconstruction(
    use_llm: bool = True,
    rule_families: Optional[list[str]] = None,
    log_progress_every: int = 25,
    sample_log_count: int = 10,
) -> tuple[pd.DataFrame, dict]:
    """
    Reconstruct redacted V2 payloads.

    Parameters
    ----------
    use_llm : bool
        If True (default), load Phi-3-mini and use it to generate
        rich contextual payloads. If False, use only the deterministic
        fallback skeletons (much faster; useful for smoke tests).
    rule_families : list of str, optional
        If provided, only reconstruct V2 instances whose rule family
        is in this list. Other V2 rows are skipped (not written).
        Useful for incremental delivery — pass ['R7'] to only do R7.
    log_progress_every : int
        Print a progress line every N instances.
    sample_log_count : int
        Number of generated payloads to dump to a sample log file
        for human review.

    Returns
    -------
    (df, report) : tuple
        df      The reconstructed DataFrame with original V2 columns
                plus reconstruction metadata.
        report  Per-family success counts and aggregate deviations.
    """
    paths.ensure_all()
    log = make_logger(paths.logs_dir / "reconstruction.log")

    section(log, "STAGE 03 — V2 PAYLOAD RECONSTRUCTION")
    log(f"Rule families requested: "
        f"{rule_families if rule_families else 'all implemented'}")
    log(f"Implemented families:    {implemented_families()}")
    log(f"Use LLM:                 {use_llm}")

    # 1. Load parsed MPIB and filter to V2
    log("\n[1/5] Loading parsed MPIB")
    from pharmguard.data.mpib import load_parsed_mpib
    df = load_parsed_mpib()
    v2 = df[df["vector"] == "V2"].copy().reset_index(drop=True)
    log(f"  ✓ Loaded {len(df):,} total instances; {len(v2):,} are V2")

    # Filter to requested families if asked
    if rule_families is not None:
        wanted = set(rule_families)
        def _row_family(row):
            for c in row["contexts"]:
                if c.get("role") == "poisoned_update":
                    return c.get("rule_family_id")
            return None
        v2["__family"] = v2.apply(_row_family, axis=1)
        v2 = v2[v2["__family"].isin(wanted)].drop(columns="__family").reset_index(drop=True)
        log(f"  ✓ Filtered to families {sorted(wanted)}: {len(v2):,} rows")

    if len(v2) == 0:
        log("  ⚠ No V2 rows remain after filtering. Nothing to do.")
        return v2, {"n_total": 0}

    # 2. Load LLM if requested
    log("\n[2/5] Loading LLM")
    generator: Optional[PhiGenerator] = None
    if use_llm:
        try:
            generator = PhiGenerator()
            log(f"  ✓ Loaded {LLM_MODEL_ID}")
        except Exception as e:
            log(f"  ✗ Failed to load LLM: {e}")
            log(f"    Falling back to skeleton-only generation.")
            generator = None
    else:
        log(f"  ⊘ Skipping LLM (use_llm=False); skeleton-only.")

    # 3. Iterate instances
    log("\n[3/5] Generating reconstructions")
    log(f"  Target: {len(v2):,} V2 instances")
    started = datetime.now()

    results: list[dict] = []
    sample_payloads: list[dict] = []
    seen_families: set[str] = set()
    for i, (_, row) in enumerate(v2.iterrows(), start=1):
        result = _reconstruct_one(
            row=row,
            generator=generator,
            log=log,
            log_progress_every=log_progress_every,
            progress_idx=i,
        )
        results.append(result)

        # Stash one sample per rule family until the cap is reached.
        # This guarantees coverage across all 10 families during human
        # review rather than over-sampling whichever family appears first.
        rule_family = _get_rule_family(row)
        if (
            result["new_text"]
            and rule_family
            and rule_family not in seen_families
            and len(sample_payloads) < sample_log_count
        ):
            sample_payloads.append({
                "sample_id":         row["sample_id"],
                "rule_family":       rule_family,
                "status":            result["generation_status"],
                "target_features":   _get_target_features(row),
                "actual_features":   result["actual_features"],
                "feature_deviation": result["feature_deviation"],
                "generated_text":    result["new_text"],
            })
            seen_families.add(rule_family)

    elapsed = (datetime.now() - started).total_seconds()
    log(f"\n  ✓ Generated {len(results):,} reconstructions in {elapsed:.1f}s "
        f"({elapsed / max(1, len(results)):.2f}s per instance)")

    # Free GPU memory before writing parquet
    if generator is not None:
        del generator
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    # 4. Substitute new payloads into contexts
    log("\n[4/5] Substituting new payloads into V2 contexts")
    new_contexts_col = []
    new_status_col = []
    new_features_col = []
    new_deviation_col = []
    new_seed_col = []
    new_original_col = []

    for (_, row), result in zip(v2.iterrows(), results):
        contexts = row["contexts"]
        new_contexts = []
        original_payload_text = None

        for c in contexts:
            if c.get("role") == "poisoned_update" and result["new_text"]:
                original_payload_text = c.get("text", "")
                new_c = dict(c)
                new_c["text"] = result["new_text"]
                new_contexts.append(new_c)
            else:
                new_contexts.append(dict(c))

        new_contexts_col.append(new_contexts)
        new_status_col.append(result["generation_status"])
        new_features_col.append(result["actual_features"])
        new_deviation_col.append(result["feature_deviation"])
        new_seed_col.append(result["generation_seed"])
        new_original_col.append(original_payload_text)

    v2["contexts"]              = new_contexts_col
    v2["generation_status"]     = new_status_col
    v2["actual_features"]       = new_features_col
    v2["feature_deviation"]     = new_deviation_col
    v2["generation_seed"]       = new_seed_col
    v2["original_redacted_text"] = new_original_col
    log(f"  ✓ Substituted payloads in {len(v2):,} rows")

    # 5. Save and report
    log("\n[5/5] Persisting reconstructed parquet")
    out_path = paths.adversarial_dir / "reconstructed_v2.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # JSON-encode list/dict columns for parquet
    df_save = v2.copy()
    df_save["contexts"]          = df_save["contexts"].apply(json.dumps)
    df_save["harm_types"]        = df_save["harm_types"].apply(
        lambda x: x if isinstance(x, str) else json.dumps(x)
    )
    df_save["actual_features"]   = df_save["actual_features"].apply(
        lambda x: json.dumps(x) if x is not None else None
    )
    df_save["feature_deviation"] = df_save["feature_deviation"].apply(
        lambda x: json.dumps(x) if x is not None else None
    )
    df_save.to_parquet(out_path, index=False)
    log(f"  ✓ Wrote {out_path}")

    # ── Drive sync verification (added after v0.8.0 data loss) ──
    # Stage 03 is the most expensive stage (~81 minutes of Phi-3 GPU
    # inference). Losing this output costs hours. Verify Drive
    # persistence immediately after write rather than discovering the
    # loss on the next session.
    try:
        from pharmguard.data.drive_sync import (
            assert_drive_persisted,
            compute_wait_for_size,
        )

        size = out_path.stat().st_size
        wait_s = compute_wait_for_size(size)
        assert_drive_persisted(
            path=out_path,
            expected_size=size,
            wait_s=wait_s,
        )
        log(f"  ✓ Drive persistence verified ({size/1024/1024:.1f} MB)")
    except Exception as e:
        raise RuntimeError(
            f"Stage 03 reconstructed_v2.parquet did not persist to "
            f"Drive: {e}. The ~81-minute Phi-3 run output is at risk; "
            f"re-save or re-run Stage 03 immediately."
        ) from e

    # Aggregate report
    report = _build_report(v2, results, elapsed)
    report_path = paths.logs_dir / "reconstruction_report.json"
    with report_path.open("w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"  ✓ Wrote {report_path}")

    # Save sample payloads for human review
    samples_path = paths.logs_dir / "reconstruction_samples.json"
    with samples_path.open("w") as f:
        json.dump(sample_payloads, f, indent=2, default=str)
    log(f"  ✓ Wrote {samples_path} ({len(sample_payloads)} samples)")

    section(log, "RECONSTRUCTION COMPLETE")
    log(f"  Total reconstructed: {len(v2):,}")
    log(f"  Status distribution:")
    for status, n in report["status_counts"].items():
        log(f"    {status:<25} {n:>5,}")
    log(f"  Per-family success:")
    for family, stats in report["per_family"].items():
        log(f"    {family:<5} success={stats['success']} "
            f"fallback={stats['fallback']} "
            f"deviated={stats['deviated']}")

    return v2, report


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _get_rule_family(row: pd.Series) -> Optional[str]:
    for c in row["contexts"]:
        if c.get("role") == "poisoned_update":
            return c.get("rule_family_id")
    return None


def _get_target_features(row: pd.Series) -> Optional[dict]:
    for c in row["contexts"]:
        if c.get("role") == "poisoned_update":
            hook = c.get("reconstruction_hook", {}) or {}
            return hook.get("features", {})
    return None


def _build_report(v2: pd.DataFrame, results: list[dict], elapsed_s: float) -> dict:
    """Aggregate per-family and overall statistics."""
    from collections import Counter

    report = {
        "n_total":      len(v2),
        "elapsed_s":    elapsed_s,
        "elapsed_per_instance_s": elapsed_s / max(1, len(v2)),
        "model_id":     LLM_MODEL_ID,
        "implemented_families": implemented_families(),
        "status_counts": dict(Counter(r["generation_status"] for r in results)),
        "per_family":   {},
    }

    # Per-family breakdown
    families = []
    for _, row in v2.iterrows():
        families.append(_get_rule_family(row))

    family_set = sorted({f for f in families if f})
    for family in family_set:
        family_results = [r for f, r in zip(families, results) if f == family]
        per = Counter(r["generation_status"] for r in family_results)
        # Aggregate per-feature deviations among successful runs
        deviations = [
            r["feature_deviation"] for r in family_results
            if r["feature_deviation"] is not None
        ]
        mean_abs_dev = {}
        if deviations:
            for key in ("lines", "words", "headers", "formatting"):
                vals = [
                    abs(d[key]) for d in deviations
                    if d.get(key) is not None and d[key] != float("inf")
                ]
                mean_abs_dev[key] = (
                    sum(vals) / len(vals) if vals else None
                )

        report["per_family"][family] = {
            "n":              len(family_results),
            "success":        per.get("success", 0),
            "fallback":       per.get("fallback", 0),
            "deviated":       per.get("deviated", 0),
            "family_not_implemented": per.get("family_not_implemented", 0),
            "mean_abs_deviation": mean_abs_dev,
        }

    return report
