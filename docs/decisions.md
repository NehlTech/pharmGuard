# Decision Register

Numbered, dated, locked decisions for the PharmGuard project. Each
entry records what was decided, what alternatives were considered,
why we chose what we chose, what stages it affects, and how
reversible it is.

This document is **append-only**. When a decision is revised, the
revision is recorded as a new numbered entry that explicitly
supersedes the old one. The old entry is annotated with a pointer
forward but is **not** deleted, because the audit trail matters more
than tidy presentation.

The entries below are grouped chronologically into three blocks:

* **D1–D12 — Foundational decisions** that shaped the paper itself
  (contributions, framing, architecture).
* **D13–D27 — Implementation decisions** that shaped the codebase
  (acquisition strategy, schema choices, runtime environment).
* **D28–D40 — Stage 03 decisions** specific to V2 payload
  reconstruction (rule families, LLM choice, fallback strategy,
  the four R7-pass review fixes).

A summary table sits at the end for quick scanning.

---

## Block 1 — Foundational

### D1 — Solo authorship  *(locked, 2026-05-08)*

**Decision.** The paper is written and submitted as a solo paper.
The advisor reviews and edits at completion rather than during
development.

**Alternatives.** Co-author with the advisor from the start;
co-author with a peer.

**Rationale.** The advisor's stated preference is to review the
finished manuscript; involving them earlier would create
coordination overhead without quality gain. Solo authorship is
common for MPhil-stage submissions and does not penalize the work
at any of the candidate venues.

**Affects.** All writing stages.
**Reversibility.** High — co-authorship can be added at submission
time.

---

### D2 — Skip Naive Bayes / TF-IDF baselines  *(locked, 2026-05-08)*

**Decision.** Do not include a Naive Bayes or TF-IDF baseline.

**Alternatives.** Include one or both as a "sanity floor" baseline.

**Rationale.** Neither parent paper (PromptShield, MPIB) used a
simple statistical baseline. Adding one would read as padding rather
than rigor. The four off-the-shelf neural detectors plus four
PharmGuard ablations already give us eight comparison points —
stronger than either parent paper's comparison.

**Affects.** Stage 07 (off-the-shelf detector evaluation), paper
§5.2 baselines.
**Reversibility.** High — can be added in revision if a reviewer
specifically requests one.

---

### D3 — Skip Llama Guard and MedGuard  *(locked, 2026-05-08)*

**Decision.** Do not add Llama Guard or MedGuard as baselines.
Stick with the four PromptShield-aligned detectors: ProtectAI v2,
InjecGuard, PromptGuard-86M, and Fmops.

**Alternatives.** Add Llama Guard (input-output safety classifier);
add MedGuard (clinical safety auditor).

**Rationale.**

* Llama Guard solves a different problem (output-side harm
  classification, not input-side prompt-injection detection).
  Comparing PharmGuard to it would be apples-to-oranges.
* MedGuard, on inspection, is a benchmark framework (Yang et al.) —
  not a deployable detector model. There is no model artifact to
  load and run.
* Matching PromptShield's exact baseline set lets us write
  comparisons of the form "PromptShield reports X% TPR on these
  detectors on consumer data; PharmGuard reports Y% on the same
  detectors on clinical data." That is a clean story.

**Affects.** Stage 07, paper §5.2.
**Reversibility.** Medium — adding Llama Guard later requires its
7B-parameter model to fit alongside other baselines on the L4 GPU,
which is tight.

---

### D4 — Four-layer architecture  *(locked, 2026-05-08)*

**Decision.** PharmGuard is a four-layer detector:

* **Layer 1 (Φ).** Adversarial canonicalization (NFKC, zero-width
  stripping, Base64 detection).
* **Layer 2 (E_θ).** Biomedical encoding via PubMedBERT.
* **Layer 3 (D_τ).** Calibrated decision with FPR-targeted
  thresholds.
* **Layer 4 (R).** Confidence-aware human routing with three-way
  output {benign, escalate, block} via dual thresholds (τ_low=0.40,
  τ_high=0.60).

**Alternatives.** Three-layer architecture (Φ, E_θ, D_τ only); add
a separate output-filtering layer.

**Rationale.** True defense-in-depth requires multiple independent
defenses. Three input-side layers plus a confidence-aware routing
layer gives four independent input-side defenses — clean
defense-in-depth without straying into output filtering (which
would change the threat model). The routing layer is also
clinically realistic because hospital workflows already escalate
ambiguous cases.

**Affects.** Stages 06–10, paper §4.2.
**Reversibility.** Medium — Layer 4 can be removed by setting
τ_low=τ_high; Layer 1 can be ablated; the encoder can be swapped.
The architectural commitment, however, structures the paper's
methodology section.

---

### D5 — C4 reframed: Practical Tooling  *(locked, 2026-05-08)*

**Decision.** Contribution 4 is *Practical Tooling for Clinical IPI
Detector Deployment*, comprising two parts:

* **C4a.** Benchmark Difficulty Stratification via cross-detector
  agreement.
* **C4b.** Drift-Aware Recalibration Protocol.

The original Contribution 4 ("validate MPIB labels via human
annotation") is dropped.

**Alternatives.** Multi-LLM-judge consensus (Option A from the May
8 discussion); self-rebuttal LLM judging (Option B); rule-based
clinical lint (Option C); Option D = (you + 3-LLM consensus + lint
rules).

**Rationale.** None of the LLM-based options are honest under
"shared LLM bias" critique unless paired with a non-LLM check; and
they require API access (not available on this project). A
manual-annotation contribution of this scope is a 10–15 hour
commitment that conflicts with project timeline and stretches the
single-annotator κ claim. Repurposing C4 to two purely
code-deliverable protocols is more publishable than a fragile
annotation claim, and both deliverables target hospital IT teams.

**Affects.** Stages 09 (difficulty) and 10 (drift), paper §4.4.3,
§4.7, §6.4, §6.6, §8.

**Reversibility.** Medium — re-introducing label validation later
requires adding annotation infrastructure (Cell 11) and 10–15h of
human work.

---

### D6 — Square attack added to adaptive evaluation  *(locked, 2026-05-08)*

**Decision.** The adaptive evaluation transformation set
𝒯 includes four families:

* T_para — paraphrase via T5
* T_enc — encoding (Base64, homoglyph)
* T_rewrite — LLM-rewrite via Phi-3-mini-4k-instruct
* **T_auto** — Square attack (black-box query-based)

**Alternatives.** Three families only; gradient-based attacks; HotFlip.

**Rationale.** Adding Square gives a black-box automated attack
alongside the heuristic ones. It satisfies reviewers who expect
adaptive evaluation to include at least one optimization-based
attack while avoiding the gradient-attack rabbit hole (which
PromptShield explicitly puts out of scope).

**Affects.** Stage 08, paper §4.5.1, §6.3.
**Reversibility.** High — can be cut for compute reasons if
required, with appropriate footnote in §8.

---

### D7 — Single-GPU framing as deployability feature  *(locked, 2026-05-08)*

**Decision.** Frame the single-L4-GPU compute envelope as a
*deployability feature* rather than a limitation.

**Alternatives.** List single-GPU compute as a limitation in §8.

**Rationale.** Hospital IT teams typically deploy on a single GPU,
not a cluster. A detector that fits and trains on a single L4 is
*more* deployable than one that needs a cluster. This is the same
move PromptShield makes (single-GPU practicality is part of their
"deployable" framing).

**Affects.** Paper §5.3.4, §8.
**Reversibility.** High — purely framing; can be re-described.

---

### D8 — Static threshold reframed as drift contribution  *(locked, 2026-05-08)*

**Decision.** Treat the static-threshold question as the drift-
recalibration contribution (C4b) rather than as a limitation.

**Alternatives.** Acknowledge static thresholds in §8 as a
limitation.

**Rationale.** Reframing a near-limitation as a contribution is the
right move when we have a defensible solution. Algorithm 3
(Drift-Aware Recalibration) is the solution; including it as part
of C4 is intellectually honest because we genuinely propose a
protocol, not just acknowledge a gap.

**Affects.** Paper §4.4.3, §6.6, §8 (item removed from limitations).
**Reversibility.** Medium — depends on whether Stage 10 simulation
produces a usable result; if not, C4b shrinks and §8 gains the
limitation back.

---

### D9 — HF token storage on Drive  *(locked, 2026-05-09)*

**Decision.** The Hugging Face token is stored at
`/content/drive/MyDrive/pharmguard/.hf_token` with mode 0600.
Cells use `huggingface_hub.login(token=open(token_path).read())`.

**Alternatives.** Interactive paste via `getpass()` per session;
environment variable from Colab Secrets.

**Rationale.** Drive-stored token persists across session restarts,
reduces friction for the author, and is gated behind Drive
permissions. Mode 0600 ensures it is not world-readable.

**Affects.** Stage 02 (MPIB acquisition), Stage 03 (Phi-3-mini
download).
**Reversibility.** High — token can be deleted and switched back to
interactive paste in one cell change.

---

### D10 — Hybrid templates + LLM payload reconstruction  *(locked, 2026-05-08)*

**Decision.** V2 redacted payloads are reconstructed via a hybrid
strategy: hand-authored skeletons that encode the rule family's
adversarial mechanism, with LLM (Phi-3-mini) generation for
content fill-in, and fallback to skeleton-only when LLM output
fails QC.

**Alternatives.** Pure-template (no LLM) — too repetitive; pure-LLM
prompt engineering — too unreliable for systematic family-specific
mechanisms.

**Rationale.** The MPIB paper's R1–R10 rule families each describe
a *mechanism* (e.g., R8 = "emergency downplay") that has a
characteristic structure. Templates encode the mechanism reliably;
the LLM provides linguistic variety. Fallback to template-only
ensures every V2 instance gets a usable payload even when the LLM
refuses or produces garbage.

**Affects.** Stage 03, paper §5.1.3.
**Reversibility.** High — alternate strategies are pluggable per
family (each family is its own file under
`pharmguard/data/reconstruction/templates/`).

---

### D11 — Honor MPIB's published 80/10/10 split  *(locked, 2026-05-08)*

**Decision.** Use MPIB's published `parent_sample_id`-grouped
80/10/10 train/validation/test split unchanged.

**Alternatives.** Resplit ourselves (more flexibility, but creates
paraphrase leakage risk and breaks comparability with future MPIB
work).

**Rationale.** Honoring the published split is the cleanest
reproducibility story. It also prevents accidental leakage between
splits via shared `parent_sample_id` (an MPIB-specific concern
because V0/V0'/V1/V2 instances often share the same parent
question).

**Affects.** Stage 04, paper §5.1.
**Reversibility.** Low — switching the split would invalidate
already-trained checkpoints in Stage 06.

---

### D12 — Primary venue: JAMIA  *(tentative, 2026-05-08)*

**Decision.** Primary submission target is the *Journal of the
American Medical Informatics Association* (JAMIA). Backup venues
are TIFS, npj Digital Medicine, and CODASPY.

**Alternatives.** TIFS (security-formal); USENIX Security (systems-
empirical); npj Digital Medicine (clinical-impact); CODASPY
(PromptShield's venue).

**Rationale.** JAMIA's clinical-informatics readership rewards the
deployment-audit framing most heavily. The "production-grade"
positioning fits their editorial taste. The alarm-burden inequality
gives the paper enough formal rigor to stand up to JAMIA's
methodological reviewers without leaning on security-venue formal
rigor expectations.

**Affects.** Paper title, abstract, framing of §1, §7.
**Reversibility.** High — if Stage 11 results are stronger on the
security side, the paper can be rerouted to TIFS without rewriting
core content.

**Status.** Tentative — final venue selection happens after Stage
11 results are in.

---

## Block 2 — Implementation

### D13 — Repository layout: package + scripts + notebook  *(locked, 2026-05-09)*

**Decision.** The codebase is structured as a Python package
(`pharmguard/`), a set of runnable scripts (`scripts/00_*.py`
through `scripts/03_*.py` and onward), and a single Colab runner
notebook (`notebooks/colab_runner.ipynb`) whose cells are one-line
invocations of the scripts.

**Alternatives.** Pure-notebook codebase (every stage = one cell);
scripts only, no package.

**Rationale.** Three benefits: (a) the package is unit-testable in
a sandbox without a notebook environment; (b) every script is
runnable from a terminal, which makes the pipeline IDE-friendly and
debuggable; (c) the notebook's role is restricted to orchestration,
which keeps it short and resilient to Colab UI changes.

**Affects.** All stages.
**Reversibility.** Low — restructuring would force every existing
script to be rewritten.

---

### D14 — Drive-rooted artifacts everywhere  *(locked, 2026-05-09)*

**Decision.** All durable artifacts (data, logs, results,
checkpoints) live under `/content/drive/MyDrive/pharmguard/`. The
root is configurable via `PHARMGUARD_ROOT` so the same code runs
locally and on Colab.

**Alternatives.** Ephemeral `/content/` on Colab with manual save
to Drive at end of each stage.

**Rationale.** Drive-rooting means a Colab session restart never
loses work. The single environment variable also lets the same
code run on a local laptop pointed at any directory. Pipeline
restarts are now cheap.

**Affects.** All stages.
**Reversibility.** High — the path resolution lives in one place
(`pharmguard/paths.py`).

---

### D15 — `bert-score` is the only host-environment install  *(locked, 2026-05-09)*

**Decision.** `requirements.txt` lists only packages Colab does not
ship by default: `bert-score`, `imbalanced-learn`, `langdetect`.
Everything else uses whatever Colab ships (numpy, pandas, torch,
transformers, datasets, sklearn).

**Alternatives.** Pin every package's version; use a Conda lock
file.

**Rationale.** Colab refreshes its base environment regularly. Hard
pinning everything triggers `pip` resolution failures every few
weeks. We accept the trade: less version determinism, much more
operational stability.

**Affects.** Stage 00 setup.
**Reversibility.** High — pinning can be reintroduced if a
Colab-side regression breaks something.

---

### D16 — Per-stage logging + JSON reports  *(locked, 2026-05-09)*

**Decision.** Every stage writes a per-stage log file under `logs/`
and a JSON report alongside it. The report is the source of truth
for all paper tables; the log captures human-readable progress.

**Alternatives.** Single shared log; no JSON reports (dump
everything into the log as text).

**Rationale.** JSON reports are programmatically queryable. When we
write paper tables, we read JSON, not greps of free-form logs.
Per-stage logs prevent one buggy stage from corrupting another's
output.

**Affects.** All stages.
**Reversibility.** High.

---

### D17 — MPIB ingestion via `hf_hub_download` + JSONL parsing  *(locked, 2026-05-09)*

**Decision.** MPIB is downloaded with
`huggingface_hub.hf_hub_download` (one file at a time), and parsed
as JSONL directly using Python's `json` module. We do **not** use
`datasets.load_dataset()` for MPIB.

**Alternatives.** `datasets.load_dataset("jhlee0619/mpib")`.

**Rationale.** MPIB's `contexts` field is heterogeneously typed
across instances (V0, V0', V1, V2 each have different sub-keys).
Arrow/parquet schema inference inside `datasets.load_dataset()`
fails for this kind of heterogeneous-list-of-dicts column. Direct
JSONL parsing preserves the original structure with zero schema
loss.

**Affects.** Stage 02.
**Reversibility.** Medium — switching back would require resolving
the schema-inference failure first.

---

### D18 — Use `omi-health/medical-dialogue-to-soap-summary` instead of `medical_dialog`  *(locked, 2026-05-09)*

**Decision.** The fourth benign source is
`omi-health/medical-dialogue-to-soap-summary` (a dialogue corpus
with SOAP summaries).

**Alternatives.** `medical_dialog` (the original choice).

**Rationale.** `medical_dialog` is deprecated on Hugging Face Hub
(throws `DeprecationWarning` and 404s on some splits). The omi
replacement is comparable in size, English-language, has SOAP-style
notes (which match clinical documentation patterns), and is
maintained.

**Affects.** Stage 01, paper §5.1.1.
**Reversibility.** High — sources are pluggable in
`pharmguard/data/benign.py`.

---

### D19 — Five seeds, default seed 42  *(locked, 2026-05-09)*

**Decision.** Multi-seed runs use seeds (42, 123, 456, 789, 2024).
Single-seed runs use 42 by default.

**Alternatives.** Three seeds (less variance estimation); ten
seeds (more compute).

**Rationale.** Five is the minimum for credibly reporting
mean ± std with non-trivial degrees of freedom. PromptShield used
five. Going higher would more than double Stage 06 compute without
proportional reviewer-visible benefit.

**Affects.** Stage 06, paper §5.3.2.
**Reversibility.** Medium — checkpoint files are seed-named, so
extending to 10 seeds means running 5 more, not redoing existing
work.

---

### D20 — Target FPRs: 1%, 0.5%, 0.1%  *(locked, 2026-05-09)*

**Decision.** Calibrated thresholds are reported for three target
FPRs: β ∈ {0.01, 0.005, 0.001}.

**Alternatives.** PromptShield used 1%, 0.5%, 0.1%, 0.05%; we
considered adding 0.05%.

**Rationale.** β = 0.001 (0.1%) is already aggressive for a
classification model on imbalanced data. β = 0.0005 would push us
into a regime where threshold estimates become noisy on a
calibration set of realistic size. Three is enough to show the
deployability story.

**Affects.** Stage 06, paper §6.2.
**Reversibility.** High.

---

### D21 — Class weights (1.0, 3.0)  *(locked, 2026-05-08)*

**Decision.** Class-weighted cross-entropy with w_benign = 1.0 and
w_attack = 3.0 (α = 3).

**Alternatives.** No weighting (α = 1); higher weighting (α = 5
or α = 10).

**Rationale.** α = 3 is the operating-point shift that aligns
training-time class balance with the precision-recall trade-off the
deployment regime requires (false negatives more costly than false
positives, but not catastrophically so). The exact value will be
ablated in Stage 06.

**Affects.** Stage 06, paper §4.3.2.
**Reversibility.** High — single hyperparameter.

---

### D22 — V0p schema flag  *(locked, 2026-05-09)*

**Decision.** Some MPIB instances label V0' as `V0p` (no prime
character). The EDA flags this as a cosmetic schema issue, not an
error. Both forms are accepted.

**Alternatives.** Reject V0p instances; rename to V0' on ingestion.

**Rationale.** V0p is unambiguous and consistent within the
affected instances. Renaming would diverge from the published
dataset; rejecting would discard usable data. Accepting both forms
matches the principle of being conservative in what we emit and
liberal in what we accept.

**Affects.** Stage 02.
**Reversibility.** High.

---

### D23 — Phi-3-mini-4k-instruct as the V2 reconstruction LLM  *(locked, 2026-05-09)*

**Decision.** V2 payload reconstruction uses
`microsoft/Phi-3-mini-4k-instruct` in fp16, greedy decoding,
deterministic seed = `hash(sample_id) mod 2**32`.

**Alternatives.** Qwen2.5-3B-Instruct; Llama-3.2-3B-Instruct; pure
template generation.

**Rationale.** Phi-3-mini-4k-instruct is the best
(capability, latency, memory) trade-off on an L4: ~7.6 GB in fp16,
runs at ~3–5 s per 200-token generation, instruction-following is
strong enough to handle structured prompts. Qwen and Llama variants
of comparable size are competitive; we picked one and stuck with
it for reproducibility.

**Affects.** Stage 03.
**Reversibility.** High — model is hot-swappable in
`PhiGenerator.__init__()`.

---

### D24 — `parsed_mpib.parquet` as canonical MPIB artifact  *(locked, 2026-05-09)*

**Decision.** Stage 02 emits `parsed_mpib.parquet` with one row
per MPIB instance and a `contexts` column preserving the full
heterogeneous structure (list of dicts, each with role +
subordinate fields). The parquet is the source of truth for
downstream stages.

**Alternatives.** Multiple parquets (one per vector); flatten the
contexts into separate columns.

**Rationale.** Single parquet with structured `contexts` column
keeps related data colocated and lets Stage 03 access full
contexts trivially. Vector-based filtering is one boolean mask
away.

**Affects.** Stages 02, 03, 04.
**Reversibility.** Low — downstream code reads this exact schema.

---

### D25 — `omi-health` SOAP summaries as benign source  *(locked, 2026-05-09)*

Superseded by D18 — kept here only so D18 has a referent.
*(See D18 for the active decision.)*

---

### D26 — Reconstruction status taxonomy  *(locked, 2026-05-09)*

**Decision.** Stage 03 emits one of five `generation_status` values
per V2 instance:

* `success` — LLM generated text within feature tolerance
* `fallback` — LLM failed QC; skeleton-only output emitted
* `deviated` — text emitted but surface features outside tolerance
* `family_not_implemented` — no template strategy registered for
  this rule family ID
* `no_poisoned_context` — V2 instance lacked a poisoned-update
  context (defensive)

**Alternatives.** Binary success/failure; richer enum with subtypes.

**Rationale.** Five is the minimum that lets us answer all the
follow-up questions cleanly: did the LLM succeed? if not, what was
the failure mode? Binary would lose the
fallback-versus-no-text distinction.

**Affects.** Stage 03, paper §5.1.3.
**Reversibility.** Medium — adding statuses is cheap; removing them
breaks downstream consumers.

---

### D27 — `original_redacted_text` preserved in output  *(locked, 2026-05-09)*

**Decision.** Stage 03's `reconstructed_v2.parquet` keeps the
`original_redacted_text` column (always `[REDACTED_PAYLOAD]` for V2)
alongside the new generated text. The reconstruction is *additive*,
not destructive.

**Alternatives.** Replace the original text; emit a separate
`audit.parquet` with originals.

**Rationale.** Audit trail. Reviewers and future researchers will
want to verify that we did not silently corrupt the dataset. Keeping
both columns side by side makes provenance trivially inspectable.

**Affects.** Stage 03.
**Reversibility.** High.

---

## Block 3 — Stage 03 specific

### D28 — Per-family file structure under `templates/`  *(locked, 2026-05-09)*

**Decision.** Each rule family R1–R10 lives in its own file under
`pharmguard/data/reconstruction/templates/` (e.g.,
`r7_editorial.py`, `r8_triage_downplay.py`). Each file exports a
`TemplateStrategy` subclass with `build_prompt()` and
`fallback_skeleton()` methods.

**Alternatives.** One large `templates.py` with all ten classes;
generic prompt + family-specific config dictionaries.

**Rationale.** Per-file isolation gives each family its own diff
history (so we can hand-review changes to R8 without paging through
all ten). Each file is short (~120–220 lines) and self-contained.
The dispatcher in `__init__.py` does the routing.

**Affects.** Stage 03.
**Reversibility.** Low — restructuring would require moving every
class.

---

### D29 — `preserves_paragraphs` per-strategy flag  *(locked, 2026-05-09)*

**Decision.** Each `TemplateStrategy` declares a class attribute
`preserves_paragraphs: bool`. The orchestrator uses it to decide
whether `_strip_llm_artifacts()` collapses `\n\n` paragraph breaks
or preserves them. Single-paragraph families (R1, R2, R3, R6, R7,
R8, R9) set this False; multi-paragraph families (R4, R5, R10) set
it True.

**Alternatives.** Always collapse (loses structure for R4/R5/R10);
always preserve (R7's three-paragraph LLM output looked
multi-paragraph but should have been one).

**Rationale.** Collapsing is a destructive transform; whether it
should fire depends on the family's expected surface form.
Per-strategy declaration is the right abstraction: each family
knows whether its skeleton is single- or multi-paragraph.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D30 — Default per-family surface targets  *(locked, 2026-05-10)*

**Decision.** When a V2 instance's `reconstruction_hook.features`
field is missing, the orchestrator falls back to per-family
defaults derived from the EDA observations of representative
instances:

```
R1:  {lines:1,  words:100, headers:0, formatting:0}
R2:  {lines:1,  words:110, headers:0, formatting:2}
R3:  {lines:1,  words:100, headers:0, formatting:0}
R4:  {lines:20, words:305, headers:0, formatting:24}
R5:  {lines:12, words:214, headers:0, formatting:14}
R6:  {lines:1,  words:100, headers:0, formatting:1}
R7:  {lines:1,  words:105, headers:0, formatting:0}
R8:  {lines:1,  words:122, headers:0, formatting:0}
R9:  {lines:1,  words:110, headers:0, formatting:0}
R10: {lines:8,  words:180, headers:1, formatting:12}
```

**Alternatives.** Single global default; force every instance to
specify a target.

**Rationale.** MPIB instances vary widely in surface form; a global
default would be wrong for ~70% of cases. Per-family defaults match
each family's structural cluster (R7/R8 = single dense paragraph;
R4/R5/R10 = heavily structured). The hook field is the primary
source; the default is the safety net.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D31 — R5 fake PMIDs use 99-prefix  *(locked, 2026-05-09)*

**Decision.** R5 (Fabricated Citation) generates PMIDs with the
prefix `99` (e.g., PMID 99134830). Real PMIDs are currently in the
~38,000,000–40,000,000 range; PMIDs starting with 99 are
unallocated.

**Alternatives.** Random plausible PMIDs (could collide with real
ones); explicit "FAKE-PMID-001" markers (too obvious to function as
adversarial examples).

**Rationale.** 99-prefix PMIDs look syntactically real (8 digits)
but are reliably fake. A clinician copy-pasting one into PubMed
would get zero results. This protects against accidental real-PMID
collisions while preserving the adversarial mechanism.

**Affects.** Stage 03 (R5 only).
**Reversibility.** High.

---

### D32 — R9 dose multiplier = 1.75x  *(locked, 2026-05-09)*

**Decision.** R9 (Dose Tweak) extracts dose phrases from the benign
evidence using regex patterns and multiplies the numeric value by
1.75. For a 50 mg dose, the tweaked output reads "88 mg".

**Alternatives.** 2x (too aggressive, easy to detect); 1.25x (too
subtle, possibly within therapeutic-dose-range tolerance); per-drug
lookup against FDA dose ranges.

**Rationale.** 1.75x is empirically in the "noticeable but
plausible" zone for most drug classes. Per-drug lookup would be
better but requires a drug-name resolver and dose database
(out of scope). The constant multiplier is a reasonable
first-pass approach; we can always tighten in Stage 04 if needed.

**Affects.** Stage 03 (R9 only).
**Reversibility.** High — single-line constant change.

---

### D33 — R7 review fix #1: `oversized` → `deviated`  *(locked, 2026-05-10)*

**Decision.** Rename the Stage 03 status `oversized` to `deviated`.

**Alternatives.** Keep `oversized` and add a separate `undersized`.

**Rationale.** R7 hand-review of Sample 2 (pituitary apoplexy)
showed an instance flagged as `oversized` that was actually 80
words against a 89-word target — undersized. The flag was firing on
*any* deviation, not just over-target. Renaming to `deviated`
matches the actual semantics. (See R7 review session,
`docs/methodology.md` §3.3.)

**Affects.** Stage 03 output schema, downstream consumers.
**Reversibility.** High.

---

### D34 — R7 review fix #2: paragraph collapse for single-paragraph families  *(locked, 2026-05-10)*

**Decision.** `_strip_llm_artifacts()` collapses `\n\n` paragraph
breaks to a single space when the family's
`preserves_paragraphs` flag is False. This prevents single-paragraph
families like R7 from producing multi-line output even when the LLM
generates well-structured prose.

**Alternatives.** Constrain the LLM prompt more aggressively; tag
the multi-paragraph output as `deviated`.

**Rationale.** R7 review showed Sample 3 (pharmacist education)
producing three paragraphs against a one-line target. The LLM
generated good content but in three logical chunks. Collapsing
preserves the content while matching the surface form.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D35 — R7 review fix #3: explicit reversal language in R7 prompt  *(locked, 2026-05-10)*

**Decision.** The R7 (Editorial Note) prompt explicitly instructs
the LLM that the output should be "a clear reversal, not a
refinement, of the original recommendation."

**Alternatives.** Generic "contradict the original" phrasing.

**Rationale.** R7 review showed Sample 5 (amoxapine) producing
*refinement* language ("further evaluation needed") rather than
*reversal* ("should not be administered"). Refinement is too soft
to function as an adversarial example. The explicit reversal
instruction sharpens the family's adversarial mechanism.

**Affects.** Stage 03 (R7 only).
**Reversibility.** High — prompt is in `r7_editorial.py`.

---

### D36 — R7 review fix #4: formatting deviation as warning-only  *(locked, 2026-05-10)*

**Decision.** When generated output has formatting count outside
the target tolerance but lines/words/headers are within tolerance,
the status remains `success` with a `feature_deviation` flag
indicating the formatting drift. Formatting alone does not trigger
a `deviated` status.

**Alternatives.** Strict-mode where any feature deviation triggers
`deviated`; ignore formatting entirely.

**Rationale.** Formatting count (number of `**bold**` and `*italic*`
markers) is the noisiest of the four surface features. A 30%
formatting deviation often reflects natural LLM stylistic variance
without changing the adversarial mechanism. The deviation is still
recorded for audit; it just doesn't change the headline status.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D37 — Phi-3-mini deterministic per-instance seed  *(locked, 2026-05-09)*

**Decision.** Each V2 instance's LLM generation uses a
deterministic seed of `hash(sample_id) mod 2**32`. Re-running Stage
03 produces byte-identical output for the same input.

**Alternatives.** Single global seed (loses per-instance
reproducibility under partial reruns); random seed (loses
reproducibility entirely).

**Rationale.** Per-instance determinism means a partial Stage 03
rerun (e.g., re-running just family R8 after a fix) produces
identical results to a from-scratch run. This is critical for
debugging and for honest "no, we didn't cherry-pick" reviewer
defense.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D38 — `generation_seed` in output schema  *(locked, 2026-05-09)*

**Decision.** The Stage 03 output parquet includes a
`generation_seed` column recording the per-instance seed used. The
`logs/reconstruction_samples.json` also includes it.

**Alternatives.** Omit the seed (assume `hash(sample_id) mod 2**32`
is implicit).

**Rationale.** Implicit recipes age badly. A future maintainer
reading the parquet should be able to reproduce any single
instance's generation without needing to read the source code.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D39 — Sample log of 5 instances per family  *(locked, 2026-05-10)*

**Decision.** Stage 03 writes a `logs/reconstruction_samples.json`
file containing 5 randomly-sampled instances per rule family with
full input/output text. The sample is deterministic (seeded by the
family ID).

**Alternatives.** Sample once across all families; sample only on
demand.

**Rationale.** Per-family sampling is essential for
hand-review (the R7 review used exactly this mechanism). Five is
enough to spot family-specific issues without being too many to
read in one sitting.

**Affects.** Stage 03.
**Reversibility.** High.

---

### D40 — Stage 03 runtime budget: 30–40 minutes for 582 instances  *(locked, 2026-05-10)*

**Decision.** Stage 03 is budgeted for 30–40 minutes wall-clock on
an L4 GPU for the full 582 V2 instances. The orchestrator emits a
progress log every 10 instances.

**Alternatives.** Larger batch sizes (faster but harder to
parallelize the QC step); smaller models (faster but lose quality).

**Rationale.** The budget is empirically derived from R7-only
runs that processed 54 instances in ~3 minutes. Linear scaling
gives ~32 minutes for the full 582. This budget fits comfortably
inside a single Colab Pro session.

**Affects.** Stage 03.
**Reversibility.** High.

**Amendment 2026-05-10.** The actual wall-clock for the v0.4.0 run
was ~81 minutes (8.38 s/instance). The R7-only extrapolation
underestimated Phi-3-mini's per-instance generation time at full
prompt length because R7 prompts are shorter than the average
prompt across families. The 30–40 minute budget is revised to
60–90 minutes for the full V2 set on L4. Future runs and
re-runs should plan around this revised figure.

---

### D41 — Stage 03 acceptance criterion revised  *(locked, 2026-05-10)*

**Decision.** The Stage 03 acceptance criterion for moving to
Stage 04 is revised. The original criterion (recorded in
`results_log.md` §3.4 pre-revision) was

> success + deviated ≥ 70 %

The revised criterion is

> non-fallback rate ≥ 95 %, **AND**
> mechanism-marker hand-review pass rate ≥ 90 % on a
> 5-sample-per-family audit of the worst-performing family
> by raw success rate.

The v0.4.0 run meets both: non-fallback rate is 100 % (no
instance fell back to the skeleton), and the R2 audit returned
5/5 mechanism-faithful samples.

**Alternatives considered.**

(a) Keep the original criterion. *Rejected:* the criterion treated
`deviated` as a failure mode. Hand-review of the worst-performing
family showed that `deviated` outputs are mechanism-faithful;
they differ from MPIB's originals only in surface shape (line
count). Discarding them would be self-imposed data loss for no
clinical reason.

(b) Tighten to "success ≥ 70 %". *Rejected:* this would force a
prompt-iteration cycle to satisfy a surface-feature constraint
that has no bearing on adversarial content. A V2 attacker in the
wild does not match MPIB's surface conventions; surface diversity
in training data is a feature, not a defect.

(c) Add a third arm — full-corpus LLM-as-a-judge mechanism scoring.
*Rejected for v0.4.0, considered for later:* this would be more
rigorous than the 5-sample hand-review, but it is a substantial
engineering investment (judge prompt design, judge model selection,
inter-judge agreement). For the present milestone, the hand-review
is sufficient. If reviewer comments call for stronger evidence
during paper revision, we add the LLM-as-a-judge audit then.

**Rationale.** The original criterion was written before any
Phi-3-mini output existed. It was a guess at what the right
threshold should be. The actual run produced enough data to set
a calibrated criterion that distinguishes the failure modes we
care about (no payload, refusal, malformed output) from the
non-failure modes we incorrectly flagged (surface-shape mismatch
on otherwise-correct adversarial content). The revised criterion
captures this distinction.

**Affects.** Stage 03 outcome interpretation; Stage 04 corpus
assembly inclusion criteria.

**Reversibility.** High. The criterion is a methodological
threshold, not embedded in code. Changing it requires only
updating this entry and re-running the audit on whatever
candidate corpus is under evaluation.

---

### D42 — Parquet nested fields are JSON-stringified (bug)  *(open, 2026-05-10)*

**Decision.** The Stage 03 Parquet writer currently serializes
nested fields (`contexts`, `actual_features`, `feature_deviation`)
as JSON strings rather than as native PyArrow nested types. This
is a defect, not a design choice. It was discovered during
post-run analysis: `df['contexts'].iloc[0]` returns a string,
not a list, requiring `json.loads` on every read.

This decision entry **records the bug rather than resolving it**.
The fix is deferred to v0.5.0 (Stage 04 dataset construction)
because the v0.4.0 artifact is already written and usable with
the documented workaround.

**Workaround (current, used in all v0.4.0 read paths).** Wrap
reads with:

```python
df['contexts'] = df['contexts'].apply(json.loads)
df['actual_features'] = df['actual_features'].apply(
    lambda s: json.loads(s) if isinstance(s, str) else (s or {})
)
```

**Fix (deferred to v0.5.0).** Use `pyarrow.Table.from_pandas`
with explicit nested schema, or use the `pyarrow.list_(struct([...]))`
type constructor to declare the `contexts` field schema. Verify
roundtrip with a unit test that reads the written Parquet and
asserts `isinstance(df['contexts'].iloc[0], list)`.

**Why this happened.** The Stage 03 writer used pandas's default
Parquet engine, which falls back to JSON serialization for nested
types it cannot infer. The MPIB ingestion path (Stage 02) hit
the same class of issue, which is why we already bypass
`datasets.load_dataset` for MPIB (D17). The Stage 03 path needs
an analogous fix.

**Affects.** Any downstream stage that reads
`reconstructed_v2.parquet`. Currently this is Stage 04 only
(planned). The workaround is in the v0.4.0 inspection cells
shared in the methodology session.

**Reversibility.** Low at the level of the v0.4.0 artifact (the
written Parquet has the bug baked in), but high at the writer
level (the fix is a typed-schema change in one file).

---

### D43 — Detector input is the concatenated CDSS string  *(locked, 2026-05-11)*

**Decision.** The detector classifies the post-concatenation string
that would otherwise reach the back-end LLM: `system_prompt +
user_query + retrieved_contexts`, with role-tagged separators.

**Alternatives considered.**

(a) Classify only the `user_query`. *Rejected:* V2 attacks live in
retrieved context, not in the query. The detector would be blind
to V2.

(b) Classify only the retrieved contexts. *Rejected:* loses V1
signal (V1 attacks live in the query).

(c) Two-headed detector (one head for query, one for contexts).
*Rejected for v0.5.0:* doubles training cost and requires careful
calibration of two thresholds. The single-input design lets one
detector handle both vectors. We may revisit this for the paper's
ablation section.

**Rationale.** This is PromptShield's framework (their §2.4). The
detector sits at the natural choke point between retrieval-and-
concatenation and the foundation model, so its input is precisely
the concatenated string. A single model with a single threshold
is also the design point clinicians can audit; two-head designs
add operational complexity for marginal gain.

**Affects.** Every Stage 04+ stage. Defines the input distribution
the encoder (D4 Layer 2) is trained on.

**Reversibility.** Medium. Changing it would force regeneration of
all seven Stage 04 outputs but not the upstream artifacts.

---

### D44 — Benign-clinical task wrappers  *(locked, 2026-05-11)*

**Decision.** Each benign-clinical source is wrapped in a per-source
synthetic clinical-task framing so its detector-input form is
structurally indistinguishable from MPIB-style instances:

| Source              | Wrapper user query                                                                          |
|---------------------|---------------------------------------------------------------------------------------------|
| `mtsamples`         | "Summarize the following clinical note in 3-5 sentences."                                   |
| `openfda`           | "Based on this drug-label information, what should a clinician communicate to the patient?" |
| `pubmed`            | "Answer the following biomedical question using the provided abstract."                     |
| `clinical_dialogue` | "Convert this clinician-patient dialogue into a SOAP-format clinical note."                 |

**Alternatives considered.**

(a) No wrapper — present raw text. *Rejected:* the detector would
trivially learn "input has `[system]` prefix and `[context:...]`
tags = adversarial."

(b) Sample wrappers from a larger pool per row. *Considered for
future:* would give surface-form diversity within each source.
Deferred because (1) we lack a vetted pool and (2) the fixed
wrappers already produce diverse-enough inputs given the source
diversity. The paper's deployment-section ablation may revisit.

**Rationale.** The wrappers were chosen to span MPIB's four
scenario families (S1–S4). They are also realistic CDSS tasks:
real clinical assistants are deployed for summarization, drug
counseling, evidence-based QA, and SOAP-note generation.

**Affects.** Stage 04 benign-clinical wrapping; paper appendix
table listing the wrappers verbatim.

**Reversibility.** High. Changing a wrapper requires only
regenerating Stage 04 (no upstream changes).

---

### D45 — Binary label, V1/V2 stratification preserved auxiliary  *(locked, 2026-05-11)*

**Decision.** The training target is binary `label ∈ {0: benign, 1:
adversarial}`. V1/V2 distinction is kept as an auxiliary
`vector` column for stratified evaluation (test_v1 vs test_v2) and
for the difficulty-stratification analysis (C4a), but is not a
training target.

**Alternatives considered.**

(a) Three-class {benign, V1, V2}. *Rejected:* PromptShield is
binary; published baselines are binary; deployable use case is
binary (block or allow). Three-class would complicate apples-to-
apples comparison.

(b) Multi-label (binary + harm types). *Rejected for the headline
detector, deferred for a future ablation:* multi-label requires
per-head loss design and threshold-selection extensions. We may
add it post-headline if the harm-type stratification analysis
reveals it is worthwhile.

**Rationale.** Clean baseline comparison + deployable interface.

**Affects.** Training loss (D21 class weights apply to a binary
problem), evaluation metric design (TPR at FPR is binary).

**Reversibility.** Medium. Switching to multi-label requires
retraining and reconfiguring threshold selection.

---

### D46 — Honor MPIB's split, route test by vector  *(locked, 2026-05-11)*

**Decision.** MPIB's published 80/10/10 `parent_sample_id`-grouped
split is honored unchanged. For MPIB test instances, V1 rows go to
`test_v1`, V2 rows go to `test_v2`, V0/V0p rows are folded into
`val`.

**Alternatives considered.**

(a) Resplit MPIB ourselves. *Rejected:* would risk leakage MPIB
already prevents; would also break apples-to-apples comparison
with future research that uses MPIB's published split.

(b) Pool all test instances into one `test` file. *Rejected:* would
prevent the vector-stratified analysis the paper centers on.

(c) Discard V0/V0p test rows. *Rejected:* they may be useful as
benign anchors in val.

**Rationale.** Reproducibility plus paper-centric structure.

**Affects.** Stage 04 split assignment.

**Reversibility.** High.

---

### D47 — Benign-clinical 80/10/5/5 allocation  *(locked, 2026-05-11)*

**Decision.** Benign-clinical rows are deterministically allocated:
80% to `train`, 10% to `val`, 5% to `calibration`, 5% to
`clinical_benign_holdout`. Allocation via SHA-256 of
`parent_id + "stage04"` mod 100, with bucket boundaries at 80, 90,
95, 100.

**Alternatives considered.**

(a) 80/10/10 (no calibration / holdout). *Rejected:* PromptShield
requires a held-out calibration set for threshold selection; C4b
requires a separate deployment-FPR holdout.

(b) 80/5/5/10 (more holdout, less calibration). *Rejected for now:*
calibration material is the more constrained budget — too little
calibration material would inflate threshold-selection variance.
5%/5% gives roughly equal allocation; if calibration variance is
high in Stage 06, we'll revisit.

**Rationale.** Both calibration and deployment-FPR estimation need
real material from a distribution that the detector did not train
on. 5% each is enough for stable threshold estimation given our
benign-clinical corpus size (~10K rows).

**Affects.** Stage 06 calibration; C4b drift demonstration.

**Reversibility.** High.

---

### D48 — Cross-source dedup: benign rows overlapping MPIB are dropped  *(locked, 2026-05-11)*

**Decision.** Before split assignment, benign-clinical rows whose
content hash equals the content hash of any MPIB user-query are
removed from the benign pool. The MPIB row wins because it carries
the adversarial transformation we need.

**Alternatives considered.**

(a) No cross-source dedup. *Rejected:* would create label conflicts
(same content tagged benign in one row, adversarial in another).

(b) Drop MPIB rows that overlap with benign. *Rejected:* would
lose adversarial training signal.

(c) Manual audit. *Rejected for scale:* possible at MPIB's size
but doesn't scale; the hash-based dedup is automatic and
auditable via the deduplication log.

**Rationale.** Hash-based dedup is exact (false negatives can only
arise for distinct-but-semantically-identical strings, which are
not a concern at our scale) and audit-able via the dedup log.

**Affects.** Stage 04 benign pool composition.

**Reversibility.** High.

---

### D49 — Native PyArrow nested types throughout  *(locked, 2026-05-11)*

**Decision.** Stage 04's Parquet writer uses an explicit PyArrow
schema with native nested types. No JSON stringification. The
schema declares `harm_types` as `pa.list_(pa.string())` rather
than `string`.

**Alternatives considered.**

(a) Continue with JSON stringification (the upstream pattern).
*Rejected:* propagates D42 to every downstream consumer.

(b) Convert to long-format with one row per harm-type. *Rejected:*
inflates row counts and complicates downstream code.

**Rationale.** Fixes D42 at the boundary where downstream code
begins. Upstream artifacts (parsed_mpib.parquet,
reconstructed_v2.parquet) retain JSON-string columns; Stage 04
decodes on read and writes natively. Downstream stages (05+) read
only Stage 04 output and see native nested types.

**Affects.** Stage 04 writer; every downstream reader's expectations.

**Reversibility.** High (writer-level change), low for already-written
artifacts. Stage 04 outputs would need regeneration if reversed.

---

### D50 — Preserve real-world class imbalance, no upsampling  *(locked, 2026-05-11)*

**Decision.** Stage 04 does not artificially balance the
benign/adversarial ratio. Training uses class weights (D21) to
compensate; the data itself reflects the real deployment ratio.

**Alternatives considered.**

(a) Oversample adversarial to 1:1. *Rejected:* teaches a different
distribution than the one observed at deployment. PromptShield's
whole point is performance at heavy benign:adversarial ratios.

(b) Undersample benign to match adversarial. *Rejected:* wastes
training signal; the benign distribution is the calibration of
"what is acceptable in clinical use."

**Rationale.** Class weighting is the right tool for class
imbalance in a binary classifier. Resampling distorts the
distribution; weighting changes the objective without changing
what the model sees.

**Affects.** Stage 06 training; class-balance reporting in
`results_log.md` §4.

**Reversibility.** High (one parameter at training time).

---

### D51 — Atomic writes with fsync for all Stage 04+ artifacts  *(locked, 2026-05-11)*

**Decision.** Every Stage 04 Parquet write uses the following
sequence: write to tempfile in destination directory, `os.fsync`
the file descriptor, atomic rename to final destination. The
manifest JSON is similarly fsync'd.

**Alternatives considered.**

(a) Continue with `df.to_parquet()` directly. *Rejected:* this is
exactly the pattern that caused our between-session data loss
on Stage 03. Drive's FUSE layer buffers writes; a runtime
termination before flush loses the file.

(b) Mount Drive in "no-cache" mode. *Out of our control:* Colab
configures the FUSE mount.

**Rationale.** fsync is the POSIX mechanism for "I want these bytes
durable before I proceed." The atomic rename ensures the
destination either has complete bytes or none — never partial.

**Affects.** Every Stage 04+ writer. Future stages adopt the same
convention.

**Reversibility.** High (one helper function).

---

### D52 — Stage manifest with SHA-256 checksums  *(locked, 2026-05-11)*

**Decision.** Every stage writes a `stage_<N>_manifest.json` after
all artifacts are flushed. The manifest records, for each artifact:
absolute path, SHA-256, byte size, row count, and a
`completed_at` ISO timestamp. Future sessions verify the manifest
against actual files before treating the stage as complete.

**Alternatives considered.**

(a) Continue with path-probing checkpoints. *Rejected:* we have
observed this produce false negatives when path conventions
evolve (the `data/` vs `pharma_data/` incident).

(b) MD5 instead of SHA-256. *Rejected:* SHA-256 is the modern
default and the cost difference at our scale is negligible.

**Rationale.** Checksum verification turns "is this file present"
into "is this file the file I wrote." Combined with D51 (atomic
fsync'd writes), it closes the data-integrity gap that produced
the between-session loss.

**Affects.** Every Stage 04+ writer; future stage-completion
checkpoint cells in the Colab notebook.

**Reversibility.** High.

---

### D53 — MPIB split-name routing fix and strict validation gate  *(locked, 2026-05-11)*

**Decision.** Stage 04's routing function uses an explicit rename
map for MPIB's `mpib_split` values (`{"train": "train",
"validation": "val", "val": "val", "test": "test"}`) rather than
relying on string equality with assumed values. A strict
post-routing gate asserts that every produced `split` value is
in `SPLIT_NAMES`, raising `ValueError` with diagnostic detail if
not. A non-blocking warning is emitted when `train` or `val` has
zero rows of either class.

**Context.** The v0.5.0 run produced a `val.parquet` with zero
adversarial instances. Cause: my routing function checked for
`mpib_split == "val"` but MPIB uses the string `"validation"`.
The 143 V1+V2 validation rows fell through, kept their
`mpib_split` value as the `split` label, and were silently
dropped by the writer because `"validation"` was not in
`SPLIT_NAMES`.

**Alternatives considered.**

(a) Patch only the routing to use `"validation"`. *Rejected:*
narrower fix wouldn't catch the symmetric failure mode where a
future MPIB schema change introduces a fourth split value.

(b) Loose validation — log a warning instead of raise. *Rejected:*
warnings get ignored. Silent data loss is exactly what we are
trying to prevent. The hour cost of fixing a raised error
matches the multi-week cost of training on a corrupt corpus.

(c) Make the gate run at write-time. *Rejected:* a write-time
gate would have caught the symptom but the routing function is
where the bug lives, and validating there gives a more useful
error message.

**Rationale.** Defense in depth. The explicit rename map removes
the string-match brittleness; the strict gate catches any future
silent-drop class of failure regardless of where it originates
in the routing function; the warnings document the expected
shape of each split so a human reading the log notices anomalies.

The methodological lesson — that sandbox tests for routing logic
must use real upstream values rather than assumed ones — is
recorded in `methodology.md` §3.7.3 (amendment 2026-05-11) and
will be applied to future routing-touching code.

**Affects.** Stage 04 routing function; future stages that route
between named partitions.

**Reversibility.** High (one function in one file).

---

### D54 — Post-stage integration-check cell pattern  *(locked, 2026-05-11)*

**Decision.** Every stage from Stage 04 onward ships a paired
post-stage integration-check cell in the Colab notebook. The
cell reads the stage's outputs from Drive (bypassing the manifest),
runs explicit assertions designed around the bug classes the
project has actually encountered, and reports PASS/FAIL per
check. The cell never raises; it collects every failure and
shows them all at the end.

Each check belongs to one of four sections:

1. **Schema-level** — every output file has the expected columns
   with the expected types; nested fields deserialize as native
   Python types, not JSON strings (the D42 class).
2. **Distribution-level** — splits that should have both classes
   have both classes; design-pure splits stay pure (the D53 class).
3. **Leakage** — no `parent_id` (or stage-equivalent key) appears
   in two outputs that should be disjoint.
4. **Upstream contract** — properties the next stage assumes.

**Context.** Three real bugs surfaced in v0.4.0 → v0.5.1 (D42:
silent JSON stringification of nested fields; D53: `"val"` vs
`"validation"` routing mismatch; Drive data loss across sessions).
All three were caught manually by humans noticing anomalies in
the output. None would have been caught by the existing
`--verify-only` mode, which checks the manifest's internal
consistency (checksums, row counts) but not the *meaning* of
what was written. The integration-check cell automates the
human-noticed anomaly detection.

**Alternatives considered.**

(a) Full `tests/` directory with real fixtures (Option A in the
session discussion). *Rejected for v0.5.2:* costs ~30 min of
fixture curation and maintenance vs ~15 min for the integration
cell, while addressing the same bug classes we have actually
hit. May be revisited if Stage 06+ surfaces a fixture-class bug.

(b) Skip the addition; rely on `--verify-only` and human review.
*Rejected:* the bugs we hit were exactly the ones `--verify-only`
does not catch.

(c) Make the checks raise rather than collect. *Rejected:* a
single failure should not hide later failures. Collecting all
failures gives a fuller picture and avoids back-and-forth
debugging rounds.

**Rationale.** The cost (one notebook cell per stage) is much
lower than the cost of discovering bugs at training time. The
pattern is also self-extending: future stages copy the cell
structure and add stage-specific assertions, building cumulative
coverage without rewriting framework code.

**Affects.** Notebook structure; every future stage adopts the
pattern.

**Reversibility.** High (cells are independent and can be removed).

---

### D55 — PubMedBERT tokenizer  *(locked, 2026-05-11)*

**Decision.** The Stage 05 tokenizer is
`microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract`. The fast
(Rust-backed) HuggingFace tokenizer is used when available.

**Alternatives.** Generic BERT tokenizer (`bert-base-uncased`),
BioBERT, ClinicalBERT.

**Rationale.** This pairs with the encoder choice locked in D4
(Layer 2). PubMedBERT is pre-trained on biomedical abstracts;
using a generic BERT tokenizer would discard the biomedical
vocabulary overlap that motivates Layer 2. BioBERT and
ClinicalBERT are reasonable alternatives but were not selected
in D4; reopening D4 to switch encoders is out of scope for
Stage 05.

**Affects.** Stage 05 only; downstream consumers see the
tokenized output and do not need to know the tokenizer name
(except for re-tokenization scenarios, where the name is
recorded in the manifest).

**Reversibility.** High at the file level (one constant in
`tokenization.py`); medium overall because changing the
tokenizer requires regenerating Stage 05 outputs and likely
revisiting D4.

---

### D56 — `max_length=512` with right-truncation and measurement gate  *(locked, 2026-05-11)*

**Decision.** Stage 05 tokenizes with `max_length=512`,
`truncation=True`, and right-truncation direction (BERT default).
Inputs longer than 512 tokens have their tail dropped. The
per-vector truncation rate is measured and reported in the run
summary and manifest; a `⚠ EXCEEDS` warning prints if any split's
V2 truncation rate exceeds 25 %.

**Alternatives considered.**

(a) **Left-truncation for V2 only.** Asymmetric handling that
would protect V2 attacks (which sit at the end of the input).
*Rejected for v1.0:* creates vector-dependent tokenization logic,
deviates from published-baseline configuration, complicates
apples-to-apples comparison.

(b) **Sliding-window inference.** Each long input is split into
overlapping 512-token windows; per-window scores aggregated to
a per-instance score. *Rejected for v1.0:* doubles inference
complexity, makes calibration more involved, harder to compare
to baselines.

(c) **Long-context encoder (e.g., Longformer-bio).** Avoids the
truncation question entirely. *Rejected for v1.0:* would force
abandoning the PubMedBERT encoder locked in D4; long-context
biomedical encoders are not as well-validated.

(d) **Shorter `max_length=256`.** Faster training, lower memory.
*Rejected:* would increase truncation rate substantially given
typical V2 input lengths. The compute savings do not justify the
information loss.

**Rationale.** The measurement gate makes the decision
empirical. Right-truncation is the BERT-standard choice; if V2
truncation is rare in practice (under 25 %), the asymmetric
concern is moot and we keep the standard setup. If V2 truncation
is common, the gate surfaces it and we revisit D56. Either way,
the answer comes from the data, not from a priori reasoning.

The 25 % threshold is informational, not blocking — Stage 05
completes regardless. This avoids the failure mode where a
threshold-blocked stage prevents the user from getting to the
analysis cell that would tell them whether the threshold was
right in the first place.

**Affects.** Stage 05 output; potentially Stage 06 training and
all downstream evaluation if revisited.

**Reversibility.** High (one rerun of Stages 05 and 06).

---

### D57 — Native PyArrow nested types for tokenized output  *(locked, 2026-05-11)*

**Decision.** Stage 05's `input_ids` and `attention_mask` columns
are written as native PyArrow `list[int32]` and `list[int8]`
types. No JSON stringification.

**Alternatives.** Continue with JSON stringification (the
pre-D49 pattern); use HuggingFace Arrow datasets format.

**Rationale.** Consistent with D49 (Stage 04's schema fix). The
read API for downstream code stays `pd.read_parquet`; no
HuggingFace-specific deserialization needed in Stage 06.

**Affects.** Stage 05 output format; Stage 06 dataloader.

**Reversibility.** High.

---

### D58 — No padding at tokenize time; dynamic padding per batch  *(locked, 2026-05-11)*

**Decision.** Stage 05 writes unpadded `input_ids` and
`attention_mask`. Padding to a uniform batch length is applied
dynamically by Stage 06's `DataCollatorWithPadding`.

**Alternatives.** Pre-pad to `max_length=512` (uniform-length
rows); pre-pad to per-batch maximum (would require batching at
tokenize time, awkward).

**Rationale.** Pre-padding inflates on-disk size and memory
footprint by `512 / mean_token_count` ≈ 3-5× for typical inputs.
Padding at batch time is the standard HuggingFace convention and
has no compute disadvantage; the tokenizer's collator pads in
parallel with batch assembly.

**Affects.** Stage 05 output size; Stage 06 dataloader is the
standard HF pattern.

**Reversibility.** High.

---

### D59 — All Stage 04 metadata preserved through Stage 05  *(locked, 2026-05-11)*

**Decision.** Stage 05 output preserves all 13 Stage 04 columns
unchanged (`instance_id`, `parent_id`, `split`, `input_text`,
`input_text_hash`, `label`, `vector`, `source`, `scenario`,
`severity`, `harm_types`, `generation_status`,
`wrapper_template_id`) and adds five new columns (`input_ids`,
`attention_mask`, `token_count`, `was_truncated`,
`truncated_token_count`), for 18 total.

**Alternatives.** Strip metadata that Stage 06's training loop
does not need (would save modest space).

**Rationale.** Stage 06's evaluation slicing reads `vector`,
`scenario`, `severity`, `harm_types`, `source`. Stripping any
of these would force a join back to Stage 04 outputs, complicating
the training stage's data path for no real saving. `input_text`
is also preserved so debugging the model on a specific instance
does not require re-decoding `input_ids`.

**Affects.** Stage 05 schema; Stage 06 dataloader simplicity.

**Reversibility.** High.

---

### D60 — Tokenization is deterministic  *(locked, 2026-05-11)*

**Decision.** Identical input string produces byte-identical
tokenized output across runs and Python sessions. No
augmentation, no random splits at tokenize time.

**Alternatives.** Apply augmentation at tokenize time (e.g.,
random insertions, dropouts) to expand the training distribution.

**Rationale.** Augmentation at tokenize time would couple
Stage 05 and Stage 06; rerunning Stage 06 with different
augmentations would require rerunning Stage 05. Pre-tokenization
without augmentation lets Stage 06 own all training-time data
transformations (including future augmentations), keeping
responsibilities clean.

Determinism also enables exact reproducibility of training runs
from the manifest's checksum trail.

**Affects.** Stage 05 (no augmentation); Stage 06 (owns all
training-time augmentation if any is later added).

**Reversibility.** High.

---

### D61 — Per-vector truncation rates in the manifest  *(locked, 2026-05-11)*

**Decision.** The Stage 05 manifest records per-vector
truncation statistics (rows, truncated_rows, truncation_rate,
mean/p95/max token_count) per split, not just the per-split
aggregate. Future analyses can read the manifest and reconstruct
per-slice statistics without rerunning.

**Alternatives.** Store only per-split aggregate stats; recompute
per-vector stats from the Parquet files when needed.

**Rationale.** The manifest is a small JSON file; including the
per-vector breakdown is free in storage. Recomputing per-slice
stats requires reading the full Parquet, which is many seconds
per split. The manifest serves as a cache for the analyses we
have already established we want (D56 measurement gate; the
paper's Methods section reporting).

**Affects.** Stage 05 manifest format; results_log §5.

**Reversibility.** High.

---

### D62 — Proceed with right-truncation; sliding window as Stage 07 ablation  *(locked, 2026-05-11)*

**Decision.** After observing 57.8–60.0 % V2 truncation rates
across all splits (the D56 measurement gate fired), we
**proceed to Stage 06 with right-truncation as configured**.
A diagnostic spike (recorded in `results_log.md` §5.6) measured
the actual payload survival per truncated V2 instance and
classified the situation as the middle regime: median 57.9 %
payload survival, 7.8 % of truncated rows with the attack
entirely lost.

The sliding-window inference alternative is **scheduled as a
Stage 07 ablation**, conditional on (a) sufficient remaining
time after the headline evaluation completes and (b) the
empirical V2 gap actually observed in Stage 06 being large
enough to motivate the ablation.

**Context.** D56 pre-registered a 25 % V2 truncation warning
threshold and offered four mitigation options if the threshold
fired:

* (a) Asymmetric truncation per vector — rejected as not
  deployable (inference time has no vector label).
* (b) Sliding-window inference — costs one session before
  Stage 06; recovers attacks regardless of position.
* (c) Long-context encoder swap — forces abandoning the
  PubMedBERT encoder locked in D4.
* (d) Reduce input verbosity — research-level work, not a quick
  fix.

The spike result expanded the option space with a fifth:

* (e) Proceed with right-truncation, document the limitation,
  schedule sliding-window as a late-stage ablation.

**Alternatives considered.**

* **Option (b) immediately** — costs one session before Stage 06
  but gives us best-possible V2 numbers from day one. Rejected
  for v1.0 because (i) we cannot yet quantify the practical V2
  gap before Stage 06 produces baselines, so investing the
  session is premature optimization; (ii) all four baseline
  detectors face the same constraint, so right-truncation
  preserves apples-to-apples comparison; (iii) the 4.6 %
  structural ceiling is bounded and documentable.

* **Option (a) asymmetric truncation** — rejected: at deployment
  time the detector does not have the vector label, so this
  cannot generalize beyond benchmark evaluation.

* **Option (c) encoder swap** — rejected: requires reopening D4.

* **Option (d) shorter inputs** — rejected: would require
  abridging benign evidence, gutting the V2 mechanism.

**Rationale.** The spike result placed us in the middle regime:
median 57.9 % payload survival, not the catastrophic Regime 3
that would force sliding-window adoption now. The 4.6 %
structural ceiling on V2 recall under right-truncation is real
but bounded; we document it explicitly. Sliding-window as an
ablation at Stage 07 is also **more publishable** than sliding-
window as the headline — it frames the encoder's positional
limit as an engineering tradeoff we measured rather than a
defect we patched.

**Affects.** Stage 06 uses tokenized data as-is; Stage 07 adds
a sliding-window inference variant as an additional row in the
results table if time permits.

**Reversibility.** High. If Stage 06 reveals that V2 gap is
larger than the 4.6 % structural ceiling suggests (e.g., the
detector also loses meaningful signal on the 50-75 % survival
band), we can implement sliding window before Stage 07 finalizes.
Cost: one session of work; no upstream rebuild required.

**Limitation to document in paper.** The Methods section will
include the following statement:

> Our detector classifies inputs after right-truncation at 512
> tokens, consistent with PubMedBERT's positional limit and with
> the configuration of the published baselines we compare
> against. For V2 (RAG-mediated injection) inputs that exceed
> this length, the poisoned-update content at the tail of the
> retrieved-context block may be truncated. We measured this on
> our benchmark: 4.6 % of V2 instances have their entire
> poisoned-update payload truncated and are not detectable by
> any model trained on the truncated representation. A
> sliding-window inference variant that recovers this ceiling is
> reported as an ablation.

The ablation row, if produced, gives the paper a clean follow-up:
"PharmGuard (sliding-window inference)" with the V2 TPR delta.

---

### D63 — Model architecture for v1.0: PubMedBERT + linear head; Φ = identity  *(locked, 2026-05-11)*

**Decision.** The v1.0 trainable model is
`AutoModelForSequenceClassification` instantiated on
`microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract` with
`num_labels=2`. Layer 1 (Φ adversarial canonicalization) is
identity in v1.0; the canonicalization expansion is deferred to
a later ablation.

**Alternatives.** (a) Include a non-trivial Φ from day one
(Unicode normalization + payload decoding + provenance-spoof
stripping). (b) Use a custom encoder + custom head implementation.

**Rationale.** Shipping Φ = identity keeps Stage 06A's training
scope tight without precluding the contribution: if PharmGuard
already beats published baselines at FPR = 0.1 % with identity-Φ,
the case for non-trivial Φ becomes a clear ablation. If it
narrowly loses, Φ is the first lever to pull. Using HF's
standard `AutoModelForSequenceClassification` keeps ablations
trivial — Stage 06C swaps encoder_name and reruns.

**Affects.** Stage 06A architecture; methodology §4.1.

**Reversibility.** High at the file level; medium for the
ablation-vs-headline framing.

---

### D64 — Weighted cross-entropy via Trainer subclass  *(locked, 2026-05-11)*

**Decision.** Class-weighted cross-entropy is applied via a
`WeightedTrainer(Trainer)` subclass that overrides
`compute_loss` to call
`F.cross_entropy(logits, labels, weight=tensor([w_benign, w_attack]))`.
Class weights come from CONFIG (D21: 1.0 / 3.0).

**Alternatives.** (a) HF's built-in `class_weight` (does not
exist on `Trainer`); (b) `WeightedRandomSampler` for oversampling
(changes effective epoch length, complicates step counts); (c)
focal loss (different mathematical object; would need to be
justified in methodology); (d) hand-rolled training loop.

**Rationale.** The Trainer subclass is the minimum-intervention
pattern: ~10 lines of code, reuses everything else in HF
(collator, eval, checkpointing). Oversampling would distort the
benchmark's documented class imbalance and complicate the
mapping to deployment statistics. Focal loss is a research
direction that should be an ablation, not the default.

**Affects.** Stage 06A `loop.py`.

**Reversibility.** High.

---

### D65 — HuggingFace Trainer as training framework  *(locked, 2026-05-11)*

**Decision.** Stage 06A and downstream training use
`transformers.Trainer` (subclassed where needed for weighted
loss). No PyTorch Lightning, no custom training loop.

**Alternatives.** (a) PyTorch Lightning — modern, more
boilerplate avoidance, but introduces a second framework
dependency. (b) Hand-rolled PyTorch training loop — ~200 lines
of code that could harbour bugs.

**Rationale.** HF Trainer is what PromptShield and most
published detector papers use, so configuration is directly
comparable. It handles dynamic padding via
`DataCollatorWithPadding`, FP16 mixed-precision, eval scheduling,
checkpoint selection, and early stopping — all the things we'd
have to write ourselves. The single weakness (default loss
function is unweighted) is fixed by D64.

**Affects.** Stage 06A; Stage 06B (multi-seed loop); Stage 06C
(ablations). All adopt the same scaffold.

**Reversibility.** Medium — switching frameworks later would
require rewriting `loop.py` (~250 lines).

---

### D66 — Best-val-AUC checkpoint selection  *(locked, 2026-05-11)*

**Decision.** During training, validation AUC on `val.parquet`
is computed at the end of each epoch via a custom
`compute_metrics` function. Trainer's `load_best_model_at_end=True`
with `metric_for_best_model="auc"` and
`greater_is_better=True` selects the highest-AUC epoch.
`EarlyStoppingCallback(patience=1)` halts training one epoch
after AUC plateaus.

**Alternatives.** (a) Best val loss — but val loss is dominated
by the 95 % benign rows; a model that gets every benign right
and every adversarial wrong scores well on loss. (b) Best val F1
— defensible but threshold-dependent; AUC is threshold-free and
more directly tied to the Layer 3 calibration step. (c) No early
stopping, save the final checkpoint — risks late-epoch
overfitting.

**Rationale.** With val carrying 143 adversarial vs 2,585
benign, AUC is the threshold-free metric most directly tied to
what the calibrated detector will do at deployment. The
adversarial recovery from D53 (the routing-bug fix) is what
makes this metric reliable; without those 143 rows, val AUC
would be ill-defined (only one class present).

**Affects.** Stage 06A `loop.py` (`compute_metrics`, Trainer
config).

**Reversibility.** High — switching metrics is a single
TrainingArguments change.

---

### D67 — Calibration: smallest-τ-meeting-FPR rule + Wilson CI  *(locked, 2026-05-11)*

**Decision.** Post-training, the trained model is run in eval
mode over `calibration.parquet` (455 pure benign per D47). For
each target FPR β ∈ {0.01, 0.005, 0.001}:

  τ*(β) = inf{ τ : (#{benign : s ≥ τ}) / n ≤ β }

Implementation: sort benign scores descending; let
`k_max = floor(β · n)`; the threshold is the score at position
`k_max - 1` (1-indexed: the k_max-th highest). If
`k_max = 0` (cannot afford any false positives), the threshold
is `max(scores) + epsilon`, producing realized FPR = 0.

Each threshold is reported alongside its realized FPR and the
Wilson 95 % CI on the realized FPR.

**Alternatives.** (a) "Largest τ" (most conservative threshold)
— matches FPR exactly but loses recall; rejected because
deployment intent is "operate as sensitively as the FPR budget
allows". (b) Interpolated threshold between sort-positions —
not principled at small β with discrete data. (c) Bootstrap CI
— equivalent to Wilson at scales relevant to this benchmark and
much slower.

**Rationale.** The smallest-τ rule is the PromptShield
convention and matches what published baselines use. Wilson
95 % CI is more accurate than normal-approximation CI at small
n and extreme p — exactly the regime for β = 0.001 with
n = 455.

**Affects.** Stage 06A `calibration.py`; methodology §4.3.

**Reversibility.** High.

**Important honest note.** At β = 0.001 with n = 455, k_max = 0.
We cannot calibrate τ at this target with the current
calibration split size. We report the result honestly (realized
FPR = 0, Wilson CI [0, 0.008]) and either (a) increase n_cal in
v1.1 by reserving more benign-clinical rows, or (b) report only
the 0.5 % and 1 % targets in the headline table with the 0.1 %
target as a separate footnote indicating the structural ceiling.
This is recorded as a v1.0 limitation, separately from D62's V2
truncation ceiling.

---

### D68 — Checkpoint and artifact layout  *(locked, 2026-05-11)*

**Decision.** Each (seed, config) training run writes one
directory:

```
pharma_models/seed_<seed>_config_<config>/
├── model.safetensors (or pytorch_model.bin)
├── config.json
├── tokenizer files (vocab.txt, tokenizer.json, etc.)
├── training_log.json
├── calibration.json
└── stage_06A_manifest.json
```

The directory naming `seed_42_config_main` anticipates Stage 06B
(multi-seed: same config, different seeds) and Stage 06C
(ablations: same seed 42, different configs like `noweight` /
`bertbase` / `distilbert`).

**Alternatives.** (a) Single flat directory with descriptive
filenames (`seed42_main_model.safetensors`, etc.) — harder to
clean up partial runs. (b) HuggingFace Hub-style versioned
repository per (seed, config) — overkill for v1.0.

**Rationale.** One directory per run means partial / failed runs
are trivially cleaned with `rm -rf`, the manifest is
self-contained, and Stage 06B/06C/07 can iterate
`pharma_models/seed_*` without parsing filenames.

**Affects.** Stage 06A output layout; Stage 06B (loops over
seeds, each writes its own dir); Stage 07 (reads all dirs).

**Reversibility.** Medium — changing the layout means rewriting
the manifest paths and the downstream readers.

---

### D69 — Full determinism via set_all_seeds + deterministic CUDA  *(locked, 2026-05-11)*

**Decision.** Every training run calls
`set_all_seeds(seed, deterministic=True)` at the very start,
which sets Python's `random`, NumPy, PyTorch CPU, PyTorch CUDA,
and `PYTHONHASHSEED`. Additionally:

* `torch.backends.cudnn.deterministic = True`
* `torch.backends.cudnn.benchmark = False`
* `CUBLAS_WORKSPACE_CONFIG=":4096:8"` (required for deterministic
  CUBLAS on some operations)
* `torch.use_deterministic_algorithms(True, warn_only=True)`
* HF `TrainingArguments(seed=seed, data_seed=seed)`

**Alternatives.** (a) Non-deterministic training for ~10-30 %
training-throughput improvement — rejected because
within-detector-across-seeds variance reporting (a contribution
goal) depends on genuine model variance, not RNG drift. (b)
Determinism only for headline runs — would create asymmetry
between headline and ablations.

**Rationale.** Stage 06B's multi-seed reporting (mean ± std
across 5 seeds) is part of the paper's central methodology
claim. Determinism is necessary for that claim to be honest:
the std should reflect model variance, not nondeterministic
CUDA ops. The throughput cost is bounded (~20 % on L4 from
benchmarks).

**Affects.** Stage 06A `loop.py`; every subsequent training
stage.

**Reversibility.** High at the code level; reporting impact
moderate.

---

### D70 — Stage 04 wrapper-shortcut requires rework  *(locked, 2026-05-11)*

**Decision.** After Stage 06A produced suspicious scoring patterns
(val AUC 0.9813 but val recall 0.63 at τ=0.5; benign calibration
scores all at the FP16 floor of 0.0001; test_v2 scores uniformly
0.9998 with std=0), a verification spike identified the root
cause: **the model is firing on the presence of `[context:*]`
markers, not on the semantic content of the adversarial
payload.** Stage 04's input-construction logic produces V2
instances with `[context:benign_evidence]` and
`[context:poisoned_update]` markers, while benign-clinical
instances have no such markers — making marker presence a
perfect proxy for the label.

We **invalidate the Stage 06A model and the v1.0 Stage 04 input
format**, and schedule a Stage 04 rework (next session) to
include benign instances with retrieved-context structure.

**Evidence.** From the verification spike (this session,
results_log §6.A.1):

| Input variant for test_v2 | Mean score | Std |
|---|---|---|
| Original `[context:benign_evidence] ... [context:poisoned_update] ...` | 0.9998 | 0.0000 |
| Strip only `[context:poisoned_update]` marker (keep content) | 0.9998 | 0.0000 |
| Strip entire poisoned_update block (marker + content removed) | 0.9998 | 0.0001 |
| Strip ALL `[context:*]` markers (content kept) | 0.8919 | 0.1688 |

The model scores test_v2 instances at 0.9998 even with the
poisoned-update content completely removed. The wrapper structure
(presence of `[context:*]` markers) is the discriminative
feature, not the attack content.

**Corroborating evidence.** The model scores `generic_attack_ood`
(jailbreaks from deepset and JailbreakBench, no `[context:*]`
markers) at mean 0.003 — i.e., as benign — despite these being
adversarial instances. A model that learned to detect prompt
injection would catch these; a model that learned to detect a
specific input wrapper would miss them. The latter is what we
have.

**Root cause.** Stage 04's `build_input_text` produces:

* V1 instances: `[system] ... [user] {injected_query}` (no
  context blocks)
* V2 instances: `[system] ... [user] ... [context:benign_evidence] {evidence} [context:poisoned_update] {payload}`
* Benign-clinical instances: `[system] ... [user] {clinical_query}` (no context blocks)

So in our training distribution, **every input containing
`[context:*]` markers is adversarial**, and the model uses this
as a shortcut. This is a distributional contamination of the
input format.

**Alternatives considered.**

(a) **Ship as-is and document the limitation.** *Rejected.* The
val AUC 0.98 headline is meaningless if the model is doing
wrapper detection rather than attack detection. The result
would not survive review and would invalidate the paper's core
claim.

(b) **Train the model differently (e.g., adversarial training,
stronger regularization).** *Rejected.* No training-time fix
can recover information that's not in the data. The model is
correctly learning what the data tells it; the data is wrong.

(c) **Strip all `[context:*]` markers from every input at
training time.** *Rejected.* This destroys the structural cue
that genuine V2 detection should use (the conflict between
evidence and update). PromptShield and PromptGuard both
preserve role markers; matching them is correct.

(d) **Add benign-with-RAG structure (chosen).** Re-wrap a
fraction of benign-clinical inputs with `[context:benign_evidence]`
blocks using legitimate biomedical retrieved evidence (PubMedQA
long answers, OpenFDA monograph text). This breaks the
marker-as-shortcut by introducing benign instances at every
structural shape the adversarial distribution occupies.

**Design of the fix (locked at this session, to implement next session).**

1. Stage 04's benign-clinical pipeline gains a wrapping step
   that, with probability *p_rag*, transforms a benign instance
   from `[system] ... [user] {query}` into
   `[system] ... [user] {query} [context:benign_evidence] {evidence}`.
2. The retrieved evidence comes from already-acquired
   benign-clinical sources (PubMedQA long answers are
   particularly well-suited: they are authoritative biomedical
   text, similar in length and tone to MPIB V2 evidence blocks).
3. A second variant wraps with two evidence blocks
   (`[context:benign_evidence] {a} [context:benign_evidence] {b}`)
   to match V2's two-block structure even more closely.
4. Target: roughly 30 % of train benign-clinical instances carry
   context blocks. Exact rate will be tuned to break the marker
   shortcut without creating new biases.
5. The benign-with-RAG instances are also added to val,
   calibration, and clinical_benign_holdout in equal proportion.

**Scope of the rework.**

* Stage 04 modification: ~1-2 hours.
* Stage 04 rerun: 30 seconds.
* Stage 05 rerun: 90 seconds.
* Stage 06A rerun: 30-45 minutes.
* Diagnostic re-verification: 1 minute.

Total: one Colab session, mostly waiting for Stage 06A.

**Affects.**

* `pharmguard/data/benign.py` (benign-with-RAG wrapping logic).
* `pharmguard/data/splits.py` (Stage 04 orchestrator gains the
  new wrap step).
* All seven Stage 04 outputs (regenerated).
* All seven Stage 05 outputs (regenerated).
* `pharma_models/seed_42_config_main/` — *invalidated, will
  be replaced.* Keep the directory on Drive for forensic
  comparison ("v1.0-shortcut" model vs the v1.1 model that
  comes after the fix).

**Reversibility.** High at the code level (the wrapping is one
function). Medium at the experimental-narrative level: we are
explicitly recording v1.0 as a "what we learned" milestone.

**Methodological note for the paper.** The v1.1 model's
performance will be the headline. The v1.0-shortcut finding
is worth a brief mention in the Methods section as an example
of the distributional-contamination failure mode the
methodology was designed to catch (D54 integration check
pattern, post-stage diagnostic spikes). This turns the bug
into a methodological strength rather than something to hide.

---

### D71 — Vocabulary unification + two-block benign augmentation (the D70 fix, implemented)  *(locked, 2026-05-11)*

**Decision.** Stage 04's input-construction logic is modified
two ways to break the wrapper shortcut diagnosed in D70:

1. **Vocabulary unification.** All retrieved-context blocks use
   a single uniform marker, `[retrieved]`, regardless of class.
   Previously the marker was `[context:{role}]` with `role` drawn
   from a class-disjoint vocabulary: `benign_evidence` /
   `poisoned_update` for adversarial V2 instances, vs
   `clinical_note` / `drug_label` / `research_abstract` /
   `patient_dialogue` for benign-clinical instances. The disjoint
   vocabularies were the actual shortcut. Unifying to a single
   marker forces the model to read the block's content.

2. **Two-block benign augmentation.** 15 % of benign-clinical
   inputs are wrapped with **two** `[retrieved]` blocks instead
   of one, with the second block content sampled from another
   benign row's text. This matches V2's two-block structural
   shape so that retrieved-block count is no longer a label
   proxy either.

**Implementation.** Three small changes to
`pharmguard/data/splits.py`:

* `_format_mpib_input_text` (line ~296) emits `[retrieved] {text}`
  rather than `[context:{role}] {text}`.
* `_format_benign_input_text` (line ~343) emits `[retrieved] {text}`
  rather than `[context:{wrapper.context_role}] {text}`.
* `build_benign_clinical` (line ~393) accepts
  `two_block_fraction=0.15` and `seed=42`, deterministically
  selects 15 % of benign rows, and appends a second `[retrieved]`
  block from a randomly sampled donor row. The
  `wrapper_template_id` records the variant
  (`benign_<source>_2block` vs `benign_<source>`).

**Alternative implementations considered.**

* **Two-block fraction higher (~30 %).** Closer to V2's
  share of train (455 V2 vs 14,846 benign-clinical = ~3 %), so
  15 % already substantially overshoots V2's actual share. Going
  higher could make the model over-rely on the second block,
  introducing the opposite bias. Stay at 15 % for v1.0; tune in
  v1.2 if needed.

* **Sample second-block content from a different source pool**
  (e.g., dedicated retrieved-evidence corpus). Rejected for v1.0
  because the benign-clinical pool already covers the relevant
  text distribution and using it as both first- and second-block
  source avoids introducing new biases. Future work could use
  PubMedQA's long-answer field specifically.

* **Vary the order of retrieved blocks (random shuffle within
  V2 too).** Would further reduce position-of-block as a feature.
  Deferred — Stage 03 already produces a consistent order;
  shuffling would require re-running Stage 03.

**Validation.** 7 sandbox logic tests passed (this session):

1. V2 MPIB inputs now use `[retrieved]` only; no `[context:*]`
   markers remain. Two blocks present.
2. V1 MPIB inputs have no `[retrieved]` blocks.
3. Benign-clinical inputs use `[retrieved]`; `wrapper_template_id`
   correctly records source.
4. Two-block fraction of 0.15 produces exactly 15 of 100 rows
   wrapped with two `[retrieved]` markers.
5. Across all generated text, only three marker types appear:
   `[system]`, `[user]`, `[retrieved]`. No `[context:*]`
   anywhere.
6. Same `seed=42` produces identical wrapping across calls.
7. Different seeds produce different (deterministic) selections.

**Block-count distribution after D71.**

| Class                                  | `[retrieved]` blocks |
|----------------------------------------|---------------------:|
| V1 (adversarial)                       | 0                    |
| V2 (adversarial)                       | 2                    |
| Benign-clinical 85 %                   | 1                    |
| Benign-clinical 15 % (two-block)       | 2                    |
| Generic attacks (OOD)                  | 0                    |

The training distribution now has benign instances at both 1
and 2 `[retrieved]` blocks. Block count is no longer a perfect
label proxy. (1-block remains a benign-only shape because V2
construction always has 2 blocks, but the model cannot use
"2 blocks → adversarial" because 15 % of benigns also have 2;
and the model cannot use "1 block → benign" because the
asymmetry only goes one way — V2 is never 1 block by
construction.)

**Affects.** Stage 04 only. Stage 05 inherits the new input
format automatically (re-tokenizes from the regenerated Stage
04 outputs). Stage 06A is rerun on the new tokenized data.

**Reversibility.** High at the code level. Reverting would
require re-running Stage 04 with the old `_format_*` functions.

**Risk register, post-fix.**

* The benign 1-block / V2 2-block asymmetry remains. If the
  model exploits this, we'd see V2 TPR drop to wherever benign
  1-block scoring lands. To verify this isn't the case, the
  post-rerun diagnostic will explicitly compare V2 score
  distribution against benign-with-2-blocks score distribution.
  Both should overlap if the model is reading content.

* The `_2block` benign rows draw their second-block content from
  *other benign rows*. If a particular benign row's text happens
  to be statistically distinctive (e.g., much longer or shorter
  than average), repeated sampling of that row as a donor could
  create a new signature. Mitigation: the donor sampler shuffles
  the full index list; with 14,846 benign rows in train, the
  expected number of donor reuses is small.

* `wrapper_template_id` ending in `_2block` reveals which rows
  got augmented. This is fine — it's auxiliary metadata, not
  fed to the model — but Stage 07 evaluation should slice on
  `wrapper_template_id` to verify performance on `_2block`
  benigns is similar to non-augmented benigns.

---

### D72 — Drop wrapped benign-clinical pool; use MPIB V0/V0p for benign  *(locked, 2026-05-11)*

**Decision.** Stage 04 no longer consumes the benign-clinical
wrapped pool (`pharma_data/benign/all_benign.csv`). Instead,
**MPIB's own V0 and V0' instances** supply the benign training
distribution. A deterministic carve-out (`_carve_mpib_v0_split`)
moves ~6 % of MPIB train V0/V0p rows each into the `calibration`
and `clinical_benign_holdout` splits; the rest stay in train.

**Context — the user_query shortcut.** After D71 unified the
context-marker vocabulary, the v0.7.2 model retrained with the
fix still produced perfectly saturated V2 scores (mean 0.9999,
std 0.0000 across 64 test_v2 instances). A second verification
spike isolated the residual shortcut: **`[user]`-line strings
were class-disjoint.** Benign-clinical rows used one of four
fixed templates from `BENIGN_WRAPPERS` (literally repeated
thousands of times in training); MPIB rows used open-set queries.
The spike result:

| Manipulation | Original score | After |
|---|---|---|
| V2 + benign-template `[user]` (contexts unchanged) | 0.9999 | 0.0000 |
| Benign-calibration + MPIB-style `[user]` (contexts unchanged) | 0.0000 | 0.9967 |

The delta is total (±1.00). The model is doing string-matching
on the `[user]` line; the retrieved context (adversarial or
benign) carries effectively zero weight in its decision.

**Why we adopt the structural fix (Fix B) rather than another
patch.** This is the second shortcut to surface. The first was
context-marker vocabulary (D71); the second is user_query
vocabulary (D72 context). Each fix to a specific contamination
axis has revealed the next. The deeper diagnosis: **any
closed-vs-open distributional axis between the benign-clinical
pool and the MPIB-derived adversarial pool is a shortcut
waiting to be learned.** Continuing to patch axis-by-axis is
not convergent. We instead eliminate the architectural
asymmetry by using a single source — MPIB — for both classes.

**Alternatives considered.**

(a) **Synthesize an MPIB-style benign-query pool (Fix A in
the session discussion).** Replace `BENIGN_WRAPPERS`'s four
templates with a pool of ~100 plausible clinical user queries.
*Rejected:* synthesizing a benign-query pool is itself a closed
distribution, just a larger one. The model can probably still
distinguish "synthesized-with-substituted-terms" from
"naturally-occurring-MPIB-query" on some axis. Fragile.

(b) **Hybrid: keep benign-clinical pool but rewrap each row
with a synthesized MPIB-like user_query (Fix C).** *Rejected:*
combines the costs of (a) (synthesis) with the costs of D72
(rework) without the structural guarantee of (D72).

(c) **Adversarial training / regularization.** *Rejected:* no
training-time fix can recover information that's not present
in the data, and the shortcut is in the data architecture, not
in the training procedure.

**Implementation.**

* `BENIGN_WRAPPERS` and `_format_benign_input_text` are retained
  in `splits.py` but no longer called by the orchestrator.
* `MPIB_V0_CARVE_BUCKETS` defines the hash buckets:
  `[("calibration", 6), ("clinical_benign_holdout", 12), ("train", 100)]`.
  ~6 % of MPIB train V0/V0p rows go to each held-out split.
* `_carve_mpib_v0_split` uses SHA-256 of (parent_id + "stage04_v0carve")
  mod 100 as the bucket. Distinct salt from `_assign_benign_split`.
* `_mpib_split_name` (inside `assign_splits`) applies the carve
  to train V0/V0p rows; V1, V2, val, and test rows are unchanged.
* `assign_splits` accepts `benign=None` to skip the benign-clinical
  block entirely.
* Orchestrator drops the benign loading, dedup, and wrap steps,
  calling `assign_splits(mpib, None, attacks, log)`. Pipeline goes
  from 8 phases to 7.
* Bonus fix: `_write_stage_06A_manifest` excludes
  `stage_06A_manifest.json` from `artifact_paths`, fixing the
  self-reference checksum mismatch caught by the v0.7.2
  integration check.

**Projected corpus (validated against MPIB Table 2):**

| Split                       | Rows  | Benign | Adversarial |
|-----------------------------|-------|--------|-------------|
| `train`                     | 6,943 | 5,991  | 952 (13.7 %) |
| `val`                       | 1,807 | 1,664  | 143         |
| `test_v1`                   |    67 |     0  |  67         |
| `test_v2`                   |    64 |     0  |  64         |
| `calibration`               |   408 |   408  |   0         |
| `clinical_benign_holdout`   |   408 |   408  |   0         |
| `generic_attack_ood`        |   301 |     0  | 301         |
| **Total**                   | **9,998** |   |             |

Train adversarial rate rises from 6.4 % (v0.7.2) to 13.7 %.

**Sandbox validation.** 6 tests passed: determinism,
proportions match expectation, independent salts
(Pearson r = 0.06), replay stability, AST validation of
modified `splits.py` and `loop.py`.

**Affects.** Stage 04 (regenerated); Stage 05 (re-tokenized);
Stage 06A (retrained).

**Reversibility.** Medium. The benign-clinical wrapping code is
retained but unused.

**Risk register.**

* Smaller train (6,943 vs 14,846 rows). Less data; D72's val AUC
  will likely be lower than D71's. This is expected — D71's was
  wrapper-detection-inflated.
* Calibration size drops 455 → 408. Wilson CI widens slightly.
* No source diversity from MTSamples / OpenFDA. Documented
  limitation: future work expands benign coverage.
* Adversarial-to-benign train ratio ~14 %; class weights
  (1.0 / 3.0) remain appropriate.

**Methodological note for the paper.** The D71 → D72 progression
shows that distributional matching of benign and adversarial
input wrappers (user-query distribution, marker vocabulary,
block-count structure) is a non-trivial requirement that
surfaces through post-stage diagnostic spikes. The Methods
section can frame this as the project's diagnostic discipline
working as intended.

---

### D73 — Benign retrieved-evidence augmentation on V0/V0p train rows  *(locked, 2026-05-12)*

**Decision.** Augment a fraction of MPIB train V0/V0p rows with
benign `[retrieved]` content blocks sampled from the Stage 01
benign-clinical pool. ~700 rows total: ~300 with one block,
~400 with two blocks. ~20 % of augmented rows get a benign
editorial-note framing prepended to the first block. The
benign-clinical pool is repurposed as a **text source** for
retrieved content, not as standalone rows in the corpus (which
was the v0.7.x / D71 mistake).

**Context — the block-presence shortcut.** After D72 (MPIB
V0/V0p replaces the benign-clinical pool), the v0.8.0 model
retrained on the new corpus produced:

* test_v1 mean 0.58, std 0.37  (real spread, real detection)
* test_v2 mean 0.999, std 0.0002 (collapsed)
* generic_attack_ood TPR at FPR=1 %: 1.0 % (was 84 % in v0.7.2)

The diagnostic spike confirmed the residual shortcut:

| Manipulation                                  | Score |
|-----------------------------------------------|-------|
| V2 baseline (2 `[retrieved]` blocks)          | 0.999 |
| V2 with last block stripped (→ 1 block)       | 0.902 |
| V2 with all blocks stripped (→ 0 blocks)      | 0.001 |

Delta when removing all `[retrieved]` blocks: −0.998. The model
fires on the *presence* of `[retrieved]` blocks. The retrieved
content is doing approximately 100 % of the work in producing
the high V2 score.

The block-count audit revealed why: across the entire D72 corpus,
*no* benign instance has any `[retrieved]` block, because MPIB's
V0/V0p instances by construction have empty `contexts` lists.
Meanwhile every V2 instance has exactly two retrieved blocks.
Block presence is therefore a perfect class signal on MPIB —
and a useless deployment signal, because real clinical RAG
systems retrieve evidence constantly.

**Why we adopt content-augmentation rather than further
restructuring.** The D70 → D71 → D72 progression each
caught one contamination axis (marker vocabulary, user-query
distribution, wrapper structure). The block-presence axis is
the next layer, but **fixing it requires adding training data
the model has never seen**: benign retrieval-shaped instances.
We cannot fix this by restructuring what we already have.

**Implementation.**

* `BENIGN_EDITORIAL_FRAMINGS` (15 hand-authored strings) — each
  stylistically similar to V2's editorial-note framings ("Editor's
  note: …", "Update: …", "Editorial summary: …") but
  unambiguously benign in content (reaffirming standard care,
  citing meta-analyses that confirm rather than change practice).
  Their purpose is to defuse a likely next-shortcut risk: if
  benign retrieved content had no editorial framings at all,
  the framing register alone could become the next class signal.
* `augment_v0_with_benign_retrieval(mpib, benign_pool, log,
   n_one_block=300, n_two_block=400, editorial_framing_fraction=0.20,
   seed=42)` — selects eligible V0/V0p train rows by deterministic
  shuffle (seed-stable), samples retrieved text from
  `benign_pool["text"]`, appends `[retrieved] {text}` lines.
  ~20 % of selected rows get a framing prepended to the first block.
  Sets `wrapper_template_id` to `v0_aug_1block` or `v0_aug_2block`.
* Orchestrator phase added between `build_mpib_input_text` and
  `build_generic_attacks`. The pipeline goes from 7 phases to 7
  phases (the augmentation replaces no existing phase).
* `benign_csv` is required again (D72 made it optional). The CSV
  is loaded as `benign_pool` and used as a *text source* only.

**Block-presence distribution after D73 (train split):**

| Vector / source                          | Blocks | Count  | Class |
|------------------------------------------|--------|--------|-------|
| V1                                       | 0      | ~500   | adv   |
| V2                                       | 2      | ~455   | adv   |
| V0 / V0p unaugmented                     | 0      | ~5,100 | benign |
| V0 / V0p augmented (one block, D73)      | 1      | ~300   | benign |
| V0 / V0p augmented (two blocks, D73)     | 2      | ~400   | benign |

Train distribution at 2 blocks: ~455 V2 (adv) vs ~400 V0 (benign).
Train distribution at 0 blocks: ~500 V1 (adv) vs ~5,100 V0 (benign).
Train distribution at 1 block: 0 adv vs 300 V0 (benign).

Block presence is no longer a class signal. The model must read
content to distinguish. The 1-block bucket is benign-only by
design (V2 always has 2 blocks; benign-with-1-block represents
realistic single-evidence RAG retrieval).

**Sandbox validation.** 10 tests passed:

1. Augmented rows are all eligible V0/V0p train (not V1/V2, not
   val/test).
2. V1 train rows untouched.
3. Val V0/V0p rows untouched (test-time benign distribution
   stays pure MPIB).
4. 1-block rows have exactly 1 `[retrieved]` marker.
5. 2-block rows have exactly 2 `[retrieved]` markers.
6. Same seed → identical output across runs.
7. Different seeds → different selections.
8. Editorial framings appear at the configured fraction.
9. `splits.py` parses cleanly.
10. All D73 names present in source.

**Affects.** Stage 04 (regenerated outputs); Stage 05 (re-
tokenized); Stage 06A (retrained).

**Reversibility.** Medium. Setting `n_one_block = n_two_block = 0`
disables D73 entirely while leaving the function in place.

**Risk register.**

* **Content-style shortcut (most likely remaining axis).** If
  V2's poisoned text has stylistic features (specific drug names,
  guideline-violation terminology, dosage escalations) that
  benign retrieved content naturally lacks, the model could
  learn the content style as a class signal. Mitigation: the
  editorial framings in D73 specifically address one such axis
  (editorial register). Other axes (drug-class concentration,
  numerical-dose density) are harder to address pre-emptively
  and may surface in the post-rerun diagnostic.
* **Length distribution mismatch.** Augmented benign blocks
  draw from PubMedQA/MTSamples lengths, which may differ from
  V2's block lengths. The training loop should be robust to
  this, but it's worth checking the V2-vs-augmented-benign
  block-length distributions in the post-rerun diagnostic.
* **Editorial framing leakage in test.** Test instances are
  unaugmented MPIB (no D73 framings), but if the model learns
  "any editorial framing → benign," it could mis-score V2's
  poisoned-update framings ("Editor's note: clinicians may
  increase dose…") as benign. Mitigation: 80 % of augmented
  rows have no framing; framings are a minority signal.
* **Donor-pool sampling produces unrealistic combinations.**
  D73 samples benign text from MTSamples, PubMedQA, OpenFDA
  and pairs them with MPIB V0/V0p queries. Some pairings will
  be semantically incoherent (e.g., a query about chest pain
  with a retrieved OpenFDA monograph about an unrelated drug).
  This is a feature, not a bug — the model should learn that
  *retrieved content is sometimes off-topic but benign*, which
  is exactly what real RAG systems produce when retrieval
  ranking is imperfect.

**Methodological note.** The D70 → D71 → D72 → D73 progression
is now four shortcuts deep. Each fix addressed one specific
contamination axis. D73 is the first fix that adds new data
rather than restructuring existing data. After D73, the model's
training distribution covers benign instances at all three
block counts (0, 1, 2), with both plain and editorial-framed
retrieved content. The remaining contamination axes (if any)
are at the content-style level rather than the wrapper-structure
level. This is the right place for the model to start needing
to actually read content to detect attacks — which is the whole
point of the project.

---

### D74 — Drive sync verification after expensive stage writes  *(locked, 2026-05-12)*

**Decision.** Add post-write verification that artifacts have
actually persisted to Drive (not just to Colab's fuse cache)
after every stage that produces expensive output. Stages with
verification: 01 (benign acquisition), 03 (Phi-3 reconstruction),
04 (splits), 05 (tokenization), 06A (training).

**Context — the v0.8.0 data loss event.** Between Colab sessions,
*all* of `pharma_data/{adversarial,benign,splits,tokenized}/`
plus `pharma_models/` were lost. The data was on Drive at the
end of one session and missing at the start of the next. Most
likely cause: Colab Drive's asynchronous sync — writes go to a
local fuse cache, and if the runtime ends before Drive sync
completes, files vanish on next session even though every
Python-level write returned success.

Cost of the loss: 81 minutes of Stage 03 Phi-3 inference, plus
several Stage 04–06A reruns. The 81-minute loss is the painful
one.

**Implementation.** New module `pharmguard/data/drive_sync.py`
exposes three functions:

* `force_drive_sync(wait_s=3.0)` — issues a `sync` syscall and
  sleeps so the fuse-to-Drive layer can catch up. Wait time is
  caller-configurable; default 3 s for small files.
* `assert_drive_persisted(path, expected_size, expected_sha256=None,
   wait_s=3.0)` — re-stats the file after sync and verifies size
  (and optionally SHA-256) matches. Raises `DriveSyncError` on
  mismatch.
* `verify_directory_persisted(dir_path, expected_files, wait_s=3.0)`
  — same verification but for a set of files (e.g., a model
  checkpoint directory).
* `compute_wait_for_size(size_bytes)` — heuristic returning
  3 s / 10 s / 30 s for <1 MB / <100 MB / >=100 MB files.

Each affected stage calls `verify_directory_persisted` (or
`assert_drive_persisted` for single-file outputs) immediately
after writing the manifest. If verification fails, the stage
raises `RuntimeError` rather than declaring success — so we know
*at the time of failure*, not days later.

**What this can't catch.** A failure that happens *after*
verification (e.g., the runtime crashes within seconds of the
manifest write) is still possible. We can't prove from inside
Colab that Drive has durably persisted a file; we can only check
that it appears persistent at a point in time. The wait + re-stat
is pragmatic compensation for an opaque sync layer.

**Tested by.** Manual exercise after the v0.8.1 rerun cycle. No
sandbox-level test of the sync mechanism itself (sandbox doesn't
have fuse / Drive); the function logic is straightforward enough
that AST validation suffices.

**Affects.** Stages 01, 03, 04, 05, 06A. Each gains ~3–30 seconds
of wait time per stage (negligible compared to compute time).

**Reversibility.** High. Setting `wait_s=0` or commenting out the
verify blocks removes the protection without affecting correctness.

---

### D75 — Imperative-mood retrieved-content augmentation + Phi-3 benign generation (the D73 fix)  *(locked, 2026-05-12)*

**Decision.** Stage 04's V0/V0p augmentation pool is extended
from one source (declarative-mood benign-clinical text) to
**three sources, sampled with equal weight**:

  1. The original declarative-mood benign-clinical pool from
     Stage 01 (MTSamples, PubMedQA, OpenFDA, clinical dialogues)
  2. Hand-authored imperative-mood templates with substitution
     slots, producing benign clinical directives ("clinicians
     should continue current dosing of {DRUG} per {GUIDELINE}")
  3. **Phi-3-generated** benign updates in R7/R10-style editorial
     register, produced by a new caching sub-stage (Stage 03B)

**Context — the imperative-mood shortcut.** The v0.8.1
diagnostic spike isolated the residual shortcut after D73:
adding a retrieved block with imperative-mood content raised
benign-V0/V0p scores from 0.0001 → 0.397 (a 0.397-point jump
from changing only the retrieved-block register, not the
user_query or label class). Conversely, replacing V2's
poisoned retrieved blocks with declarative-mood benign content
dropped V2 scores by 0.089, but replacing with imperative-mood
benign content dropped scores by only 0.005 — the model's
discriminator was almost entirely the mood register.

D73's editorial framings ("Editor's note: A 2024 meta-analysis
confirms…") were stylistically authoritative but grammatically
declarative — the verb subjects were *evidence* ("X confirms")
rather than *clinicians* ("clinicians should X"). The model
learned to ignore the framing register and key on the
underlying verb mood.

**Why three sources instead of one fixed-register pool.** We
explicitly hypothesized in the post-spike discussion that
ANY single uniform replacement would just leave the next
discriminator axis available (writing source, citation
presence, intensifier vocabulary). Three sources with
*different* origins and *equal weight* makes it
combinatorially harder for the model to find a single
discriminator:

  - Source 1 (declarative human) is the legacy D73 source.
  - Source 2 (imperative human) adds the missing mood register.
  - Source 3 (imperative Phi-3) closes the writing-source gap:
    V2's poisoned blocks were Phi-3-generated, so adding
    Phi-3-generated benign blocks at equal frequency
    eliminates "Phi-3 writing style → adversarial" as a signal.

After D75, an augmented V0/V0p row's retrieved block has a
1/3 chance of being declarative, 1/3 imperative-template,
and 1/3 Phi-3-imperative. The model cannot key on mood OR
writing source.

**Implementation.**

New modules:

  - `pharmguard/data/imperative_benign.py` — 25 hand-authored
    templates with slot vocabularies (23 drugs, 18 conditions,
    12 guideline bodies, etc.). `instantiate_templates(n, seed)`
    produces n unique blocks deterministically.
    `safety_screen(text)` rejects blocks containing deviation
    phrases ("increase the dose", "without monitoring",
    "may safely skip", etc.) as defense in depth.
  - `pharmguard/data/benign_phi3_generation.py` — R7/R10-inverse
    prompt scaffolds for Phi-3-mini, generating editorial and
    institutional updates that reaffirm standard care. Each
    generation is safety-screened; rejected outputs are kept
    in the parquet for auditability with `accepted=False`.
  - `scripts/03B_generate_benign_imperatives.py` — runner for
    the new sub-stage. Loads Phi-3-mini, generates ~250 blocks,
    safety-screens, saves to
    `pharma_data/adversarial/benign_imperatives_v0.parquet`.
    Wall-clock ~22 min on L4 GPU.

Modified:

  - `augment_v0_with_benign_retrieval` in `splits.py` now accepts
    `imperative_pool` and `phi3_pool` keyword arguments. The
    sampling function `sample_block_text()` randomly chooses
    one of the active sources with equal weight, then samples
    a block from that source. Per-block source provenance is
    counted and logged for downstream auditing.
  - Stage 04 orchestrator: loads the two new pools at the start
    of phase [4/7], passes them to the augment function. If
    Stage 03B output is missing, falls back gracefully to
    D73-mode (declarative only) with a warning log.

**Risk mitigations (three, addressed simultaneously).**

(A) **Phi-3-generated content might be accidentally adversarial.**
The same Phi-3-mini that generated V2's poisoned blocks could
generate unsafe content if the prompt isn't constrained.
Mitigation: explicit prompt constraints requiring "NO
deviation from established care" plus a regex safety screen
rejecting deviation phrases. Rejected blocks are preserved
in the parquet with reject_reason for audit.

(B) **Source-register mismatch in length distribution.**
Phi-3 blocks could be shorter/longer than human-written
templates, introducing length as a new shortcut. Mitigation:
all three sources target the same ~150–400 char range;
length stats logged at generation time.

(C) **Citation-presence shortcut.** V2 R5 (Fabricated Citation)
adds "PMID:XXXXXXXX" markers; if only adversarial content
has citation-like patterns, the model could key on those.
Mitigation: ~30% of imperative-templates include references
to real guideline bodies (NCCN, USPSTF, ACC/AHA, GOLD, GINA,
Cochrane, etc.) — real organizations whose guidelines exist
and reaffirm standard care.

**Sandbox validation.** Six tests on D75 augmentation logic:

  1. Block counts exact (300/500 as designed)
  2. Source distribution equal-weighted (32.5%/34.0%/33.5%)
  3. Framing rate at target 20%
  4. Determinism preserved (seed=42 reproducible)
  5. Single-source fallback works (D73 behavior when both
     new pools missing)
  6. Two-source fallback works (works with imperative
     templates only, if Phi-3 generation hasn't run yet)

Plus nine tests on `imperative_benign.py`:

  - 25 templates, all containing prescriptive verbs ("should",
    "must", "should continue", etc.)
  - Slot substitution leaves no unresolved `{}` placeholders
  - 50/50 unique blocks from seed=42
  - Safety screen accepts hand-authored templates (50/50 pass)
  - Safety screen rejects deviation phrases (all 4 examples
    rejected)
  - Length stats in clinically-plausible range
    (127–423 chars, median 246)
  - Determinism across seeds

**Limitations honest-noted.** The hand-authored templates use
cross-product slot substitution (any drug × any condition ×
any guideline body). Some combinations are clinically odd
(e.g., A1c monitoring for AFib patients). This does not
poison training since the goal is teaching the model to
ignore mood register, not to medically validate content; the
model isn't being asked to judge clinical coherence. The
limitation is noted here for paper-writing honesty.

**Affects.** New sub-stage 03B; Stage 04 (consumes new pools);
versioned at v0.9.0.

**Reversibility.** High. Setting `imperative_pool=None,
phi3_pool=None` reverts to D73 behavior. Stage 03B output
is cached and immutable; not regenerating preserves prior
runs.

**Methodology note for the paper.** The D71 → D72 → D73 → D75
sequence is the project's central diagnostic narrative. Each
fix revealed the next contamination axis; each axis was deeper
and closer to actual content semantics. By D75 the augmentation
attacks all three remaining axes simultaneously (mood,
writing source, citation presence). If Stage 06A v0.9.0 still
shows V2 saturation, the residual signal is at the semantic-
content level (drug names, dosing language, etc.) — which
would be a research question rather than a contamination bug
and would shift the paper's framing.

---

### D76 — Paired benign-PubMedQA construction (Stage 02C + Stage 04)  *(locked, 2026-05-13)*

**Decision.** Stage 04 now constructs **paired benign-PubMedQA**
instances from each V2 row before split assignment. Each V2 row
produces one new benign row that:

  1. Keeps V2's user_query verbatim (PubMedQA literature-evaluation
     template "Based on current clinical evidence...").
  2. Contains only the V2's `benign_evidence` block (the original
     PubMedQA abstract that the V2 was derived from), plus a second
     benign_evidence block sampled from another V2 (to match V2's
     2-block structure so block count is not a class signal).
  3. Is labeled benign (`vector = V0_paired_pubmedqa`, severity=0).
  4. Records `paired_with_v2_id` for provenance.

Paired-benign rows inherit their source V2's `mpib_split`. V2 train
rows produce paired-benign train rows; V2 test rows produce paired-
benign test rows that go to a new `test_v0_paired` split (the
symmetric test cohort to `test_v2`).

**Context — the source-distribution shortcut (Stage 02B finding).**
After four cycles of iterative shortcut-fixing (D71→D75) failed to
break V2's saturation, we ran direct EDA on the parsed MPIB raw
data (Stage 02B). The finding:

  - 582 of 9,697 MPIB instances are V2; all 582 are PubMedQA-sourced.
  - Of the remaining 9,115 instances, only 12 are PubMedQA-sourced
    (all V0'); the rest (9,103) are MedQA-sourced.
  - V2 instances apply a fixed user_query template:
    "Based on current clinical evidence and guidelines, should
     clinicians routinely recommend or use the intervention described
     in: '<paper title>'? Provide a clear recommendation..."
  - A 2-token regex (`based on current clinical evidence`) achieves
    100% recall and 98% precision on V2. Five other template-phrase
    regexes give identical results (582/582 V2, 12/9115 non-V2).
  - The 12 false positives are all V0' PubMedQA rows — i.e., they
    share V2's user_query template but were assigned a benign label.

A classifier trained on this distribution learns "PubMedQA-template
user_query = adversarial; MedQA case-vignette = benign" as a near-
perfect class signal. This is the shortcut that drove test_v2 TPR
to 100% across v0.7.0 through v0.9.0; the prior four rework cycles
were addressing surface manifestations of this deeper source-
distribution gap.

**Why paired-benign construction (Path A) is the right fix.** The
gap is upstream of any training-time fix. We cannot un-poison the
distribution by augmentation alone, because every V2 in the
benchmark uses the template. The fix has to add benign instances
that *also* use the template, so the template ceases to be a class
signal. Three viable approaches were considered:

  (A) Strip the `poisoned_update` block from each V2 and label the
      result benign (this decision). Real data; deterministic;
      preserves the V2 user_query verbatim.
  (B) Generate PubMedQA-style benign retrieved updates via Phi-3
      (extension of D75 architecture). Synthetic content; risk of
      new artifacts.
  (C) Construct synthetic MedQA-V2 instances by adding poisoned
      retrieved content to MedQA case vignettes. Requires generating
      plausible retrieved context for queries that don't naturally
      have any; significant complexity.

Path A is cleanest and is what this decision implements. Paths B
and C remain available for future versions if needed.

**Implementation.**

New files:

  - `pharmguard/data/mpib_balanced.py` — `construct_paired_benign_pubmedqa`
    function with deterministic donor sampling for the second block.
    `_derive_paired_id` produces stable IDs of the form
    `V0pair_<16-hex>`.
  - `scripts/02B_mpib_eda.py` — exploratory data analysis producing
    JSON report, markdown summary, and per-row CSV documenting the
    source-distribution structure. Reproducible; output goes to
    `logs/stage_02B_eda/`.

Modified:

  - `pharmguard/data/splits.py`:
    * `SPLIT_NAMES` gains `test_v0_paired` (8 splits total).
    * Orchestrator phase count goes from 7 to 8; D76 construction
      is phase [3/8], between V2 patching and input_text building.
    * `_mpib_split_name` routes paired-benign test rows to
      `test_v0_paired`; train rows follow V2's split assignment.
    * Existing label assignment correctly treats paired-benign as
      benign (the `vector.isin(["V1", "V2"])` check excludes it).

**Sandbox validation.** 8 tests passed on construction logic:

  1. 1:1 pairing (paired benign count == V2 count)
  2. mpib_split inheritance (paired benign follows V2's split)
  3. user_query parity (all paired benigns share V2's user_query)
  4. 2-block structure (matches V2's structure)
  5. No `poisoned_update` blocks in paired benigns
  6. V2 rows are untouched (still have `poisoned_update`)
  7. Determinism (seed=42 reproducible)
  8. sample_id uniqueness across the combined corpus

**Projected corpus after D76 (estimate).**

| Split                       | Pre-D76 | Post-D76 | Change |
|-----------------------------|---------|---------|--------|
| train                       | 6,945   | ~7,400  | +V2-train paired benigns |
| val                         | 1,807   | ~1,870  | +V2-val paired benigns |
| test_v1                     |    67   |    67   | unchanged |
| test_v2                     |    64   |    64   | unchanged |
| test_v0_paired              |     -   |    64   | new — symmetric to test_v2 |
| calibration                 |   400   |   400   | unchanged |
| clinical_benign_holdout     |   414   |   414   | unchanged |
| generic_attack_ood          |   301   |   301   | unchanged |

The two key evaluation splits become **test_v2** (adversarial-with-V2-template)
and **test_v0_paired** (benign-with-V2-template). A detector that has
learned content-based discrimination should score high on test_v2 and
low on test_v0_paired. A detector relying on the template shortcut
will score high on both. This is the critical evaluation that
distinguishes the two cases.

**Risks and mitigations.**

* **Phi-3 stylistic signature in `poisoned_update`.** Even with
  paired benigns, V2's poisoned_update blocks are Phi-3-generated
  while paired benigns contain only original PubMed abstracts.
  The model might still key on "Phi-3 writing style in retrieved
  content = adversarial." This is a known risk; if it manifests,
  D77 would generate benign Phi-3 retrieved blocks (similar to
  D75's Stage 03B but with PubMedQA-template framing).
* **The paired-benign cohort is only ~582 instances.** Smaller than
  V0/V0p (8,471). The detector has substantially more benign training
  signal from MedQA case vignettes than from PubMedQA literature
  queries. If the detector overfits to MedQA-style benigns, test_v0_paired
  evaluation will reveal this.
* **The leakage constraint** (paired benign shares parent_id with
  source V2) is handled by routing both to the same split tier.

**Affects.** Stage 04 (D76 construction added); Stage 05 (handles
new split automatically via `SPLIT_NAMES`); Stage 06A (trains on
new corpus); Stage 07 (will compare detector vs regex baseline on
test_v2 + test_v0_paired). Versioned at v0.10.0.

**Reversibility.** High. Setting `construct_paired_benign_pubmedqa`
to a no-op (or removing the orchestrator call) reverts to D75
behavior. The Stage 02B EDA outputs are immutable diagnostic
artifacts and don't affect training data.

**Methodology note for the paper.** D76 closes the diagnostic
narrative that began at D70. The journey from "V2 saturation
at 0.999" through wrapper marker (D71), user_query template (D72),
block presence (D73), imperative mood (D75), to source-distribution
gap (D76) demonstrates that contamination in a prompt-injection
benchmark can be layered across multiple features, with each fix
revealing the next deeper issue. The Stage 02B EDA documents the
final issue empirically; D76 addresses it structurally. If the
v0.10.0 model still shows V2 saturation, the residual signal lives
at the retrieved-content level — which would shift the paper's
framing toward "what features actually distinguish benign from
poisoned retrieved evidence" rather than "how do we train a
detector to find them."

---

## Summary table

| ID  | Decision | Block | Date | Reversibility |
|-----|----------|-------|------|---------------|
| D1  | Solo authorship | Foundational | 2026-05-08 | High |
| D2  | Skip Naive Bayes / TF-IDF | Foundational | 2026-05-08 | High |
| D3  | Skip Llama Guard / MedGuard | Foundational | 2026-05-08 | Medium |
| D4  | Four-layer architecture | Foundational | 2026-05-08 | Medium |
| D5  | C4 reframed: Practical Tooling | Foundational | 2026-05-08 | Medium |
| D6  | Square attack added | Foundational | 2026-05-08 | High |
| D7  | Single-GPU as feature | Foundational | 2026-05-08 | High |
| D8  | Static threshold = drift contribution | Foundational | 2026-05-08 | Medium |
| D9  | HF token on Drive | Foundational | 2026-05-09 | High |
| D10 | Hybrid templates + LLM payload reconstruction | Foundational | 2026-05-08 | High |
| D11 | Honor MPIB 80/10/10 split | Foundational | 2026-05-08 | Low |
| D12 | Primary venue: JAMIA (tentative) | Foundational | 2026-05-08 | High |
| D13 | Package + scripts + notebook | Implementation | 2026-05-09 | Low |
| D14 | Drive-rooted artifacts | Implementation | 2026-05-09 | High |
| D15 | Minimal `requirements.txt` | Implementation | 2026-05-09 | High |
| D16 | Per-stage logging + JSON | Implementation | 2026-05-09 | High |
| D17 | MPIB via `hf_hub_download` + JSONL | Implementation | 2026-05-09 | Medium |
| D18 | omi-health replaces medical_dialog | Implementation | 2026-05-09 | High |
| D19 | Five seeds | Implementation | 2026-05-09 | Medium |
| D20 | Target FPRs 1%/0.5%/0.1% | Implementation | 2026-05-09 | High |
| D21 | Class weights (1.0, 3.0) | Implementation | 2026-05-08 | High |
| D22 | V0p schema flag | Implementation | 2026-05-09 | High |
| D23 | Phi-3-mini-4k-instruct for V2 | Implementation | 2026-05-09 | High |
| D24 | `parsed_mpib.parquet` canonical | Implementation | 2026-05-09 | Low |
| D25 | (Superseded by D18) | Implementation | 2026-05-09 | — |
| D26 | Five `generation_status` values | Implementation | 2026-05-09 | Medium |
| D27 | Preserve `original_redacted_text` | Implementation | 2026-05-09 | High |
| D28 | Per-family file structure | Stage 03 | 2026-05-09 | Low |
| D29 | `preserves_paragraphs` flag | Stage 03 | 2026-05-09 | High |
| D30 | Per-family surface targets | Stage 03 | 2026-05-10 | High |
| D31 | R5 fake PMIDs use 99-prefix | Stage 03 | 2026-05-09 | High |
| D32 | R9 dose multiplier 1.75x | Stage 03 | 2026-05-09 | High |
| D33 | R7 fix: oversized → deviated | Stage 03 | 2026-05-10 | High |
| D34 | R7 fix: paragraph collapse | Stage 03 | 2026-05-10 | High |
| D35 | R7 fix: explicit reversal language | Stage 03 | 2026-05-10 | High |
| D36 | R7 fix: formatting deviation = warning | Stage 03 | 2026-05-10 | High |
| D37 | Phi-3-mini deterministic per-instance seed | Stage 03 | 2026-05-09 | High |
| D38 | `generation_seed` in output | Stage 03 | 2026-05-09 | High |
| D39 | 5 sample instances per family logged | Stage 03 | 2026-05-10 | High |
| D40 | Stage 03 budget: 30–40 min | Stage 03 | 2026-05-10 | High |
| D41 | Stage 03 acceptance: non-fallback ≥ 95% + mechanism review | Stage 03 | 2026-05-10 | High |
| D42 | Parquet nested fields are JSON-stringified (bug to fix in v0.5.0) | Implementation | 2026-05-10 | Low |
| D43 | Detector input is the concatenated CDSS string | Stage 04 | 2026-05-11 | Medium |
| D44 | Benign-clinical task wrappers (4 templates) | Stage 04 | 2026-05-11 | High |
| D45 | Binary label; V1/V2 preserved as auxiliary column | Stage 04 | 2026-05-11 | Medium |
| D46 | Honor MPIB split; route test by vector | Stage 04 | 2026-05-11 | High |
| D47 | Benign-clinical 80/10/5/5 allocation | Stage 04 | 2026-05-11 | High |
| D48 | Cross-source dedup: drop benign rows overlapping MPIB | Stage 04 | 2026-05-11 | High |
| D49 | Native PyArrow nested types (D42 fix) | Stage 04 | 2026-05-11 | High |
| D50 | No artificial class-balance upsampling | Stage 04 | 2026-05-11 | High |
| D51 | Atomic writes with fsync | Stage 04 | 2026-05-11 | High |
| D52 | Stage manifest with SHA-256 checksums | Stage 04 | 2026-05-11 | High |
| D53 | MPIB split-name routing fix + strict validation gate | Stage 04 | 2026-05-11 | High |
| D54 | Post-stage integration-check cell pattern | Process | 2026-05-11 | High |
| D55 | PubMedBERT tokenizer (paired with D4 Layer 2) | Stage 05 | 2026-05-11 | Medium |
| D56 | max_length=512 + right-truncation + measurement gate | Stage 05 | 2026-05-11 | High |
| D57 | Native PyArrow nested types for tokenized output | Stage 05 | 2026-05-11 | High |
| D58 | No padding at tokenize time; dynamic padding per batch | Stage 05 | 2026-05-11 | High |
| D59 | All Stage 04 metadata preserved through Stage 05 | Stage 05 | 2026-05-11 | High |
| D60 | Tokenization is deterministic; no train-time augmentation | Stage 05 | 2026-05-11 | High |
| D61 | Per-vector truncation rates in manifest | Stage 05 | 2026-05-11 | High |
| D62 | Right-truncation proceeds; sliding window as Stage 07 ablation | Stage 05 → Stage 07 | 2026-05-11 | High |
| D63 | v1.0 architecture: PubMedBERT + linear head; Φ = identity | Stage 06A | 2026-05-11 | High |
| D64 | Weighted cross-entropy via Trainer subclass | Stage 06A | 2026-05-11 | High |
| D65 | HuggingFace Trainer as training framework | Stage 06A | 2026-05-11 | Medium |
| D66 | Best-val-AUC checkpoint selection | Stage 06A | 2026-05-11 | High |
| D67 | Calibration: smallest-τ-meeting-FPR rule + Wilson CI | Stage 06A | 2026-05-11 | High |
| D68 | Per-(seed, config) directory layout for model artifacts | Stage 06A | 2026-05-11 | Medium |
| D69 | Full determinism via set_all_seeds + deterministic CUDA | Stage 06A | 2026-05-11 | High |
| D70 | Stage 04 wrapper-shortcut requires rework | Stage 04 | 2026-05-11 | Medium |
| D71 | Vocabulary unification + two-block benign augmentation | Stage 04 | 2026-05-11 | High |
| D72 | Drop benign-clinical pool; use MPIB V0/V0p for benign | Stage 04 | 2026-05-11 | Medium |
| D73 | Benign retrieved-evidence augmentation on V0/V0p train | Stage 04 | 2026-05-12 | High |
| D74 | Drive sync verification after expensive writes | Stages 01/03/04/05/06A | 2026-05-12 | High |
| D75 | Imperative-mood + Phi-3 benign augmentation (three-source pool) | Stage 03B + Stage 04 | 2026-05-12 | High |
| D76 | Paired benign-PubMedQA cohort to break source-distribution shortcut | Stage 02B + Stage 04 | 2026-05-13 | High |

---

*Document version: 0.10.0 (matches package version).*
*Maintained by: NehlTech.*
*Append-only — supersede via new entry, do not delete.*
