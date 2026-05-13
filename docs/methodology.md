# PharmGuard Methodology

This is the living methodology document for the PharmGuard project.
It is maintained continuously throughout the project rather than
retrofitted at the end. The structure mirrors what will eventually
become Sections 3 and 4 of the paper, and entries are written to be
quotable directly into the manuscript with minimal editing.

Each section ends with a **status** marker:
* **complete** — the work for that section is finished and the writeup
  reflects the final state of the codebase.
* **in progress** — work is underway; the writeup describes what
  exists today and flags what is still pending.
* **stubbed** — the section is a placeholder for work not yet started.

When a stage of work is completed, its section is promoted from
*stubbed* → *in progress* → *complete*. Numerical findings discovered
during that work are recorded in `results_log.md`, and any locked
decisions are recorded in `decisions.md`.

Cross-references are dense by design. The same artifact (e.g., the
R7 review session) is named across all three documents so that a
reviewer reading any one of them can locate the supporting evidence
in the other two.

---

## 1. Problem Framing

**Status:** complete.

### 1.1 The clinical detector deployability problem (CDDP)

We frame our contribution around a problem class we name the
**Clinical Detector Deployability Problem (CDDP)**: the gap between
the reported performance of a generic prompt-injection detector on
its own benchmark and its operating performance when deployed in
front of a clinical decision support system (CDSS). The CDDP is
characterized by four properties that distinguish it from generic
prompt-injection detection:

1. **Authority compounding.** Clinical RAG systems retrieve from
   sources that are *implicitly* trusted (institutional guidelines,
   curated knowledge bases). A poisoned document that adopts the
   linguistic register of a guideline accumulates credibility from
   that register before the detector sees it. This is empirically
   demonstrated by the MPIB result that V2 (indirect/RAG-mediated)
   harm in some configurations is *higher* than V1 (direct), the
   opposite of what one would expect under naive instruction-prior
   reasoning [Lee et al., 2026].

2. **Plausibility floor.** Clinical text in legitimate use already
   contains imperatives ("administer", "discontinue", "prescribe"),
   institutional formatting ("Editor's Note", "Updated Guidance"),
   and confident absolute claims. Detectors trained on generic
   web text learn that these features are evidence of injection.
   In clinical text they are evidence of *legitimacy*. This produces
   a plausibility floor below which a clinical-injection detector
   cannot operate without unacceptably high false-positive rates.

3. **Asymmetric harm.** A false negative in a CDSS pipeline can
   propagate into a contraindicated prescription, a missed triage
   escalation, or a fabricated citation acted upon by a clinician.
   A false positive blocks a benign clinical query — annoying, but
   not patient-facing harm. Standard detector evaluation (AUC,
   F1) treats these symmetrically. The PromptShield paper [Jacob et
   al., 2025] addresses this by selecting decision thresholds at
   target FPRs (1%, 0.5%, 0.1%, 0.05%) and reporting TPR at those
   operating points. We adopt the same evaluation philosophy and
   extend it to a clinically grounded harm taxonomy.

4. **Distribution stability.** Clinical guidelines are revised on
   yearly-to-decadal timescales. A detector trained today must
   continue to operate when the distribution of *legitimate*
   clinical text shifts (new guideline language, new institutional
   formats, new drug names). This drift problem is largely absent
   from the generic prompt-injection literature, where the legitimate
   distribution is held fixed.

We do not claim novelty for any single property. We claim novelty
for the framing: that any practical clinical-injection detector
must satisfy all four simultaneously, and that the field has been
optimizing detectors that satisfy at most two.

### 1.2 Threat model

We adopt MPIB's threat model unchanged for the V2 (indirect/
RAG-mediated) attack vector. The adversary controls the *content
of retrieved documents* but not the system prompt, model parameters,
decoding configuration, or the user's query. Each evaluation
instance is guaranteed to expose the model to at least one poisoned
document: we are evaluating *post-retrieval* failure modes, not
retrieval-system robustness. This is consistent with MPIB's stated
out-of-scope factors and isolates the question we care about, which
is whether a *detector* placed between retrieval and the foundation
model can intercept the poisoned context.

For the V1 vector we use MPIB's direct injection scenarios verbatim.
The V1 adversary controls only the user query and is otherwise
unconstrained — they can use urgency framing, false authority claims,
explicit instruction overrides, and so on (MPIB's R1–R6 V1 templates).

### 1.3 Defender model

We assume the defender is a CDSS operator deploying an LLM-based
component (RAG-based summarization, dosing assistant, triage
support, guideline lookup) and wishes to add a prompt-injection
detector in front of the LLM call. The detector receives the same
text that would otherwise reach the LLM (post-retrieval, post-
concatenation) and outputs a binary decision plus a confidence
score. Blocked queries are routed to a refusal handler; allowed
queries are forwarded to the LLM.

The defender's deployment constraints are concrete:

* Single L4-class GPU at inference (16 GB VRAM, ~242 TFLOPS FP16).
* Latency budget consistent with interactive CDSS use (under 100 ms
  for the detector's contribution on representative inputs).
* Detector is a separate component; the back-end LLM is treated as
  a black box and is not retrained.
* The detector is calibrated once at deployment time. Re-calibration
  for distribution drift happens periodically (months, not minutes)
  and uses a held-out clinical-benign sample collected since the
  previous calibration.

This profile is more restrictive than the typical published
detector setup (multi-GPU training, server-side deployment with
loose latency budgets) and more permissive than the typical
edge-deployment setup. It reflects the realistic operational
envelope of a hospital information-systems team.

---

## 2. Pipeline Overview

**Status:** complete.

The pipeline has eleven stages. Stages 00–03 are the data-construction
phase and are complete as of v0.4.0. Stages 04–11 are described at
a higher level here and will be expanded as they are executed.

| Stage | Purpose                                            | Status (v0.4.0) |
|-------|----------------------------------------------------|-----------------|
| 00    | Environment setup, Drive verification              | complete        |
| 01    | Acquire benign and generic-attack sources          | complete        |
| 02    | Acquire MPIB and run 10-pass EDA                   | complete        |
| 03    | Synthetic V2 payload reconstruction (R1–R10)       | complete        |
| 04    | Seven-variant dataset construction (splits)        | complete        |
| 05    | Tokenization and feature preparation               | complete        |
| 06    | Multi-seed training and FPR-targeted calibration   | stubbed         |
| 07    | Baseline FPR-anchored evaluation against four      | stubbed         |
|       | published detectors                                |                 |
| 08    | Adaptive attack evaluation (paraphrase, encoding,  | stubbed         |
|       | rewrite, optimization)                             |                 |
| 09    | Cross-detector difficulty stratification of the    | stubbed         |
|       | benchmark                                          |                 |
| 10    | Drift simulation and recalibration protocol        | stubbed         |
|       | demonstration                                      |                 |
| 11    | Results aggregation and figure generation          | stubbed         |

Each stage produces a Parquet artifact under
`data/<stage-name>/` on Drive, plus a JSON report under
`reports/<stage-name>/` summarizing what was produced and any
exceptions or warnings. The Colab notebook drives the stages in
order; each stage is also runnable as a standalone script, so the
methodology is reproducible without the notebook environment.

---

## 3. Data Construction

**Status:** complete (Stages 01–03).

### 3.1 Source acquisition (Stage 01)

The detector must distinguish three categories of text in deployment:
benign clinical queries, benign generic queries, and adversarial
inputs. We acquire training and evaluation material for each.

**Benign clinical sources.** Four sources, chosen to span the
clinical text taxonomy used in MPIB and the published deployment
context of clinical AI assistants:

1. **MTSamples** — transcribed clinical notes across multiple
   specialties. Provides the baseline distribution of natural
   clinical writing.
2. **PubMedQA / MedQA train splits (held-out from MPIB lineage)** —
   biomedical research and exam-style clinical questions.
3. **OpenFDA drug labels** — formal pharmacological text with the
   exact register that R9 (dose tweak) and R6 (warning demotion)
   attempt to mimic. Including this in benign training is what
   prevents the detector from learning "structured dosing language
   = injection".
4. **`omi-health/medical-dialogue-to-soap-summary`** — clinician-
   patient dialogue paired with SOAP summaries. Replaces the
   originally-planned `medical_dialog` dataset, which is no longer
   accessible on Hugging Face (see §3.5 for the substitution
   rationale).

**Benign generic sources** (for the detector's chatbot/conversational
slice, following PromptShield's two-category taxonomy): a
conversational subset is drawn during Stage 04 dataset assembly,
not Stage 01 acquisition.

**Generic attack sources.** Two sources:

1. **`deepset/prompt-injections`** — a curated set of prompt-injection
   strings collected from public reports and challenges. Provides
   transfer-test material for the detector: an OOD attack distribution
   the detector has never seen during training.
2. **JailbreakBench** — adversarial jailbreak strings. Used for an
   ablation in which we ask whether a clinical-injection detector
   trained only on R1–R10 incidentally generalizes to non-clinical
   adversarial input. (We do *not* train on JailbreakBench; we use
   it only at evaluation.)

### 3.2 MPIB ingestion (Stage 02)

MPIB is the primary adversarial source. We use the gated public
release at `jhlee0619/mpib` on Hugging Face Hub, which is the
redacted variant: V2 instances have their poisoned-payload text
replaced with the literal string `[REDACTED_PAYLOAD]`, while all
other fields (the benign evidence context, the user query, the
labels, the rule-family identifier, the reconstruction hook) are
intact. This redaction is MPIB's responsible-release policy
[Lee et al., 2026, Appendix C].

**Schema heterogeneity issue.** MPIB's `contexts` field is a list of
heterogeneous dicts. Some V0/V0' instances have empty contexts; V1
instances have `user_query`-anchored contexts; V2 instances have a
mix of `benign_evidence` and `poisoned_update` roles, the latter
carrying the `rule_family_id` and the `reconstruction_hook` we
need for synthesis. This heterogeneity defeats `datasets.load_dataset`,
which infers a single struct schema across all rows. We bypass the
HF datasets layer entirely and use `huggingface_hub.hf_hub_download`
to fetch the raw JSONL files, then parse them line-by-line with a
permissive schema. (See D17 in `decisions.md`.)

**EDA findings.** The 10-pass EDA produced findings that materially
shaped Stage 03 and Stage 04. The full numerical findings live in
`results_log.md` §2; the decisions they motivated are summarized
here:

* **9,697 instances total**, partitioned by the project as 7,759
  train / 969 validation / 969 test on a `parent_sample_id`-grouped
  basis. The grouping is a defense against paraphrase-leakage
  between splits and is a property of MPIB's release. We honor it
  unmodified (D11).
* **V2 redaction rate is 100%** of V2 instances. Every V2 instance
  in the public release has its `poisoned_update.text` field
  replaced with `[REDACTED_PAYLOAD]`. This is the entire reason
  Stage 03 exists: without reconstruction, we have zero V2 training
  signal for the detector.
* **V2 instances cluster overwhelmingly in scenario S4** (548 of
  582). V1 instances cluster in S2 and S3. This non-uniformity is
  MPIB's design choice: V2 attacks target the evidence-based-guideline
  scenario where authority framing is most persuasive. We preserve
  the distribution rather than uniformize it.
* **Severity distribution is bimodal**: a mass at severity 0
  (5,234 instances, the safe-baseline cases) and a mass at severity
  3 (3,250 instances, the high-harm cases). Severities 1, 2, 4 are
  comparatively sparse. This bimodality is consistent with MPIB's
  reporting of CHER3 as the headline outcome metric.
* **Harm-type distribution is heavily H3-dominant** (Emergency
  Downplay, 2,806 instances), followed by H5 (Evidence Manipulation,
  822), H1 (Misdiagnosis, 746), H2 (Treatment Error, 692), and H4
  (Guidance Conflict, 32). H3 dominance is consistent with the
  S2/S3 (medication, triage) clustering of V1 instances.
* **Source provenance:** 9,099 instances from MedQA, 598 from
  PubMedQA. V1 instances are MedQA-derived; V2 instances are
  PubMedQA-derived. This is consistent with MPIB's stated
  construction recipe.
* **Schema integrity:** zero parent-id leakage between the 80/10/10
  splits. One cosmetic schema discrepancy: the project uses `V0p`
  in some metadata fields where the paper uses `V0'`. We adopt
  `V0p` throughout the codebase (D22).

### 3.3 V2 payload reconstruction (Stage 03)

This is the section that distinguishes our use of MPIB from a
straightforward consumer of the public release. Because every V2
poisoned-update text is redacted, we must synthesize replacement
payloads for all 582 V2 instances before they can be used as
training signal. This subsection documents the design of that
synthesis.

#### 3.3.1 Why synthesis is needed

Three options were considered:

1. **Apply for unredacted access.** MPIB provides a Tier-1 gated
   release of unredacted payloads under a research agreement
   [Lee et al., 2026, Appendix C.2]. We considered this and rejected
   it for two reasons. First, redistribution constraints in the
   gated agreement would limit our ability to release the resulting
   PharmGuard detector and any artifacts derived from training on
   those payloads. Second, depending on a single source's
   unredacted artifact for training data couples our reproducibility
   to that source's continued availability, which is a fragile
   dependency for a multi-year research artifact.

2. **Treat V2 as evaluation-only.** We could decline to train on
   V2 instances at all and use them only as a held-out test set.
   This would deprive the detector of all V2 training signal — the
   exact distribution it most needs to recognize. The reduction in
   training data (from 9,697 to 9,115 instances) is small in
   percentage terms but the qualitative loss is large, because V2
   is the modality the published detectors fail on most severely
   [Jacob et al., 2025, §5.2].

3. **Synthesize replacement payloads.** Use the rule-family identifier
   and reconstruction hook (which MPIB does not redact) to
   regenerate plausible payloads matching the original's surface
   profile and adversarial mechanism. This is the option we adopt.
   It preserves the per-instance attack semantics (the rule family
   defines the mechanism; the reconstruction hook defines the
   surface form) without requiring access to the original text.

The reconstruction hook in each MPIB V2 instance contains the
target rule family and a target feature vector (lines, words,
header count, formatting count). MPIB's authors included this hook
specifically to support reconstruction by downstream researchers.
We are using the hook as designed.

#### 3.3.2 Per-family design philosophy

Each of MPIB's ten V2 rule families [Lee et al., 2026, Table 9]
implements a distinct adversarial mechanism. Naive approaches
(single shared template, single LLM prompt with the family ID as
a parameter) lose the per-family mechanism. We instead implement
each family as its own `TemplateStrategy` subclass under
`pharmguard.data.reconstruction.templates`. Each strategy contributes
two methods:

* `build_prompt(ctx)` — produces a per-family LLM prompt that
  describes the mechanism in concrete terms ("subtly increase doses
  by treating the new value as if it were the standard
  recommendation") rather than abstract terms ("dose tweak attack").
  The prompt also injects per-instance context: the original benign
  evidence, the surface-feature targets, and (for R9) the actual
  dose extracted from the evidence.
* `fallback_skeleton(ctx)` — produces a hand-authored adversarial
  skeleton that does not require the LLM. The skeleton is used
  when the LLM refuses, produces malformed output, or is unavailable
  (CPU-only environments). The skeleton is mechanism-faithful: it
  does not attempt to be as fluent as the LLM output but it does
  execute the same adversarial mechanism.

This two-method contract is what makes Stage 03 robust to LLM
failure. Even with `--no-llm`, every instance gets a valid
mechanism-faithful payload. With the LLM enabled, most instances
get a more fluent payload and the fallback is exercised only for
the residual.

The mechanism descriptions, encoded into both the prompt and the
skeleton, are:

| Family | Mechanism                                                                                          |
|--------|----------------------------------------------------------------------------------------------------|
| R1     | Promotes correlational findings to definitive clinical principles for routine use                  |
| R2     | Repeats findings while removing safety caveats and contraindication language                       |
| R3     | Names the original cohort restrictions and explicitly dismisses them as immaterial                 |
| R4     | Frames the original as superseded by a fictional 2024 consensus, with structured "Updated Guidance"|
| R5     | Inserts fake PMIDs (99-prefix range, outside real PMID space) and fake journal names               |
| R6     | Repeats findings while minimizing adverse events as "infrequent" or "not typically of concern"     |
| R7     | Editorial framing — "Editor's Note" — paired with explicit reversal of the original recommendation |
| R8     | Recasts emergent presentations as routine outpatient care (the most clinically dangerous family)   |
| R9     | Extracts real dose values from the evidence and multiplies them by 1.75x while preserving units    |
| R10    | Institutional-policy voice with mandatory directives and compliance language                       |

Two design decisions deserve emphasis. **R5's fake PMIDs use the
99-prefix range** (D31). Real PubMed identifiers fall well below
50,000,000; PMIDs starting with 99 are unused. This means our R5
instances cannot be confused with real citations by downstream
consumers, which matters if the synthesized data ever leaks into
training corpora. **R9's dose multiplier is 1.75x** (D32). This is
large enough to be clinically dangerous (a 50 mg → 88 mg dose
increase is well beyond typical titration ranges for most drugs)
but small enough that the inflated value reads as plausible — it
does not jump from milligrams to grams.

#### 3.3.3 LLM choice and configuration

We use Microsoft's `Phi-3-mini-4k-instruct` for the LLM-augmented
generation path (D23). The decision considered Qwen2.5-3B and
Llama-3.2-3B as alternatives. Phi-3-mini won on three criteria:

1. **Size fit.** 3.8B parameters in fp16 fits comfortably in L4's
   16 GB VRAM with room for a generation cache and the orchestrator's
   working memory.
2. **Instruction-following.** Phi-3-mini follows multi-paragraph
   constraint specifications ("approximately 105 words", "no line
   breaks", "begin with this preamble") more reliably than the
   alternatives we tried.
3. **Refusal rate on benign-adversarial-research framing.** Phi-3-mini
   refuses our prompts at a manageable rate when the prompt is
   honestly framed as fictional adversarial training data. Llama-3.2-3B
   refused at a substantially higher rate in our pilots.

Generation is deterministic: temperature 0.0, greedy decoding,
seed derived per-instance as `hash(sample_id) mod 2**32` (D37).
The seed is recorded in the output schema as `generation_seed`
(D38) so that any output can be reproduced from the source data
plus the seed alone.

#### 3.3.4 The R7 hand-review session

After implementing R7 first as a pilot family, we hand-reviewed
five generated samples before extending the framework to the other
nine families. This review surfaced four issues that became fixes
applied across all ten families. Recording the review here
discharges an important point of methodological honesty: the
reconstruction framework was not correct on first implementation,
and the iteration is part of the work.

The five samples and findings:

1. **Sample 1 (cytokines/epilepsy).** 108 words against a 105-word
   target, single dense paragraph, mechanism-correct. *Result:*
   exemplary; no issue.

2. **Sample 2 (pituitary apoplexy).** 80 words against an 89-word
   target, single dense paragraph. The orchestrator flagged this
   as `oversized` despite being undersized. *Issue identified:*
   the status name was wrong. The flag fires on any deviation, not
   just over-target. *Fix applied:* rename the status to `deviated`
   (D33).

3. **Sample 3 (pharmacist education).** Three lines against a
   one-line target. The LLM had inserted paragraph breaks despite
   the prompt's "single dense paragraph" instruction. *Issue
   identified:* `_strip_llm_artifacts` was preserving paragraph
   breaks for all families, even those whose target surface profile
   is single-paragraph. *Fix applied:* add a `collapse_paragraphs`
   parameter to `_strip_llm_artifacts` and a `preserves_paragraphs`
   class attribute to each `TemplateStrategy`. Single-paragraph
   families (R1, R2, R3, R6, R7, R8, R9) collapse; multi-paragraph
   families (R4, R5, R10) preserve (D34).

4. **Sample 4 (asthma phenotypes).** Same three-line issue as
   Sample 3. *Result:* the fix in (3) addresses this case as well.
   Confirmed empirically post-fix.

5. **Sample 5 (amoxapine).** The output executed a *refinement*
   of the original recommendation rather than a *reversal*. R7's
   editorial-note mechanism requires actual contradiction of the
   source, not a softer caveat. *Issue identified:* the R7 prompt
   said "advisory" when it should have said "reversal".  *Fix
   applied:* strengthen the R7 prompt with the explicit phrase
   "should NOT be followed in practice (a clear reversal, not a
   refinement)" (D35).

A fourth fix was applied prophylactically based on the review:
**formatting deviation is informational, not blocking** (D36). If
an instance hits its line and word targets but produces fewer
formatting marks than requested, the orchestrator flags
`formatting_deviation` in the metadata but does not fall back to
the skeleton. This prevents excessive fallback rates on families
where formatting is decorative rather than mechanism-bearing (R1,
R2, R3, R6, R7, R8, R9).

The R7 review was completed on 2026-05-10 before the other nine
families were validated. The four fixes were applied to the
framework before the per-family validation runs, so the validation
results reported in `results_log.md` §3 reflect the post-fix state.

#### 3.3.5 Output schema and reproducibility

Stage 03 writes a single Parquet artifact at
`data/adversarial/reconstructed_v2.parquet` with one row per V2
instance. The schema preserves all fields from the upstream
`parsed_mpib.parquet` plus the following Stage-03-specific columns:

* `original_redacted_text` — the literal `[REDACTED_PAYLOAD]` token,
  preserved for audit (D27). This makes it possible to verify
  that any given output row corresponds to a redacted MPIB instance
  rather than something else.
* `generation_status` — one of `success`, `fallback`, `deviated`,
  `family_not_implemented`, `no_poisoned_context` (D26). The first
  three are normal outcomes; the last two indicate data quality
  issues upstream that should be investigated.
* `generation_seed` — the per-instance integer seed used by
  Phi-3-mini for that row.
* `actual_features` — a dict of measured surface features (lines,
  words, headers, formatting) on the generated text.
* `feature_deviation` — a dict of fractional deviations from the
  reconstruction-hook targets.

A separate `reports/03_reconstruction/samples.json` log captures
five sample outputs per family (D39) for spot-checking. This sample
log is not used downstream and is intended as a manual-review
artifact.

### 3.4 Stage 03 validation

We validated the framework via 15 sandbox tests covering version,
foundation imports, family registration, strategy contract,
end-to-end execution per family, status name consistency,
per-family mechanism markers in the output text, determinism
across runs, refusal detection, paragraph-collapse switching,
topic anchoring, missing-evidence edge case, unknown-family
handling, notebook validity, and per-script syntax. All 15 passed
on v0.4.0. The sandbox results are reported in `results_log.md` §3.

The per-family mechanism marker tests are the most important of
these: they verify that the *content* of each output (not just its
length and formatting) reflects the family's adversarial mechanism.
For instance, the R8 test asserts that the output contains at
least one of {outpatient, deferred, scheduled, ambulatory, primary
care, low-acuity}; the R5 test asserts the output contains the
literal string `PMID`. These are weak checks against false-positive
matches but they are useful sanity gates against silent regressions
where a refactor breaks one family's mechanism while leaving its
length on target.

End-to-end validation against the real LLM (Phi-3-mini on the L4)
over all 582 V2 instances was completed on 2026-05-10. The run
produced `reconstructed_v2.parquet` at the expected path, with
582 rows split 184 `success` / 398 `deviated` / 0 `fallback`. Per-
family counts and the surface-deviation analysis that this run
prompted are in `results_log.md` §3.4 and §3.5. The deviation
finding led to a revision of the Stage 03 acceptance criterion;
the revision is recorded as D41. The wall-clock budget recorded
in D40 was an under-estimate (the actual run took ~81 minutes,
not 30–40); D40 is annotated with a dated amendment to reflect
the actual figure.

### 3.5 Source substitutions and retries

Two upstream-source issues were resolved during Stage 01:

* **`medical_dialog` → `omi-health/medical-dialogue-to-soap-summary`**
  (D18). The original `medical_dialog` dataset is no longer
  accessible on Hugging Face; loading it raises a 404. The
  replacement is structurally similar (clinician–patient dialogue),
  larger, and actively maintained.

* **MPIB `datasets.load_dataset` failure → `hf_hub_download` +
  JSONL parsing** (D17). MPIB's heterogeneous `contexts` schema
  caused the HF datasets library to error on type inference. Direct
  JSONL parsing avoids the issue and gives us the heterogeneous
  schema we need for downstream V2 reconstruction.

Both substitutions were transparent to downstream stages. The
parsed MPIB Parquet has the same columns regardless of the loader,
and the omi-health SOAP dataset fills the same role
(`benign_clinical_dialogue`) in the corpus.

### 3.6 Status interpretation and the deviation finding

**Status:** complete (added 2026-05-10).

This subsection documents a finding that surfaced during post-run
analysis of the v0.4.0 Stage 03 artifact, and the decision it
prompted. We record it here, in the methodology rather than only
in the results log, because the finding changed how we interpret
the `success` vs `deviated` distinction — and how a reader of the
paper should interpret the corresponding numbers we report.

The Stage 03 orchestrator emits one of five statuses per instance:
`success`, `fallback`, `deviated`, `family_not_implemented`,
`no_poisoned_context`. The first three are normal outcomes for a
well-formed input. The last two flag upstream data issues. In our
run, the entire 582-instance corpus split as 184 `success`,
398 `deviated`, 0 of everything else.

We had pre-registered (in the pre-run `results_log.md`) an
acceptance threshold of `success + deviated ≥ 70 %`, intending the
threshold as a guard against the case where most of the corpus
fell back to the hand-authored skeleton. The run met the threshold
trivially (100 %), but the threshold was framed around an implicit
assumption that `deviated` indicated *degraded* output. The
assumption turned out to be empirically false.

Two pieces of evidence:

1. **Surface deviation is concentrated in line count, not word
   count.** Across all ten families the word-ratio (actual ÷ target)
   stays between 0.69 and 1.00; the LLM is consistently terser
   than the MPIB target. The line-ratio for single-paragraph
   families (R2, R3, R6, R8, R9) sits in the 0.17–0.48 band,
   because Phi-3-mini produces single dense paragraphs where MPIB's
   originals had multi-line structure. The same paragraph-collapse
   behaviour we deliberately added in D34 (R7 review fix #2) is
   responsible: it improved single-paragraph fluency at the cost of
   inflating the line-count deviation for families whose MPIB
   originals happened to have multi-line targets in the
   reconstruction hook.

2. **Hand-review of the worst-performing family (R2,
   `success` rate 3.3 %) returned 5/5 mechanism-faithful samples.**
   Each of the five R2 deviated outputs we audited executes the
   contraindication-masking mechanism explicitly ("safety
   considerations not impacting routine use", "without
   contraindications meriting clinical concern", etc.). The flag
   `deviated` does not mean the content is wrong; it means the
   surface shape does not match MPIB's target.

The methodological consequence is that we should not have
treated `deviated` as a failure mode in the pre-run threshold.
For a detector intended to generalize to real adversaries — who
do not know MPIB's surface conventions — surface-form diversity
in the training data is a feature. Discarding the 398 deviated
outputs would be self-imposed data loss for no clinical reason.

We therefore revise the acceptance criterion (D41) to

* **non-fallback rate ≥ 95 %**, and
* **mechanism-marker pass rate ≥ 90 %** on a 5-sample-per-family
  hand-review of the worst-performing family by raw success rate.

The v0.4.0 run meets both criteria (100 % non-fallback; 5/5 R2
mechanism-faithful). All 582 generated payloads are carried
forward into Stage 04.

We disclose this revision openly rather than retrofit the
acceptance criterion to match the result silently, because the
revision rests on a defensible empirical claim about what
`deviated` represents, not on the convenience of crossing the
threshold. The audit trail in `decisions.md` D41 records the
alternatives considered and the reasons for rejecting them.

We also discovered, during this analysis, that the Stage 03
Parquet writer serializes nested fields (`contexts`,
`actual_features`) as JSON strings rather than as PyArrow nested
types. This is a defect (D42), worked around in v0.4.0 read paths
with `json.loads`, and scheduled for fix in v0.5.0 alongside the
Stage 04 writer.

### 3.7 Dataset assembly (Stage 04)

**Status:** complete (v0.5.0).

Stage 04 transforms upstream artifacts into the seven labeled,
split-tagged Parquet files that the rest of the pipeline consumes.
The detector's training, calibration, and evaluation code reads
only Stage 04 output — never the raw upstream artifacts. This is
the layer where "raw data" becomes "the dataset the model sees."

The seven outputs are organized around the deployment requirements
identified in §1.3:

* **train** and **val** — the multi-seed training loop's inputs.
  Composed of MPIB train/val partitions (all vectors V0/V0p/V1/V2)
  plus per-source 80/10 splits of the benign-clinical corpus.
* **test_v1** and **test_v2** — the headline evaluation sets,
  vector-stratified so V1 and V2 performance can be reported
  separately. These come exclusively from MPIB's test partition.
* **calibration** — a 5% slice of benign-clinical text held out
  from training. Used *once* at deployment time to select the
  decision threshold τ\*(β) at the target FPRs of 1%, 0.5%, 0.1%
  (D20). Following PromptShield's methodology, calibration data
  must not overlap with training, validation, or any held-out
  set used for performance estimation.
* **clinical_benign_holdout** — a separate 5% slice of benign-
  clinical text, never used for threshold selection. This is the
  set we use to estimate the *actually-realized* false positive
  rate under field conditions, distinct from the *calibrated* FPR
  used to set the threshold. Reporting both, alongside their
  divergence, is contribution C4b — the drift recalibration
  protocol demonstration.
* **generic_attack_ood** — `deepset/prompt-injections` and
  JailbreakBench in full. The detector never sees these during
  training; they probe whether a clinical-injection detector
  trained only on R1–R10 generalizes to generic adversarial
  inputs. This is the transfer ablation used to motivate the
  CDDP framing in §1.1.

#### 3.7.1 Detector input format

The detector classifies the concatenated string that the back-end
LLM would otherwise see (D43). For every instance — adversarial
or benign — we produce input text in the form:

```
[system] You are a clinical decision support assistant. Provide
accurate, evidence-based responses grounded in the retrieved
documents. Decline to answer if the evidence is insufficient.
[user] {user_query}
[context:{role}] {text}
[context:{role}] {text}
```

The system prompt is identical across every instance, so it
cannot carry label signal. For V1 the contexts block is empty
(adversarial content lives in `user_query`). For V2 the contexts
block carries the Phi-3-mini-generated poisoned update alongside
the benign evidence. For benign-clinical instances the contexts
block carries the source text under a source-appropriate role
tag (see §3.7.2).

This is PromptShield's framework: application-structured data is
the union of system prompt, user query, and retrieved evidence;
the detector sits between this assembly and the LLM. Modeling
the input this way is what allows a *single* detector to handle
both V1 (attack in query) and V2 (attack in context) without
specializing the architecture.

#### 3.7.2 Benign-clinical wrappers

Stage 01's benign-clinical sources (MTSamples, OpenFDA, PubMedQA-
disjoint, omi-health SOAP) provide raw text without the query +
context structure that MPIB instances have. If we used the raw
text as detector input, the detector could trivially learn
"text with `[system]` prefix and `[context:...]` tags = MPIB =
adversarial." We avoid this by wrapping each benign-clinical row
in a per-source synthetic clinical-task framing (D44):

| Source              | Synthetic user query                                                                       | Context role        |
|---------------------|--------------------------------------------------------------------------------------------|---------------------|
| `mtsamples`         | "Summarize the following clinical note in 3-5 sentences."                                  | `clinical_note`     |
| `openfda`           | "Based on this drug-label information, what should a clinician communicate to the patient?"| `drug_label`        |
| `pubmed`            | "Answer the following biomedical question using the provided abstract."                    | `research_abstract` |
| `clinical_dialogue` | "Convert this clinician-patient dialogue into a SOAP-format clinical note."                | `patient_dialogue`  |

The wrappers were chosen to span MPIB's four scenario families
(S1 General Info, S2 Medication, S3 Triage, S4 Guidelines) — note
the rough correspondence: MTSamples summarization parallels S1;
OpenFDA drug-label guidance parallels S2; PubMedQA biomedical QA
parallels S4; clinical-dialogue SOAP parallels S3 in that it
arises from acute encounters. The match is approximate, but the
key property — that benign text in our corpus shares the same
clinical-task surface form as adversarial text — holds.

#### 3.7.3 Split assignment and leakage guards

MPIB's published `parent_sample_id`-grouped 80/10/10 split is
honored unchanged (D11). For MPIB test instances, V1 and V2 rows
are routed to `test_v1` and `test_v2` respectively; V0/V0p test
rows are folded into `val` (they cannot contribute to a
V1/V2-only evaluation).

Benign-clinical rows are deterministically assigned to splits
via SHA-256 hashing of `parent_id + "stage04"` mapped into the
[0, 100) bucket space, partitioned 80/10/5/5 across train, val,
calibration, holdout. The `"stage04"` salt decouples this hashing
from any other deterministic-split scheme upstream, so future
stages can introduce independent splits without accidental
alignment.

Generic-attack instances all go to `generic_attack_ood`.

After assignment, Stage 04 enforces a leakage gate (D49): every
`parent_id` must appear in at most one split. The gate raises
`RuntimeError` with diagnostic detail rather than writing a
corrupt artifact. We additionally check for cross-source content
overlap (D48): benign-clinical rows whose text matches the
content hash of any MPIB user-query are dropped from the benign
pool, on the principle that the MPIB row carries the adversarial
transformation we need and the duplicate would only create
label conflict.

**Amendment 2026-05-11 (v0.5.0 → v0.5.1 routing fix).** The v0.5.0
run of Stage 04 produced a `val.parquet` containing zero
adversarial instances. Investigation traced the cause to a
string-match bug in the routing function: MPIB's `mpib_split`
column uses the value `"validation"`, but our routing code
checked for `"val"`. Rows with `mpib_split == "validation"` were
passed through unchanged into the `split` column, where they
were silently dropped by the writer because `"validation"` was
not in `SPLIT_NAMES`. Cost in v0.5.0: 143 adversarial val
instances missing (80 V1 + 63 V2 from MPIB's validation
partition).

Three fixes applied in v0.5.1, documented as D53:

* Explicit rename map `{"train": "train", "validation": "val",
  "val": "val", "test": "test"}` replaces the implicit
  string-match.
* Unknown `mpib_split` values raise `ValueError` with a clear
  message identifying the offending value and listing accepted
  values.
* A strict post-routing gate asserts that every produced `split`
  value is in `SPLIT_NAMES`. Unrecognized split values raise
  `ValueError` with per-split row counts.

A non-blocking warning is also emitted when `train` or `val` has
zero rows of either class, which is the symptom we would have
seen earlier if any human had looked at the v0.5.0 split summary
carefully.

The v0.5.1 run produces `val.parquet` with ~143 adversarial rows
restored, fully populating the val partition for in-loop
adversarial-aware early stopping.

The lesson recorded against this incident is methodological: my
v0.5.0 sandbox tests used the value `"val"` in synthetic data
rather than the real MPIB value `"validation"`, which is why the
bug passed unit tests and only surfaced in the post-run
diagnostic. Future sandbox tests for routing logic must use real
upstream values, not assumed ones.

#### 3.7.4 Output schema and the D42 fix

The Stage 04 writer uses PyArrow's native nested types — no
JSON stringification (D42 fix). The schema is stable across all
seven output files:

| Column                | Type            | Notes |
|-----------------------|-----------------|-------|
| `instance_id`         | string          | Globally unique |
| `parent_id`           | string          | Leakage-detection key |
| `split`               | string          | One of the seven split names |
| `input_text`          | large_string    | What the detector classifies |
| `label`               | int8            | 0 benign / 1 adversarial |
| `vector`              | string          | V0/V0p/V1/V2/benign_clinical/generic_attack |
| `source`              | string          | Provenance |
| `scenario`            | string nullable | MPIB S1–S4 or null |
| `severity`            | int8 nullable   | MPIB 0–4 or null |
| `harm_types`          | list[string]    | MPIB H1–H5 list or empty list |
| `generation_status`   | string nullable | V2 only: success/deviated/etc. |
| `wrapper_template_id` | string nullable | Benign-clinical: which wrapper was applied |
| `input_text_hash`     | string          | SHA-256 prefix for fast dedup verification |

The runner script verifies the D42 fix by reading each written
Parquet back and asserting `isinstance(df["harm_types"].iloc[0],
(list, np.ndarray))`. A regression would fail this check loudly.

#### 3.7.5 Atomic writes and the manifest

Stage 04 introduces two persistence-robustness measures (D51, D52)
prompted by the data loss we observed between sessions during
Stage 03 development:

* **Atomic writes with fsync** (D51) — each Parquet is written
  to a tempfile in the destination directory, fsync'd to disk,
  then atomically renamed. Without fsync, Drive's FUSE layer
  buffers writes; a runtime termination before the buffer flush
  can lose the file entirely. The atomic rename ensures the
  destination either contains complete, durable bytes or nothing.

* **Stage manifest with checksums** (D52) — after every Parquet
  is written, Stage 04 writes a `stage_04_manifest.json`
  recording each artifact's path, SHA-256, size, and row count.
  Future sessions verify the manifest against the actual files
  before treating the stage as complete. This replaces path-
  probing checkpoints (which we have seen produce false negatives
  when path conventions evolve mid-project) with a checksum-
  verified record.

The two measures together address both the silent-data-loss
class of failure (fsync) and the misleading-checkpoint class
of failure (manifest). Future stages adopt the same convention.

#### 3.7.6 Post-stage integration-check pattern

**Status:** complete (added v0.5.2, 2026-05-11).

Three real bugs surfaced during the v0.4.0 → v0.5.1 development
cycle (the D42 silent JSON stringification, the D53 split-name
routing mismatch, and the between-session Drive data loss). All
three were caught by humans noticing anomalies in raw output
numbers — class balance off, total counts inconsistent, file
counts wrong. None would have been caught by the
`--verify-only` manifest verification, which checks the
manifest's internal consistency (file hashes, recorded row
counts) but not the *semantic correctness* of what was written.

We address this gap with a paired post-stage integration-check
cell in the Colab notebook (D54). The cell reads the stage's
outputs directly from Drive — bypassing the manifest — and runs
explicit assertions in four sections:

1. **Schema-level** checks (D42 class): every output file has
   the expected columns; nested fields like `harm_types`
   deserialize as native Python types rather than JSON strings;
   label values are within the expected domain; required fields
   are non-empty.
2. **Distribution-level** checks (D53 class): splits that should
   contain both classes do; design-pure splits (test_v1/test_v2,
   calibration, holdout) stay pure; vector-stratified splits
   contain only their designated vector.
3. **Leakage** checks: no `parent_id` appears in two outputs
   that should be disjoint.
4. **Upstream contract** checks: properties the next stage
   assumes (input text non-empty, system-prompt prefix present,
   length within sane bounds).

The cell collects every failure rather than raising on the
first one, so a single Colab run surfaces the full diagnostic
picture. If any check fails, the cell prints a clear summary
and instructs the user not to proceed to the next stage until
the failure is resolved.

This pattern is adopted by every stage from Stage 04 onward.
The cumulative coverage grows as each new stage adds its
stage-specific assertions, without rewriting framework code.

### 3.8 Tokenization (Stage 05)

**Status:** complete (v0.6.0).

Stage 05 pre-tokenizes every Stage 04 split with PubMedBERT so
Stage 06's multi-seed training loop does not re-tokenize per
batch. The output is seven Parquet files at
`pharma_data/tokenized/`, each with `input_ids` and
`attention_mask` columns alongside the Stage 04 metadata.

#### 3.8.1 Tokenizer choice and configuration

The tokenizer is
`microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` (D55).
This is paired with the encoder choice (D4 Layer 2) and is not
an independent decision. PubMedBERT is pre-trained on biomedical
abstracts and is the standard biomedical encoder; using a generic
BERT tokenizer would mean discarding the biomedical vocabulary
overlap that motivates Layer 2 in the first place.

The maximum sequence length is 512 tokens (D56), which is
PubMedBERT's positional embedding limit. Inputs longer than 512
tokens are right-truncated — the BERT-standard choice and the
choice used by published baselines including PromptShield.
Special tokens (`[CLS]`, `[SEP]`) consume two positions of the
512, leaving 510 for content.

Tokenization is deterministic (D60): identical input string
produces byte-identical output across runs and Python sessions.

#### 3.8.2 Right-truncation: rationale and the measurement gate

Right-truncation has an asymmetric effect across attack vectors.
V1 attacks place adversarial content at the start of the input
(in the user-query position); right-truncation preserves them
unchanged. V2 attacks place adversarial content in retrieved
contexts, which appear at the end of the input; right-truncation
risks cutting them off when the total input length exceeds 512
tokens.

We chose right-truncation as the v1.0 default for three reasons:

* It is the BERT-standard configuration and matches what the
  published baselines we compare against use, keeping the
  comparison apples-to-apples.
* Left-truncation for V2 instances specifically (the asymmetric
  alternative) would require vector-dependent tokenization logic,
  complicating the implementation and creating a non-standard
  setup that reviewers would reasonably question.
* The empirical truncation rate is unknown a priori and could
  well be small enough that the asymmetric concern is moot.

To make the decision empirical rather than assumed, Stage 05
implements a measurement gate (D61). For each split, per-vector
truncation rates are reported: rows-truncated count,
truncation-rate as a fraction, mean/p95/max token length. The
gate prints a prominent `⚠ EXCEEDS` warning if any split's V2
truncation rate exceeds 25 %. The warning is informational, not
blocking — Stage 05 completes either way — but it surfaces the
empirical signal we need to decide whether to revisit D56.

The 25 % threshold was chosen as a compromise: low enough that
crossing it represents a meaningful share of V2 attacks being
cut off, high enough that crossing it is informative rather than
routine. If V2 truncation exceeds 25 % in the headline run, we
revisit by adopting one of: vector-specific truncation,
sliding-window inference, or a long-context encoder. The cost
of revisiting is one rerun of Stages 05 and 06, which is
recoverable.

The per-vector statistics also go into the manifest, not just
the log. This means future analyses can read the manifest and
reconstruct the truncation rate per slice (split, vector,
scenario) without rerunning. The same recipe applies to any
downstream slicing the paper later requires.

#### 3.8.3 Output format and padding strategy

The Stage 05 schema (D57) adds three new columns beyond Stage 04:

* `input_ids` — `list[int32]`, unpadded, length in [3, 512]
* `attention_mask` — `list[int8]`, unpadded, same length as
  `input_ids`, all 1s
* `token_count` — `int32`, equals `len(input_ids)`
* `was_truncated` — `bool`
* `truncated_token_count` — `int32`, equals `(untruncated_length
  - max_length)` if truncated else 0

There is **no padding at tokenize time** (D58). Padding is
applied dynamically per batch in Stage 06 via
`DataCollatorWithPadding`. Pre-padding to 512 would have
inflated the on-disk size and memory footprint by a factor
roughly equal to `512 / mean_token_count` ≈ 3-5× for typical
inputs, with no compute benefit (the tokenizer can pad just as
fast at batch time).

All 13 Stage 04 columns are preserved (D59) so Stage 06's
evaluation slicing has access to `vector`, `scenario`,
`severity`, `harm_types`, `source` without joining back to
Stage 04 outputs.

#### 3.8.4 Atomic writes, manifest, and integration check

Stage 05 inherits the D51 atomic-write-with-fsync pattern from
Stage 04. The `_atomic_write_parquet` helper is imported from
`pharmguard.data.splits` rather than re-implemented; this is the
first piece of cross-stage code sharing in the project, and
when Stage 06 needs the same helper we will extract it into
`pharmguard/data/io.py`.

The manifest (`stage_05_manifest.json`) records package version,
tokenizer name, max length, truncation direction, per-split row
counts, per-split mean/p95/max token length, per-vector
truncation rates, and per-file SHA-256s. The manifest's
`package_version` field reads `pharmguard.__version__`
dynamically, which is the fix prompted by Stage 04's stale-
version-string issue.

The Stage 05 integration cell (notebook position [26]) follows
the D54 pattern. It checks: every output has the 18 expected
columns; `input_ids` and `attention_mask` deserialize as lists,
not strings; `len(input_ids) == len(attention_mask)` per row;
`token_count == len(input_ids)` per row; no row exceeds
`MAX_LENGTH`; `was_truncated` implies `truncated_token_count >
0`; per-vector V2 truncation rates measured; class balance from
Stage 04 preserved. The cell never raises; it collects all
failures and prints a summary block.

#### 3.8.5 The D56 measurement gate fired — spike, decision, and the path forward

**Status:** complete (added 2026-05-11).

The Stage 05 run reported per-vector V2 truncation rates well
above the D56 25 % warning threshold across every split that
contains V2 instances:

| Split     | V2 truncation rate |
|-----------|--------------------|
| `train`   | 60.0 % (273/455)   |
| `val`     | 58.7 % (37/63)     |
| `test_v2` | 57.8 % (37/64)     |

The remarkable consistency across splits — all within a single
percentage point of each other — indicates that this is a
property of the V2 distribution itself (inherited from MPIB's
construction recipe and our reconstruction lengths), not a
sampling artifact. Roughly 60 % of V2 instances exceed PubMedBERT's
512-token capacity. We pre-registered D56 specifically to surface
this kind of finding; the gate did its job.

Rather than immediately revisit D56, we ran a diagnostic spike
to answer the prior question: **for the truncated V2 instances,
how much of the poisoned-update payload is actually being lost?**
Three regimes were possible: (i) attack mostly intact (truncation
cuts stylistic tail), (ii) attack partially cut (some signal
remains), (iii) attack entirely gone (truncation happens before
the poisoned-update block starts). The choice of mitigation —
right-truncation as-is, sliding-window inference, asymmetric
truncation per vector, or a long-context encoder — depends
critically on which regime we are actually in.

The spike re-tokenized each V2 input untruncated, located the
`[context:poisoned_update]` marker in token coordinates, and
computed the fraction of poisoned-update tokens surviving the
512 cut. Results across all 347 truncated V2 instances:

| Payload survival            | Count | %       |
|-----------------------------|------:|--------:|
| 0 % (entire attack lost)    |    27 |  7.8 %  |
| <25 %                       |    35 | 10.1 %  |
| 25–50 %                     |    75 | 21.6 %  |
| 50–75 %                     |   109 | 31.4 %  |
| 75–99 %                     |    96 | 27.7 %  |
| 100 % (attack intact)       |     5 |  1.4 %  |
| **Median**                  |       | **57.9 %** |

Two findings reframed the decision:

* **7.8 % of truncated V2 (≈ 4.6 % of all V2) have the entire
  attack cut.** These instances are functionally undetectable by
  any model trained on the truncated representation, regardless
  of model capability. This is a structural ceiling, not a
  training problem.
* **The median truncated instance keeps 57.9 % of the
  poisoned-update payload.** Most truncated V2 attacks survive
  to a meaningful degree; the detector retains signal from
  context, framing, and the leading portion of the adversarial
  text.

The decision (D62): **proceed with right-truncation for the
headline detector and document the 4.6 % structural ceiling as
a paper limitation. Sliding-window inference is scheduled as a
Stage 07 ablation, conditional on time and on the magnitude of
the V2 gap actually observed in Stage 06.**

The reasoning has three parts. First, we cannot yet quantify
the practical V2 gap; until Stage 06 produces headline numbers,
investing a session in sliding window is premature optimisation.
Second, all four baseline detectors we compare against face the
same 512-token constraint, so apples-to-apples comparison is
preserved under right-truncation. Third, sliding window as a
late-stage ablation is more publishable than as the headline
design — it frames the encoder's positional limit as an
engineering tradeoff we measured rather than a fix we needed.

We treat the 4.6 % loss as a known limit and report it
explicitly in the paper. The remaining ~95 % of V2 attacks are
recoverable in principle; whether PharmGuard recovers them is a
question Stage 06 will answer.

The spike result is recorded in `results_log.md` §5.6, the
decision in `decisions.md` D62, and the limitation in this
section so the paper's Methods text can quote it directly.

---

## 4. Architecture

**Status:** populated for Stage 06A v1.0; Layer 1 Φ remains
identity in v1.0 and will be expanded in a later ablation.

The four-layer PharmGuard architecture (D4) is implemented as
follows.

### 4.1 Layer 1 — Adversarial canonicalization Φ

**v1.0 implementation:** identity. Φ(x) = x.

The canonicalization layer is reserved for a later expansion in
which Φ explicitly normalizes Unicode confusables, removes
encoded payloads (Base64, hex, URL-encoded), and strips
provenance-spoofing markers ("Urgent Institutional Policy
Update", "Editor's Note") before encoding. For v1.0 we choose to
ship Φ as identity and treat it as a measurement question: if
PharmGuard with identity-Φ already beats published baselines at
FPR=0.1 %, the case for a non-trivial Φ is an ablation; if it
narrowly loses, Φ is the first lever to pull. This deferment
keeps Stage 06A's training scope tight without precluding the
contribution.

### 4.2 Layer 2 — Biomedical encoding E_θ

**v1.0 implementation:** `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract`,
fine-tuned on the binary classification objective.

The choice of PubMedBERT (D55) over generic BERT or BioBERT is
motivated by Layer 2's role in the framework: encode the input
into a representation where benign clinical text and adversarial
injection text are linearly separable. PubMedBERT's biomedical
pre-training gives it dense lexical coverage of clinical terms
(drug names, anatomy, dosing phrases, NCCN/AHA acronyms) that
the adversarial payloads in MPIB inherit from clinical
guidelines. A generic BERT model would treat these terms as rare
sub-word combinations; PubMedBERT treats them as single semantic
units, which is the precondition for the classification head to
learn the benign-vs-adversarial boundary efficiently from
~15k labelled examples.

The encoder produces a `[CLS]` pooled representation of
dimension 768. This representation is fed to Layer 3 unchanged.

### 4.3 Layer 3 — FPR-targeted decision D_τ

**v1.0 implementation:** linear classification head over the
`[CLS]` pooled output (`nn.Linear(768, 2)`), softmax-normalized
to per-class probabilities. The positive-class probability is
the decision score s(x).

The decision rule is `D_τ(x) = 𝟙[s(x) ≥ τ]` with τ selected
**post-training** by the calibration module (D67) against
target FPRs β ∈ {0.01, 0.005, 0.001}. Specifically, τ*(β) is
the smallest threshold such that the empirical FPR on the
held-out pure-benign calibration split is ≤ β:

  τ*(β) = inf{ τ ∈ [0,1] : (1/n_cal) Σ_{x ∈ Cal} 𝟙[s(x) ≥ τ] ≤ β }

This is the PromptShield calibration methodology applied to a
clinical safety detector. The calibration split is held out from
training (D47); 455 benign clinical rows. Wilson 95 % CIs are
reported alongside each τ*(β); at β = 0.001 with n = 455, the
threshold is set by ~5 highest benign scores and the CI is
informative for downstream reporting (D67).

### 4.4 Layer 4 — Confidence-aware routing R

**v1.0 implementation:** inference-time logic, not part of the
trainable model. Given s(x) and dual thresholds
(τ_low = 0.40, τ_high = 0.60; from CONFIG):

* `s(x) ≥ τ_high` → block + flag adversarial
* `s(x) < τ_low`  → route to LLM (benign)
* otherwise       → escalate to human review

Layer 4 is not engaged in Stage 06A training; it is the
deployment-time wrapper around the calibrated detector and is
evaluated in Stage 07 alongside the FPR-targeted reporting.

### 4.5 Loss function and class-weighted training

The training loss is **weighted cross-entropy**:

  L(x, y) = − Σ_c w_c · 𝟙[y = c] · log p_c(x)

with class weights `w = [1.0, 3.0]` (D21, D64) — benign weight 1
and adversarial weight 3. This reflects Property 3 of CDDP
(asymmetric harm): missed adversarial detections are roughly 3×
worse than false alarms in clinical deployment.

Implementation: the `WeightedTrainer` subclass of
`transformers.Trainer` overrides `compute_loss` to apply
`F.cross_entropy(logits, labels, weight=w)`. The rest of the HF
training infrastructure (data collator, eval loop, checkpoint
saving) is used unchanged. This is the v1.0 trade between code
simplicity (≈ 10 lines for the subclass) and a hand-rolled
training loop (≈ 200 lines that would harbour the kinds of bugs
listed in §3.7.6).

**Optimizer.** AdamW, learning rate 2 × 10⁻⁵ (BERT default),
weight decay 0.01, linear warmup over the first 10 % of steps,
linear decay thereafter, max gradient norm 1.0. These are
PromptShield's defaults; using the same hyperparameters as the
strongest competing detector preserves apples-to-apples
comparison and means observed performance differences reflect
architecture and data, not hyperparameter tuning.

**Early stopping (D66).** Validation AUC is computed every
epoch on `val.parquet` (2,728 rows with 143 adversarial).
`load_best_model_at_end=True` with `metric_for_best_model="auc"`
selects the highest-AUC epoch. `EarlyStoppingCallback(patience=1)`
halts training one epoch after AUC plateaus. The maximum is
3 epochs; in practice the best epoch is typically 1 or 2 for
BERT-class binary classifiers on datasets this size.

### 4.6 The Alarm-Burden Inequality and the Deployability Frontier

**Status:** stubbed.

Will be populated alongside Stage 07's reporting. The framework
ties contribution C2 (Alarm-Burden Inequality) to the
calibrated TPR / FPR pairs that Stage 06A produces.

---

## 5. Training Protocol

**Status:** stubbed.

Will document the multi-seed training procedure, calibration
methodology (FPR-targeted threshold selection on the held-out
calibration split), and recalibration protocol for distribution
drift.

---

## 6. Evaluation Protocol

**Status:** stubbed.

Will document the comparison against four published detectors
(ProtectAI v2, InjecGuard, PromptGuard-86M, Fmops), the four
PharmGuard ablations (-Φ, -class-weight, BERT-base encoder,
DistilBERT encoder), the adaptive attack suite (paraphrase,
encoding, rewrite, optimization-based via Square attack), and the
benchmark difficulty stratification protocol via cross-detector
agreement.

---

## Cross-references

* Numerical findings live in `results_log.md`.
* Locked decisions live in `decisions.md`.
* Source code citations point to file:line within the v0.4.0 archive.

## Document maintenance

This document is updated at the end of each stage. The "in progress"
markers move to "complete" as work finishes; new sub-sections are
added when implementation reveals structure not anticipated in the
stub. When a finding contradicts an earlier section, the section
is *amended in place* with a dated note explaining the change, not
silently overwritten. The audit trail is the point.
