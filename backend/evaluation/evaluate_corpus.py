"""Run the synthetic answer-key evaluator across a folder of case bundles."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from backend.evaluation.evaluate_import_bundle import evaluate_bundle_metrics

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
DEFAULT_HOLDOUT_DIR = Path(__file__).resolve().parent / "holdout"


def run_corpus_evaluation(directory: str | Path | list[Path] | None = None, verbose: bool = False) -> int:
    if isinstance(directory, list):
        roots = directory
    elif directory:
        roots = [Path(directory)]
    else:
        roots = [DEFAULT_CORPUS_DIR]

    for root in roots:
        if not root.exists():
            raise SystemExit(f"Directory not found: {root}")

    case_files = sorted(case_file for root in roots for case_file in root.rglob("*_case.json"))
    if not case_files:
        raise SystemExit(f"No *_case.json bundles found under {[str(r) for r in roots]}")

    target_str = ", ".join(str(r) for r in roots)
    print("=" * 80)
    print("DARKLENS SYNTHETIC CORPUS & HOLDOUT EVALUATION")
    print(f"Target directory: {target_str}")
    print("=" * 80)

    results: list[dict[str, Any]] = []
    failures: list[str] = []

    total_checks_passed = 0
    total_checks = 0
    total_expected_positives = 0
    total_detected_positives = 0
    total_predicted_at_030 = 0
    total_tp_at_030 = 0
    total_expected_decoys = 0
    total_detected_decoys = 0
    total_auto_accepted = 0
    total_unsupported_links = 0

    for case_path in case_files:
        case_name = case_path.name.removesuffix("_case.json")
        answer_path = case_path.with_name(f"{case_name}_answer_key.json")
        if not answer_path.exists():
            print(f"SKIP {case_path.name}: matching {answer_path.name} not found")
            continue

        metrics = evaluate_bundle_metrics(str(case_path), str(answer_path))
        results.append(metrics)

        total_checks_passed += metrics["checks_passed"]
        total_checks += metrics["checks_total"]
        total_expected_positives += len(metrics["expected_positive_pairs"])
        total_detected_positives += len(metrics["detected_positive_pairs"])

        # Precision @ 0.30
        scored_pairs = set(tuple(p) for p in metrics["predicted_scored_pairs"])
        expected_pos_set = set(tuple(p) for p in metrics["expected_positive_pairs"])
        tp_count = len(scored_pairs & expected_pos_set)
        total_tp_at_030 += tp_count
        total_predicted_at_030 += len(scored_pairs)

        total_expected_decoys += len(metrics["expected_decoy_pairs"])
        total_detected_decoys += len(metrics["detected_decoy_pairs"])
        total_auto_accepted += metrics["auto_accepted_count"]
        total_unsupported_links += metrics["unsupported_links_count"]

        status = "PASS" if metrics["checks_failed"] == 0 else "FAIL"
        if metrics["checks_failed"] > 0:
            failures.append(case_path.name)

        print(f"\n[{status}] {case_path.name} — {metrics['case_title']} ({metrics['case_id']})")
        print(f"  • Records: {metrics['entity_count']} entities, {metrics['observation_count']} observations → {metrics['candidate_link_count']} candidate links derived")
        print(f"  • Answer-key checks: {metrics['checks_passed']}/{metrics['checks_total']} passed")
        print(f"  • Positive recall: {len(metrics['detected_positive_pairs'])}/{len(metrics['expected_positive_pairs'])} ({metrics['recall']:.0%})")
        print(f"  • Precision (score ≥ 0.30): {metrics['precision_at_030']:.0%}")
        print(f"  • Decoy suggestions: {len(metrics['detected_decoy_pairs'])}/{len(metrics['expected_decoy_pairs'])} surfaced (within allowed bounds)")
        print(f"  • Integrity: auto-accepted = {metrics['auto_accepted_count']}, unsupported links = {metrics['unsupported_links_count']}, score bounds OK = {metrics['score_out_of_bounds_count'] == 0}")

        if verbose or metrics["checks_failed"] > 0:
            for name, passed, detail in metrics["outcomes"]:
                print(f"    {'✓' if passed else '✗'} {name}: {detail}")
            if metrics["missed_positive_pairs"]:
                print(f"    Missed positive pairs: {', '.join(' ↔ '.join(p) for p in metrics['missed_positive_pairs'])}")

    if not results:
        raise SystemExit("No case bundles had a matching answer key.")

    overall_recall = total_detected_positives / max(1, total_expected_positives)
    overall_precision = total_tp_at_030 / max(1, total_predicted_at_030)
    decoy_pass_rate = (total_expected_decoys - total_detected_decoys) / max(1, total_expected_decoys)

    print("\n" + "=" * 80)
    print("CORPUS SUMMARY TABLE")
    print("=" * 80)
    header = f"{'Case File':<24} {'Title':<14} {'Entities':<9} {'Links':<7} {'Checks':<9} {'Recall':<8} {'Prec@0.30':<10} {'Decoys':<8} {'Integrity'}"
    print(header)
    print("-" * len(header))
    for m in results:
        case_file = f"{m['case_id']}"
        title = m['case_title'][:13]
        ent = str(m['entity_count'])
        links = str(m['candidate_link_count'])
        checks = f"{m['checks_passed']}/{m['checks_total']}"
        rec = f"{m['recall']:.0%}"
        prec = f"{m['precision_at_030']:.0%}"
        dec = f"{len(m['detected_decoy_pairs'])}/{len(m['expected_decoy_pairs'])}"
        integ = "PASS" if m['integrity_passed'] else "FAIL"
        print(f"{case_file:<24} {title:<14} {ent:<9} {links:<7} {checks:<9} {rec:<8} {prec:<10} {dec:<8} {integ}")

    print("\n" + "=" * 80)
    print("AGGREGATE CORPUS METRICS")
    print("=" * 80)
    print(f"• Total cases evaluated:        {len(results)}")
    print(f"• Total checks passed:          {total_checks_passed}/{total_checks} ({total_checks_passed/max(1, total_checks):.0%})")
    print(f"• Positive-pair recall:         {total_detected_positives}/{total_expected_positives} ({overall_recall:.0%})")
    print(f"• Candidate precision (@ 0.30): {total_tp_at_030}/{total_predicted_at_030} ({overall_precision:.0%})")
    print(f"• Decoys tested:                {total_expected_decoys} ({total_detected_decoys} surfaced under allowed bounds)")
    print(f"• Auto-accepted links:          {total_auto_accepted} (0 required)")
    print(f"• Unsupported links:            {total_unsupported_links} (0 required)")
    print("=" * 80)
    print("LIMITATIONS AND EVALUATION BOUNDARIES:")
    print("1. All data, entities, and observations are synthetic and fictional.")
    print("2. Fixture metrics evaluate deterministic rule consistency on constructed scenarios.")
    print("3. These scores are review-priority indicators and DO NOT represent real-world")
    print("   attribution accuracy, calibrated identity probabilities, or generalization to arbitrary data.")
    print("=" * 80)

    if failures:
        print(f"\nCASES NEEDING REVIEW: {', '.join(failures)}")
        return 1

    print("\nALL CORPUS EVALUATION CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    is_verbose = "-v" in sys.argv or "--verbose" in sys.argv
    if "--all" in sys.argv:
        targets: list[Path] | Path | None = [DEFAULT_CORPUS_DIR, DEFAULT_HOLDOUT_DIR]
    elif "--holdout" in sys.argv:
        targets = DEFAULT_HOLDOUT_DIR
    elif "--corpus" in sys.argv:
        targets = DEFAULT_CORPUS_DIR
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        targets = Path(sys.argv[1])
    else:
        targets = None
    raise SystemExit(run_corpus_evaluation(targets, verbose=is_verbose))
