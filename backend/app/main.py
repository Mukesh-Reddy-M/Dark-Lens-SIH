"""Local FastAPI endpoints for the DarkLens synthetic prototype."""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import get_case_payload, init_db, session, utc_now
from .analysis import analyze_case, enrich_observation_details
from .imports import BundleValidationError, normalize_case_bundle

app = FastAPI(
    title="DarkLens Prototype API",
    version="0.1.0",
    description="Local API for a synthetic, human-reviewed threat-intelligence demonstration.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewUpdate(BaseModel):
    status: Literal["accepted", "rejected", "needs_more_evidence", "unreviewed"]
    note: str = Field(default="", max_length=500)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "synthetic_data_only": True}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    with session() as db:
        rows = db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
        return [dict(row) | {"synthetic": bool(row["synthetic"])} for row in rows]


@app.post("/api/cases/preview")
def preview_case(bundle: dict) -> dict:
    """Validate a synthetic JSON bundle and preview its contents without persisting."""
    try:
        normalized = normalize_case_bundle(bundle)
    except BundleValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors) from error

    case = normalized["case"]
    with session() as db:
        exists = bool(db.execute("SELECT 1 FROM cases WHERE id=?", (case["id"],)).fetchone())

    entity_type_counts: dict[str, int] = {}
    for ent in normalized["entities"]:
        t = ent["type"]
        entity_type_counts[t] = entity_type_counts.get(t, 0) + 1

    return {
        "valid": True,
        "case_id": case["id"],
        "case_title": case["title"],
        "case_description": case["description"],
        "case_exists": exists,
        "counts": {
            "sources": len(normalized["sources"]),
            "entities": len(normalized["entities"]),
            "observations": len(normalized["observations"]),
        },
        "entity_types": entity_type_counts,
        "warning": (
            f"Case ID '{case['id']}' already exists in the workspace. DarkLens never overwrites cases; you must choose a new ID or delete the existing case before importing."
            if exists else None
        ),
        "message": "Valid version 1.0 synthetic case bundle ready for import.",
    }


@app.post("/api/cases/import", status_code=201)
def import_case(bundle: dict) -> dict:
    """Import one validated synthetic JSON bundle and create reviewable leads."""
    try:
        normalized = normalize_case_bundle(bundle)
    except BundleValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors) from error

    case = normalized["case"]
    imported_at = utc_now()
    with session() as db:
        if db.execute("SELECT 1 FROM cases WHERE id=?", (case["id"],)).fetchone():
            raise HTTPException(
                status_code=409,
                detail=f"Case ID '{case['id']}' already exists. DarkLens creates new cases upon import and never overwrites existing records silently. Please provide a unique case ID or delete/rename the existing case."
            )

        # IDs in a bundle are local to that case. Keep them unchanged when
        # possible, and add the case ID only when another case already owns
        # the same database key. Build all maps before inserting so every
        # foreign-key reference follows the remapped ID.
        remapped_ids: list[dict[str, str]] = []

        def allocate_ids(table: str, records: list[dict], record_type: str) -> dict[str, str]:
            mapping: dict[str, str] = {}
            reserved: set[str] = set()
            for record in records:
                original_id = record["id"]
                imported_id = original_id
                if db.execute(f"SELECT 1 FROM {table} WHERE id=?", (imported_id,)).fetchone():
                    imported_id = f"{original_id}--{case['id']}"
                    suffix = 2
                    while imported_id in reserved or db.execute(f"SELECT 1 FROM {table} WHERE id=?", (imported_id,)).fetchone():
                        imported_id = f"{original_id}--{case['id']}-{suffix}"
                        suffix += 1
                    remapped_ids.append({"record_type": record_type, "original_id": original_id, "imported_id": imported_id})
                mapping[original_id] = imported_id
                reserved.add(imported_id)
            return mapping

        source_ids = allocate_ids("sources", normalized["sources"], "source")
        entity_ids = allocate_ids("entities", normalized["entities"], "entity")
        observation_ids = allocate_ids("evidence", normalized["observations"], "observation")
        sources = [{**source, "id": source_ids[source["id"]]} for source in normalized["sources"]]
        entities = [{**entity, "id": entity_ids[entity["id"]]} for entity in normalized["entities"]]
        observations = []
        for item in normalized["observations"]:
            details = dict(item["details"])
            for field in ("entity_id", "actor_entity_id", "key", "wallet"):
                value = details.get(field)
                if isinstance(value, str) and value in entity_ids:
                    details[field] = entity_ids[value]
            observations.append({
                **item,
                "id": observation_ids[item["id"]],
                "source_id": source_ids[item["source_id"]],
                "entity_id": entity_ids[item["entity_id"]] if item["entity_id"] else None,
                "details": details,
            })
        db.execute(
            "INSERT INTO cases(id,title,description,status,synthetic,created_at,last_imported_at) VALUES(?,?,?,?,?,?,?)",
            (case["id"], case["title"], case["description"], "open", 1, imported_at, imported_at),
        )
        db.executemany(
            "INSERT INTO sources(id,case_id,name,source_type,reliability,collected_at,dataset_label) VALUES(?,?,?,?,?,?,?)",
            [(source["id"], case["id"], source["name"], source["source_type"], source["reliability"], imported_at, "SYNTHETIC JSON IMPORT v1") for source in sources],
        )
        db.executemany(
            "INSERT INTO entities(id,case_id,type,display_label,first_seen,last_seen,attributes_json) VALUES(?,?,?,?,?,?,?)",
            [(entity["id"], case["id"], entity["type"], entity["display_label"], entity["first_seen"], entity["last_seen"], json.dumps(entity["attributes"], sort_keys=True)) for entity in entities],
        )
        entities_by_id = {entity["id"]: entity for entity in entities}
        db.executemany(
            "INSERT INTO evidence(id,case_id,source_id,entity_id,evidence_type,summary,observed_at,confidence,details_json) VALUES(?,?,?,?,?,?,?,?,?)",
            [(item["id"], case["id"], item["source_id"], item["entity_id"], item["evidence_type"], item["summary"], item["observed_at"], item["confidence"], json.dumps(enrich_observation_details(item, entities_by_id), sort_keys=True)) for item in observations],
        )
        payload = get_case_payload(db, case["id"])
        analysis = analyze_case(payload)
        candidates = list(analysis["suggestions"])
        seen_pairs = {(item["from_entity_id"], item["to_entity_id"]) for item in candidates}
        candidates.extend(item for item in analysis["behavioral_leads"] if (item["from_entity_id"], item["to_entity_id"]) not in seen_pairs)
        for index, candidate in enumerate(candidates, start=1):
            link_id = f"{case['id']}-L{index:03d}"
            breakdown = {
                "signals": candidate["signals"],
                "caution": candidate["caution"],
                "score_is_probability": False,
                "score_explanation": candidate.get("score_explanation", "Review priority combines the listed evidence signal, source reliability, and record confidence."),
                "path_entity_ids": candidate.get("path_entity_ids", []),
                "has_conflicts": candidate.get("has_conflicts", False),
                "dossier": candidate.get("dossier", {}),
            }
            db.execute(
                "INSERT INTO links(id,case_id,from_entity_id,to_entity_id,relation,score,priority,review_status,score_breakdown_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (link_id, case["id"], candidate["from_entity_id"], candidate["to_entity_id"], candidate["relation"], candidate["score"], candidate["priority"], candidate["review_status"], json.dumps(breakdown, sort_keys=True)),
            )
            db.executemany("INSERT INTO link_evidence(link_id,evidence_id) VALUES(?,?)", [(link_id, evidence_id) for evidence_id in candidate["evidence_ids"]])
        db.execute(
            "INSERT INTO audit_events(case_id,actor_label,action,target_id,timestamp,note) VALUES(?,?,?,?,?,?)",
            (case["id"], "synthetic_import", "case_imported", case["id"], imported_at, f"Imported {len(entities)} entities, {len(observations)} observations, and generated {len(candidates)} candidate links from a version 1.0 synthetic bundle. {len(remapped_ids)} reused record IDs were namespaced for this case."),
        )
        result = get_case_payload(db, case["id"])
    return {
        "case": result["case"],
        "entity_count": len(result["entities"]),
        "source_count": len(result["sources"]),
        "observation_count": len(result["evidence"]),
        "candidate_link_count": len(result["links"]),
        "remapped_ids": remapped_ids,
        "message": "Synthetic case imported. Candidate links were created for analyst review; none were accepted automatically." + (f" {len(remapped_ids)} reused record IDs were safely namespaced." if remapped_ids else ""),
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    with session() as db:
        payload = get_case_payload(db, case_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if payload["case"]["synthetic"]:
        analysis = analyze_case(payload)
        payload["evidence_associations"] = analysis["evidence_associations"]
        dossier_by_pair = {
            (s["from_entity_id"], s["to_entity_id"]): s.get("dossier", {})
            for s in analysis.get("suggestions", [])
        }
        for link in payload["links"]:
            pair = (link["from_entity_id"], link["to_entity_id"])
            dossier = dossier_by_pair.get(pair) or dossier_by_pair.get(pair[::-1])
            if dossier:
                link["dossier"] = dossier
                link["has_conflicts"] = dossier.get("has_conflicts", False)
    return payload


@app.get("/api/cases/{case_id}/timeline")
def get_timeline(case_id: str) -> list[dict]:
    with session() as db:
        if not db.execute("SELECT 1 FROM cases WHERE id=?", (case_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Case not found")
        rows = db.execute("""
            SELECT e.id, e.entity_id, ent.display_label AS entity_label,
                   e.evidence_type, e.summary, e.observed_at,
                   e.confidence, s.name AS source_name, s.reliability AS source_reliability
            FROM evidence e
            JOIN sources s ON s.id=e.source_id
            LEFT JOIN entities ent ON ent.id=e.entity_id
            WHERE e.case_id=?
            ORDER BY e.observed_at, e.id
        """, (case_id,)).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/cases/{case_id}/analysis")
def run_analysis(case_id: str) -> dict:
    """Preview deterministic links from the local synthetic evidence only."""
    with session() as db:
        payload = get_case_payload(db, case_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if not payload["case"]["synthetic"]:
        raise HTTPException(status_code=403, detail="Analysis preview is limited to synthetic cases")
    return analyze_case(payload)


@app.post("/api/cases/{case_id}/analysis")
def save_analysis_suggestions(case_id: str) -> dict:
    """Add missing synthetic analysis leads to the review queue, idempotently."""
    with session() as db:
        payload = get_case_payload(db, case_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if not payload["case"]["synthetic"]:
            raise HTTPException(status_code=403, detail="Analysis is limited to synthetic cases")

        entities = {entity["id"]: entity for entity in payload["entities"]}
        for observation in payload["evidence"]:
            details = enrich_observation_details(observation, entities)
            if details != observation.get("details", {}):
                db.execute("UPDATE evidence SET details_json=? WHERE id=?", (json.dumps(details, sort_keys=True), observation["id"]))
                observation["details"] = details

        analysis = analyze_case(payload)
        candidates = list(analysis["suggestions"])
        exact_pairs = {(row["from_entity_id"], row["to_entity_id"]) for row in candidates}
        candidates.extend(row for row in analysis["behavioral_leads"] if (row["from_entity_id"], row["to_entity_id"]) not in exact_pairs)
        existing = {(row["from_entity_id"], row["to_entity_id"]) for row in payload["links"]}
        next_number = 1
        added = 0
        for candidate in candidates:
            pair = (candidate["from_entity_id"], candidate["to_entity_id"])
            breakdown = {
                "signals": candidate["signals"],
                "caution": candidate["caution"],
                "score_is_probability": False,
                "score_explanation": candidate.get("score_explanation", "Review priority combines the listed evidence signal, source reliability, and record confidence."),
                "path_entity_ids": candidate.get("path_entity_ids", []),
                "has_conflicts": candidate.get("has_conflicts", False),
                "dossier": candidate.get("dossier", {}),
            }
            if pair in existing or pair[::-1] in existing:
                db.execute(
                    "UPDATE links SET score_breakdown_json=? WHERE case_id=? AND ((from_entity_id=? AND to_entity_id=?) OR (from_entity_id=? AND to_entity_id=?))",
                    (json.dumps(breakdown, sort_keys=True), case_id, pair[0], pair[1], pair[1], pair[0]),
                )
                continue
            while db.execute("SELECT 1 FROM links WHERE id=?", (f"{case_id}-L{next_number:03d}",)).fetchone():
                next_number += 1
            link_id = f"{case_id}-L{next_number:03d}"
            next_number += 1
            db.execute(
                "INSERT INTO links(id,case_id,from_entity_id,to_entity_id,relation,score,priority,review_status,score_breakdown_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (link_id, case_id, candidate["from_entity_id"], candidate["to_entity_id"], candidate["relation"], candidate["score"], candidate["priority"], candidate["review_status"], json.dumps(breakdown, sort_keys=True)),
            )
            db.executemany("INSERT INTO link_evidence(link_id,evidence_id) VALUES(?,?)", [(link_id, evidence_id) for evidence_id in candidate["evidence_ids"]])
            existing.add(pair)
            added += 1
        if added:
            db.execute(
                "INSERT INTO audit_events(case_id,actor_label,action,target_id,timestamp,note) VALUES(?,?,?,?,?,?)",
                (case_id, "synthetic_analysis", "candidate_links_generated", case_id, utc_now(), f"Generated {added} new synthetic candidate links. No link was accepted automatically."),
            )
        return {"case_id": case_id, "analysis": analysis, "added_count": added, "candidate_link_count": len(existing)}


@app.patch("/api/links/{link_id}/review")
def update_link_review(link_id: str, update: ReviewUpdate) -> dict:
    with session() as db:
        link = db.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")
        db.execute("UPDATE links SET review_status=? WHERE id=?", (update.status, link_id))
        db.execute(
            "INSERT INTO audit_events(case_id,actor_label,action,target_id,timestamp,note) VALUES(?,?,?,?,?,?)",
            (link["case_id"], "demo_analyst", f"review_status:{link['review_status']}->{update.status}", link_id, utc_now(), update.note),
        )
        db.commit()
        updated = db.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
        result = dict(updated)
        result["score_breakdown"] = json.loads(result.pop("score_breakdown_json"))
        result["evidence_ids"] = [r[0] for r in db.execute("SELECT evidence_id FROM link_evidence WHERE link_id=? ORDER BY evidence_id", (link_id,))]
        return result


@app.get("/api/cases/{case_id}/export.json")
def export_json(case_id: str) -> dict:
    with session() as db:
        payload = get_case_payload(db, case_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if payload["case"]["synthetic"]:
        analysis = analyze_case(payload)
        payload["evidence_associations"] = analysis.get("evidence_associations", [])
        dossier_by_pair = {
            (s["from_entity_id"], s["to_entity_id"]): s.get("dossier", {})
            for s in analysis.get("suggestions", [])
        }
        for link in payload["links"]:
            if not link.get("dossier"):
                pair = (link["from_entity_id"], link["to_entity_id"])
                dossier = dossier_by_pair.get(pair) or dossier_by_pair.get(pair[::-1])
                if dossier:
                    link["dossier"] = dossier
                    link["has_conflicts"] = dossier.get("has_conflicts", False)
    payload["case"]["exported_at"] = utc_now()
    return payload


@app.get("/api/cases/{case_id}/export.csv")
def export_csv(case_id: str, kind: Literal["entities", "evidence", "links", "audit"] = "links") -> Response:
    with session() as db:
        payload = get_case_payload(db, case_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Case not found")
    rows = payload["audit_events"] if kind == "audit" else payload[kind]
    if not rows:
        if kind == "audit":
            stream = io.StringIO(newline="")
            csv.writer(stream).writerow(["id", "case_id", "actor_label", "action", "target_id", "timestamp", "note"])
            return Response(content=stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="darklens-{case_id}-{kind}.csv"'})
        return Response(content="", media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="darklens-{case_id}-{kind}.csv"'})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    return Response(content=stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="darklens-{case_id}-{kind}.csv"'})


@app.get("/api/cases/{case_id}/report.md")
def export_report(case_id: str) -> Response:
    with session() as db:
        payload = get_case_payload(db, case_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Case not found")

    if payload["case"]["synthetic"]:
        analysis = analyze_case(payload)
        dossier_by_pair = {
            (s["from_entity_id"], s["to_entity_id"]): s.get("dossier", {})
            for s in analysis.get("suggestions", [])
        }
        for link in payload["links"]:
            if not link.get("dossier"):
                pair = (link["from_entity_id"], link["to_entity_id"])
                dossier = dossier_by_pair.get(pair) or dossier_by_pair.get(pair[::-1])
                if dossier:
                    link["dossier"] = dossier
                    link["has_conflicts"] = dossier.get("has_conflicts", False)

    entities = {row["id"]: row for row in payload["entities"]}
    evidence = {row["id"]: row for row in payload["evidence"]}
    sources = {row["id"]: row for row in payload["sources"]}
    accepted = sum(row["review_status"] == "accepted" for row in payload["links"])
    rejected = sum(row["review_status"] == "rejected" for row in payload["links"])
    pending = len(payload["links"]) - accepted - rejected
    lines = [
        f"# DarkLens case report: {payload['case']['id']}",
        "",
        f"**Case:** {payload['case']['title']}  ",
        f"**Status:** {payload['case']['status']}  ",
        f"**Generated:** {utc_now()}  ",
        f"**Data mode:** {'Synthetic' if payload['case']['synthetic'] else 'Case records'}",
        "",
        "> Candidate links are review leads, not proof of identity. Scores prioritize review and are not probabilities.",
        "",
        "## Case summary",
        "",
        f"- Entities: {len(payload['entities'])}",
        f"- Evidence records: {len(payload['evidence'])}",
        f"- Sources: {len(payload['sources'])}",
        f"- Candidate links: {len(payload['links'])} ({accepted} accepted, {rejected} rejected, {pending} pending or more evidence)",
        "",
        "## Candidate links",
    ]
    for link in payload["links"]:
        left = entities.get(link["from_entity_id"], {}).get("display_label", link["from_entity_id"])
        right = entities.get(link["to_entity_id"], {}).get("display_label", link["to_entity_id"])
        dossier = link.get("dossier") or link.get("score_breakdown", {}).get("dossier") or {}
        has_conflicts = link.get("has_conflicts") or dossier.get("has_conflicts", False)
        lines.extend([
            "",
            f"### {link['id']} · {left} ↔ {right}",
            "",
            f"- Proposed relationship: `{link['relation']}`",
            f"- Review priority: {link['score']:.0%} ({link['priority']})",
            f"- Analyst status: `{link['review_status']}`",
            f"- Evidence IDs: {', '.join(link['evidence_ids']) or 'None'}",
            f"- Conflict status: {'⚠️ Confirmed Contradiction Detected' if has_conflicts else '✓ No Confirmed Contradictions'}",
        ])
        if dossier.get("inference_path"):
            path_str = " → ".join(p.get("label", p.get("entity_id", "")) for p in dossier["inference_path"])
            lines.append(f"- Inference path: `{path_str}`")
        if dossier.get("source_independence"):
            si = dossier["source_independence"]
            lines.append(f"- Source independence: **{si.get('rating', 'unknown').upper()}** · {si.get('description', '')}")
        caution = link.get("score_breakdown", {}).get("caution")
        if caution:
            lines.append(f"- Caution: {caution}")

        # Supporting evidence provenance
        supporting = dossier.get("supporting_evidence")
        if supporting:
            lines.append("- Supporting evidence provenance:")
            for s in supporting:
                lines.append(f"  - `{s['observation_id']}` ({s.get('observed_at') or 'Undated'}) · {s['summary']}")
                lines.append(f"    - Source: {s['source_name']} (reliability: {s['source_reliability']:.0%}) | Confidence: {s['confidence']:.0%} | Match: {s['match_strength']:.0%} | Contribution: +{s['contribution']:.2f}")
        else:
            lines.append("- Evidence details:")
            for evidence_id in link["evidence_ids"]:
                item = evidence.get(evidence_id)
                if not item:
                    continue
                source = sources.get(item["source_id"], {})
                lines.append(f"  - `{evidence_id}` · {item['observed_at']} · {item['summary']} (source: {source.get('name', item['source_id'])}; reliability {source.get('reliability', 0):.0%}; evidence confidence {item['confidence']:.0%})")

        # Counter-evidence and conflicts
        counter = dossier.get("counter_evidence")
        if counter:
            lines.append("- Counter-evidence & inconsistencies:")
            for c in counter:
                kind_tag = "⚠️ Confirmed Contradiction" if c.get("is_confirmed_contradiction") else "ℹ️ Review Context"
                lines.append(f"  - [{kind_tag}] `{c['observation_id']}` · {c['summary']}")
                lines.append(f"    - Conflict explanation: {c['explanation']}")

        # Grouped duplicate evidence
        grouped = dossier.get("grouped_evidence")
        if grouped:
            lines.append("- Grouped duplicate / dependent clues:")
            for g in grouped:
                lines.append(f"  - `{g['observation_id']}` · {g['reason']}")

        # Weak or missing evidence
        weak = dossier.get("weak_or_missing_evidence")
        if weak:
            lines.append("- Missing or weak evidence factors:")
            for w in weak:
                lines.append(f"  - {w}")
    lines.extend(["", "## Analyst audit history", ""])
    if payload["audit_events"]:
        for event in payload["audit_events"]:
            lines.append(f"- {event['timestamp']} · {event['actor_label']} · `{event['target_id']}` · `{event['action']}` · {event['note'] or 'No note'}")
    else:
        lines.append("No analyst review actions have been recorded.")
    lines.extend(["", "---", "Synthetic intelligence workspace export. Handle according to the case team's data governance rules.", ""])
    filename = f"darklens-{case_id}-report.md"
    return Response(content="\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
