"""SQLite persistence and synthetic fixture for local development."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scoring import score_link

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("DARKLENS_DB_PATH", ROOT / "data" / "darklens.sqlite3"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


@contextmanager
def session():
    db = connect()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def init_db() -> None:
    with session() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                synthetic INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                display_label TEXT NOT NULL,
                first_seen TEXT,
                last_seen TEXT,
                attributes_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                reliability REAL NOT NULL CHECK(reliability BETWEEN 0 AND 1),
                collected_at TEXT NOT NULL,
                dataset_label TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                source_id TEXT NOT NULL REFERENCES sources(id),
                entity_id TEXT REFERENCES entities(id),
                evidence_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                from_entity_id TEXT NOT NULL REFERENCES entities(id),
                to_entity_id TEXT NOT NULL REFERENCES entities(id),
                relation TEXT NOT NULL,
                score REAL NOT NULL CHECK(score BETWEEN 0 AND 1),
                priority TEXT NOT NULL,
                review_status TEXT NOT NULL CHECK(review_status IN ('unreviewed','accepted','rejected','needs_more_evidence')),
                score_breakdown_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS link_evidence (
                link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
                PRIMARY KEY(link_id, evidence_id)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                actor_label TEXT NOT NULL,
                action TEXT NOT NULL,
                target_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_entities_case ON entities(case_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_case_date ON evidence(case_id, observed_at);
            CREATE INDEX IF NOT EXISTS idx_links_case ON links(case_id);
            CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id, timestamp);
        """)
        # Existing local databases predate case descriptions; keep them usable.
        case_columns = {row[1] for row in db.execute("PRAGMA table_info(cases)")}
        if "description" not in case_columns:
            db.execute("ALTER TABLE cases ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        if not db.execute("SELECT 1 FROM cases WHERE id='NIGHTJAR-2026-001'").fetchone():
            seed_nightjar(db)


def seed_nightjar(db: sqlite3.Connection, *, reset: bool = False) -> None:
    """Load the fixed Nightjar fixture. Answer-key data is never loaded here."""
    fixture_path = ROOT / "backend" / "fixtures" / "nightjar_seed.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    case_id = fixture["case"]["id"]
    if db.execute("SELECT 1 FROM cases WHERE id=?", (case_id,)).fetchone():
        if not reset:
            return
        db.execute("DELETE FROM cases WHERE id=?", (case_id,))

    case = fixture["case"]
    db.execute(
        "INSERT INTO cases(id,title,status,synthetic,created_at,last_imported_at) VALUES(?,?,?,?,?,?)",
        (case["id"], case["title"], case["status"], int(case["synthetic"]), case["created_at"], case["last_imported_at"]),
    )
    db.executemany(
        "INSERT INTO entities(id,case_id,type,display_label,first_seen,last_seen,attributes_json) VALUES(?,?,?,?,?,?,?)",
        [(e["id"], case_id, e["type"], e["display_label"], e["first_seen"], e["last_seen"], _json(e["attributes"])) for e in fixture["entities"]],
    )
    db.executemany(
        "INSERT INTO sources(id,case_id,name,source_type,reliability,collected_at,dataset_label) VALUES(?,?,?,?,?,?,?)",
        [(s["id"], case_id, s["name"], s["source_type"], s["reliability"], case["last_imported_at"], s["dataset_label"]) for s in fixture["sources"]],
    )
    db.executemany(
        "INSERT INTO evidence(id,case_id,source_id,entity_id,evidence_type,summary,observed_at,confidence,details_json) VALUES(?,?,?,?,?,?,?,?,?)",
        [(o["id"], case_id, o["source"], o["entity"], o["type"], o["summary"], o["date"], o["confidence"], _json(o["details"])) for o in fixture["observations"]],
    )
    for link in fixture["links"]:
        signals = {name: (float(values[0]), float(values[1])) for name, values in link["signals"].items()}
        score, breakdown = score_link(signals, cap=float(link.get("score_cap", 1.0)))
        db.execute(
            "INSERT INTO links(id,case_id,from_entity_id,to_entity_id,relation,score,priority,review_status,score_breakdown_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (link["id"], case_id, link["from"], link["to"], link["relation"], score, "high_priority" if score >= .85 else "review" if score >= .40 else "weak", link["status"], _json({"signals": breakdown, "caution": link.get("caution", ""), "score_is_probability": False})),
        )
        db.executemany("INSERT INTO link_evidence(link_id,evidence_id) VALUES(?,?)", [(link["id"], evidence_id) for evidence_id in link["evidence"]])


def row_dict(row: sqlite3.Row, json_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    result = dict(row)
    for key in json_fields:
        if key in result:
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    if "synthetic" in result:
        result["synthetic"] = bool(result["synthetic"])
    return result


def get_case_payload(db: sqlite3.Connection, case_id: str) -> dict[str, Any] | None:
    case_row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case_row:
        return None
    entities = [row_dict(row, ("attributes_json",)) for row in db.execute("SELECT * FROM entities WHERE case_id=? ORDER BY type, display_label", (case_id,))]
    sources = [row_dict(row) for row in db.execute("SELECT * FROM sources WHERE case_id=? ORDER BY name", (case_id,))]
    evidence = [row_dict(row, ("details_json",)) for row in db.execute("SELECT * FROM evidence WHERE case_id=? ORDER BY observed_at, id", (case_id,))]
    links = [row_dict(row, ("score_breakdown_json",)) for row in db.execute("SELECT * FROM links WHERE case_id=? ORDER BY score DESC", (case_id,))]
    for link in links:
        link["evidence_ids"] = [r[0] for r in db.execute("SELECT evidence_id FROM link_evidence WHERE link_id=? ORDER BY evidence_id", (link["id"],))]
        breakdown = link.get("score_breakdown") or {}
        link["has_conflicts"] = breakdown.get("has_conflicts", False)
        link["dossier"] = breakdown.get("dossier", {})
    audit = [row_dict(row) for row in db.execute("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp DESC, id DESC", (case_id,))]
    return {"case": row_dict(case_row), "entities": entities, "sources": sources, "evidence": evidence, "links": links, "audit_events": audit}
