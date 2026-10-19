# DarkLens MVP Specification

## Goal

Demonstrate how DarkLens turns a small, safe dataset into **reviewable investigative leads**. The prototype must explain every link and its uncertainty. It must not claim to identify a real person.

## Demo scenario

Use a fully synthetic case containing three fictional personas across two fictional marketplaces. One persona changes handle between marketplaces but reuses a PGP key; another shares a wallet with the first; a third writes similarly but has no strong identifier overlap. Add a few synthetic posts, timestamps, source records, and infrastructure indicators. The interface should show the first two as stronger links and the writing-style-only match as weak and requiring review.

All names, domains, keys, wallets, posts, and infrastructure values must be generated for the demo. Do not connect to Tor, scan hosts, crawl marketplaces, or ingest personal data.

## User and primary workflow

**User:** an analyst reviewing a possible relationship between personas.

1. Open the case dashboard and see the synthetic sources and latest ingestion time.
2. Search for a handle or identifier.
3. Explore the actor/persona graph and filter by evidence type or confidence.
4. Select a link to inspect the evidence, source, timestamp, reliability, and score breakdown.
5. Review the timeline and mark a lead as reviewed, rejected, or needs more evidence.
6. Export the current case as JSON and CSV.

## MVP data model

- **Case:** id, title, created_at, status.
- **Entity:** id, type (`persona`, `handle`, `pgp_key`, `wallet`, `post`, `service`, `infrastructure`), display_label, first_seen, last_seen, attributes.
- **Source:** id, name, source_type, reliability (0–1), collected_at, dataset_label.
- **Evidence:** id, source_id, evidence_type, summary, observed_at, confidence (0–1), details.
- **Link:** id, from_entity_id, to_entity_id, relation, score (0–1), evidence_ids, review_status (`unreviewed`, `accepted`, `rejected`, `needs_more_evidence`).
- **Audit event:** id, case_id, actor_label (`demo_analyst`), action, target_id, timestamp, note.

Every graph edge must resolve to one or more evidence records. Missing provenance is a data error, not an implicit link.

## Link scoring for the demo

Use a deterministic, documented baseline rather than a trained model. For each candidate persona-to-persona link, combine available signals with these initial weights:

| Signal | Weight |
| --- | ---: |
| Exact synthetic PGP key reuse | 0.45 |
| Exact synthetic wallet reuse | 0.30 |
| Handle similarity | 0.10 |
| Writing-style similarity | 0.10 |
| Activity-pattern similarity | 0.05 |

For each signal, multiply its match value (0–1) by the source reliability (0–1), then sum weighted values and cap the result at 1.0. Show the signal contributions, source, and reliability beside the score. Treat scores as **review priority**, not probability of identity. A missing signal contributes zero; it is not evidence against a link. Keep the weights in one configuration file so they can be adjusted and documented.

Suggested UI labels: `High priority` (score ≥ 0.70), `Review` (0.40–0.69), and `Weak` (< 0.40). These are demo thresholds, not validated forensic standards.

## Screens and features

1. **Case overview:** record counts, source list, last import, and a short safety notice that all data is synthetic.
2. **Graph explorer:** personas and identifiers as nodes; evidence-backed relationships as edges; filters for edge type, score band, and review status.
3. **Evidence panel:** selected edge’s score breakdown, evidence summaries, source reliability, timestamps, and analyst review control.
4. **Timeline:** evidence and observations ordered by time, filterable by entity and evidence type.
5. **Export:** JSON for the case data and CSV for entities, links, and evidence. Include provenance and review status.

## Out of scope

- Live Tor or marketplace access, crawling, scanning, or autonomous collection.
- Real personal data or real attribution to named people.
- Predictive claims from stylometry, embeddings, or machine learning.
- Production authentication, multi-user permissions, deployment, or operational scheduling.
- OpenSearch, Neo4j, and PDF reporting in the first demonstrator.

## Initial implementation choice

Start with a single local application: **FastAPI + SQLite** for the API and persisted demo case, and **React + Cytoscape.js** for the interface. Keep data access and scoring behind small modules so SQLite can later be replaced with PostgreSQL and NetworkX can be added if graph analysis needs it. Load the synthetic fixture through a seed/import command; do not build collectors.

## Acceptance criteria

- A fresh local setup can load the synthetic case and open the dashboard.
- The graph contains at least three personas, two marketplaces, and the identifier/evidence records described in the demo scenario.
- Every displayed link has inspectable evidence, source, timestamp, reliability, and score breakdown.
- The shared-key and shared-wallet links rank above the stylometry-only link in the seeded scenario.
- An analyst can change review status, and the action appears in the audit trail.
- Timeline filtering and JSON/CSV exports work on the seeded case.
- The UI consistently describes matches as leads for human review, not proof of identity.
- No network collection or outbound requests are needed to run the prototype.

## Build sequence

1. Create the app skeleton and synthetic fixture.
2. Implement entities, evidence, link scoring, and case APIs.
3. Build case overview, graph, and evidence review flow.
4. Add timeline, audit trail, and JSON/CSV exports.
5. Run the acceptance checklist and prepare a short demo walkthrough.
