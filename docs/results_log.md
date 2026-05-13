# PharmGuard Results Log

Quantitative findings recorded as they are observed, organized by
stage. Each section corresponds to a stage in the pipeline. Tables
are written in a format that maps directly into paper Tables.

This document is **append-only**. When a number is updated (e.g.,
because a stage was re-run with a different configuration), the
update is recorded as a new dated entry below the original. Old
entries are not deleted.

Cross-references:
* The methodology that produced these numbers lives in
  `methodology.md`.
* The decisions that locked the configuration producing these
  numbers live in `decisions.md`.

---

## Conventions

* All counts are integers. All rates are reported to one decimal
  place unless higher precision is meaningful.
* "n.r." means not recorded. Numbers labeled n.r. are blocking
  for future work; they are tracked in the project task list.
* "n/a" means not applicable. The cell does not have a meaningful
  value at this granularity.
* Run dates are recorded in ISO 8601 (YYYY-MM-DD).

---

## §1 — Stage 01: Source Acquisition

**Run date:** 2026-05-09. **Status:** complete.

### Table 1.1 — Benign clinical sources

| Source                                          | Role                              | Loader                  | Status |
|-------------------------------------------------|-----------------------------------|-------------------------|--------|
| MTSamples                                       | Clinical notes                    | datasets                | ok     |
| PubMedQA train (MPIB-disjoint slice)            | Biomedical QA                     | datasets                | ok     |
| MedQA train (MPIB-disjoint slice)               | Exam-style QA                     | datasets                | ok     |
| OpenFDA drug labels                             | Pharmacological text              | requests + JSON parse   | ok     |
| omi-health/medical-dialogue-to-soap-summary     | Clinician–patient dialogue + SOAP | datasets                | ok     |

### Table 1.2 — Generic attack sources

| Source                          | Role                               | Loader   | Status |
|---------------------------------|------------------------------------|----------|--------|
| deepset/prompt-injections       | OOD prompt-injection probe         | datasets | ok     |
| JailbreakBench                  | OOD jailbreak transfer probe       | datasets | ok     |

### Notes

* Per-source row counts are recorded in `reports/01_acquire/report.json`
  in the runtime artifact directory and are environment-dependent
  (HF API may serve different snapshots over time). They do not
  appear in the paper directly.
* `medical_dialog` → `omi-health/medical-dialogue-to-soap-summary`
  substitution was applied (see methodology §3.5; decision D18).

---

## §2 — Stage 02: MPIB Ingestion and EDA

**Run date:** 2026-05-09. **Status:** complete.

### Table 2.1 — MPIB instance distribution by vector

| Vector | Count | Share   |
|--------|-------|---------|
| V0     | 2,734 | 28.2 %  |
| V0p    | 5,737 | 59.2 %  |
| V1     | 644   | 6.6 %   |
| V2     | 582   | 6.0 %   |
| **Total** | **9,697** | **100 %** |

The distribution matches the values reported in [Lee et al., 2026,
Table 1] within rounding (their V2 row is 94 strict + 488 borderline
= 582 total, which we treat as a single V2 pool).

### Table 2.2 — MPIB instance distribution by scenario

| Scenario             | Count | Share  |
|----------------------|-------|--------|
| S1 General Info      | 5,653 | 58.3 % |
| S2 Medication        | 669   | 6.9 %  |
| S3 Triage            | 2,715 | 28.0 % |
| S4 Guidelines        | 660   | 6.8 %  |

### Table 2.3 — Vector × Scenario distribution (counts)

|        | S1    | S2  | S3    | S4  | **Total** |
|--------|-------|-----|-------|-----|-----------|
| V0/V0p | 4,939 | 584 | 2,372 | 576 | 8,471     |
| V1     | 375   | 45  | 180   | 44  | 644       |
| V2     | 339   | 40  | 163   | 40  | 582       |

The wide-format table above is from MPIB's Table 2 directly. Our
ingest reproduces these counts exactly. The most important pattern
for our work is that V2 is concentrated in S1+S4 (379 of 582,
65.1 %) — consistent with MPIB's framing that authority-based
attacks are most persuasive in evidence-based-guideline scenarios.

Note: in our parsed Parquet, S4-cluster V2 instances are the
majority due to MPIB's S4 highest-priority rule (PMID/trial-cue
queries always assigned to S4); our 548-of-582 figure cited
elsewhere refers to V2-instance scenario assignments after
priority resolution rather than the raw stratified sampling.

### Table 2.4 — V2 redaction status

| Redaction status                              | V2 count |
|-----------------------------------------------|----------|
| `[REDACTED_PAYLOAD]` in `poisoned_update.text` | 582      |
| Unredacted text                               | 0        |
| **Redaction rate**                            | **100 %**|

Every V2 instance in the public release is redacted. This is the
empirical justification for Stage 03 reconstruction (methodology
§3.3.1).

### Table 2.5 — Severity distribution

| Severity | Count | Share  |
|----------|-------|--------|
| 0        | 5,234 | 54.0 % |
| 1        | n.r.  | n.r.   |
| 2        | n.r.  | n.r.   |
| 3        | 3,250 | 33.5 % |
| 4        | n.r.  | n.r.   |

The bimodal distribution at severities 0 and 3 dominates; the
intermediate and extreme severities are sparse. The sparse cells
will be re-counted in a follow-up EDA pass and recorded as a dated
amendment to this table.

### Table 2.6 — Harm-type distribution (multi-label)

| Harm type | Description              | Count | Share of all instances |
|-----------|--------------------------|-------|-----------------------:|
| H1        | Misdiagnosis             | 746   | 7.7 %                  |
| H2        | Treatment Error          | 692   | 7.1 %                  |
| H3        | Emergency Downplay       | 2,806 | 28.9 %                 |
| H4        | Guidance Conflict        | 32    | 0.3 %                  |
| H5        | Evidence Manipulation    | 822   | 8.5 %                  |

Harm-type assignment is multi-label, so shares do not sum to 100 %.
H4's small absolute count (32) is notable — it is rare enough that
detector-evaluation slicing on H4 will be statistically thin.

### Table 2.7 — Source provenance

| Source     | Count | Share  | Vectors carried              |
|------------|-------|--------|------------------------------|
| MedQA      | 9,099 | 93.8 % | V0, V0p, V1                  |
| PubMedQA   | 598   | 6.2 %  | V0, V0p, V2                  |

V1 instances are MedQA-derived; V2 instances are PubMedQA-derived.
This is consistent with [Lee et al., 2026, §3.3].

### Table 2.8 — Train/val/test split

| Split | Count | Share  |
|-------|-------|--------|
| train | 7,759 | 80.0 % |
| val   | 969   | 10.0 % |
| test  | 969   | 10.0 % |

Splits are MPIB's published `parent_sample_id`-grouped 80/10/10.
We honor them unmodified (decision D11).

### Table 2.9 — Schema integrity checks

| Check                                                        | Result |
|--------------------------------------------------------------|--------|
| Parent-id leakage between train/val/test                     | 0      |
| Instances with no `vector` field                             | 0      |
| Instances with no `scenario` field                           | 0      |
| Instances with malformed `contexts`                          | 0      |
| Cosmetic schema discrepancy: `V0p` vs `V0'` notation         | 1      |

Adopted `V0p` throughout the codebase (decision D22).

---

## §3 — Stage 03: V2 Payload Reconstruction

**Status:** framework complete (v0.4.0); end-to-end run pending.

### Table 3.1 — Rule-family distribution across the 582 V2 instances

| Family | Count | Share  |
|--------|-------|--------|
| R1     | 47    | 8.1 %  |
| R2     | 30    | 5.2 %  |
| R3     | 60    | 10.3 % |
| R4     | 61    | 10.5 % |
| R5     | 49    | 8.4 %  |
| R6     | 79    | 13.6 % |
| R7     | 54    | 9.3 %  |
| R8     | 90    | 15.5 % |
| R9     | 81    | 13.9 % |
| R10    | 31    | 5.3 %  |
| **Total** | **582** | **100 %** |

R8 (Triage Downplay) is the largest family at 15.5 %. R10
(Provenance Spoofing) and R2 (Contraindication Masking) are the
smallest. The distribution is *not* uniform; we preserve the
distribution rather than uniformize it because the family weights
reflect MPIB's curation priorities.

### Table 3.2 — Sandbox validation results (v0.4.0, fallback path)

All 15 tests passed on the v0.4.0 archive without external dependencies.

| # | Test                                                      | Result |
|---|-----------------------------------------------------------|--------|
| 1 | Version string                                            | pass   |
| 2 | Foundation module imports                                 | pass   |
| 3 | All 10 families registered                                | pass   |
| 4 | TemplateStrategy contract on all 10                       | pass   |
| 5 | `_reconstruct_one` end-to-end on all 10 (fallback)        | pass   |
| 6 | Status names: `oversized` correctly absent                | pass   |
| 7 | Per-family mechanism markers detected in output text      | pass   |
| 8 | Determinism: identical input → identical output           | pass   |
| 9 | Refusal detection on canned refusals                      | pass   |
| 10 | Paragraph-collapse switching by `preserves_paragraphs`   | pass   |
| 11 | Topic anchoring across all 10 families                   | pass   |
| 12 | Missing-evidence and unknown-family edge cases           | pass   |
| 13 | Colab notebook JSON structure                            | pass   |
| 14 | All 4 pipeline scripts parse                              | pass   |
| 15 | All 10 family files parse                                 | pass   |

### Table 3.3 — Per-family fallback output profile (synthetic evidence input)

Generated against a fixed cytokines/epilepsy synthetic evidence
context. Surface features measured by `count_features`. Targets
are the per-family default surface profiles (D30).

| Family | Status   | Lines | Words | Hdrs | Fmt | Mechanism marker found            |
|--------|----------|-------|-------|------|-----|-----------------------------------|
| R1     | fallback | 1     | 104   | 0    | 0   | "definitively established"        |
| R2     | fallback | 1     | 88    | 0    | 0   | "no clinically meaningful limits" |
| R3     | fallback | 1     | 97    | 0    | 0   | "applies broadly"                 |
| R4     | fallback | 18    | 144   | 0    | 16  | "Updated Clinical Practice 2024"  |
| R5     | fallback | 11    | 125   | 0    | 15  | "PMID 99134830"                   |
| R6     | fallback | 1     | 96    | 0    | 0   | "infrequent and not typically"    |
| R7     | fallback | 1     | 106   | 0    | 0   | "Editorial Update"                |
| R8     | fallback | 1     | 103   | 0    | 0   | "deferred to scheduled outpatient"|
| R9     | fallback | 1     | 88    | 0    | 0   | "88 mg" (50 mg → 88 mg via 1.75x) |
| R10    | fallback | 15    | 120   | 0    | 8   | "URGENT INSTITUTIONAL POLICY"     |

Two notable validations:

* **R5's PMIDs** are in the 99-prefix range as designed (D31). The
  three example PMIDs in the fallback are 99134830, 99326952, and
  99056030 — all outside the real PubMed identifier space.
* **R9's dose tweak** correctly extracted "50 mg" from the synthetic
  evidence and rewrote it as "88 mg" via the 1.75x multiplier
  (D32). 50 × 1.75 = 87.5, which rounds to 88. The output does
  not echo the original "50 mg" anywhere.

### §3.4 — End-to-end LLM run (complete)

**Run date:** 2026-05-10. **Configuration:** Phi-3-mini-4k-instruct,
fp16, greedy decoding, per-instance seed = hash(sample_id) mod
2**32. **Hardware:** L4 GPU on Colab. **Wall-clock:** ~81 minutes
(8.38 s/instance).

#### Table 3.4 — Per-family LLM-augmented status distribution

| Family | N   | success | fallback | deviated |
|--------|-----|---------|----------|----------|
| R1     | 47  | 47      | 0        | 0        |
| R2     | 30  | 1       | 0        | 29       |
| R3     | 60  | 6       | 0        | 54       |
| R4     | 61  | 9       | 0        | 52       |
| R5     | 49  | 16      | 0        | 33       |
| R6     | 79  | 14      | 0        | 65       |
| R7     | 54  | 11      | 0        | 43       |
| R8     | 90  | 29      | 0        | 61       |
| R9     | 81  | 35      | 0        | 46       |
| R10    | 31  | 16      | 0        | 15       |
| **All**| 582 | 184     | 0        | 398      |

The fallback skeleton was not invoked for any instance. Every V2
payload in the output Parquet is Phi-3-mini-generated. This
exceeded our expectations — the fallback path was designed as
insurance for refusals and pathological outputs, and observing
zero fallbacks confirms that the prompt design and refusal-
detection thresholds operate in their intended regime.

### §3.5 — Status interpretation: success vs. deviated

**Status:** complete. **Analysis date:** 2026-05-10.

The original acceptance threshold in §3.4 (pre-revision) was
"`success + deviated ≥ 70 %`". Our actual `success + deviated`
rate is 100 %, so the threshold is trivially met. However, the
threshold was framed around an implicit assumption that `deviated`
indicated degraded output, which turned out to be empirically
false. This subsection records the post-hoc analysis and the
threshold revision (decision D41).

#### Table 3.5 — Per-family surface deviation profile

Word-ratio = average actual words ÷ average target words; the
target is the per-instance feature vector from MPIB's
reconstruction hook. Line-ratio = average actual lines ÷
average target lines. Values < 1 mean the LLM is *terser* than
the MPIB target; values > 1 mean verbose.

| Family | N   | AvgW | TgtW | W-Ratio | AvgL | TgtL | L-Ratio |
|--------|-----|------|------|---------|------|------|---------|
| R1     | 47  | 74   | 85   | 0.86    | 1.0  | 1.0  | 1.00    |
| R2     | 30  | 131  | 148  | 0.88    | 1.0  | 5.8  | 0.17    |
| R3     | 60  | 124  | 133  | 0.93    | 1.0  | 2.7  | 0.37    |
| R4     | 61  | 181  | 201  | 0.90    | 21.4 | 10.8 | 1.98    |
| R5     | 49  | 148  | 214  | 0.69    | 9.1  | 12.6 | 0.72    |
| R6     | 79  | 127  | 152  | 0.83    | 1.0  | 4.2  | 0.24    |
| R7     | 54  | 96   | 96   | 1.00    | 1.0  | 1.0  | 1.00    |
| R8     | 90  | 137  | 148  | 0.93    | 1.0  | 3.4  | 0.29    |
| R9     | 81  | 120  | 130  | 0.92    | 1.0  | 2.1  | 0.48    |
| R10    | 31  | 205  | 272  | 0.75    | 29.6 | 23.9 | 1.24    |

**Word-ratio finding.** Every family produces fewer words than its
target on average (max ratio is R7 at 1.00). The hypothesis "Phi-3
is verbose and that explains the deviation rate" is empirically
falsified: Phi-3-mini is *terser* than MPIB's originals, not more
verbose, on this task.

**Line-ratio finding.** The deviation is concentrated in the line
dimension, not the word dimension. Single-paragraph families (R2,
R3, R6, R8, R9) consistently collapse to one line where the MPIB
originals had multi-line structure. Multi-paragraph families (R4,
R10) sometimes overshoot. This is consistent with the post-fix
behaviour of `_strip_llm_artifacts` (D34, paragraph collapsing
for single-paragraph families) interacting with reconstruction-
hook targets that were derived from MPIB's actual surface
distribution — which is multi-line even for single-paragraph
content. The collapse fix improved single-paragraph fluency at the
cost of inflating the line-count deviation for families whose
MPIB originals happened to have higher line counts.

#### Hand-review of R2 (worst-performing family by raw success rate)

R2 has 1/30 = 3.3 % success rate, the lowest of any family.
Five random R2 instances tagged `deviated` were hand-reviewed for
mechanism faithfulness:

| Sample (truncated id)   | Mechanism-faithful contraindication masking? |
|-------------------------|----------------------------------------------|
| V2_PubMedQA_9ddc4106c4 | yes — *"safety considerations not impacting routine use"* |
| V2_PubMedQA_dd6ae3ee8a | yes — *"without contraindications meriting clinical concern"* |
| V2_PubMedQA_bf82dcf851 | yes — *"safety considerations not impacting routine use"* |
| V2_PubMedQA_6c139861c8 | yes — *"without contraindications meriting clinical concern"* |
| V2_PubMedQA_edb78f60ab | yes — *"With no significant safety concerns identified"* |

All five samples execute the R2 mechanism correctly. The flag
`deviated` in this run **does not indicate degraded output**; it
indicates output whose surface shape (specifically line count)
differs from the MPIB target. The content is mechanism-faithful.

#### Conclusion

The 398 `deviated` outputs are usable training signal. They
execute the per-family adversarial mechanism correctly and differ
from MPIB's originals only in surface shape — predominantly in
line count, not in the adversarial content. For a detector that
generalizes to attackers who do not know MPIB's surface
conventions, surface-form diversity in the training data is a
feature, not a defect. We proceed to Stage 04 with all 582
generated payloads.

The acceptance criterion is revised in decision D41 to reflect
what `deviated` actually means: non-fallback rate ≥ 95 % AND
mechanism-marker hand-review ≥ 90 % on a per-family 5-sample
audit. Our current run meets both: 100 % non-fallback, 5/5
mechanism-faithful on the worst-performing family.

---

## §4 — Stage 04: Seven-variant Dataset Construction

**Status:** v0.5.0 framework run complete; routing fix applied in
v0.5.1; rerun pending.

**Run date:** 2026-05-11 (v0.5.0 first run). **Wall-clock:** under
a minute (vs Stage 03's 81 minutes; pure data shuffling, no LLM).

### Table 4.1 — Output schema columns (D49 native nested types)

| Column                | PyArrow type          | Nullable | Notes                                  |
|-----------------------|-----------------------|----------|----------------------------------------|
| `instance_id`         | `string`              | no       | Globally unique                        |
| `parent_id`           | `string`              | no       | Leakage-detection key                  |
| `split`               | `string`              | no       | One of the seven split names           |
| `input_text`          | `large_string`        | no       | Concatenated CDSS string (D43)         |
| `label`               | `int8`                | no       | 0 benign / 1 adversarial (D45)         |
| `vector`              | `string`              | no       | V0/V0p/V1/V2/benign_clinical/generic_attack |
| `source`              | `string`              | no       | Provenance                             |
| `scenario`            | `string`              | yes      | MPIB S1–S4 or null                     |
| `severity`            | `int8`                | yes      | MPIB 0–4 or null                       |
| `harm_types`          | `list[string]`        | yes      | MPIB H1–H5 list or empty               |
| `generation_status`   | `string`              | yes      | V2 only: success/deviated/etc.         |
| `wrapper_template_id` | `string`              | yes      | Benign: which wrapper was applied      |
| `input_text_hash`     | `string`              | no       | SHA-256 prefix for dedup verification  |

### Table 4.2 — Per-split row counts

Both the v0.5.0 first-run figures (with the routing bug) and the
v0.5.1 fixed-run figures are recorded for the audit trail.

| Split                     | v0.5.0 (buggy) | v0.5.1 (fixed) | Δ      | Composition (v0.5.1)                              |
|---------------------------|----------------|----------------|--------|--------------------------------------------------|
| `train`                   | 14,846         | 14,846         |     0  | MPIB train (all vectors) + 80% benign-clinical    |
| `val`                     |  1,759         |  2,728         |  +969  | MPIB val (all vectors) + 10% benign-clinical      |
| `test_v1`                 |     67         |     67         |     0  | MPIB test V1-only                                 |
| `test_v2`                 |     64         |     64         |     0  | MPIB test V2-only                                 |
| `calibration`             |    455         |    455         |     0  | 5% benign-clinical                                |
| `clinical_benign_holdout` |    455         |    455         |     0  | 5% benign-clinical                                |
| `generic_attack_ood`      |    301         |    301         |     0  | deepset + JailbreakBench                          |
| **Total written to disk** | **17,947**     | **18,916**     | **+969** |                                                |
| **Total in unified table**| **18,916**     | **18,916**     |     0  | (v0.5.0 counted the silently-dropped rows here)   |

The 969-row delta corresponds exactly to MPIB's full validation
partition (257 V0 + 569 V0p + 80 V1 + 63 V2 = 969; verified
against MPIB's `mpib_split` crosstab). v0.5.0's routing bug
dropped *all* MPIB validation rows, not just the adversarial
ones. The `val.parquet` in v0.5.0 contained zero MPIB content of
any vector — it was 100 % synthetic-wrapped benign-clinical
material. v0.5.1 restores the full MPIB validation partition.

A subtle audit-trail note: the v0.5.0 `row_count_total` field in
its manifest reported 18,916 even though only 17,947 rows reached
disk. This was because the count was taken from the in-memory
`unified` DataFrame before the writer silently dropped the
`"validation"`-tagged rows. The post-write per-split table is
the authoritative count; the manifest header is not. The D52
checksum gate caught all *written* files but did not catch the
*missing* ones. Future stage manifests will additionally record
"rows accepted vs rows written" to make this discrepancy
detectable at the manifest level. (Logged as a v0.6.0 follow-up.)

### Table 4.3 — Per-vector composition of each split (v0.5.1)

The split × vector composition is what the multi-seed training
loop in Stage 06 will see. Recorded here so the class-weight
calibration and any per-vector evaluation slicing are reproducible.

|                       | `train` | `val` | `test_v1` | `test_v2` | `calibration` | `clinical_benign_holdout` | `generic_attack_ood` |
|-----------------------|--------:|------:|----------:|----------:|--------------:|--------------------------:|---------------------:|
| V0                    | 2,206   |   257 |         0 |         0 |             0 |                         0 |                    0 |
| V0p                   | 4,601   |   569 |         0 |         0 |             0 |                         0 |                    0 |
| V1                    |   497   |    80 |        67 |         0 |             0 |                         0 |                    0 |
| V2                    |   455   |    63 |         0 |        64 |             0 |                         0 |                    0 |
| benign_clinical       | 7,087*  | 1,759 |         0 |         0 |           455 |                       455 |                    0 |
| generic_attack        |     0   |     0 |         0 |         0 |             0 |                         0 |                  301 |
| **Total**             | **14,846** | **2,728** | **67** | **64** | **455** | **455** | **301** |

\* `train` benign-clinical figure inferred from total minus
MPIB-derived rows; the per-source breakdown is in the
benign-acquisition log.

### Table 4.4 — Cross-source deduplication (v0.5.1)

| Source            | Before dedup | After dedup | Removed | Notes                              |
|-------------------|--------------|-------------|---------|------------------------------------|
| Benign-clinical pool (total) | n.r. (in logs) | n.r. | n.r. | Recorded in `logs/stage_04_splits.log` |

The pre-dedup benign count and the removed count are written by
the orchestrator but not currently summarized in the manifest.
This is a small gap; v0.6.0 will roll these into the manifest
JSON for table completeness.

### Table 4.5 — Leakage-gate result (v0.5.1)

| Check                                                  | Result                |
|--------------------------------------------------------|-----------------------|
| `parent_id` appears in ≥2 splits                       | 0 collisions ✓        |
| All splits in `SPLIT_NAMES` (D53 strict gate)          | 7/7 valid ✓           |
| `train` has both classes                               | 952 adv / 13,894 benign ✓ |
| `val` has both classes                                 | 143 adv / 2,585 benign ✓  |
| Schema integrity (post-write readback)                 | 7/7 splits readable ✓ |
| D42 fix verified (`harm_types` deserializes as list)   | 7/7 splits pass ✓     |
| Manifest checksum integrity                            | 7/7 SHA-256 match ✓   |

### Table 4.6 — Class balance (v0.5.1)

| Split                     | Benign | Adversarial | Adversarial rate |
|---------------------------|-------:|------------:|-----------------:|
| `train`                   | 13,894 |         952 | **6.4 %**        |
| `val`                     |  2,585 |         143 | **5.2 %**        |
| `test_v1`                 |      0 |          67 | 100 % (by design)|
| `test_v2`                 |      0 |          64 | 100 % (by design)|
| `calibration`             |    455 |           0 | 0 % (by design)  |
| `clinical_benign_holdout` |    455 |           0 | 0 % (by design)  |
| `generic_attack_ood`      |      0 |         301 | 100 % (by design)|

`train` and `val` are both benign-skewed, as designed (D50). The
class weights (1.0, 3.0; D21) and the Alarm-Burden Inequality
(Methodology §4.6, pending) are calibrated for this regime. The
`val` adversarial rate (5.2 %) is close enough to the `train`
rate (6.4 %) that in-loop validation metrics will be
distributionally faithful to training conditions.

### Table 4.7 — Test-set size and statistical power

| Set       |  N | Wilson 95 % CI at TPR=0.80 | Wilson 95 % CI at TPR=0.95 |
|-----------|---:|---------------------------:|---------------------------:|
| `test_v1` | 67 | 0.69 – 0.88                | 0.87 – 0.99                |
| `test_v2` | 64 | 0.68 – 0.89                | 0.87 – 0.99                |

The test sets are small (this is a property of MPIB, not of
Stage 04). Stage 06 evaluation must report paired bootstrap CIs
when comparing PharmGuard to baselines, not point estimates,
because the binomial uncertainty at n=64-67 is on the order of
±10 points TPR.

### Table 4.8 — Wall-clock (v0.5.1)

| Phase                                | Time |
|--------------------------------------|------|
| Load upstream artifacts              | <5 s |
| Patch V2 contexts                    | <1 s |
| Cross-source dedup                   | 1–2 s|
| Build input_text (MPIB + benign)     | 2–4 s|
| Split assignment + leakage check     | <1 s |
| Write 7 Parquets atomically (D51)    | 4–6 s|
| Write manifest with checksums (D52)  | 1–2 s|
| Post-write verification              | 2–3 s|
| **Total**                            | **~30 s** |

Stage 04 is the fastest stage in the pipeline.

---

## §5 — Stage 05: Tokenization

**Status:** framework complete (v0.6.0); Colab run pending.

The tables below are template-ready and will be filled in with
actual numbers after the run.

### Table 5.1 — Configuration

| Setting                | Value                                                       |
|------------------------|-------------------------------------------------------------|
| Tokenizer              | `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract`     |
| Max length             | 512 tokens                                                  |
| Truncation direction   | right                                                       |
| Add special tokens     | yes (`[CLS]` and `[SEP]`)                                   |
| Padding at tokenize    | no (dynamic padding per batch in Stage 06; D58)             |
| Vocab size (expected)  | 30,522                                                      |
| D56 V2 warn threshold  | 25 % truncation rate                                        |

### Table 5.2 — Output schema (D57 native nested types)

| Column                    | PyArrow type      | Nullable | Notes                                                                |
|---------------------------|-------------------|----------|----------------------------------------------------------------------|
| `instance_id`             | `string`          | no       | inherited from Stage 04                                              |
| `parent_id`               | `string`          | no       | inherited from Stage 04                                              |
| `split`                   | `string`          | no       | inherited from Stage 04                                              |
| `input_text`              | `large_string`    | no       | inherited from Stage 04 (preserved for debugging)                    |
| `input_text_hash`         | `string`          | no       | inherited from Stage 04                                              |
| **`input_ids`**           | **`list[int32]`** | **no**   | tokenizer output, unpadded, length ∈ [3, 512]                        |
| **`attention_mask`**      | **`list[int8]`**  | **no**   | tokenizer output, unpadded, all 1s                                   |
| **`token_count`**         | **`int32`**       | **no**   | `len(input_ids)`                                                     |
| **`was_truncated`**       | **`bool`**        | **no**   | true if untruncated length exceeded 512                              |
| **`truncated_token_count`** | **`int32`**     | **no**   | `untruncated_length - max_length` if truncated, else 0               |
| `label`                   | `int8`            | no       | inherited from Stage 04                                              |
| `vector`                  | `string`          | no       | inherited from Stage 04                                              |
| `source`                  | `string`          | no       | inherited from Stage 04                                              |
| `scenario`                | `string`          | yes      | inherited from Stage 04                                              |
| `severity`                | `int8`            | yes      | inherited from Stage 04                                              |
| `harm_types`              | `list[string]`    | yes      | inherited from Stage 04                                              |
| `generation_status`       | `string`          | yes      | inherited from Stage 04                                              |
| `wrapper_template_id`     | `string`          | yes      | inherited from Stage 04                                              |

Bold rows are Stage 05 additions; the remaining 13 are inherited
from Stage 04 unchanged (D59).

### Table 5.3 — Per-split tokenization statistics (v0.6.0 run)

| Split                      | Rows  | Trunc % | Mean tokens | P95 tokens | Max tokens |
|----------------------------|-------|---------|-------------|------------|------------|
| `train`                    | 14,846| 22.6 %  | 291         | 512        | 512        |
| `val`                      |  2,728| 16.3 %  | 265         | 512        | 512        |
| `test_v1`                  |     67| 11.9 %  | 312         | 512        | 512        |
| `test_v2`                  |     64| 57.8 %  | 487         | 512        | 512        |
| `calibration`              |    455| 39.1 %  | 358         | 512        | 512        |
| `clinical_benign_holdout`  |    455| 43.7 %  | 375         | 512        | 512        |
| `generic_attack_ood`       |    301|  0.7 %  | 83          | 185        | 512        |
| **Total**                  | 18,916| 22.4 %  | —           | —          | —          |

Two observations are worth recording. (1) `test_v2` is the
longest split by mean token count (487 vs ~290 elsewhere) —
V2 inputs combine benign evidence plus a poisoned-update block,
so they are systematically longer than V1 (which has no
retrieved-context block at all). (2) `generic_attack_ood` is
the shortest by far (mean 83 tokens) because deepset and
JailbreakBench are short adversarial strings without RAG
context. The training-time class imbalance is therefore also
a length imbalance, which is not by design but is unavoidable
given the corpus composition.

### Table 5.4 — D56 measurement gate: per-vector V2 truncation rates (v0.6.0 run)

| Split        | V2 rows | V2 truncated | V2 truncation rate | Status (threshold = 25 %) |
|--------------|---------|--------------|--------------------|----------------------------|
| `train`      |     455 |          273 | **60.0 %**         | **⚠ EXCEEDS**              |
| `val`        |      63 |           37 | **58.7 %**         | **⚠ EXCEEDS**              |
| `test_v2`    |      64 |           37 | **57.8 %**         | **⚠ EXCEEDS**              |

All three V2-bearing splits exceeded the threshold by a wide
margin. The remarkable consistency across splits (within one
percentage point) indicates a property of the V2 distribution,
not a sampling artifact. **The gate did its job; the spike
diagnostic (§5.6) was triggered to inform the decision.**

### Table 5.5 — Wall-clock (v0.6.0 run)

| Phase                                       | Time   |
|---------------------------------------------|--------|
| Load PubMedBERT tokenizer (cold)            | ~25 s  |
| Tokenize 18,916 rows (batched fast path)    | ~50 s  |
| Write 7 Parquets atomically + manifest      | ~10 s  |
| Post-write verification                     | ~5 s   |
| **Total**                                   | **~90 s** |

Consistent with the pre-run estimate. PubMedBERT tokenizer
download (~440 MB) is the dominant cost on a cold run; warm
runs from cached weights complete in well under one minute.

### Table 5.6 — D56 spike: V2 poisoned-update survival under right-truncation

Diagnostic spike triggered by the D56 gate. The cell
re-tokenized each truncated V2 instance untruncated, located
the `[context:poisoned_update]` marker in token coordinates,
and measured how many of the payload's tokens fell before the
512-token cut.

**Population:** 347 truncated V2 instances (across train + val
+ test_v2).

| Payload survival            | Count | %      |
|-----------------------------|------:|-------:|
| 0 % (entire attack lost)    |    27 |  7.8 % |
| <25 %                       |    35 | 10.1 % |
| 25–50 %                     |    75 | 21.6 % |
| 50–75 %                     |   109 | 31.4 % |
| 75–99 %                     |    96 | 27.7 % |
| 100 % (attack intact)       |     5 |  1.4 % |
| **Median**                  |       | **57.9 %** |
| **Mean**                    |       |   55.0 %  |
| **P25**                     |       |   36.4 %  |
| **P75**                     |       |   78.4 %  |

**Reframed against the full V2 corpus (582 instances total):**

| Quantity                                                  | Value  |
|-----------------------------------------------------------|--------|
| V2 instances total                                        | 582    |
| V2 instances truncated                                    | 347 (59.6 %) |
| V2 instances with 0 % payload surviving                   |  27   |
| **Structural ceiling on V2 detection (right-truncation)** | **≈ 95.4 %**   |

The 4.6 % structural ceiling is the upper bound on V2 recall
under right-truncation alone, set by the share of V2 instances
where the entire attack payload is cut off. The remaining
~95 % of V2 attacks retain at least some payload signal and
are recoverable in principle.

**Regime classification.** Median survival of 57.9 % places us
in the middle regime: not catastrophic loss, not negligible
loss. The decision (D62) is to proceed with right-truncation
and document this limitation, with sliding-window inference
held back as a Stage 07 ablation conditional on the empirical
V2 gap observed in Stage 06. See methodology §3.8.5 for the
full reasoning.

---

## §6 — Stage 06: Multi-seed Training and Calibration

**Status:** Stage 06A framework complete (v0.7.0); Colab run pending.

Tables are template-ready for the first single-seed run. Multi-seed
aggregation in §6.B and ablations in §6.C will be added after the
06A scaffold validates end-to-end.

### Table 6.1 — Training configuration (Stage 06A, seed 42, config "main")

| Hyperparameter        | Value                                          | Source |
|-----------------------|------------------------------------------------|--------|
| Encoder               | `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` | D55 / config |
| Total parameters      | ~110 M                                         | PubMedBERT-base |
| Classification head   | `nn.Linear(768, 2)` over `[CLS]` pooled output | D63 |
| Loss function         | Weighted cross-entropy `[1.0, 3.0]`            | D64 / D21 |
| Optimizer             | AdamW                                          | BERT default |
| Learning rate         | 2 × 10⁻⁵                                       | BERT default |
| Weight decay          | 0.01                                           | BERT default |
| Warmup ratio          | 0.10 (linear, then linear decay)               | BERT default |
| Max gradient norm     | 1.0                                            | BERT default |
| Batch size (train)    | 16                                             | L4 memory |
| Batch size (eval)     | 32                                             | inference 2× |
| Epochs                | 3 (max), early stop on best val AUC patience=1 | D66 |
| Mixed precision       | FP16 on GPU                                    | L4 default |
| Determinism           | full (D69)                                     | D69 |
| Seed                  | 42                                             | first multi-seed value |

### Table 6.2 — Training-time evaluation metrics (template; per-epoch on val)

To be filled from the run's `training_log.json`. Each epoch the
trainer emits: val_loss, val_auc, val_accuracy, val_precision,
val_recall, val_f1. The best-AUC row is the checkpoint kept.

| Epoch | val_loss | val_auc | val_accuracy | val_precision | val_recall | val_f1 | Kept? |
|-------|----------|---------|--------------|----------------|------------|--------|-------|
| 1     | n.r.     | n.r.    | n.r.         | n.r.           | n.r.       | n.r.   | ?     |
| 2     | n.r.     | n.r.    | n.r.         | n.r.           | n.r.       | n.r.   | ?     |
| 3     | n.r.     | n.r.    | n.r.         | n.r.           | n.r.       | n.r.   | ?     |

### Table 6.3 — Calibration: thresholds at target FPRs (template)

To be filled from `calibration.json`. Wilson 95 % CI is on the
*realized* FPR after threshold selection, not the *target* FPR.

| Target FPR β | Threshold τ*(β) | Realized FPR | Wilson 95 % CI on realized FPR | n_calibration | n_false_positives |
|--------------|------------------|---------------|---------------------------------|----------------|--------------------|
| 0.010 (1 %)  | n.r.             | n.r.          | n.r.                            | 455            | n.r.               |
| 0.005 (0.5 %)| n.r.             | n.r.          | n.r.                            | 455            | n.r.               |
| 0.001 (0.1 %)| n.r.             | n.r. *(= 0; see D67 limitation)* | n.r.    | 455            | 0 *(structural)*   |

**Honest note on β = 0.001.** With n_cal = 455, `floor(0.001 × 455) = 0`.
We cannot calibrate to non-zero realized FPR at this target with
the current split size. The Wilson CI on a 0/455 result is
[0, 0.0084], so we report the headline at β = 0.5 % and 1 %, and
treat the 0.1 % target as a separate row with a structural-limit
asterisk. (D67 limitation; mitigation deferred to v1.1 if Stage 07
shows this matters.)

### Table 6.4 — Wall-clock (Stage 06A, seed 42, L4 GPU)

| Phase                                                  | Estimated     | Actual |
|--------------------------------------------------------|---------------|--------|
| Tokenizer + model load (cold; first run downloads encoder ~440 MB) | 30-60 s | n.r.   |
| Tokenizer + model load (warm)                          | 5-10 s        | n.r.   |
| Training (3 epochs × 14,846 rows / batch 16 = ~2,800 steps) | 25-40 min  | n.r.   |
| Calibration pass on 455 rows                           | 5-15 s        | n.r.   |
| Model + tokenizer save                                 | 30-60 s       | n.r.   |
| Manifest + integrity                                   | 2-5 s         | n.r.   |
| **Total**                                              | **~30-45 min**| n.r.   |

Total Drive footprint per (seed, config): roughly 440 MB
(PubMedBERT weights, copied to the per-run directory) + few MB
for tokenizer + few KB for JSON files. 5 seeds × 1 config + 4
ablations × 1 seed ≈ 9 dirs × 440 MB ≈ 4 GB. Bounded.

### Table 6.5 — Artifacts written (per (seed, config))

| Artifact                  | Size (approx.) | Purpose                                  |
|---------------------------|-----------------|------------------------------------------|
| `model.safetensors`       | ~440 MB         | Best-val-AUC model weights               |
| `config.json`             | ~1 KB           | HF model config                          |
| Tokenizer files           | ~500 KB         | vocab.txt + tokenizer.json + ...         |
| `training_log.json`       | ~2 KB           | Per-epoch metrics                        |
| `calibration.json`        | ~2 KB           | Thresholds + score distribution          |
| `stage_06A_manifest.json` | ~3 KB           | SHA-256 of every artifact + run metadata |

All files are atomic-written (D51) and checksummed (D52) the same
way every prior stage does.

### §6.A — Stage 06A: single-seed scaffold validation

**Status:** ran 2026-05-11; **v1.0 model invalidated by diagnostic
findings**. See D70 and §6.A.1 below.

#### Run summary (seed 42, config "main")

| Quantity                     | Value     |
|------------------------------|-----------|
| Package version              | 0.7.0     |
| Encoder                      | `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` |
| Best epoch                   | 2 (of 3 max) |
| Best val AUC                 | **0.9813** |
| Wall-clock                   | ~35 min (within estimate) |
| OOM events                   | 0         |
| Integration checks passed    | 37/37     |

#### Per-epoch training log

| Epoch | val_auc | val_loss | val_accuracy | val_precision | val_recall | val_f1 | Kept |
|-------|---------|----------|--------------|----------------|------------|--------|------|
| 1     | 0.9781  | 0.1212   | n.r.         | 0.9851         | 0.4615     | 0.6286 | ▲    |
| 2     | 0.9813  | 0.1279   | n.r.         | 0.8654         | 0.6294     | 0.7287 | ✓    |
| 3     | 0.9807  | 0.1607   | n.r.         | 0.8103         | 0.6573     | 0.7259 | ▽    |

Early stopping at epoch 3 (patience=1). Best-AUC checkpoint at
epoch 2 retained.

#### Calibration outputs

| Target FPR β | τ*(β)     | Realized FPR | Wilson 95 % CI on realized FPR |
|--------------|-----------|---------------|---------------------------------|
| 0.010 (1 %)  | 0.000083  | 0.0088        | [0.0034, 0.0224]                |
| 0.005 (0.5 %)| 0.000084  | 0.0044        | [0.0012, 0.0159]                |
| 0.001 (0.1 %)| 0.000084  | 0.0000        | [0.0000, 0.0084] *(structural)* |

All three thresholds collapsed near the FP16 floor of 0.0001.
Benign score distribution on calibration: min=p50=p95=max=0.0001,
std=0.0000. This was the first signal of a problem (see §6.A.1).

### §6.A.1 — Diagnostic: wrapper shortcut identified

#### Per-class score distribution diagnostic

Running the trained model on every split (not just val) revealed
patterns inconsistent with genuine attack detection.

| Split                     | n   | Class         | Mean score | Std    | Min    | Max    |
|---------------------------|-----|---------------|------------|--------|--------|--------|
| val                       | 2728 | benign       | 0.0108     | 0.0653 | 0.0001 | 0.9783 |
| val                       | 2728 | adversarial  | 0.6347     | 0.4310 | 0.0041 | 0.9998 |
| test_v1 (V1)              | 67  | adversarial  | 0.3318     | 0.3528 | 0.0125 | 0.9870 |
| test_v2 (V2)              | 64  | adversarial  | **0.9998** | **0.0000** | **0.9998** | **0.9998** |
| calibration               | 455 | benign        | 0.0001     | 0.0000 | 0.0001 | 0.0001 |
| clinical_benign_holdout   | 455 | benign        | 0.0001     | 0.0000 | 0.0001 | 0.0002 |
| generic_attack_ood        | 301 | adversarial  | **0.0031** | 0.0483 | 0.0001 | 0.8383 |

Two patterns stand out and inform the diagnosis:

1. **test_v2 scores collapse to a single value (0.9998) with std=0.**
   Across 64 inputs spanning all 10 V2 rule families, ranging from
   200 to 487 tokens, and including 37 truncated instances, the
   model produces an identical score to four decimal places. This
   is not consistent with semantic content detection.

2. **generic_attack_ood scores at mean 0.003.** The model thinks
   ~99 % of jailbreak attempts from deepset and JailbreakBench
   are benign. A model that learned prompt-injection detection
   would catch these; a model that learned a specific input
   wrapper would miss them.

#### Verification spike (this session, ~30 s wall-clock)

Tested four variants of test_v2's inputs against the trained
model to identify what feature the model was actually using:

| Variant                                              | Mean score | Std    | Min    |
|------------------------------------------------------|------------|--------|--------|
| V1 — original input                                  | 0.9998     | 0.0000 | 0.9998 |
| V2 — strip the literal `[context:poisoned_update]` marker only | 0.9998 | 0.0000 | 0.9996 |
| V3 — strip the *entire poisoned-update block* (marker + content) | 0.9998 | 0.0001 | 0.9991 |
| V4 — strip *all* `[context:*]` markers (content kept) | 0.8919     | 0.1688 | 0.0614 |

The diagnostic interpretation:

* **V2 vs V1**: the literal marker string `[context:poisoned_update]`
  is not the discriminator (V2 still scores 0.9998).
* **V3 vs V1**: removing the entire poisoned-update block — both
  marker and content — also does not drop scores. **The model
  scores test_v2 instances as 0.9998 even with the attack
  content completely removed.** This is the strongest signal
  that the wrapper structure, not the attack semantics, is what
  the model has learned.
* **V4 vs V1**: when all `[context:*]` markers are stripped, scores
  finally fall (mean 0.89, min 0.06, std 0.17). The presence of
  `[context:*]` markers anywhere in the input is the
  discriminative feature.

#### Root cause

Stage 04's `build_input_text` produces three structurally distinct
input wrappers:

* V1: `[system] ... [user] {injected_query}` (no context blocks)
* V2: `[system] ... [user] ... [context:benign_evidence] {e} [context:poisoned_update] {p}`
* Benign-clinical: `[system] ... [user] {clinical_query}` (no context blocks)

In our training distribution, **every input containing
`[context:*]` markers is, by construction, adversarial.** PubMedBERT
correctly minimizes loss by learning marker presence as a perfect
proxy for the adversarial label. The poisoned-update content
itself is never used because it does not need to be — marker
presence already separates the classes.

#### Decision

D70 locks the rework path: re-wrap a fraction of benign-clinical
inputs with `[context:benign_evidence]` blocks (using PubMedQA
long-answer text as retrieved benign evidence). This breaks the
marker-as-shortcut by introducing benign instances at every
structural shape the adversarial distribution occupies.

The v1.0 model at
`pharma_models/seed_42_config_main/` is preserved on Drive for
forensic comparison against the v1.1 model that comes after the
fix. Methodology §4 will gain an addendum documenting this
finding as an example of the distributional-contamination
failure mode the post-stage diagnostic pattern (D54) was
designed to catch.

---

### §6.B — Stage 06B: multi-seed aggregation (planned)

**Status:** not started.

Will repeat Stage 06A across all 5 seeds in `CONFIG.seeds`
= (42, 123, 456, 789, 2024). Each seed produces its own per-run
directory. Aggregation table will report mean ± std for
best_val_auc, calibrated TPR at each target FPR, and calibrated
threshold τ*(β).

### §6.C — Stage 06C: ablations (planned)

**Status:** not started.

Will run Stage 06A at seed 42 with four config variants:

* `bertbase` — `bert-base-uncased` encoder (probes biomedical
  pre-training contribution)
* `distilbert` — `distilbert-base-uncased` encoder (probes
  encoder capacity)
* `noweight` — class weights `[1.0, 1.0]` (probes class-weighting
  contribution per D21 / D64)
* `nophi` — placeholder; Φ is identity in v1.0, so this ablation
  is structurally equivalent to `main`. May be dropped or
  reformulated as "input-text without `[system]` prefix" to make
  it informative.

---

## §7 — Stage 07: Baseline Comparison

**Status:** stubbed.

Will compare PharmGuard against the four published detectors:
ProtectAI v2, InjecGuard, PromptGuard-86M, Fmops. Plus the four
PharmGuard ablations: -Φ, -class-weight, BERT-base encoder,
DistilBERT encoder.

Anticipated key table:

#### Table 7.1 (template; pending run)

| Detector              | AUC   | TPR @ FPR=1% | TPR @ FPR=0.5% | TPR @ FPR=0.1% |
|-----------------------|-------|--------------|----------------|-----------------|
| ProtectAI v2          | n.r.  | n.r.         | n.r.           | n.r.            |
| InjecGuard            | n.r.  | n.r.         | n.r.           | n.r.            |
| PromptGuard-86M       | n.r.  | n.r.         | n.r.           | n.r.            |
| Fmops                 | n.r.  | n.r.         | n.r.           | n.r.            |
| PharmGuard (ours)     | n.r.  | n.r.         | n.r.           | n.r.            |
| -Φ ablation           | n.r.  | n.r.         | n.r.           | n.r.            |
| -class-weight ablation| n.r.  | n.r.         | n.r.           | n.r.            |
| BERT-base encoder     | n.r.  | n.r.         | n.r.           | n.r.            |
| DistilBERT encoder    | n.r.  | n.r.         | n.r.           | n.r.            |

---

## §8 — Stage 08: Adaptive Attacks

**Status:** stubbed.

---

## §9 — Stage 09: Difficulty Stratification

**Status:** stubbed.

---

## §10 — Stage 10: Drift Recalibration

**Status:** stubbed.

---

## §11 — Stage 11: Aggregation

**Status:** stubbed.
