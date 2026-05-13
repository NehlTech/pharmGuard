# PharmGuard

> A production-grade indirect prompt injection detector for clinical decision support systems.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-research--in--progress-orange.svg)](#status)

PharmGuard is a four-layer detector for indirect prompt injection (IPI)
attacks in retrieval-augmented clinical AI systems. It is the first
detector explicitly designed for the clinical operating regime, where
the base rate of attacks is low and the cost of a false positive
(blocked legitimate clinical query) is high.

## What problem does this solve?

Hospitals are deploying LLM-based clinical decision support (CDSS)
that retrieves drug references, treatment guidelines, and recent
literature in real time. An adversary who can place malicious text
in any retrievable document can hijack the assistant — recommending
unsafe doses, downplaying emergent symptoms, or fabricating evidence.

Existing prompt-injection detectors were built and validated on
consumer chatbot data. When pointed at clinical text, they fire on
legitimate medical communication (which is full of imperatives like
*"administer 5 mg"* and *"do not exceed"*). At realistic deployment
base rates, their false-positive rate makes them unusable.

PharmGuard closes this gap with three architectural decisions:

1. **Adversarial canonicalization** of every input (NFKC normalization,
   zero-width stripping, Base64 detection) so encoded payloads cannot
   slip past the detector unprocessed.
2. **A biomedical encoder** (PubMedBERT) so clinical vocabulary is
   represented natively, not flagged as suspicious imperatives.
3. **FPR-calibrated decision thresholds** computed on a held-out
   clinical calibration set, so the detector operates at deployment-
   realistic false-positive budgets (β ≤ 10⁻³).

## Status

Research in progress. This repository tracks pipeline development
stage by stage. Each commit represents a complete, working subset of
the pipeline; nothing is a stub.

| Stage | Description | Status |
|-------|-------------|--------|
| 00 | Environment setup + ephemeral-data rescue | ✅ |
| 01 | Pharmaceutical data acquisition | ✅ |
| 02 | MPIB acquisition + EDA | ✅ |
| 03 | Synthetic V2 payload reconstruction (R1–R10) | ✅ |
| 04 | Seven-variant dataset construction | ✅ |
| 05 | PubMedBERT tokenization (right-truncation + measurement gate) | ✅ |
| 06 | Multi-seed PharmGuard training | 🟡 06A scaffold built |
| 07 | Off-the-shelf detector evaluation | ⏳ |
| 08 | Adaptive attacks + Δ_rob computation | ⏳ |
| 09 | Cross-detector difficulty analysis | ⏳ |
| 10 | Drift-aware recalibration simulation | ⏳ |
| 11 | Results aggregation | ⏳ |

## Quick start (Colab)

The pipeline is designed to run on Google Colab Pro with a single L4
GPU.

### One-time setup

1. **Create a Hugging Face account** at <https://huggingface.co>.
2. **Accept the MPIB conditions:** visit
   <https://huggingface.co/datasets/jhlee0619/mpib> and click
   "Agree and access repository."
3. **Generate a Read token** at
   <https://huggingface.co/settings/tokens>.
4. **Open the runner notebook** in Colab:
   `notebooks/colab_runner.ipynb`. The first cells handle Drive
   mounting, repo cloning, and token persistence.

### Running stages

The runner notebook has one cell per stage. Re-run individual cells
to re-run individual stages; everything else stays intact on Drive.

You can also invoke any stage directly from a terminal cell:

```bash
!cd /content/pharmguard && python scripts/00_setup.py
!cd /content/pharmguard && python scripts/01_acquire_data.py
!cd /content/pharmguard && python scripts/02_acquire_mpib.py
```

## Project layout

```
pharmGuard/
├── README.md                   This file
├── LICENSE                     MIT
├── requirements.txt            Pip-installable optional packages
│
├── pharmguard/                 The Python package
│   ├── __init__.py
│   ├── config.py               PharmGuardConfig (frozen dataclass)
│   ├── paths.py                ProjectPaths (Drive-rooted on Colab)
│   ├── env.py                  Runtime environment check
│   ├── seeds.py                set_all_seeds() for reproducibility
│   ├── logging_utils.py        Per-stage file logger
│   └── data/
│       ├── benign.py           Clinical benign acquisition
│       ├── attacks.py          Generic OOD attack acquisition
│       ├── mpib.py             MPIB pull, parse, EDA
│       └── reconstruction/     V2 payload reconstruction
│           ├── core.py         Phi-3-mini orchestration + QC
│           ├── surface_features.py
│           └── templates/      One file per rule family
│               ├── base.py     TemplateStrategy abstract base
│               ├── r1_exaggeration.py
│               ├── r2_masking.py
│               ├── r3_generalization.py
│               ├── r4_outdated.py
│               ├── r5_citation.py
│               ├── r6_warning_demotion.py
│               ├── r7_editorial.py
│               ├── r8_triage_downplay.py
│               ├── r9_dose_tweak.py
│               └── r10_provenance.py
│
├── scripts/                    Runnable pipeline stages
│   ├── 00_setup.py
│   ├── 01_acquire_data.py
│   ├── 02_acquire_mpib.py
│   ├── 03_reconstruct_payloads.py
│   ├── 04_construct_splits.py
│   ├── 05_tokenize.py
│   └── 06A_train_single_seed.py
│
├── notebooks/
│   └── colab_runner.ipynb      Single Colab entry point
│
└── docs/                        Living methodology documentation
    ├── methodology.md          Per-stage methodology writeup
    ├── decisions.md            Numbered decision register (D1+)
    └── results_log.md          Quantitative findings per stage
```

The `docs/` directory is maintained continuously throughout the
project rather than retrofitted at the end. It holds the raw
material for the paper's Methods and Results sections, captures
locked decisions with their rationale, and records every
quantitative finding as it is observed. See
[`docs/methodology.md`](docs/methodology.md) for the entry point.

## Design principles

* **Drive-rooted everything on Colab.** All artifacts (data, logs,
  results, checkpoints) live under `/content/drive/MyDrive/pharmguard/`.

* **Stages are independent scripts, not notebook cells.** Notebook
  cells in the runner are one-line invocations of the underlying
  script.

* **No version pinning of the host environment.** We work with
  whatever Colab ships. Only `bert-score`, `imbalanced-learn`,
  `langdetect` get installed.

* **Self-healing.** Stage 00 includes a rescue routine that detects
  ephemeral data left behind by prior broken runs and moves it to
  Drive.

## Citation

This work is research in progress.

## Acknowledgements

* **MPIB** (Lee et al., 2026) — clinical IPI evaluation corpus.
* **PromptShield** (Jacob et al., CODASPY 2025) — deployment-FPR
  calibration philosophy informing PharmGuard's Layer 3.

## License

MIT (see [LICENSE](LICENSE)).
