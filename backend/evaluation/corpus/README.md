# Synthetic Test Corpus Fixtures

This directory contains version 1.0 synthetic case bundles (`*_case.json`) and corresponding evaluation answer keys (`*_answer_key.json`).

> **Safety & Scope Boundary:** All records in this corpus are strictly fictional and synthetic. They use reserved IP addresses (RFC 5737 / RFC 3849), synthetic wallets, and invented personas. No live dark-web sources, real wallets, or personal identities are included or accessed. Answer keys reside solely in this folder and are never loaded or exposed by the application, API, or dashboard.

---

## Corpus Overview

| Case ID | Title | Synthetic Scenario | Key Evidence & Adversarial Decoys |
|---|---|---|---|
| `CASE-2026-002` | **Hollowreed** | Counterfeit ticket vendor migrates across 3 marketplaces (Tallow Bazaar, Quillmarket, Dunmere Exchange). | • **Positives:** PGP key FP3 reuse, wallet W3 reuse, sign-off phrase consistency, status-page certificate CS-1001 matching.<br>• **Decoys:** Unverified self-claim (`saltmarsh_official`), shared exchange hot wallet (high-volume co-activity), boilerplate template text. |
| `CASE-2026-003` | **Driftwood** | Fake course certificate vendor across 3 marketplaces (Tidepool, Rooklane, Saltgrass). | • **Positives:** Shared PGP-style key between `wavecutter` and `wave_cutter_`; language-mix style overlap to `reef_ghost`.<br>• **Decoys:** Activity-pattern overlap (`plainsong` ↔ `wavecutter_mirror`); shared template boilerplate. |
| `CASE-2026-004` | **Copperline** | Counterfeit event pass vendors moving funds through cryptocurrency payment flows (Vellum and Ashlar). | • **Positives:** Multi-input wallet clustering (`SYNTH-W5` ↔ `SYNTH-W6` joint transaction inputs); account-to-wallet correlation.<br>• **Decoys:** Shared posting window between unrelated vendors (`copperwire` ↔ `lathe9`). |
| `CASE-2026-005` | **Glasshouse** | Service and infrastructure correlation across marketplaces, forums, and shops. | • **Positives:** Certificate transparency serial CS-2001 match; unique host fingerprint path connecting services.<br>• **Decoys:** Shared `/24` subnet proximity (contextual, not attribution); generic banner overlap. |
| `CASE-2026-006` | **Marrowbone** | Vendor handle changing hands across marketplaces (Orchard Row → Lamplight). | • **Positives:** PGP key FP7 reuse linking original `marrowbone` to `bonewhistle` and `ashen_bell`.<br>• **Decoys:** Activity schedule similarity (`ashen_bell` ↔ `salt_candle`). |
| `CASE-2026-007` | **Lowtide** | Unreliable tips and rumours vs. archived marketplace records. | • **Positives:** Shared PGP key between `lowtide_trader` and `norrow`.<br>• **Decoys:** Unverified forum tips and rumours discounted; weak style similarity (`tide_low` ↔ `norrow`). |

---

## Running Corpus Evaluation

The evaluation suite executes each bundle in an isolated, disposable SQLite database, leaving the active workspace database (`data/darklens.sqlite3`) completely untouched.

### Run All Cases

From the repository root with `.venv` active:

```bash
python -m backend.evaluation.evaluate_corpus
```

Or target a specific directory:

```bash
python -m backend.evaluation.evaluate_corpus backend/evaluation/corpus
```

### Run an Individual Bundle

```bash
python -m backend.evaluation.evaluate_import_bundle \
    backend/evaluation/corpus/CASE-2026-002_case.json \
    backend/evaluation/corpus/CASE-2026-002_answer_key.json
```

---

## Metrics & Verification Rules

1. **Answer-Key Checks**: Explicit checks defined in each `*_answer_key.json` validating that candidate links meet expected score thresholds (`>=0.85` for strong leads, `<=0.45` for weak leads) and that decoys do not exceed configured ceilings (`<0.30` or `<0.50`).
2. **Positive-Pair Recall**: Ratio of true persona/identity pairs successfully surfaced by analysis over total expected positive pairs.
3. **Candidate Precision (@ 0.30 threshold)**: Proportion of surfaced leads with score $\ge 0.30$ that correspond to confirmed answer-key relationships rather than false decoys.
4. **No Auto-Acceptance Rule**: 100% of candidate links must be generated in `unreviewed` or `needs_more_evidence` state. Zero links may be automatically accepted.
5. **Evidence Provenance Rule**: 100% of candidate links must cite one or more valid, existing evidence IDs from the imported bundle. Unsupported links fail the evaluation.
6. **Score Bounding Rule**: 100% of candidate link scores must fall strictly within the unit interval $[0.0, 1.0]$.
