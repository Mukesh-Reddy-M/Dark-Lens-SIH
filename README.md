# DarkLens - SIH 2026 Project

**DarkLens: Dark Web Threat Actor Attribution Platform** is a research prototype for organizing synthetic threat-actor clues into an explainable, analyst-reviewed case graph. It is being developed for Smart India Hackathon 2026 Problem Statement 26151.

> **Prototype boundary:** The current app uses fictional, synthetic records only. It does not connect to Tor, crawl marketplaces, scan hosts, or identify real people. Candidate links are investigative leads, not proof of identity.

## SIH submission details

| Field | Submitted detail |
| --- | --- |
| Hackathon | Smart India Hackathon 2026 |
| Problem statement ID | SIH26151 (26151 in the submitted template) |
| Problem statement title | Dark web threat actor de-anonymization |
| Theme / technology bucket | Blockchain & Cybersecurity |
| Category | Software |
| SIH team ID | 148418 |
| SIH team name | Ctrl Alt Defeat |
| Submitted idea ID | 203630 |
| Idea title | DarkLens: Dark Web Threat Actor Attribution Platform |
| Repository | [Mukesh-Reddy-M/Dark-Lens-SIH](https://github.com/Mukesh-Reddy-M/Dark-Lens-SIH) |

### Team and responsibilities

The submitted material confirms the SIH team ID and team name. It does not include the individual member roster, so names and assigned responsibilities should be copied from the official SIH team portal before the final presentation.

| Team member | SIH role / project responsibility |
| --- | --- |
| Mukesh Reddy (`Mukesh-Reddy-M`) | Repository owner / point of contact; confirm official SIH role and contribution list |
| Remaining registered members | Add official names and agreed workstream responsibilities |

Suggested workstreams to assign across the registered team: frontend and interaction design; API and data model; synthetic case/evaluation; graph and evidence analysis; presentation and documentation. These are planning roles, not claims about current individual contributions.

## Problem and proposed solution

Threat actors may reuse handles, PGP keys, cryptocurrency wallets, infrastructure, or writing patterns across online services. Investigators can spend significant time joining these scattered records, and a weak match can create a false attribution.

DarkLens is intended to put those clues into a single relationship graph. Each proposed relationship should show its supporting evidence, source reliability, review priority, and review status. An analyst remains responsible for accepting or rejecting a lead.

### Proposed analysis modules

1. **Infrastructure correlation** - compare archived service indicators such as certificates, banners, and exposed-page details with permitted public records to suggest infrastructure relationships.
2. **Identifier and actor graph** - connect synthetic handles, PGP keys, wallets, services, and personas, with evidence attached to each proposed edge.
3. **Persona-link analysis** - compare writing and behavioural clues, such as stylometric features and activity windows, to surface possible migration or rebranding leads.

The SIH proposal also describes an analyst dashboard, timeline queries, source reliability scoring, scheduled collection, and exports. Automated collection and live sources are outside the current prototype scope.

## Progress so far

### Working in the current prototype

- **Dark dashboard:** React + Vite interface with responsive layout, synthetic-data indicator, case overview, graph, evidence detail, and timeline.
- **Local API:** FastAPI service supplies case, evidence, timeline, review, and export data.
- **Persistent case store:** SQLite stores the case records and analyst review audit events.
- **Nightjar synthetic case:** fixed fixture with **22 entities, 24 observations, 6 synthetic sources, and 6 candidate links**.
- **Relationship graph:** SVG graph built from case links and evidence identifier associations. Nodes can be selected and dragged; graph controls include layout selection, zoom, recenter, and fullscreen.
- **Evidence panel:** selected-record details, associated evidence, source reliability summary, and candidate-link review controls.
- **Review queue:** dedicated sidebar view of all six candidate links, filterable by review state, with endpoint labels, evidence provenance, signal breakdowns, caution notes, and Accept, Reject, or More evidence actions.
- **Analyst review:** decisions update a link through the API, write an audit event, and reload the case. No link is automatically accepted.
- **Audit history:** a second Review Queue view lists recorded decisions with candidate ID, previous/new state, analyst label, timestamp, and note.
- **Synthetic analysis:** extracts typed indicators from entity labels, supported attributes, observation details, and summaries; connects explicit entity references; and can surface bounded, evidence-backed paths through identifiers or infrastructure. Generic quoted style markers, explicit posting/activity schedules, and (when supplied) raw sample text can add weak leads capped at 45%. Raw text uses local character n-gram and function-word features and requires multiple sufficiently long samples. Candidates include source/evidence support and cautions; scores are review priorities, not identity probabilities.
- **Timeline:** 24 chronological synthetic observations with range filtering. Hovering or selecting an event opens an explanation panel with the observation summary, plain-language interpretation, source and reliability, evidence confidence, and any candidate link that uses it.
- **Navigation and search:** sidebar navigation scrolls to case sections or opens Review Queue, Reports, Saved Searches, and Settings panels. Entity search selects a matching record in the graph.
- **JSON case import & preview:** preview and import a validated version 1.0 synthetic bundle from the case selector. The API validates structure, size limits, IDs, timestamps, source/entity references, and detects existing case IDs via an in-memory preview before saving. Imports never overwrite existing cases silently (returns 409 Conflict). Reused record IDs are namespaced for the case, with references updated. Links are never accepted automatically. A downloadable example is included at [`backend/fixtures/case_bundle_v1.template.json`](backend/fixtures/case_bundle_v1.template.json).
- **Strict case isolation:** switching cases or reloading cleanly scopes the relationship graph, evidence details, timeline, review queue, analysis preview, and exports exclusively to that case's records without cross-case contamination or stale Nightjar fallbacks.
- **Traceable candidate links:** candidate leads display complete inference paths (`path_entity_ids`), supporting observations, source reliability, confidence factors, and caution advisories in both the Review Queue and Evidence Panel. Evidence associations remain distinct from attribution candidates, and scores are review priorities, not identity probabilities.
- **Evidence provenance & quality scoring:** every signal supporting a candidate link exposes its exact observation ID, source, source reliability rating, observation confidence, match strength, quality weight, timestamp, and contribution breakdown.
- **Duplicate & dependent evidence handling:** automatically detects exact duplicate observations (same entity, source, and normalized content) and clues with explicit shared provenance (e.g. `mirror_of`, `derived_from`). Grouped duplicates are discounted in scoring to avoid false corroboration inflation, while remaining individually visible in the dossier with grouping reasons.
- **Counter-evidence & conflict detection:** surfaces observations that weaken or contradict a proposed link beside supporting evidence. Differentiates confirmed contradictions (explicit denials, unproven impersonations) from review context inconsistencies (concurrency windows, shared hosting).
- **Candidate evidence dossier:** comprehensive dossiers embedded directly into the candidate detail, review queue, and exported Markdown/JSON reports, covering supporting evidence, counter-evidence, source independence ratings, inference paths, weak/missing evidence, and cautions.
- **Analyst decision protection & idempotence:** analysis reruns are idempotent—no duplicate links are created, dossiers refresh cleanly, and analyst decisions (accepted, rejected, needs more evidence), notes, and audit events are strictly preserved.
- **Corpus & holdout evaluation suites:** 6-case regression corpus (`backend/evaluation/corpus/`) and separate 4-case synthetic holdout suite (`backend/evaluation/holdout/`) evaluating generalization on unseen scenarios. All answer keys remain strictly evaluator-only and are never loaded by the API.
- **Hollowreed evaluation fixture:** [`backend/fixtures/hollowreed_case.json`](backend/fixtures/hollowreed_case.json) is the submitted fictional case with the required synthetic mode added. The answer key remains outside the app database and is used only for evaluation.
- **Multiple cases:** select imported cases from the case menu; graph, timeline, review queue, analysis, and exports follow the active case.
- **Reports and exports:** generated Markdown case report with link explanations, evidence provenance, review states, cautions, and audit history; full-case JSON and CSV downloads for entities, evidence, links, and audit events.
- **Saved searches:** stored in browser local storage on the current device.
- **Graph preference:** Settings can show or hide evidence-derived associations.

### Nightjar case outline

The case is intentionally fictional. Its synthetic clues demonstrate both stronger cross-identifier links and weaker lookalike or generic-text decoys:

| Candidate | Illustrative relationship | Case interpretation |
| --- | --- | --- |
| L1 | `mothlight` and `m0thl1ght` | Synthetic PGP, wallet, and sign-off clues reinforce a possible same-operator lead. Analyst review is still required. |
| L2 | Lantern Row service and a synthetic host record | Certificate and reserved example-IP matches demonstrate infrastructure correlation. |
| L3 | `pale_heron` and an inferred persona | Writing, activity-time, and timing clues suggest a possible migration, but there is no shared identifier; the score is capped low. |
| D1 | `coldfinch` and `cold_finch` | Handle resemblance only; included as a weak decoy. |
| D2 | `ashwren` and `mothlight` | Generic public boilerplate only; included as a weak decoy. |
| D3 | Paperwasp and Gravel Market services | Generic banner similarity while certificate and IP records differ; included as a weak decoy. |

The fixture uses synthetic names, addresses, certificates, identifiers, and marketplace records. Values such as `198.51.100.23` and `203.0.113.40` are documentation-only example addresses.

## Current architecture

```text
React + Vite dashboard
        │ HTTP / JSON
        ▼
FastAPI local service
        │ SQL
        ▼
SQLite case database  ◄── fixed Nightjar JSON fixture
```

| Layer | Current implementation | Notes |
| --- | --- | --- |
| Frontend | React, Vite, CSS, Framer Motion, SVG | Search, graph, evidence, timeline, review and export controls. |
| API | Python, FastAPI, Uvicorn | Runs locally on port 8001 by default. |
| Persistence | SQLite | Default database path is `data/darklens.sqlite3`; can be changed with `DARKLENS_DB_PATH`. |
| Case data | `backend/fixtures/nightjar_seed.json` | Deterministic synthetic seed data. |
| Scoring | Transparent independent-signal combination | Each signal contributes match strength × source reliability; behavioural-only leads are capped at 45%. These are review scores, not calibrated probabilities. |
| Evaluation | `backend/evaluation/evaluate_case.py` plus synthetic edge fixtures | Checks candidate links, audit requirements, exact-match positives, misleading-match negatives, and weak activity-only leads; this is not real-world model validation. |

The current build does **not** include PostgreSQL, Neo4j, OpenSearch, live collectors, an autonomous scheduler, a trained ML model, or an LLM. Analysis is deterministic and local: typed indicators, explicit references, bounded graph paths, schedule overlap, reported style markers, and optional character n-gram/function-word similarity when a bundle includes multiple raw writing samples. The raw-text feature is an untrained similarity heuristic, not author identification; it requires broader labelled evaluation before its usefulness can be assessed.

## API overview

The local API reference is available at `http://127.0.0.1:8001/docs` while the backend is running.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service health and synthetic-data indicator. |
| `GET` | `/api/cases` | List local cases. |
| `POST` | `/api/cases/import` | Validate and import a version 1.0 synthetic JSON bundle; generates reviewable candidate links. |
| `GET` | `/api/cases/{case_id}` | Fetch case, entities, sources, evidence, links, and audit events for the history view. |
| `GET` | `/api/cases/{case_id}/timeline` | Fetch observations in chronological order. |
| `GET` | `/api/cases/{case_id}/analysis` | Read-only exact-value match preview for a synthetic case; does not persist suggestions. |
| `POST` | `/api/cases/{case_id}/analysis` | Generate missing synthetic leads and add them to the review queue without changing existing analyst decisions. |
| `PATCH` | `/api/links/{link_id}/review` | Set `accepted`, `rejected`, `needs_more_evidence`, or `unreviewed`; writes an audit event. |
| `GET` | `/api/cases/{case_id}/export.json` | Download a full case JSON export. |
| `GET` | `/api/cases/{case_id}/report.md` | Download a human-readable case report with evidence and audit history. |
| `GET` | `/api/cases/{case_id}/export.csv` with `kind=entities`, `kind=evidence`, `kind=links`, or `kind=audit` | Download a selected record collection as CSV. |

### JSON import format (version 1.0)

Use the included [`backend/fixtures/case_bundle_v1.template.json`](backend/fixtures/case_bundle_v1.template.json) example. Required top-level fields are `schema_version: "1.0"`, `data_mode: "synthetic"`, `case`, `sources`, `entities`, and `observations`. A case requires a title; its ID is optional and will be generated if omitted. Sources require unique IDs, a name, a source type, and reliability from 0 to 1. Entities require unique IDs, an allowed type, and a display label; optional attributes must be JSON objects. Observations require unique IDs (or let the importer generate them), a source ID, optional entity ID, timezone-qualified ISO 8601 `observed_at`, evidence type, summary, confidence from 0 to 1, and optional JSON-object details. References must point to records in the same bundle.

Bundles are limited to 5 MB, 100 sources, 500 entities, and 2,000 observations. IDs must be unique across the local workspace. Do not supply candidate `links`: DarkLens derives those from the observations so imported claims cannot self-assert their own attribution. The current prototype rejects non-synthetic bundles.

## Run locally

Requirements: Node.js/npm and Python 3.9 or later.

### Canonical setup: repository root

All commands should be run from the **repository root** (`Dark-Lens/`) using the canonical **root virtual environment** (`.venv`).

If you intentionally run the backend from inside `backend/`, activate the root environment with `source ../.venv/bin/activate` and use `python -m uvicorn app.main:app --reload --port 8001`. From the repository root, use the `backend.app.main:app` command shown below.

> **Environment notice:** A secondary `backend/.venv` directory exists from earlier development and is preserved for compatibility. Do not delete it yet, but use the root `.venv` as the single canonical environment for all setup, run, and evaluation commands.

### 1. Start the backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8001
```

The dashboard expects the API on port **8001** by default. The API initializes the SQLite database and seeds Nightjar on first start. Open `http://127.0.0.1:8001/docs` to view the API documentation.

### 2. Start the dashboard

In a second terminal, from the repository root:

```bash
npm install
npm run dev
```

Open the Vite address shown in the terminal (normally `http://localhost:5173`). The dashboard reads the API at `http://127.0.0.1:8001` by default. Set `VITE_API_BASE_URL` before starting Vite to use a different API address.

### Reset the synthetic Nightjar case

This replaces Nightjar's case records, including review decisions and audit events, with the committed fixture. **Note:** Only run this if a clean baseline is explicitly required in the primary database, as it will overwrite manual review decisions:

```bash
source .venv/bin/activate
python -m backend.app.seed --reset-nightjar
```

### Check the fixture evaluation

All evaluation suites execute against isolated temporary databases and preserve the working database (`data/darklens.sqlite3`) and any recorded analyst review decisions.

From the repository root with `.venv` active:

```bash
# 1. Run full evaluation across both regression corpus and synthetic holdout suite (9 cases):
python -m backend.evaluation.evaluate_corpus --all

# 2. Run holdout evaluation only (Foxglove, Blackthorn, Osprey):
python -m backend.evaluation.evaluate_corpus --holdout

# 3. Run regression corpus only (Hollowreed, Driftwood, Copperline, Glasshouse, Marrowbone, Lowtide):
python -m backend.evaluation.evaluate_corpus --corpus

# 4. Check Nightjar baseline in a clean disposable database:
python -m backend.evaluation.evaluate_case

# 5. Verify case isolation across multi-case imports and queries:
python -m backend.evaluation.check_case_isolation

# 6. Verify analyst decision protection and analysis idempotence:
python -m backend.evaluation.check_analyst_protection

# 7. Check analyst review persistence, audit trail, and exports in a disposable database:
python -m backend.evaluation.check_review_workflow
```

#### Evaluation Metrics & Rules

| Metric | Definition | Rule / Benchmark |
|---|---|---|
| **Positive-Pair Recall** | Detected positive pairs ÷ expected positive pairs in answer key | $\ge 90\%$ across corpus & holdout |
| **Candidate Precision (@ 0.30)** | True positive candidate pairs ÷ total candidate pairs with score $\ge 0.30$ | $\ge 85\%$ across corpus & holdout |
| **Decoy Suppression** | Decoys that are either not surfaced as candidates or stay below configured decoy caps | $100\%$ within configured decoy thresholds |
| **No Auto-Acceptance** | Candidate links automatically set to `accepted` upon import or analysis | **0 permitted**; all links require analyst review |
| **Evidence Provenance** | Candidate links citing valid, existing observation record IDs | **100% required**; missing provenance is treated as an integrity failure |
| **Score Bounds** | Candidate review-priority scores strictly within $[0.0, 1.0]$ | **100% required** |

#### Expected Evaluation Output (`--all`)

```text
================================================================================
DARKLENS SYNTHETIC CORPUS & HOLDOUT EVALUATION
Target directory: .../backend/evaluation/corpus, .../backend/evaluation/holdout
================================================================================
[PASS] CASE-2026-002_case.json — Hollowreed (CASE-2026-002) ...
[PASS] CASE-2026-003_case.json — Driftwood (CASE-2026-003) ...
[PASS] CASE-2026-004_case.json — Copperline (CASE-2026-004) ...
[PASS] CASE-2026-005_case.json — Glasshouse (CASE-2026-005) ...
[PASS] CASE-2026-006_case.json — Marrowbone (CASE-2026-006) ...
[PASS] CASE-2026-007_case.json — Lowtide (CASE-2026-007) ...
[PASS] HOLDOUT-2026-001_case.json — Foxglove (HOLDOUT-2026-001) ...
[PASS] HOLDOUT-2026-002_case.json — Blackthorn (HOLDOUT-2026-002) ...
[PASS] HOLDOUT-2026-003_case.json — Osprey (HOLDOUT-2026-003) ...
[PASS] HOLDOUT-2026-004_case.json — Nightshade (HOLDOUT-2026-004) ...
================================================================================
• Total cases evaluated:        10
• Total checks passed:          78/78 (100%)
• Positive-pair recall:         32/32 (100%)
• Candidate precision (@ 0.30): 32/34 (94%)
• Decoys tested:                16 (7 surfaced under allowed bounds)
• Auto-accepted links:          0 (0 required)
• Unsupported links:            0 (0 required)
================================================================================
ALL CORPUS EVALUATION CHECKS PASSED.
```

> **Evaluation Limitations:** All cases, personas, and observations are synthetic and fictional. These evaluation metrics measure deterministic rule consistency on controlled scenarios. They do not constitute measured real-world accuracy, calibrated identity probabilities, or generalization to arbitrary dark-web data.

Analysis returns **evidence associations** separately from **attribution candidates**. Associations are graph-only edges that show which records are connected by source evidence; they do not enter the review queue on their own. The graph uses a muted dashed style for these edges. Candidate links still require an exact shared typed indicator or an eligible bounded multi-hop path. Scores account for match strength, source reliability, and record confidence, and longer inference paths receive an uncertainty discount.

## Repository map

```text
backend/
  app/
    database.py          SQLite schema, fixture loading, and case payloads
    main.py              FastAPI endpoints for case data, import, review, and exports
    analysis.py          Generic typed-indicator extraction, graph-only evidence associations, cautious candidate links, and capped behavioural leads
    imports.py           JSON bundle validation and normalization
    scoring.py           Explainable review-priority score calculation
    seed.py              Load or reset the Nightjar fixture
  fixtures/
    nightjar_seed.json   Fictional case entities, sources, observations, links
    case_bundle_v1.template.json  Example synthetic case import bundle
    hollowreed_case.json  Fictional 17-entity test case with synthetic mode declared
  evaluation/
    answer_key.json      Expected outcomes used only by the local evaluator
    analysis_edge_cases.json  Positive and adversarial identifier and activity cases
    evaluate_case.py     Synthetic fixture evaluation script
    check_review_workflow.py  Isolated review persistence and audit check
    check_case_isolation.py   Automated multi-case isolation verification
    check_analyst_protection.py  Automated analyst decision protection & idempotence check
    check_evidence_quality.py Automated evidence quality, provenance, conflict & deduplication verification
    evaluate_import_bundle.py  Import a synthetic case into a disposable DB and compare with an answer key
    evaluate_corpus.py   Aggregate case/answer-key evaluations for corpus & holdout suites
    corpus/              Synthetic test corpus bundles and answer keys (CASE-2026-002 to 007)
    holdout/             Synthetic holdout bundles and answer keys (HOLDOUT-2026-001 to 004)
src/
  App.jsx                Dashboard, graph, evidence, timeline, and interactions
  api.js                 Frontend API calls and export URLs
  styles.css             Dashboard visual system and responsive styles
requirements.txt         Python API dependencies
```

## Safety and interpretation rules

- Prototype input is synthetic; do not add scraped or sensitive real-world data to this demonstration.
- No live Tor, marketplace, infrastructure-scanning, or wallet-collection functionality is present.
- A score is a **review-priority score**, not a probability that two records belong to the same person.
- Common phrases, activity times, name resemblance, and banner strings can produce false matches.
- Every candidate remains subject to human review. Record the supporting evidence and uncertainty; do not state an inferred persona as a confirmed real-world identity.
- Any future live-source work requires appropriate legal authority, approved data access, access controls, security review, auditability, and a false-positive evaluation plan.

## Next milestones

1. **Complete SIH team record:** add the verified registered-member names and actual contributions from the SIH team portal; assign a presenter and demo responsibilities.
2. **Stabilize the demo:** add API and UI interaction tests for case loading, review updates, audit events, filters, exports, and reset behavior.
3. **Strengthen the synthetic evaluation:** report per-link outcomes and precision/recall at explicitly stated thresholds; include limitations and avoid describing fixture checks as model performance.
4. **Improve review reporting:** add audit-event export and a fuller analyst identity model.
5. **Expand matcher evaluation:** add more adversarial fixtures and measure missed and false matches before using the rules beyond demo leads.
6. **Prototype further analysis carefully:** only after rule evaluation, consider a small stylometry baseline on labelled, consented or public research text. Keep source reliability and human review visible.
7. **Prepare the SIH presentation:** show the problem, safe synthetic workflow, Nightjar case walkthrough, architecture, measured fixture results, risks, and a clearly scoped future plan.

## Current status summary

**Stage:** local, synthetic-data prototype with a connected dashboard and API. The Nightjar review queue, audit-history view, isolated persistence workflow, schema-driven indicator/reference matching, bounded identifier/infrastructure path analysis with traceable inference chains, evidence provenance breakdown, mirror/derivation duplicate detection and discounting, counter-evidence and conflict classification, candidate evidence dossiers, cautious style/activity leads, hardened JSON case import with validation preview and duplicate conflict handling, case isolation, idempotent re-analysis, export reporting, 6-case regression corpus, and 4-case synthetic holdout suite are implemented. The matcher remains heuristic and calibrated for synthetic leads. Automated collection and trained stylometry are not implemented.

### Rough whole-project completion estimate

As of **20 October 2026**, the project is approximately **66% complete** against the full proposed platform. This is a rough, unweighted average of the workstream estimates below, not a measured software metric:

| Workstream | Estimate | Remaining work |
| --- | ---: | --- |
| Dashboard and analyst workflow | 94% | UI polish and full browser interaction verification. |
| API, storage, and reporting | 92% | Authentication/roles, production deployment hardening. |
| Explainable analysis | 70% | Stylometry research baseline, calibrated identity scores. |
| Synthetic case and evaluation | 90% | Continued expansion of adversarial decoys and edge-case suites. |
| Security, source governance, and operations | 10% | Threat model, access controls, lawful source process, monitoring and deployment. |
| SIH team and presentation readiness | 35% | Confirm roster, team walkthrough, demo script, and final presentation. |

The estimate includes JSON bundle import with pre-validation preview, multi-case isolation, traceable inference paths, evidence quality dossiers, conflict analysis, duplicate discounting, idempotent analysis reruns, alongside activity-window analysis, richer exports, 6-case regression corpus, and 4-case holdout evaluation. It does not count live collection, a trained stylometry model, or production deployment as complete.
