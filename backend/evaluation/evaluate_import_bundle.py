"""Import a synthetic case into a disposable database and compare its leads to an answer key."""

from __future__ import annotations

import json
from itertools import combinations
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from backend.app import database
from backend.app.main import get_case, import_case


def _threshold(text: str, operator: str) -> float:
    match = re.search(rf"{re.escape(operator)}\s*([0-9.]+)", text)
    if not match:
        raise ValueError(f"Cannot read {operator} score threshold from {text!r}")
    return float(match.group(1))


def evaluate_bundle_metrics(bundle_path: str, answer_path: str) -> dict[str, Any]:
    """Execute bundle evaluation in an isolated database and return structured metrics."""
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    answer = json.loads(Path(answer_path).read_text(encoding="utf-8"))
    original_db_path = database.DB_PATH
    with tempfile.TemporaryDirectory(prefix="darklens-import-eval-") as temp_dir:
        database.DB_PATH = Path(temp_dir) / "evaluation.sqlite3"
        try:
            database.init_db()
            imported = import_case(bundle)
            payload = get_case(imported["case"]["id"])
        finally:
            database.DB_PATH = original_db_path

    # Imports namespace IDs that collide with records already in the workspace.
    # Translate answer-key entity IDs to their persisted IDs before comparing.
    entity_id_map = {
        item["original_id"]: item["imported_id"]
        for item in imported.get("remapped_ids", [])
        if item["record_type"] == "entity"
    }
    map_pair = lambda pair: frozenset(entity_id_map.get(entity_id, entity_id) for entity_id in pair)
    by_pair = {
        frozenset((row["from_entity_id"], row["to_entity_id"])): row
        for row in payload["links"]
    }
    entity_types = {entity_id_map.get(entity["id"], entity["id"]): entity["type"] for entity in bundle.get("entities", [])}
    outcomes: list[tuple[str, bool, str]] = []
    expected_positive_pairs: set[frozenset[str]] = set()
    expected_decoy_pairs: set[frozenset[str]] = set()

    for item in answer.get("links", []):
        pair = map_pair(item["pair"])
        row = by_pair.get(pair)
        kind = item["type"]
        if kind in {"strong", "weak"}:
            expected_positive_pairs.add(pair)
            if kind == "strong":
                threshold = _threshold(item["expected_score"], ">=")
                passed = row is not None and row["score"] >= threshold and row["review_status"] != "accepted"
            else:
                threshold = _threshold(item["expected_score"], "<=")
                passed = row is not None and row["score"] <= threshold and row["review_status"] == "needs_more_evidence"
        else:
            expected_decoy_pairs.add(pair)
            threshold = _threshold(item["expected_score"], "<")
            passed = row is None or (row["score"] < threshold and row["review_status"] != "accepted")
        detail = "no candidate" if row is None else f"score={row['score']:.3f}, status={row['review_status']}"
        outcomes.append((item["id"], passed, detail))

    # Treat unlisted handle-to-handle edges inside a declared persona as cluster-consistent.
    for persona in answer.get("personas", []):
        members = [entity_id_map.get(entity_id, entity_id) for entity_id in persona.get("entities", []) if entity_types.get(entity_id_map.get(entity_id, entity_id)) == "handle"]
        expected_positive_pairs.update(frozenset(pair) for pair in combinations(members, 2))

    # Integrity & Safety Checks:
    # 1. No candidate link is accepted automatically upon import/analysis
    auto_accepted = [row["id"] for row in payload["links"] if row["review_status"] == "accepted"]
    outcomes.append((
        "no-auto-acceptance",
        len(auto_accepted) == 0,
        "0 candidate links automatically accepted" if not auto_accepted else f"auto-accepted: {', '.join(auto_accepted)}"
    ))

    # 2. Every candidate link cites existing evidence records
    case_evidence_ids = {obs["id"] for obs in payload["evidence"]}
    unsupported = [
        row["id"] for row in payload["links"]
        if not row["evidence_ids"] or not set(row["evidence_ids"]).issubset(case_evidence_ids)
    ]
    outcomes.append((
        "evidence-provenance",
        len(unsupported) == 0,
        "all candidate links cite valid evidence records" if not unsupported else f"unsupported links: {', '.join(unsupported)}"
    ))

    # 3. All scores are bounded in [0.0, 1.0]
    out_of_bounds = [row["id"] for row in payload["links"] if not (0.0 <= float(row["score"]) <= 1.0)]
    outcomes.append((
        "score-bounds",
        len(out_of_bounds) == 0,
        "all scores within [0.0, 1.0]" if not out_of_bounds else f"out-of-bounds: {', '.join(out_of_bounds)}"
    ))

    detected_positive = expected_positive_pairs & set(by_pair)
    missed = expected_positive_pairs - detected_positive
    decoy_matches = expected_decoy_pairs & set(by_pair)
    unexpected = set(by_pair) - expected_positive_pairs - expected_decoy_pairs
    predicted_scored_pairs = {pair for pair, row in by_pair.items() if float(row["score"]) >= 0.30}
    precision = len(predicted_scored_pairs & expected_positive_pairs) / max(1, len(predicted_scored_pairs))
    recall = len(detected_positive) / max(1, len(expected_positive_pairs))

    graph_entities = {endpoint for row in payload["links"] for endpoint in (row["from_entity_id"], row["to_entity_id"])}
    linked_evidence = {evidence_id for row in payload["links"] for evidence_id in row["evidence_ids"]}
    for observation in payload["evidence"]:
        if observation["id"] not in linked_evidence:
            continue
        if observation.get("entity_id"):
            graph_entities.add(observation["entity_id"])
        details = observation.get("details", {})
        if details.get("actor_entity_id"):
            graph_entities.add(details["actor_entity_id"])
        graph_entities.update(details[field] for field in ("key", "wallet") if details.get(field) in {entity["id"] for entity in payload["entities"]})
    graph_entity_count = sum(entity["id"] in graph_entities for entity in payload["entities"])

    checks_passed = sum(1 for _, passed, _ in outcomes if passed)
    checks_total = len(outcomes)

    return {
        "case_id": payload["case"]["id"],
        "case_title": payload["case"]["title"],
        "entity_count": imported["entity_count"],
        "observation_count": imported["observation_count"],
        "candidate_link_count": imported["candidate_link_count"],
        "outcomes": outcomes,
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "checks_failed": checks_total - checks_passed,
        "expected_positive_pairs": [sorted(list(p)) for p in expected_positive_pairs],
        "detected_positive_pairs": [sorted(list(p)) for p in detected_positive],
        "missed_positive_pairs": [sorted(list(p)) for p in missed],
        "expected_decoy_pairs": [sorted(list(p)) for p in expected_decoy_pairs],
        "detected_decoy_pairs": [sorted(list(p)) for p in decoy_matches],
        "unexpected_pairs": [sorted(list(p)) for p in unexpected],
        "predicted_scored_pairs": [sorted(list(p)) for p in predicted_scored_pairs],
        "precision_at_030": precision,
        "recall": recall,
        "auto_accepted_count": len(auto_accepted),
        "unsupported_links_count": len(unsupported),
        "score_out_of_bounds_count": len(out_of_bounds),
        "integrity_passed": len(auto_accepted) == 0 and len(unsupported) == 0 and len(out_of_bounds) == 0,
        "graph_visible_entity_count": graph_entity_count,
        "review_queue_states": sorted({row["review_status"] for row in payload["links"]}),
    }


def evaluate(bundle_path: str, answer_path: str, verbose: bool = True) -> int:
    metrics = evaluate_bundle_metrics(bundle_path, answer_path)
    if verbose:
        for name, passed, detail in metrics["outcomes"]:
            print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")

        print(f"\nImported {metrics['entity_count']} entities, {metrics['observation_count']} observations, and {metrics['candidate_link_count']} candidate links.")
        print(f"Answer-key positive-pair recall: {len(metrics['detected_positive_pairs'])}/{len(metrics['expected_positive_pairs'])} ({metrics['recall']:.0%})")
        print(f"Candidate precision at 0.30 review-score threshold: {metrics['precision_at_030']:.0%}")
        print(f"Decoy pairs suggested: {len(metrics['detected_decoy_pairs'])}/{len(metrics['expected_decoy_pairs'])}")

        add_str = ", ".join(" ↔ ".join(p) for p in metrics["unexpected_pairs"]) or "none"
        print(f"Additional candidate pairs: {add_str}")
        print(f"Review queue states: {', '.join(metrics['review_queue_states']) or 'empty'}")
        print(f"Graph-visible entities: {metrics['graph_visible_entity_count']}/{metrics['entity_count']}; candidate edges: {metrics['candidate_link_count']}")
        print(f"\n{metrics['checks_passed']}/{metrics['checks_total']} answer-key & integrity checks passed. Synthetic fixture evaluation only; not real-world accuracy.")
        if metrics["missed_positive_pairs"]:
            print("Missed positive pairs:", ", ".join(" ↔ ".join(p) for p in metrics["missed_positive_pairs"]))

    return 0 if metrics["checks_failed"] == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m backend.evaluation.evaluate_import_bundle case.json answer_key.json")
    raise SystemExit(evaluate(sys.argv[1], sys.argv[2]))
