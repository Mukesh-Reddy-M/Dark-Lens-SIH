"""Automated verification of Evidence Quality, Deduplication, and Contradiction Analysis."""

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


def run_evidence_quality_check() -> int:
    holdout_dir = Path(__file__).resolve().parent / "holdout"
    bundle_path = holdout_dir / "HOLDOUT-2026-004_case.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    print("=" * 80)
    print("DARKLENS EVIDENCE QUALITY & CONTRADICTION ANALYSIS VERIFICATION")
    print("=" * 80)

    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-quality-check-") as temp_dir:
        database.DB_PATH = Path(temp_dir) / "quality_test.sqlite3"
        try:
            database.init_db()

            # 1. Import case with duplicate records, dependent sources, and conflicts
            imported = import_case(bundle)
            case_id = imported["case"]["id"]
            payload = get_case(case_id)
            links = payload["links"]
            print(f"✓ Imported {case_id} ({payload['case']['title']}) with {len(links)} candidate links.")

            # Find primary candidate link (nightshade_lab <-> belladonna_rx)
            primary_link = next(l for l in links if l["from_entity_id"] == "ENT-001" and l["to_entity_id"] == "ENT-002")
            dossier = primary_link.get("dossier") or primary_link.get("score_breakdown", {}).get("dossier", {})
            assert dossier, "Candidate link missing structured dossier"

            # 2. Verify Evidence Provenance Completeness
            supporting = dossier.get("supporting_evidence", [])
            assert len(supporting) >= 2, f"Expected at least 2 supporting evidence items, got {len(supporting)}"
            for s in supporting:
                assert s["observation_id"], "Missing observation_id in provenance"
                assert s["source_id"], "Missing source_id in provenance"
                assert s["source_name"], "Missing source_name in provenance"
                assert 0.0 <= s["source_reliability"] <= 1.0, f"Invalid source_reliability: {s['source_reliability']}"
                assert 0.0 <= s["confidence"] <= 1.0, f"Invalid confidence: {s['confidence']}"
                assert 0.0 <= s["match_strength"] <= 1.0, f"Invalid match_strength: {s['match_strength']}"
                assert 0.0 <= s["quality_weight"] <= 1.0, f"Invalid quality_weight: {s['quality_weight']}"
                assert s["contribution"] >= 0.0, f"Invalid contribution: {s['contribution']}"
                assert s["inference_depth"] >= 1, f"Invalid inference_depth: {s['inference_depth']}"
            print(f"✓ Evidence Provenance Verified: {len(supporting)} supporting signals carry complete distinct factors (source reliability, confidence, match, contribution).")

            # 3. Verify Duplicate & Dependent Evidence Grouping (Non-Inflation)
            grouped = dossier.get("grouped_evidence", [])
            assert any(g["observation_id"] == "OBS-003" for g in grouped), "OBS-003 (mirror of OBS-002) was not grouped in dossier"
            mirror_item = next(g for g in grouped if g["observation_id"] == "OBS-003")
            assert "prevent" in mirror_item["reason"].lower() or "mirror" in mirror_item["reason"].lower()
            print("✓ Duplicate & Dependent Evidence Handling Verified: OBS-003 detected as explicit mirror of OBS-002; grouped and discounted to prevent corroboration inflation.")

            # 4. Verify Source Independence Rating
            source_ind = dossier.get("source_independence", {})
            assert source_ind.get("unique_source_count") >= 2, "Expected 2 independent sources"
            assert source_ind.get("rating") == "high", f"Expected high independence rating, got {source_ind.get('rating')}"
            print(f"✓ Source Independence Verified: Rating is {source_ind.get('rating').upper()} ({source_ind.get('description')}).")

            # 5. Verify Counter-Evidence and Confirmed Contradictions
            # Check candidate link involving ENT-006 <-> ENT-007 (weak link with concurrency)
            concurrency_link = next(l for l in links if l["from_entity_id"] == "ENT-006" and l["to_entity_id"] == "ENT-007")
            c_dossier = concurrency_link.get("dossier") or concurrency_link.get("score_breakdown", {}).get("dossier", {})
            counter_items = c_dossier.get("counter_evidence", [])
            assert len(counter_items) >= 1, "Expected concurrency counter-evidence in ENT-006 <-> ENT-007"
            assert any(c["conflict_type"] == "review_context_inconsistency" for c in counter_items), "Expected review_context_inconsistency"
            assert not any(c["is_confirmed_contradiction"] for c in counter_items), "Concurrency should be review context, not confirmed contradiction"
            print("✓ Review Context Verified: Concurrency observation properly surfaced as review_context_inconsistency without false hard contradiction.")

            # 6. Verify Analyst Decision Protection & Idempotent Dossier Refresh
            update_link_review(primary_link["id"], ReviewUpdate(status="accepted", note="Verified shared PGP key across independent sources."))
            payload_reviewed = get_case(case_id)
            reviewed_link = next(l for l in payload_reviewed["links"] if l["id"] == primary_link["id"])
            assert reviewed_link["review_status"] == "accepted"

            # Rerun analysis
            reanalysis = save_analysis_suggestions(case_id)
            assert reanalysis["added_count"] == 0, "Re-analysis must not add duplicate links"

            payload_after = get_case(case_id)
            after_link = next(l for l in payload_after["links"] if l["id"] == primary_link["id"])
            assert after_link["review_status"] == "accepted", "Analyst acceptance was overwritten by re-analysis!"
            assert after_link.get("dossier"), "Dossier was lost after re-analysis"
            print("✓ Analyst Decision Protection & Dossier Refresh Verified: Accepted status and dossier preserved across re-analysis.")

            # 7. Verify Export Dossier Inclusion (Markdown & JSON)
            json_export = export_json(case_id)
            export_link = next(l for l in json_export["links"] if l["id"] == primary_link["id"])
            assert export_link.get("dossier"), "Export JSON missing candidate dossier"
            assert export_link["dossier"].get("supporting_evidence"), "Export JSON dossier missing supporting evidence"

            report_resp = export_report(case_id)
            report_text = report_resp.body.decode("utf-8")
            assert "Supporting evidence provenance" in report_text, "Markdown report missing supporting evidence provenance"
            assert "Source independence" in report_text, "Markdown report missing source independence section"
            print("✓ Export Fidelity Verified: Markdown report and JSON bundle both export complete evidence dossiers.")

        finally:
            database.DB_PATH = original_db_path

    print("=" * 80)
    print("ALL EVIDENCE QUALITY & CONTRADICTION CHECKS PASSED.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_evidence_quality_check())
