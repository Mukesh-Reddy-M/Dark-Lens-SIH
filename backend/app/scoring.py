"""Explainable review-priority scoring for the synthetic prototype.

Scores are triage values, not probabilities of identity. The independent-signal
combination lets separate high-quality clues reinforce one another; each signal
is discounted by its source reliability and every contribution is returned.
"""

from __future__ import annotations

from collections.abc import Mapping


def score_link(
    signals: Mapping[str, tuple[float, float] | tuple[float, float, float]], *, cap: float = 1.0
) -> tuple[float, list[dict[str, float | str]]]:
    if not 0 <= cap <= 1:
        raise ValueError("Score cap must be between zero and one")
    remaining = 1.0
    breakdown: list[dict[str, float | str]] = []
    for signal, values in signals.items():
        match, reliability = values[:2]
        evidence_confidence = values[2] if len(values) > 2 else 1.0
        if not 0 <= match <= 1 or not 0 <= reliability <= 1 or not 0 <= evidence_confidence <= 1:
            raise ValueError(f"Signal values for {signal} must be between 0 and 1")
        # A weighted mean keeps source and record quality visible without
        # multiplying two imperfect-but-related quality estimates into an
        # unjustifiably low score.
        quality_weight = 0.70 * reliability + 0.30 * evidence_confidence
        contribution = match * quality_weight
        remaining *= 1.0 - contribution
        breakdown.append({
            "signal": signal,
            "match": match,
            "source_reliability": reliability,
            "evidence_confidence": evidence_confidence,
            "quality_weight": round(quality_weight, 4),
            "contribution": round(contribution, 4),
        })
    raw_score = 1.0 - remaining
    return round(min(raw_score, cap), 4), breakdown


def priority_label(score: float) -> str:
    if score >= 0.85:
        return "high_priority"
    if score >= 0.40:
        return "review"
    return "weak"
