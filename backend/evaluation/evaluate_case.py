"""Compare an exported case payload against the private synthetic answer key."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.analysis import analyze_case

HERE = Path(__file__).resolve().parent


def main(payload_path: str) -> int:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    answer_key = json.loads((HERE / "answer_key.json").read_text(encoding="utf-8"))
    actual = {row["id"]: row for row in payload.get("links", [])}
    results: list[tuple[str, bool, str]] = []
    for expected in answer_key["links"]:
        row = actual.get(expected["id"])
        if row is None:
            results.append((expected["id"], expected["expected"] == "decoy", "missing candidate"))
            continue
        endpoints_match = {row["from_entity_id"], row["to_entity_id"]} == {expected["from"], expected["to"]}
        score = float(row["score"])
        status = row["review_status"]
        if expected["expected"] == "strong":
            passed = endpoints_match and score >= expected["minimum_score"] and status != "accepted"
        elif expected["expected"] == "weak":
            passed = endpoints_match and score <= expected["maximum_score"] and status == expected["required_status"]
        else:
            passed = endpoints_match and score < expected["maximum_score"] and status != "accepted"
        results.append((expected["id"], passed, f"score={score:.2f}, state={status}"))
    audit = payload.get("audit_events", [])
    unlogged_decisions = [
        row["id"] for row in actual.values()
        if row["review_status"] in {"accepted", "rejected"}
        and not any(
            event.get("target_id") == row["id"]
            and event.get("action", "").endswith(f"->{row['review_status']}")
            for event in audit
        )
    ]
    results.append(("explicit-review-audit", not unlogged_decisions,
                    "every accept/reject has a matching audit event" if not unlogged_decisions
                    else f"decisions without matching audit events: {', '.join(unlogged_decisions)}"))

    edge_fixture = json.loads((HERE / "analysis_edge_cases.json").read_text(encoding="utf-8"))
    edge_result = analyze_case(edge_fixture)
    observed_pairs = {
        tuple(sorted((row["from_entity_id"], row["to_entity_id"])))
        for row in edge_result["suggestions"]
    }
    expected_pairs = {tuple(sorted(pair)) for pair in edge_fixture["expected_pairs"]}
    forbidden_pairs = {tuple(sorted(pair)) for pair in edge_fixture["forbidden_pairs"]}
    missing = expected_pairs - observed_pairs
    false_matches = forbidden_pairs & observed_pairs
    results.append(("analysis-positive-edge-cases", not missing,
                    f"{len(expected_pairs) - len(missing)}/{len(expected_pairs)} exact identifier/infrastructure pairs found"))
    results.append(("analysis-negative-edge-cases", not false_matches,
                    f"{len(false_matches)} forbidden lookalike/boilerplate/banner pairs suggested"))
    observed_behavior = {
        tuple(sorted((row["from_entity_id"], row["to_entity_id"])))
        for row in edge_result["behavioral_leads"]
    }
    expected_behavior = {tuple(sorted(pair)) for pair in edge_fixture["expected_behavior_pairs"]}
    forbidden_behavior = {tuple(sorted(pair)) for pair in edge_fixture["forbidden_behavior_pairs"]}
    missing_behavior = expected_behavior - observed_behavior
    false_behavior = forbidden_behavior & observed_behavior
    all_capped = all(row["score"] <= 0.45 and row["review_status"] == "needs_more_evidence" for row in edge_result["behavioral_leads"])
    results.append(("activity-positive-edge-cases", not missing_behavior,
                    f"{len(expected_behavior) - len(missing_behavior)}/{len(expected_behavior)} repeated-hour profile pairs found"))
    results.append(("activity-negative-edge-cases", not false_behavior,
                    f"{len(false_behavior)} unrelated or under-sampled pairs suggested"))
    results.append(("activity-leads-remain-weak", all_capped,
                    "all activity-only leads are capped at 45% and require more evidence" if all_capped
                    else "an activity-only lead exceeded its review cap or status rule"))
    for link_id, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} {link_id}: {detail}")
    passed_count = sum(passed for _, passed, _ in results)
    print(f"{passed_count}/{len(results)} synthetic evaluation checks passed")
    true_ids = {row["id"] for row in answer_key["links"] if row["expected"] in {"strong", "weak"}}
    predicted_ids = {link_id for link_id, row in actual.items() if float(row["score"]) >= .30}
    true_positives = len(true_ids & predicted_ids)
    precision = true_positives / len(predicted_ids) if predicted_ids else 0.0
    recall = true_positives / len(true_ids) if true_ids else 0.0
    print(f"Seeded-link fixture-threshold precision: {precision:.0%}; recall: {recall:.0%}")
    print("All results are deterministic synthetic-fixture checks, not measured real-world performance.")
    return 0 if passed_count == len(results) else 1


def run_clean_baseline() -> int:
    """Run evaluation against a fresh, unreviewed Nightjar baseline in a temporary database.

    This preserves any manual analyst decisions recorded in data/darklens.sqlite3.
    """
    import tempfile
    from backend.app import database
    from backend.app.main import export_json

    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-clean-eval-") as temp_dir:
        database.DB_PATH = Path(temp_dir) / "baseline.sqlite3"
        try:
            database.init_db()
            payload = export_json("NIGHTJAR-2026-001")
            temp_export = Path(temp_dir) / "nightjar_clean_export.json"
            temp_export.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return main(str(temp_export))
        finally:
            database.DB_PATH = original_db_path


if __name__ == "__main__":
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in {"--disposable", "--clean-baseline"}):
        raise SystemExit(run_clean_baseline())
    if len(sys.argv) == 2:
        raise SystemExit(main(sys.argv[1]))
    raise SystemExit("Usage: python -m backend.evaluation.evaluate_case [case-export.json | --disposable]")
