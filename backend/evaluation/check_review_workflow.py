"""Exercise review updates and audit persistence in a disposable SQLite database."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backend.app import database
from backend.app.main import ReviewUpdate, export_csv, export_report, get_case, run_analysis, update_link_review


def main() -> int:
    original_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-review-check-") as directory:
        database.DB_PATH = Path(directory) / "case.sqlite3"
        try:
            database.init_db()
            empty_audit_csv = export_csv("NIGHTJAR-2026-001", "audit")
            if "target_id" not in empty_audit_csv.body.decode("utf-8"):
                raise AssertionError("Empty audit CSV should still include its column header")
            before_analysis = get_case("NIGHTJAR-2026-001")
            preview = run_analysis("NIGHTJAR-2026-001")
            after_analysis = get_case("NIGHTJAR-2026-001")
            if not preview["read_only"] or preview["suggestion_count"] != 2:
                raise AssertionError("Synthetic analysis preview returned unexpected output")
            if before_analysis["links"] != after_analysis["links"] or before_analysis["audit_events"] != after_analysis["audit_events"]:
                raise AssertionError("Analysis preview modified the case or review history")
            print("PASS analysis preview is repeatable and does not alter links or audit history")

            actions = [("L1", "accepted"), ("D1", "rejected"), ("L3", "needs_more_evidence")]
            for link_id, status in actions:
                update_link_review(link_id, ReviewUpdate(status=status, note="disposable workflow check"))

            refreshed = get_case("NIGHTJAR-2026-001")
            states = {link["id"]: link["review_status"] for link in refreshed["links"]}
            if any(states[link_id] != status for link_id, status in actions):
                raise AssertionError(f"Review status did not persist after reload: {states}")
            if len(refreshed["audit_events"]) != len(actions):
                raise AssertionError("Each review action should have one audit event")
            if any(event["note"] != "disposable workflow check" for event in refreshed["audit_events"]):
                raise AssertionError("Audit notes were not preserved")
            report = export_report("NIGHTJAR-2026-001")
            audit_csv = export_csv("NIGHTJAR-2026-001", "audit")
            if "Analyst audit history" not in report.body.decode("utf-8") or "disposable workflow check" not in report.body.decode("utf-8"):
                raise AssertionError("Markdown report omitted the audit history")
            if "target_id" not in audit_csv.body.decode("utf-8") or "L1" not in audit_csv.body.decode("utf-8"):
                raise AssertionError("Audit CSV omitted the recorded review decisions")
            print("PASS review decisions persist after reloading the case payload")
            print("PASS accept, reject, and more-evidence actions each create an audit event")
            print("PASS Markdown report and audit CSV contain the recorded history")
            print("PASS empty audit CSV retains its header row")
            print("PASS all checks used a temporary database; the saved Nightjar case was untouched")
            return 0
        finally:
            database.DB_PATH = original_path


if __name__ == "__main__":
    raise SystemExit(main())
