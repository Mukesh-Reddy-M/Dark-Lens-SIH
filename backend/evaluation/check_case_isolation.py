"""Automated test script verifying strict case isolation in DarkLens."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from backend.app import database
from backend.app.main import get_case, get_timeline, import_case


def run_case_isolation_check() -> int:
    corpus_dir = Path(__file__).resolve().parent / "corpus"
    holdout_dir = Path(__file__).resolve().parent / "holdout"

    bundle1_path = corpus_dir / "CASE-2026-002_case.json"
    bundle2_path = holdout_dir / "HOLDOUT-2026-001_case.json"

    bundle1 = json.loads(bundle1_path.read_text(encoding="utf-8"))
    bundle2 = json.loads(bundle2_path.read_text(encoding="utf-8"))

    print("=" * 80)
    print("DARKLENS CASE ISOLATION VERIFICATION")
    print("=" * 80)

    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-isolation-check-") as temp_dir:
        database.DB_PATH = Path(temp_dir) / "isolation_test.sqlite3"
        try:
            database.init_db()

            # Import first case
            res1 = import_case(bundle1)
            case_id1 = res1["case"]["id"]
            print(f"✓ Imported Case 1: {case_id1} ({res1['case']['title']})")

            # Import second case
            res2 = import_case(bundle2)
            case_id2 = res2["case"]["id"]
            print(f"✓ Imported Case 2: {case_id2} ({res2['case']['title']})")

            # Verify Case 1 payload
            payload1 = get_case(case_id1)
            case1_entity_ids = {e["id"] for e in payload1["entities"]}
            case1_evidence_ids = {e["id"] for e in payload1["evidence"]}
            case1_link_ids = {l["id"] for l in payload1["links"]}

            # Verify Case 2 payload
            payload2 = get_case(case_id2)
            case2_entity_ids = {e["id"] for e in payload2["entities"]}
            case2_evidence_ids = {e["id"] for e in payload2["evidence"]}
            case2_link_ids = {l["id"] for l in payload2["links"]}

            # 1. No overlap between entity IDs, evidence IDs, or link IDs
            entity_overlap = case1_entity_ids & case2_entity_ids
            evidence_overlap = case1_evidence_ids & case2_evidence_ids
            link_overlap = case1_link_ids & case2_link_ids

            assert not entity_overlap, f"Leaked entity IDs between cases: {entity_overlap}"
            assert not evidence_overlap, f"Leaked evidence IDs between cases: {evidence_overlap}"
            assert not link_overlap, f"Leaked link IDs between cases: {link_overlap}"
            print("✓ Entity, evidence, and link IDs strictly segregated (0 ID overlap).")

            # 2. Case 1 links only connect Case 1 entities
            for link in payload1["links"]:
                assert link["from_entity_id"] in case1_entity_ids, f"Link {link['id']} connects foreign entity {link['from_entity_id']}"
                assert link["to_entity_id"] in case1_entity_ids, f"Link {link['id']} connects foreign entity {link['to_entity_id']}"
                for eid in link["evidence_ids"]:
                    assert eid in case1_evidence_ids, f"Link {link['id']} references foreign evidence {eid}"
            print(f"✓ Case 1 links ({len(payload1['links'])}) strictly reference Case 1 entities and evidence.")

            # 3. Case 2 links only connect Case 2 entities
            for link in payload2["links"]:
                assert link["from_entity_id"] in case2_entity_ids, f"Link {link['id']} connects foreign entity {link['from_entity_id']}"
                assert link["to_entity_id"] in case2_entity_ids, f"Link {link['id']} connects foreign entity {link['to_entity_id']}"
                for eid in link["evidence_ids"]:
                    assert eid in case2_evidence_ids, f"Link {link['id']} references foreign evidence {eid}"
            print(f"✓ Case 2 links ({len(payload2['links'])}) strictly reference Case 2 entities and evidence.")

            # 4. Evidence associations isolation
            assoc1 = payload1.get("evidence_associations", [])
            for edge in assoc1:
                assert edge["from_entity_id"] in case1_entity_ids, f"Assoc edge connects foreign entity {edge['from_entity_id']}"
                assert edge["to_entity_id"] in case1_entity_ids, f"Assoc edge connects foreign entity {edge['to_entity_id']}"
            print(f"✓ Case 1 evidence associations ({len(assoc1)}) strictly reference Case 1 entities.")

            assoc2 = payload2.get("evidence_associations", [])
            for edge in assoc2:
                assert edge["from_entity_id"] in case2_entity_ids, f"Assoc edge connects foreign entity {edge['from_entity_id']}"
                assert edge["to_entity_id"] in case2_entity_ids, f"Assoc edge connects foreign entity {edge['to_entity_id']}"
            print(f"✓ Case 2 evidence associations ({len(assoc2)}) strictly reference Case 2 entities.")

            # 5. Timeline isolation
            timeline1 = get_timeline(case_id1)
            assert len(timeline1) == len(payload1["evidence"]), "Timeline 1 length does not match evidence count"
            for event in timeline1:
                assert event["id"] in case1_evidence_ids, f"Timeline 1 contains foreign evidence {event['id']}"
            print(f"✓ Case 1 timeline ({len(timeline1)} events) contains exclusively Case 1 observations.")

            timeline2 = get_timeline(case_id2)
            assert len(timeline2) == len(payload2["evidence"]), "Timeline 2 length does not match evidence count"
            for event in timeline2:
                assert event["id"] in case2_evidence_ids, f"Timeline 2 contains foreign evidence {event['id']}"
            print(f"✓ Case 2 timeline ({len(timeline2)} events) contains exclusively Case 2 observations.")

            # 6. Audit trail isolation
            with database.session() as db:
                audit1 = db.execute("SELECT * FROM audit_events WHERE case_id=?", (case_id1,)).fetchall()
                audit2 = db.execute("SELECT * FROM audit_events WHERE case_id=?", (case_id2,)).fetchall()
                assert len(audit1) >= 1 and all(dict(row)["case_id"] == case_id1 for row in audit1)
                assert len(audit2) >= 1 and all(dict(row)["case_id"] == case_id2 for row in audit2)
            print("✓ Audit event logs strictly isolated per case ID.")

        finally:
            database.DB_PATH = original_db_path

    print("=" * 80)
    print("ALL CASE ISOLATION CHECKS PASSED.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_case_isolation_check())
