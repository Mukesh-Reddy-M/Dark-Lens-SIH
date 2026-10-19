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
- **Analyst review:** Accept, Reject, and More evidence actions update a link through the API and write an audit event. The UI reloads the case after a review action.
- **Timeline:** 24 chronological synthetic observations with range filtering. Hovering or selecting an event opens an explanation panel with the observation summary, plain-language interpretation, source and reliability, evidence confidence, and any candidate link that uses it.
- **Navigation and search:** sidebar navigation scrolls to case sections or opens Reports, Saved Searches, and Settings panels. Entity search selects a matching record in the graph.
- **Exports:** full-case JSON and separate CSV downloads for entities, evidence, and links.
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
| Scoring | Transparent independent-signal combination | Each signal contributes match strength × source reliability; the combined triage score is capped as configured. It is not a calibrated probability. |
| Evaluation | `backend/evaluation/evaluate_case.py` and separate answer key | Checks the fixed synthetic fixture expectations; this is not real-world model validation. |

The current build does **not** include PostgreSQL, Neo4j, OpenSearch, live collectors, an autonomous scheduler, a trained ML model, or an LLM. Persona-style and activity evidence is prewritten in the synthetic fixture; the prototype does not train or run a stylometry model yet. Those remain future work from the proposal.

## API overview

The local API reference is available at `http://127.0.0.1:8001/docs` while the backend is running.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service health and synthetic-data indicator. |
| `GET` | `/api/cases` | List local cases. |
| `GET` | `/api/cases/{case_id}` | Fetch case, entities, sources, evidence, links, and audit events. |
| `GET` | `/api/cases/{case_id}/timeline` | Fetch observations in chronological order. |
| `PATCH` | `/api/links/{link_id}/review` | Set `accepted`, `rejected`, `needs_more_evidence`, or `unreviewed`; writes an audit event. |
| `GET` | `/api/cases/{case_id}/export.json` | Download a full case JSON export. |
| `GET` | `/api/cases/{case_id}/export.csv` with `kind=entities`, `kind=evidence`, or `kind=links` | Download a selected record collection as CSV. |

## Run locally

Requirements: Node.js/npm and Python 3.9 or later.

### 1. Start the backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8001
```

The API initializes the SQLite database and seeds Nightjar on first start. Open `http://127.0.0.1:8001/docs` to view the API.

### 2. Start the dashboard

In a second terminal, from the repository root:

```bash
npm install
npm run dev
```

Open the Vite address shown in the terminal (normally `http://localhost:5173`). The dashboard reads the API at `http://127.0.0.1:8001` by default. Set `VITE_API_BASE_URL` before starting Vite to use a different API address.

### Reset the synthetic Nightjar case

This replaces Nightjar's case records, including review decisions and audit events, with the committed fixture:

```bash
source .venv/bin/activate
python -m backend.app.seed --reset-nightjar
```

### Check the fixture evaluation

Export a JSON case from the app/API, then run:

```bash
python backend/evaluation/evaluate_case.py path/to/case-export.json
```

The report is a deterministic check against synthetic expected outcomes only. It must not be presented as evidence of production accuracy.

## Repository map

```text
backend/
  app/
    database.py          SQLite schema, fixture loading, and case payloads
    main.py              FastAPI endpoints for case data, review, and exports
    scoring.py           Explainable review-priority score calculation
    seed.py              Load or reset the Nightjar fixture
  fixtures/
    nightjar_seed.json   Fictional case entities, sources, observations, links
  evaluation/
    answer_key.json      Expected outcomes used only by the local evaluator
    evaluate_case.py     Synthetic fixture evaluation script
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
4. **Improve analyst workflow:** add a dedicated link-review queue, complete audit-history view, and richer evidence provenance in exports.
5. **Prototype one explainable analysis module at a time:** start with deterministic identifier/infrastructure matching; then evaluate a small stylometry baseline on labelled, consented or public research text. Keep source reliability and human review visible.
6. **Prepare the SIH presentation:** show the problem, safe synthetic workflow, Nightjar case walkthrough, architecture, measured fixture results, risks, and a clearly scoped future plan.

## Current status summary

**Stage:** local, synthetic-data prototype with a connected dashboard and API. The case workflow and user-interface interactions are implemented; automated collection and trained analysis modules are not. The immediate team priority is to complete the official roster, stabilize the demo, and present the synthetic evaluation honestly.
