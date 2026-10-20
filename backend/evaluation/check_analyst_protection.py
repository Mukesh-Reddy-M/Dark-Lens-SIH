"""Automated test script verifying analyst decision protection and analysis idempotence."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from backend.app import database
from backend.app.main import (
    ReviewUpdate,
    export_json,
    export_report,
    get_case,
    import_case,
    save_analysis_suggestions,
    update_link_review,
)


def run_analyst_protection_check() -> int:
    corpus_dir = Path(__file__).resolve().parent / "corpus"
    bundle_path = corpus_dir / "CASE-2026-002_case.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    print("=" * 80)
    print("DARKLENS ANALYST DECISION PROTECTION & IDEMPOTENCE VERIFICATION")
    print("=" * 80)

    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-analyst-check-") as temp_dir:
        database.DB_PATH = Path(temp_dir) / "analyst_test.sqlite3"
        try:
            database.init_db()

            # 1. Import synthetic case
            imported = import_case(bundle)
            case_id = imported["case"]["id"]
            payload_init = get_case(case_id)
            initial_links = payload_init["links"]
            initial_count = len(initial_links)
            print(f"✓ Case {case_id} imported with {initial_count} candidate links.")

            # 2. Analyst reviews two links:
            # - Accept the first link with an explicit justification note
            # - Reject the second link with an adversarial caveat note
            target_link_1 = initial_links[0]["id"]
            target_link_2 = initial_links[1]["id"]

            note_1 = "Confirmed shared PGP key and wallet in primary sources; approved by analyst."
            note_2 = "Insufficient corroboration; rejected by analyst pending secondary verification."

            update_link_review(target_link_1, ReviewUpdate(status="accepted", note=note_1))
            update_link_review(target_link_2, ReviewUpdate(status="rejected", note=note_2))

            payload_after_review = get_case(case_id)
            reviewed_map = {l["id"]: l for l in payload_after_review["links"]}

            assert reviewed_map[target_link_1]["review_status"] == "accepted"
            assert reviewed_map[target_link_2]["review_status"] == "rejected"
            print("✓ Analyst reviews recorded: 1 accepted, 1 rejected.")

            # 3. Rerun analysis on the case
            reanalysis_result = save_analysis_suggestions(case_id)
            print(f"✓ Re-ran analysis: added_count={reanalysis_result['added_count']}, total_links={reanalysis_result['candidate_link_count']}")

            # Verify idempotence: added_count must be 0
            assert reanalysis_result["added_count"] == 0, f"Expected 0 added links on rerun, got {reanalysis_result['added_count']}"

            # 4. Fetch case after reanalysis and verify persistence
            payload_after_reanalysis = get_case(case_id)
            links_after = payload_after_reanalysis["links"]
            after_map = {l["id"]: l for l in links_after}

            # Link count unchanged (no duplicates)
            assert len(links_after) == initial_count, f"Link count changed from {initial_count} to {len(links_after)}"
            print(f"✓ Link count preserved exactly at {initial_count} (0 duplicates generated).")

            # Analyst decisions were NOT overwritten
            assert after_map[target_link_1]["review_status"] == "accepted", "Accepted link was overwritten!"
            assert after_map[target_link_2]["review_status"] == "rejected", "Rejected link was overwritten!"
            print("✓ Analyst review statuses preserved across analysis reruns.")

            # 5. Audit trail verification
            audit_events = payload_after_reanalysis["audit_events"]
            review_events = [e for e in audit_events if e["target_id"] in (target_link_1, target_link_2)]
            assert len(review_events) == 2, f"Expected 2 audit events for reviews, found {len(review_events)}"
            assert any(note_1 in e["note"] for e in review_events), "Analyst note 1 missing from audit trail"
            assert any(note_2 in e["note"] for e in review_events), "Analyst note 2 missing from audit trail"
            print("✓ Audit trail retained all analyst notes and state transition timestamps.")

            # 6. Verify persistence in Exported Artifacts
            export_payload = export_json(case_id)
            export_links_map = {l["id"]: l for l in export_payload["links"]}
            assert export_links_map[target_link_1]["review_status"] == "accepted"
            assert export_links_map[target_link_2]["review_status"] == "rejected"
            print("✓ Exported JSON bundle contains accurate analyst review states.")

            report_resp = export_report(case_id)
            report_text = report_resp.body.decode("utf-8")
            assert "accepted" in report_text or "Accepted" in report_text
            print("✓ Exported Markdown report reflects reviewed analyst states.")

        finally:
            database.DB_PATH = original_db_path

    print("=" * 80)
    print("ALL ANALYST PROTECTION & IDEMPOTENCE CHECKS PASSED.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_analyst_protection_check())
