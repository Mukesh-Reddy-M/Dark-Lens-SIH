# Synthetic Holdout Evaluation Suite

This directory contains separate version 1.0 synthetic holdout case bundles (`*_case.json`) and evaluation answer keys (`*_answer_key.json`).

> **Safety & Scope Boundary:** All records in this holdout suite are strictly synthetic and fictional. They use reserved IP addresses (RFC 5737 / RFC 3849), synthetic cryptocurrency addresses, and invented entity handles. No live dark-web sources, real wallets, or personal identities are included or accessed. Answer keys reside solely in this evaluation folder and are never loaded, parsed, or exposed by the application, API, or dashboard.

---

## Holdout Purpose

While the regression corpus (`backend/evaluation/corpus/`) verifies that known cases retain expected lead derivation and scoring stability, this holdout suite verifies that the heuristics generalize across unseen synthetic scenarios without overtuning:
- Testing multi-stage vendor migration with unverified forum rumor decoys (`HOLDOUT-2026-001`).
- Testing infrastructure migration with certificate transparency matching and common CDN proxy decoys (`HOLDOUT-2026-002`).
- Testing data broker identity clustering with bilingual writing markers and shared exchange deposit pooling decoys (`HOLDOUT-2026-003`).
- Testing duplicate mirror reports, explicit downstream derivations, public denial contradictions, and concurrent activity review context (`HOLDOUT-2026-004`).

---

## Holdout Cases

| Case ID | Title | Scenario | Key Features & Adversarial Decoys |
|---|---|---|---|
| `HOLDOUT-2026-001` | **Foxglove** | Botanical vendor migrates across Bramble Bazaar, Briar Road, and Heather Forum. | • **Positives:** PGP key `FP81`, wallet `W81`, sign-off phrase consistency, SSL certificate `CS-4401` match.<br>• **Decoys:** Unverified forum rumor (`foxglove_imposter`), shared exchange pooling wallet (`briar_buyer_88`), concurrent writing style overlap (`belladonna_apothecary` ↔ `nightshade_lab`). |
| `HOLDOUT-2026-002` | **Blackthorn** | Threat syndicate running a panel migrates across hosting providers and forums. | • **Positives:** PGP key `FP92`, wallet `W92`, double-space sign-off, certificate `CS-9902` match to host `198.51.100.77`.<br>• **Decoys:** Unverified chat impersonation claim (`thorn_admin_imposter`), common CDN reverse proxy (`198.51.100.99`), weekday morning schedule overlap (`shadow_broker_99` ↔ `sloe_scout`). |
| `HOLDOUT-2026-003` | **Osprey** | Broker of telemetry and credential dumps operates across three leak boards. | • **Positives:** PGP key `FP73`, wallet `W73`, bilingual phrase quirks, certificate `CS-7711` match to host `198.51.100.63`.<br>• **Decoys:** Copycat handle rumor (`osprey_fan`), shared exchange pooling deposit (`harbor_relay`), concurrent rare-word overlap (`gull_watcher` ↔ `cormorant_scout`). |
| `HOLDOUT-2026-004` | **Nightshade** | Marketplace vendor with mirror sites, downstream forum reposts, and counter-evidence. | • **Positives:** PGP key `FP55`, wallet `W55`, SSL certificate `CS-5501` match.<br>• **Decoys & Contradictions:** Exact mirror site (`OBS-003` grouped to avoid corroboration inflation), downstream repost (`OBS-005` tracked as derived clue), explicit public denial contradiction (`OBS-006` flagged as confirmed contradiction), and concurrent posting activity (`OBS-008` surfaced as review context inconsistency). |

---

## Running Holdout Evaluation

The evaluation suite executes each holdout bundle in an isolated, temporary SQLite database. The working database (`data/darklens.sqlite3`) is untouched.

### Run Holdout Cases Only

```bash
python -m backend.evaluation.evaluate_corpus --holdout
# or
python -m backend.evaluation.evaluate_corpus backend/evaluation/holdout
```

### Run All Cases (Corpus + Holdout)

```bash
python -m backend.evaluation.evaluate_corpus --all
```
