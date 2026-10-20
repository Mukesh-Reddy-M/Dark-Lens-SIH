"""Deterministic, read-only analysis for importer-compatible synthetic cases."""

from __future__ import annotations

from collections import defaultdict
from collections import Counter
from datetime import datetime, timezone
from math import sqrt
import re
from typing import Any

from .scoring import priority_label, score_link


MATCH_FIELDS = {
    "key": ("shared_pgp_key", "identifier"),
    "wallet": ("shared_wallet", "identifier"),
    "certificate": ("certificate_serial_match", "infrastructure"),
    "ip": ("ip_match", "infrastructure"),
}
SIGNAL_CATEGORY = {signal: category for signal, category in MATCH_FIELDS.values()}
ACTIVITY_EVIDENCE_TYPES = {"activity_pattern", "writing_and_activity"}
IDENTIFIER_TYPES = {"pgp_key", "wallet"}
FUNCTION_WORDS = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "had", "has", "have", "he", "her", "his", "i", "if", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "she", "that", "the", "their", "them", "there", "they", "this", "to", "was", "we", "were", "with", "you", "your"}
IDENTIFIER_TOKEN_PATTERNS = (
    re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"),
    re.compile(r"(?<![\w.-])(?:[A-Z0-9-]+\.)+[A-Z]{2,}(?![\w.-])", re.IGNORECASE),
    re.compile(r"\b[a-z2-7]{56}\.onion\b", re.IGNORECASE),
    re.compile(r"\bCS-\d+\b|\bFP\d+\b|\bW\d+\b", re.IGNORECASE),
    re.compile(r"\b0x[a-f0-9]{8,}\b|\b[a-f0-9]{40,64}\b", re.IGNORECASE),
    re.compile(r"\bSYNTH-[A-Z0-9][A-Z0-9-]{3,}\b", re.IGNORECASE),
    re.compile(r"\bbc1[a-z0-9]{25,90}\b", re.IGNORECASE),
    re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
)
NON_ATTRIBUTION_EVIDENCE = {"rumour", "rumor", "tip", "analyst_note", "context_note"}


def _identifier_tokens(value: Any) -> set[str]:
    """Extract exact, typed indicator values without treating ordinary words as IDs."""
    text = str(value or "")
    tokens = {match.group(0).casefold() for pattern in IDENTIFIER_TOKEN_PATTERNS for match in pattern.finditer(text)}
    return {
        token for token in tokens
        if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", token)
        or all(0 <= int(part) <= 255 for part in token.split("."))
    }


def _normalized_record_values(observation: dict[str, Any]) -> list[str]:
    """Flatten scalar values from a record so importers can use arbitrary field names."""
    values = [str(observation.get("summary", ""))]
    details = observation.get("details") or {}
    if isinstance(details, dict):
        for value in details.values():
            values.extend(str(item) for item in (value if isinstance(value, list) else [value]) if isinstance(item, (str, int, float)))
    return values


def _asset_indicator_type(token: str) -> str | None:
    """Classify only high-specificity key and wallet indicators for direct matching."""
    normalized = token.casefold()
    if normalized.startswith("bc1") or re.fullmatch(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}", token):
        return "wallet"
    if re.fullmatch(r"0x[a-f0-9]{40}", normalized) or re.fullmatch(r"(?:synth-)?w\d+", normalized):
        return "wallet"
    if normalized.startswith("fp") or re.fullmatch(r"[a-f0-9]{40,64}", normalized):
        return "key"
    return None


def _indicator_entity_map(entities: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    """Map explicit indicator values in labels/attributes to their owning entities."""
    result: dict[str, set[str]] = defaultdict(set)
    for entity_id, entity in entities.items():
        values = [entity.get("display_label", "")]
        if entity.get("type") in IDENTIFIER_TYPES:
            result[str(entity_id).casefold()].add(entity_id)
        attributes = entity.get("attributes") or {}
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                attribute_values = value if isinstance(value, list) else [value]
                values.extend(attribute_values)
                for attribute_value in attribute_values:
                    if not isinstance(attribute_value, (str, int, float)):
                        continue
                    if re.search(r"key|wallet|fingerprint|certificate|domain|address|ip|identifier|hash", str(key), re.IGNORECASE):
                        result[str(attribute_value).strip().casefold()].add(entity_id)
                    for token in _identifier_tokens(attribute_value):
                        result[token].add(entity_id)
        for value in values:
            for token in _identifier_tokens(value):
                result[token].add(entity_id)
    return result


def _entity_aliases(entity: dict[str, Any]) -> set[str]:
    label = str(entity.get("display_label", "")).strip()
    aliases = {label, label.split(" (", 1)[0].strip()}
    attributes = entity.get("attributes") or {}
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            if re.search(r"alias|handle|username|screen.?name|nickname", str(key), re.IGNORECASE):
                values = value if isinstance(value, list) else [value]
                aliases.update(str(item).strip() for item in values if isinstance(item, str) and len(item.strip()) >= 3)
    return {item for item in aliases if item}


def _entity_mentions(summary: str, entities: dict[str, dict[str, Any]]) -> set[str]:
    """Find exact entity names in text, preferring longer names over substrings."""
    candidates: list[tuple[int, int, str]] = []
    for entity_id, entity in entities.items():
        aliases = _entity_aliases(entity)
        if entity.get("type") in {"service", "marketplace"}:
            base_label = str(entity.get("display_label", "")).split(" (", 1)[0].strip()
            aliases.add(base_label)
            aliases.add(re.sub(r"\s+(?:market|forum|shop|exchange|service)$", "", base_label, flags=re.IGNORECASE).strip())
        for alias in aliases:
            if len(alias) < 3:
                continue
            for match in re.finditer(rf"(?<![\w]){re.escape(alias)}(?![\w])", summary, re.IGNORECASE):
                candidates.append((match.start(), match.end(), entity_id))
    found: set[str] = set()
    occupied: list[tuple[int, int]] = []
    for start, end, entity_id in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0])):
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        found.add(entity_id)
        occupied.append((start, end))
    return found


def _handle_mentions(summary: str, entities: dict[str, dict[str, Any]]) -> list[str]:
    """Resolve only exact handle labels explicitly named in an observation."""
    found = []
    for entity_id, entity in entities.items():
        if entity.get("type") != "handle":
            continue
        if any(re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", summary, re.IGNORECASE) for alias in _entity_aliases(entity)):
            found.append(entity_id)
    return found


def enrich_observation_details(observation: dict[str, Any], entities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Extract explicit synthetic identifiers from summaries for graph display.

    This intentionally does not infer identity from handle resemblance, banners,
    generic phrases, or blockchain co-spending.
    """
    details = dict(observation.get("details") or {})
    summary = str(observation.get("summary", ""))
    owner_id = observation.get("entity_id")
    owner = entities.get(owner_id, {})
    handle_ids = _handle_mentions(summary, entities)

    if owner.get("type") in IDENTIFIER_TYPES and len(handle_ids) == 1:
        details.setdefault("actor_entity_id", handle_ids[0])
        details.setdefault("key" if owner["type"] == "pgp_key" else "wallet", owner_id)

    if owner.get("type") in {"service", "infrastructure"}:
        certificate = re.search(r"\bCS-\d+\b", summary, re.IGNORECASE)
        address = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", summary)
        if certificate:
            details.setdefault("certificate", certificate.group(0).upper())
        if address:
            details.setdefault("ip", address.group(0))
    return details


def _activity_leads(payload: dict[str, Any], entities: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare explicit schedules and sufficiently sampled UTC activity windows."""
    profiles: dict[str, dict[str, Any]] = defaultdict(lambda: {"records": [], "features": set(), "confidences": [], "observations": []})
    day_names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    for observation in payload.get("evidence", []):
        entity_id = observation.get("entity_id")
        if not entity_id or entities.get(entity_id, {}).get("type") != "handle":
            continue
        kind = str(observation.get("evidence_type", observation.get("type", ""))).casefold()
        if "activity" not in kind and "posting_pattern" not in kind:
            continue
        summary = str(observation.get("summary", ""))
        if re.search(r"too short|insufficient sample|not enough data|unreliable sample|uncertain", summary, re.IGNORECASE):
            continue
        profiles[entity_id]["confidences"].append(float(observation.get("confidence", 0.75)))
        profiles[entity_id]["observations"].append(observation)
        if re.search(r"\bweekends?\b", summary, re.IGNORECASE):
            profiles[entity_id]["features"].add("days:weekend")
        if re.search(r"\bweekdays?\b", summary, re.IGNORECASE):
            profiles[entity_id]["features"].add("days:weekday")
        for day in day_names:
            if re.search(rf"\b{day}s?\b", summary, re.IGNORECASE):
                profiles[entity_id]["features"].add(f"day:{day}")
        for match in re.finditer(r"\b(\d{1,2}):?00?\s*(?:-|to|through)\s*(\d{1,2}):?00?\s*(?:UTC|GMT)?\b", summary, re.IGNORECASE):
            start, end = int(match.group(1)), int(match.group(2))
            if 0 <= start < 24 and 0 <= end <= 24:
                profiles[entity_id]["features"].update(f"hour:{hour}" for hour in range(start, max(start + 1, end)))
        for part in ("morning", "afternoon", "evening", "night", "midday"):
            if re.search(rf"\b{part}\b", summary, re.IGNORECASE):
                profiles[entity_id]["features"].add(f"daypart:{part}")
        observed_at = observation.get("observed_at")
        if not observed_at or "posting_pattern" in kind:
            continue
        try:
            timestamp = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        except ValueError:
            continue
        timestamp = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        profiles[entity_id]["records"].append((timestamp, observation))

    candidates: list[dict[str, Any]] = []
    eligible = {}
    for entity_id, profile in profiles.items():
        records = profile["records"]
        dates = {timestamp.date() for timestamp, _ in records}
        histogram: dict[int, float] = defaultdict(float)
        if len(records) >= 3 and len(dates) >= 2:
            for timestamp, _ in records:
                histogram[timestamp.hour] += 1 / len(records)
                profile["features"].add(f"hour:{timestamp.hour}")
        reliability_values = [float(sources.get(obs.get("source_id"), {}).get("reliability", 0)) for _, obs in records]
        reliability_values.extend(float(sources.get(obs.get("source_id"), {}).get("reliability", 0)) for obs in payload.get("evidence", []) if obs.get("entity_id") == entity_id and "posting_pattern" in str(obs.get("evidence_type", "")).casefold())
        if not profile["features"] and not histogram:
            continue
        eligible[entity_id] = {
            "histogram": histogram,
            "records": records,
            "observations": profile["observations"],
            "features": profile["features"],
            "reliability": sum(reliability_values) / len(reliability_values) if reliability_values else 0.65,
            "confidence": sum(profile["confidences"]) / len(profile["confidences"]) if profile["confidences"] else 0.75,
        }

    ids = sorted(eligible)
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            left_profile, right_profile = eligible[left], eligible[right]
            overlap = sum(min(left_profile["histogram"].get(hour, 0), right_profile["histogram"].get(hour, 0)) for hour in range(24))
            common_features = left_profile["features"] & right_profile["features"]
            feature_overlap = len(common_features) / max(1, len(left_profile["features"] | right_profile["features"]))
            if overlap < 0.5 and not common_features:
                continue
            reliability = min(left_profile["reliability"], right_profile["reliability"])
            raw_match = max(overlap, feature_overlap)
            score, breakdown = score_link({"activity_pattern_overlap": (raw_match, reliability, min(left_profile["confidence"], right_profile["confidence"]))}, cap=0.45)
            records = left_profile["records"] + right_profile["records"]
            evidence_ids = {record["id"] for _, record in records} | {obs["id"] for obs in left_profile["observations"] + right_profile["observations"]}
            candidates.append({
                "from_entity_id": left,
                "to_entity_id": right,
                "from_label": entities[left]["display_label"],
                "to_label": entities[right]["display_label"],
                "relation": "similar_posting_pattern",
                "score": score,
                "priority": priority_label(score),
                "signals": breakdown,
                "evidence_ids": sorted(evidence_ids),
                "sample_counts": {left: len(left_profile["records"]), right: len(right_profile["records"])},
                "review_status": "needs_more_evidence",
                "score_is_probability": False,
                "caution": "Schedule overlap is a weak behavioural clue. Shared routines are common and do not identify the same operator.",
            })
    candidates.sort(key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"]))
    return candidates


def _explicit_style_leads(payload: dict[str, Any], entities: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare generic, explicitly reported writing traits; never infer from raw handles."""
    by_handle: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for observation in payload.get("evidence", []):
        kind = observation.get("evidence_type", observation.get("type"))
        if kind != "writing_style":
            continue
        owner_id = observation.get("entity_id")
        owners = [owner_id] if entities.get(owner_id, {}).get("type") == "handle" else _handle_mentions(str(observation.get("summary", "")), entities)
        summary = str(observation.get("summary", ""))
        if re.search(r"too short|insufficient sample|not enough data|unreliable sample|uncertain", summary, re.IGNORECASE):
            continue
        markers = {f"quoted:{match.group(1).strip().casefold().strip(' .,!?:;') }" for match in re.finditer(r"['\"]([^'\"]{2,80})['\"]", summary)}
        for match in re.finditer(r"\buses?\s+(?:the\s+)?(?:rare\s+)?word\s+['\"]?([\w-]{3,})", summary, re.IGNORECASE):
            markers.add(f"word:{match.group(1).casefold()}")
        for match in re.finditer(r"\bmixes?\s+([a-z]+)\s+with\s+([a-z]+)\s+words?\b", summary, re.IGNORECASE):
            markers.add(f"language_pair:{match.group(1).casefold()}:{match.group(2).casefold()}")
        if re.search(r"two spaces after|double[- ]space", summary, re.IGNORECASE):
            markers.add("punctuation:double_space_after_period")
        if re.search(r"DD[- ]Mon[- ]YYYY|day[- ]month[- ]year date", summary, re.IGNORECASE):
            markers.add("date_format:day_month_year")
        for entity_id in owners:
            for marker in markers:
                by_handle[entity_id][marker].append(observation)

    leads = []
    handle_ids = sorted(by_handle)
    exact_pairs = set()
    for index, left in enumerate(handle_ids):
        for right in handle_ids[index + 1:]:
            common = set(by_handle[left]) & set(by_handle[right])
            if not common:
                continue
            common_records = [record for marker in common for record in by_handle[left][marker] + by_handle[right][marker]]
            reliability_values = [float(sources.get(record.get("source_id"), {}).get("reliability", 0)) for record in common_records]
            reliability = min(reliability_values, default=0.0)
            confidence = min((float(record.get("confidence", 0.75)) for record in common_records), default=0.75)
            score, breakdown = score_link({"explicit_style_marker_overlap": (min(1.0, len(common) / 4), reliability, confidence)}, cap=0.45)
            evidence_ids = {record["id"] for record in common_records}
            # Keep explicit concurrency/uncertainty notes in the evidence trail, not as support.
            for observation in payload.get("evidence", []):
                summary = str(observation.get("summary", ""))
                if left in _handle_mentions(summary, entities) and right in _handle_mentions(summary, entities) and re.search(r"same time|active in|overlap", summary, re.IGNORECASE):
                    evidence_ids.add(observation["id"])
            exact_pairs.add((left, right))
            leads.append({
                "from_entity_id": left,
                "to_entity_id": right,
                "from_label": entities[left]["display_label"],
                "to_label": entities[right]["display_label"],
                "relation": "weak_reported_style_similarity",
                "score": score,
                "priority": priority_label(score),
                "signals": breakdown,
                "evidence_ids": sorted(evidence_ids),
                "review_status": "needs_more_evidence",
                "score_is_probability": False,
                "caution": "A few explicitly described style markers overlap. This is weak, synthetic-only evidence; concurrent activity or other contrary clues must be reviewed, and style similarity does not establish a shared operator.",
            })
    leads.sort(key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"]))
    return leads


def _raw_text_style_leads(payload: dict[str, Any], entities: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare sufficiently large, explicitly supplied sample text using local features."""
    samples: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for observation in payload.get("evidence", []):
        owner = observation.get("entity_id")
        if not owner or entities.get(owner, {}).get("type") != "handle":
            continue
        kind = str(observation.get("evidence_type", "")).casefold()
        details = observation.get("details") or {}
        text = ""
        if isinstance(details, dict):
            for field in ("raw_text", "content", "body", "sample_text"):
                if isinstance(details.get(field), str):
                    text = details[field]
                    break
        if not text and any(term in kind for term in ("raw_post", "raw_listing", "writing_sample", "message_text", "listing_text", "post_text")):
            text = str(observation.get("summary", ""))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 80:
            samples[owner].append((text[:4000], observation))

    def vector(texts: list[str]) -> Counter[str]:
        combined = " ".join(texts).casefold()
        words = re.findall(r"[a-z']+", combined)
        grams = Counter(combined[index:index + 3] for index in range(max(0, len(combined) - 2)) if combined[index:index + 3].strip())
        word_counts = Counter(f"function:{word}" for word in words if word in FUNCTION_WORDS)
        grams.update(word_counts)
        return grams

    def cosine(left: Counter[str], right: Counter[str]) -> float:
        shared = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in shared)
        denominator = sqrt(sum(value * value for value in left.values()) * sum(value * value for value in right.values()))
        return numerator / denominator if denominator else 0.0

    eligible = {}
    for entity_id, records in samples.items():
        unique_texts = list(dict.fromkeys(text for text, _ in records))[:100]
        if len(unique_texts) < 3 or sum(map(len, unique_texts)) < 300:
            continue
        eligible[entity_id] = (vector(unique_texts), records[:100], unique_texts)

    leads = []
    ids = sorted(eligible)
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            similarity = cosine(eligible[left][0], eligible[right][0])
            if similarity < 0.52:
                continue
            # Very high overlap is more consistent with copied text than a
            # distinctive author signal, so keep it below the lead threshold.
            exact_overlap = max(cosine(vector([a]), vector([b])) for a in eligible[left][2] for b in eligible[right][2])
            if exact_overlap > 0.96:
                continue
            observations = [item[1] for item in eligible[left][1] + eligible[right][1]]
            reliability = min((float(sources.get(item.get("source_id"), {}).get("reliability", 0.65)) for item in observations), default=0.65)
            confidence = min((float(item.get("confidence", 0.75)) for item in observations), default=0.75)
            score, breakdown = score_link({"character_ngram_and_function_word_similarity": (similarity, reliability, confidence)}, cap=0.45)
            leads.append({
                "from_entity_id": left, "to_entity_id": right,
                "from_label": entities[left]["display_label"], "to_label": entities[right]["display_label"],
                "relation": "weak_raw_text_style_similarity", "score": score, "priority": priority_label(score),
                "signals": breakdown, "evidence_ids": sorted({item["id"] for item in observations}),
                "sample_counts": {left: len(eligible[left][1]), right: len(eligible[right][1])},
                "review_status": "needs_more_evidence", "score_is_probability": False,
                "caution": "Local character n-gram and function-word similarity is a weak lead. Shared templates, copied text, short samples, and language differences can distort it; review the source samples manually.",
            })
    return sorted(leads, key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"]))


def _reference_leads(payload: dict[str, Any], entities: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build explainable direct and multi-hop leads from explicit record references.

    The extractor uses the import schema, entity labels/attributes, and ordinary
    typed indicators in summaries. It does not depend on fixture names or IDs.
    """
    indicator_map = _indicator_entity_map(entities)
    edges: dict[tuple[str, str], dict[str, Any]] = {}

    def add_edge(left: str, right: str, observation: dict[str, Any], signal: str, base: float, caution: str = "") -> None:
        if left == right or left not in entities or right not in entities:
            return
        pair = tuple(sorted((left, right)))
        source_reliability = float(sources.get(observation.get("source_id"), {}).get("reliability", 0.65))
        record_confidence = float(observation.get("confidence", 0.75))
        summary = " ".join(_normalized_record_values(observation))
        details = observation.get("details") or {}
        common_flag = isinstance(details, dict) and any(
            details.get(field) is True
            for field in ("common", "shared_publicly", "boilerplate", "counter_evidence")
        )
        if common_flag or re.search(r"shared by many|common (?:template|banner|phrase|identifier)|default (?:icon|banner|credential)|boilerplate|unrelated organisation|unrelated organization|no funds (?:move|transfer)|not the same|different (?:owner|operator)|shared hosting", summary, re.IGNORECASE):
            base = min(base, 0.20)
            caution = caution or "The record contains a common-indicator or contradictory-context warning."
        if signal == "explicit_identifier_association":
            token_frequency = max((len(indicator_map.get(token, set())) for token in _identifier_tokens(summary)), default=0)
            if token_frequency > 2:
                base = min(base, 0.20)
                caution = caution or "This indicator is attached to several entities in the case, so it has low discriminating value."
        quality_weight = 0.70 * source_reliability + 0.30 * record_confidence
        score = min(1.0, base * quality_weight)
        row = edges.setdefault(pair, {"weight": score, "signals": [], "evidence_ids": set(), "cautions": set()})
        row["weight"] = max(row["weight"], score)
        row["signals"].append({"signal": signal, "match": base, "source_reliability": source_reliability, "evidence_confidence": record_confidence, "quality_weight": round(quality_weight, 4), "contribution": round(score, 4), "evidence_id": observation["id"]})
        row["evidence_ids"].add(observation["id"])
        if caution:
            row["cautions"].add(caution)

    for observation in payload.get("evidence", []):
        owner = observation.get("entity_id")
        if owner not in entities:
            continue
        kind = str(observation.get("evidence_type", observation.get("type", ""))).casefold().replace("-", "_")
        if kind in NON_ATTRIBUTION_EVIDENCE or any(term in kind for term in ("rumour", "rumor", "tip", "analyst_note", "context_note")):
            continue
        summary = str(observation.get("summary", ""))
        referenced = _entity_mentions(summary, entities)
        tokens = _identifier_tokens(summary)
        for value in _normalized_record_values(observation):
            tokens.update(_identifier_tokens(value))
            exact_value = value.strip().casefold()
            referenced.update(indicator_map.get(exact_value, set()))
        referenced.update(entity_id for token in tokens for entity_id in indicator_map.get(token, set()))
        owner_type = entities[owner].get("type")
        identity_kind = any(term in kind for term in ("key", "wallet", "payment", "profile", "transfer", "identifier", "fingerprint"))
        infrastructure_kind = any(term in kind for term in ("status", "certificate", "dns", "ssh", "fingerprint", "banner", "favicon", "infrastructure", "host"))
        co_input = bool(re.search(r"co[- ]?inputs?|together as inputs|both inputs|same transaction spends", summary, re.IGNORECASE))
        explicit_subnet = bool(re.search(r"same (?:/\d+|subnet|network|address range)", summary, re.IGNORECASE))

        for target in referenced:
            if target == owner:
                continue
            target_type = entities[target].get("type")
            base = 0.0
            signal = "explicit_entity_reference"
            caution = ""
            if ((owner_type in IDENTIFIER_TYPES and target_type == "handle") or (owner_type == "handle" and target_type in IDENTIFIER_TYPES)):
                base, signal = 0.96, "explicit_identifier_association"
            elif owner_type == "handle" and target_type in {"service", "marketplace", "infrastructure"} and (infrastructure_kind or "profile" in kind):
                base, signal, caution = 0.58, "explicit_contextual_infrastructure_reference", "An account-to-infrastructure reference is contextual evidence and does not show common control."
            elif owner_type in {"service", "marketplace", "infrastructure"} and target_type == "handle" and (infrastructure_kind or "profile" in kind):
                base, signal, caution = 0.58, "explicit_contextual_infrastructure_reference", "An account-to-infrastructure reference is contextual evidence and does not show common control."
            elif "profile" in kind and owner_type == "handle" and target_type in {"service", "marketplace"}:
                base, signal, caution = 0.72, "explicit_marketplace_presence", "Marketplace presence is contextual evidence and does not establish that two accounts share an operator."
            elif identity_kind and co_input and owner_type == "wallet" and target_type == "wallet":
                base, signal = 0.94, "explicit_joint_transaction_input"
            elif explicit_subnet and owner_type in {"service", "infrastructure"} and target_type in {"service", "infrastructure"}:
                base, signal, caution = 0.38, "explicit_network_proximity", "Network proximity is a weak lead and does not establish common control."
            elif infrastructure_kind and owner_type in {"service", "infrastructure"} and target_type in {"service", "infrastructure"}:
                base, signal = 0.90, "explicit_infrastructure_reference"
            if base:
                add_edge(owner, target, observation, signal, base, caution)

        # A single record can explicitly describe a relationship between two
        # identifiers while being attached to only one of them (e.g. co-inputs).
        if identity_kind and co_input:
            asset_ids = {owner} | {item for item in referenced if entities[item].get("type") in IDENTIFIER_TYPES}
            for left_index, left in enumerate(sorted(asset_ids)):
                for right in sorted(asset_ids)[left_index + 1:]:
                    if entities[left].get("type") == entities[right].get("type") == "wallet":
                        add_edge(left, right, observation, "explicit_joint_transaction_input", 0.94)

    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (left, right), edge in edges.items():
        adjacency[left].append((right, edge))
        adjacency[right].append((left, edge))

    associations = []
    for (left, right), edge in sorted(edges.items()):
        associations.append({
            "from_entity_id": left,
            "to_entity_id": right,
            "from_label": entities[left]["display_label"],
            "to_label": entities[right]["display_label"],
            "relation": "evidence_association",
            "score": edge["weight"],
            "signals": edge["signals"],
            "evidence_ids": sorted(edge["evidence_ids"]),
            "caution": "; ".join(sorted(edge["cautions"])) or "This edge records that the cited synthetic evidence connects these records. It is not an attribution conclusion.",
            "is_attribution_candidate": False,
        })

    leads: dict[tuple[str, str], dict[str, Any]] = {}
    def keep_candidate(path: list[str], path_edges: list[dict[str, Any]], relation: str, score: float, caution: str, *, candidate_class: str = "attribution") -> None:
        pair = tuple(sorted((path[0], path[-1])))
        if relation == "wallet_cluster_correlation":
            score_explanation = "Strongest account-to-wallet edge plus a capped corroboration adjustment for repeated joint-input evidence. This is a review score, not an identity probability."
        elif relation == "strong_unique_infrastructure_indicator_path":
            score_explanation = "A distinctive fingerprint appears in source evidence on both service paths; the link remains an analyst lead and is not proof of common control."
        elif relation == "weak_contextual_infrastructure_correlation":
            score_explanation = "Weakest path edge, capped at 45% because the path relies on shared marketplace or infrastructure context."
        else:
            score_explanation = f"Minimum evidence-edge score across {len(path_edges)} path step(s), with an 18% uncertainty discount for each additional step."
        if pair in leads:
            if score <= leads[pair]["score"]:
                leads[pair]["evidence_ids"].update(eid for edge in path_edges for eid in edge["evidence_ids"])
                return
        leads[pair] = {
            "from_entity_id": pair[0], "to_entity_id": pair[1],
            "from_label": entities[pair[0]]["display_label"], "to_label": entities[pair[1]]["display_label"],
            "relation": relation, "score": round(score, 4), "priority": priority_label(score),
            "signals": [signal for edge in path_edges for signal in edge["signals"]],
            "evidence_ids": {eid for edge in path_edges for eid in edge["evidence_ids"]},
            "review_status": "needs_more_evidence" if score < 0.60 else "unreviewed",
            "score_is_probability": False, "caution": caution,
            "is_attribution_candidate": candidate_class == "attribution",
            "candidate_class": candidate_class,
            "path_entity_ids": path,
            "score_explanation": score_explanation,
        }

    # Repeated joint inputs are a separately classified financial-network
    # relationship lead, not a conclusion that two wallets share an operator.
    for (left, right), edge in edges.items():
        if not any(signal["signal"] == "explicit_joint_transaction_input" for signal in edge["signals"]):
            continue
        distinct_records = {signal.get("evidence_id") for signal in edge["signals"] if signal.get("evidence_id")}
        if len(distinct_records) < 2 or entities[left].get("type") != "wallet" or entities[right].get("type") != "wallet":
            continue
        corroboration = min(0.16, 0.08 * (len(distinct_records) - 1))
        score = min(0.95, edge["weight"] + corroboration)
        keep_candidate(
            [left, right], [edge], "repeated_wallet_co_input_relationship", score,
            "Repeated joint transaction inputs support a wallet-network relationship. Co-spending can be caused by shared services or joint activity and does not establish a shared operator.",
            candidate_class="financial_relationship",
        )

    # A shared subnet can warrant a weak lead, but never a strong attribution.
    for (left, right), edge in edges.items():
        if any(signal["signal"] == "explicit_network_proximity" for signal in edge["signals"]):
            keep_candidate(
                [left, right], [edge], "weak_shared_network_proximity", min(0.45, edge["weight"]),
                "Same-subnet proximity is a weak contextual clue. Hosting providers and address ranges are shared; this does not establish common control.",
                candidate_class="contextual_infrastructure",
            )

    # Direct record connections are emitted as evidence associations only.
    # Candidate leads below require an eligible multi-hop identity path, while
    # the independent exact-value matcher handles direct shared indicators.
    endpoints = [entity_id for entity_id, entity in entities.items() if entity.get("type") in {"handle", "service"}]
    for start in endpoints:
        start_type = entities[start].get("type")
        max_path_edges = 6 if start_type == "handle" else 4
        stack: list[tuple[str, list[str], list[dict[str, Any]]]] = [(start, [start], [])]
        shortest_depth: dict[str, int] = {start: 0}
        visited_states = 0
        while stack:
            visited_states += 1
            if visited_states > 3000:
                break
            current, path, path_edges = stack.pop()
            if len(path_edges) >= max_path_edges:
                continue
            for neighbor, edge in adjacency.get(current, []):
                if neighbor in path:
                    continue
                next_path, next_edges = path + [neighbor], path_edges + [edge]
                depth = len(next_edges)
                previous_depth = shortest_depth.get(neighbor)
                if previous_depth is not None and previous_depth <= depth:
                    continue
                shortest_depth[neighbor] = depth
                next_type = entities[neighbor].get("type")
                if next_type == start_type and neighbor != start and len(next_edges) >= 2:
                    middle_types = [entities[item].get("type") for item in next_path[1:-1]]
                    identifier_path = start_type == "handle" and middle_types and all(item in IDENTIFIER_TYPES for item in middle_types)
                    infrastructure_path = start_type == "service" and middle_types and all(item == "infrastructure" for item in middle_types)
                    contextual_path = start_type == "handle" and "service" in middle_types and "infrastructure" in middle_types and all(item in IDENTIFIER_TYPES | {"service", "infrastructure"} for item in middle_types)
                    if identifier_path or infrastructure_path or contextual_path:
                        min_weight = min(item["weight"] for item in next_edges)
                        distinctive_bridges = []
                        if infrastructure_path:
                            for entity_id in next_path[1:-1]:
                                label = str(entities[entity_id].get("display_label", ""))
                                if not re.search(r"fingerprint|host key|certificate|ssh", label, re.IGNORECASE):
                                    continue
                                tokens = _identifier_tokens(label)
                                observed = {
                                    observation["id"] for observation in payload.get("evidence", [])
                                    if tokens & {token for value in _normalized_record_values(observation) for token in _identifier_tokens(value)}
                                }
                                if 2 <= len(observed) <= 4:
                                    distinctive_bridges.append(entity_id)
                        repeated_wallet_cluster = identifier_path and any(
                            signal["signal"] == "explicit_joint_transaction_input"
                            for item in next_edges for signal in item["signals"]
                        )
                        if contextual_path:
                            score = min(0.45, min_weight)
                            caution = "This weak contextual lead passes through marketplace presence and infrastructure correlation. Shared hosting or marketplace context does not establish a shared operator."
                            relation = "weak_contextual_infrastructure_correlation"
                        elif repeated_wallet_cluster:
                            score = min(0.92, min_weight + 0.12)
                            caution = "This lead is supported by a repeated wallet co-input cluster and explicit account-to-wallet references. Wallet clustering can reflect shared services or joint activity; it does not prove that the accounts have one operator."
                            relation = "wallet_cluster_correlation"
                        elif distinctive_bridges:
                            score = min(0.92, min_weight + 0.28)
                            caution = "The services connect through a distinctive certificate or host fingerprint observed on both infrastructure paths. Reused or copied infrastructure remains possible; review the cited records before drawing a conclusion."
                            relation = "strong_unique_infrastructure_indicator_path"
                        else:
                            # Multi-hop chains accumulate uncertainty. Do not
                            # increase a score simply because a path is longer.
                            score = min(0.65, min_weight * (0.82 ** (len(next_edges) - 1)))
                            caution = "A multi-hop lead through explicit identifier or infrastructure references. Each extra hop lowers reliability; review every cited record. This is not proof of common control."
                            relation = "multi_hop_identifier_correlation" if start_type == "handle" else "multi_hop_infrastructure_correlation"
                        keep_candidate(next_path, next_edges, relation, score, caution)
                elif next_type in (IDENTIFIER_TYPES | {"service", "infrastructure"} if start_type == "handle" else {"infrastructure"}):
                    stack.append((neighbor, next_path, next_edges))

    return {
        "leads": sorted(leads.values(), key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"])),
        "associations": associations,
    }


def _detect_duplicates_and_dependencies(
    observations: list[dict[str, Any]], sources: dict[str, Any]
) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Detect exact duplicate observations or records with explicit shared provenance.

    Does not infer dependence from similar text or matching indicators alone.
    Returns (primary_by_obs_id, grouped_clues_list, grouped_by_primary_id).
    """
    primary_by_id: dict[str, str] = {}
    grouped_clues: list[dict[str, Any]] = []
    grouped_by_primary: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # 1. Exact duplicates: same entity_id, same source_id, identical summary & normalized content
    seen_exact: dict[tuple[str, str, str], str] = {}
    for obs in observations:
        obs_id = obs["id"]
        entity_id = obs.get("entity_id", "")
        source_id = obs.get("source_id", "")
        summary_norm = str(obs.get("summary", "")).strip().casefold()
        key = (entity_id, source_id, summary_norm)
        if key in seen_exact:
            primary_id = seen_exact[key]
            primary_by_id[obs_id] = primary_id
            clue = {
                "observation_id": obs_id,
                "summary": obs.get("summary", ""),
                "observed_at": obs.get("observed_at"),
                "source_id": source_id,
                "source_name": sources.get(source_id, {}).get("name", source_id),
                "primary_observation_id": primary_id,
                "grouping_type": "exact_duplicate",
                "reason": f"Exact duplicate observation from same source ({source_id}); grouped with {primary_id} to prevent artificial corroboration inflation.",
            }
            grouped_clues.append(clue)
            grouped_by_primary[primary_id].append(clue)
        else:
            seen_exact[key] = obs_id

    # 2. Explicit shared provenance / downstream mirror:
    for obs in observations:
        obs_id = obs["id"]
        if obs_id in primary_by_id:
            continue
        details = obs.get("details") or {}
        derived_from = details.get("derived_from") or details.get("derived_from_observation_id")
        mirror_of = details.get("mirror_of") or details.get("mirror_of_source_id")
        if derived_from and any(o["id"] == derived_from for o in observations):
            primary_by_id[obs_id] = derived_from
            clue = {
                "observation_id": obs_id,
                "summary": obs.get("summary", ""),
                "observed_at": obs.get("observed_at"),
                "source_id": obs.get("source_id", ""),
                "source_name": sources.get(obs.get("source_id", ""), {}).get("name", obs.get("source_id", "")),
                "primary_observation_id": derived_from,
                "grouping_type": "explicit_derivation",
                "reason": f"Explicit downstream derivation citing observation {derived_from}; grouped to prevent double-counting.",
            }
            grouped_clues.append(clue)
            grouped_by_primary[derived_from].append(clue)
        elif mirror_of:
            for other in observations:
                if other["source_id"] == mirror_of and other.get("entity_id") == obs.get("entity_id"):
                    if str(other.get("summary", "")).strip().casefold() == str(obs.get("summary", "")).strip().casefold():
                        primary_by_id[obs_id] = other["id"]
                        clue = {
                            "observation_id": obs_id,
                            "summary": obs.get("summary", ""),
                            "observed_at": obs.get("observed_at"),
                            "source_id": obs.get("source_id", ""),
                            "source_name": sources.get(obs.get("source_id", ""), {}).get("name", obs.get("source_id", "")),
                            "primary_observation_id": other["id"],
                            "grouping_type": "explicit_mirror",
                            "reason": f"Explicit mirror of source {mirror_of}; grouped with {other['id']} to prevent duplicate corroboration.",
                        }
                        grouped_clues.append(clue)
                        grouped_by_primary[other["id"]].append(clue)
                        break

    return primary_by_id, grouped_clues, grouped_by_primary


def _detect_counter_evidence_and_conflicts(
    left_id: str,
    right_id: str,
    entities: dict[str, Any],
    observations: list[dict[str, Any]],
    sources: dict[str, Any],
    path_entity_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], bool, bool, str]:
    """Identify counter-evidence and inconsistencies for an entity pair.

    Distinguishes confirmed contradictions (explicit counter-evidence, verified refutations)
    from review context (concurrency, different secondary keys, shared hosting).
    Returns (counter_evidence_list, has_conflicts, has_inconsistencies, conflict_summary).
    """
    pair_entities = {left_id, right_id}
    if path_entity_ids:
        pair_entities.update(path_entity_ids)

    counter_evidence: list[dict[str, Any]] = []
    seen_obs_ids: set[str] = set()

    for obs in observations:
        obs_id = obs["id"]
        if obs_id in seen_obs_ids:
            continue
        owner_id = obs.get("entity_id")
        summary = str(obs.get("summary", ""))
        details = obs.get("details") or {}
        kind = str(obs.get("evidence_type", obs.get("type", ""))).casefold()

        mentions = _entity_mentions(summary, entities)
        is_relevant = (owner_id in pair_entities) or bool(mentions & pair_entities)
        if not is_relevant:
            continue

        # 1. Confirmed Contradictions (explicit synthetic counter-evidence)
        explicit_counter = (
            details.get("counter_evidence") is True
            or bool(details.get("conflict"))
            or kind in ("counter_evidence", "denial", "refutation")
            or bool(re.search(r"\b(?:not the same|different (?:owner|operator|person|entity)|unrelated organisation|unrelated organization|refutes?|denies? (?:being|operating|owning))\b", summary, re.IGNORECASE))
        )
        if explicit_counter:
            seen_obs_ids.add(obs_id)
            explanation = details.get("conflict") or details.get("counter_explanation") or "Record explicitly reports distinct operators or refutes common control."
            counter_evidence.append({
                "observation_id": obs_id,
                "summary": summary,
                "observed_at": obs.get("observed_at"),
                "source_id": obs.get("source_id"),
                "source_name": sources.get(obs.get("source_id"), {}).get("name", obs.get("source_id")),
                "conflict_type": "confirmed_contradiction",
                "is_confirmed_contradiction": True,
                "explanation": str(explanation),
            })
            continue

        # 2. Impersonation Claims without proof
        if kind == "impersonation_claim" or re.search(r"\b(?:claims to be .* but presents no|unverified impersonation|impersonat)\b", summary, re.IGNORECASE):
            seen_obs_ids.add(obs_id)
            counter_evidence.append({
                "observation_id": obs_id,
                "summary": summary,
                "observed_at": obs.get("observed_at"),
                "source_id": obs.get("source_id"),
                "source_name": sources.get(obs.get("source_id"), {}).get("name", obs.get("source_id")),
                "conflict_type": "confirmed_contradiction",
                "is_confirmed_contradiction": True,
                "explanation": "Unverified self-claim or impersonation attempt without cryptographic corroboration; conflicts with direct attribution.",
            })
            continue

        # 3. Review Context: Concurrency / Timing overlap
        if re.search(r"\b(?:active at the same time|concurrent activity|concurrently|both were active|overlap.*lowers chance)\b", summary, re.IGNORECASE):
            seen_obs_ids.add(obs_id)
            counter_evidence.append({
                "observation_id": obs_id,
                "summary": summary,
                "observed_at": obs.get("observed_at"),
                "source_id": obs.get("source_id"),
                "source_name": sources.get(obs.get("source_id"), {}).get("name", obs.get("source_id")),
                "conflict_type": "review_context_inconsistency",
                "is_confirmed_contradiction": False,
                "explanation": "Concurrent activity window noted; simultaneous presence across services weakens a single-operator migration hypothesis.",
            })
            continue

        # 4. Review Context: Shared hosting / high-fanout pooling
        if details.get("common") is True or re.search(r"\b(?:shared hosting|reverse proxy|common exchange pooling|exchange hot wallet|used by many unrelated)\b", summary, re.IGNORECASE):
            seen_obs_ids.add(obs_id)
            counter_evidence.append({
                "observation_id": obs_id,
                "summary": summary,
                "observed_at": obs.get("observed_at"),
                "source_id": obs.get("source_id"),
                "source_name": sources.get(obs.get("source_id"), {}).get("name", obs.get("source_id")),
                "conflict_type": "review_context_inconsistency",
                "is_confirmed_contradiction": False,
                "explanation": "Shared infrastructure or deposit pooling context; indicators reflect shared multi-tenant services rather than dedicated infrastructure.",
            })

    # 5. Review Context: Cryptographic Key Divergence
    left_keys = {
        obs.get("entity_id") for obs in observations
        if obs.get("entity_id") and entities.get(obs["entity_id"], {}).get("type") == "pgp_key"
        and left_id in _handle_mentions(str(obs.get("summary", "")), entities)
    }
    right_keys = {
        obs.get("entity_id") for obs in observations
        if obs.get("entity_id") and entities.get(obs["entity_id"], {}).get("type") == "pgp_key"
        and right_id in _handle_mentions(str(obs.get("summary", "")), entities)
    }
    if left_keys and right_keys and not (left_keys & right_keys):
        counter_evidence.append({
            "observation_id": "KEY-DIVERGENCE",
            "summary": f"{entities.get(left_id, {}).get('display_label', left_id)} lists key(s) {sorted(left_keys)} while {entities.get(right_id, {}).get('display_label', right_id)} lists key(s) {sorted(right_keys)} with no overlap.",
            "observed_at": None,
            "source_id": "ANALYSIS",
            "source_name": "DarkLens Key Discrepancy Analyzer",
            "conflict_type": "review_context_inconsistency",
            "is_confirmed_contradiction": False,
            "explanation": "Disjoint cryptographic keys: entities maintain distinct verified keys without cross-signing.",
        })

    has_conflicts = any(item["is_confirmed_contradiction"] for item in counter_evidence)
    has_inconsistencies = len(counter_evidence) > 0
    if has_conflicts:
        conflict_summary = f"Confirmed Contradiction: {sum(1 for i in counter_evidence if i['is_confirmed_contradiction'])} record(s) explicitly refute or contradict common control."
    elif has_inconsistencies:
        conflict_summary = f"Review Context: {len(counter_evidence)} potential inconsistency clue(s) (concurrency or shared hosting) require analyst scrutiny."
    else:
        conflict_summary = "No conflicting records or contradictions identified."

    return counter_evidence, has_conflicts, has_inconsistencies, conflict_summary


def build_candidate_dossier(
    left_id: str,
    right_id: str,
    entities: dict[str, Any],
    sources: dict[str, Any],
    candidate: dict[str, Any],
    all_observations: list[dict[str, Any]],
    grouped_clues_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Construct a comprehensive evidence dossier for an analyst review."""
    supporting_obs_ids = set(candidate.get("evidence_ids", []))
    supporting_obs = [obs for obs in all_observations if obs["id"] in supporting_obs_ids]

    supporting_evidence: list[dict[str, Any]] = []
    signals = candidate.get("signals", [])
    path = candidate.get("path_entity_ids", [])
    inference_depth = max(1, len(path) - 1) if path else 1

    for obs in supporting_obs:
        src = sources.get(obs.get("source_id"), {})
        sig_match = next((s for s in signals if isinstance(s, dict) and s.get("evidence_id") == obs["id"]), None)
        match_strength = sig_match.get("match", 1.0) if sig_match else 1.0
        rel = float(src.get("reliability", 0.75))
        conf = float(obs.get("confidence", 0.75))
        qw = sig_match.get("quality_weight", round(0.70 * rel + 0.30 * conf, 4)) if sig_match else round(0.70 * rel + 0.30 * conf, 4)
        contrib = sig_match.get("contribution", round(match_strength * qw, 4)) if sig_match else round(match_strength * qw, 4)
        supporting_evidence.append({
            "observation_id": obs["id"],
            "summary": obs.get("summary", ""),
            "observed_at": obs.get("observed_at"),
            "entity_id": obs.get("entity_id"),
            "source_id": obs.get("source_id"),
            "source_name": src.get("name", obs.get("source_id")),
            "source_type": src.get("source_type", "unknown"),
            "source_reliability": rel,
            "confidence": conf,
            "match_strength": match_strength,
            "quality_weight": qw,
            "contribution": contrib,
            "inference_depth": inference_depth,
            "contribution_role": "Primary supporting observation",
        })

    counter_evidence, has_conflicts, has_inconsistencies, conflict_summary = _detect_counter_evidence_and_conflicts(
        left_id, right_id, entities, all_observations, sources, path
    )

    pair_grouped: list[dict[str, Any]] = []
    if grouped_clues_map:
        for obs_id in supporting_obs_ids:
            pair_grouped.extend(grouped_clues_map.get(obs_id, []))

    supporting_source_ids = {obs["source_id"] for obs in supporting_obs if obs.get("source_id")}
    unique_sources = [
        {
            "id": s_id,
            "name": sources.get(s_id, {}).get("name", s_id),
            "source_type": sources.get(s_id, {}).get("source_type", "unknown"),
            "reliability": float(sources.get(s_id, {}).get("reliability", 0.75)),
        }
        for s_id in sorted(supporting_source_ids)
    ]
    if len(unique_sources) >= 2 and all(s["reliability"] >= 0.75 for s in unique_sources):
        rating = "high"
        source_desc = f"Corroborated across {len(unique_sources)} independent sources with high reliability."
    elif len(unique_sources) >= 2:
        rating = "moderate"
        source_desc = f"Corroborated across {len(unique_sources)} sources (varying reliability)."
    else:
        rating = "low"
        source_desc = f"Single source dependency: all supporting evidence derives from {unique_sources[0]['name'] if unique_sources else 'one source'}."

    source_independence = {
        "rating": rating,
        "description": source_desc,
        "unique_source_count": len(unique_sources),
        "unique_sources": unique_sources,
        "is_single_source": len(unique_sources) <= 1,
    }

    inference_path = [
        {
            "entity_id": eid,
            "label": entities.get(eid, {}).get("display_label", eid),
            "type": entities.get(eid, {}).get("type", "unknown"),
        }
        for eid in path
    ] if path else []

    weak_or_missing: list[str] = []
    if len(signals) <= 1:
        weak_or_missing.append("Single evidence signal: lacks secondary multi-discipline corroboration.")
    if not any("key" in str(s.get("signal", "")).lower() or "cert" in str(s.get("signal", "")).lower() for s in signals if isinstance(s, dict)):
        weak_or_missing.append("No cryptographic verification (e.g. matching PGP key or SSL certificate).")
    if source_independence["is_single_source"]:
        weak_or_missing.append("Single source dependency: corroborating evidence from an independent source is missing.")
    if inference_depth > 1:
        weak_or_missing.append(f"Inference depth is {inference_depth} hops; each hop increases uncertainty.")
    if counter_evidence:
        weak_or_missing.append(f"{len(counter_evidence)} counter-evidence or inconsistency clue(s) detected.")

    cautions = list(dict.fromkeys(
        ([candidate.get("caution", "")] if candidate.get("caution") else []) +
        ([conflict_summary] if has_conflicts or has_inconsistencies else []) +
        ([f"Source Independence: {source_desc}"] if source_independence["is_single_source"] else [])
    ))

    return {
        "candidate_id": candidate.get("id"),
        "from_entity_id": left_id,
        "to_entity_id": right_id,
        "from_label": entities.get(left_id, {}).get("display_label", left_id),
        "to_label": entities.get(right_id, {}).get("display_label", right_id),
        "score": candidate.get("score", 0.0),
        "priority": candidate.get("priority", "weak"),
        "has_conflicts": has_conflicts,
        "has_inconsistencies": has_inconsistencies,
        "conflict_summary": conflict_summary,
        "supporting_evidence": supporting_evidence,
        "counter_evidence": counter_evidence,
        "grouped_evidence": pair_grouped,
        "source_independence": source_independence,
        "inference_path": inference_path,
        "weak_or_missing_evidence": weak_or_missing,
        "cautions": cautions,
        "score_explanation": candidate.get("score_explanation", "Review priority combines the listed evidence signal, source reliability, and record confidence."),
    }


def analyze_case(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze a synthetic case without collecting data or writing decisions.

    Evidence-only graph associations are kept separate from attribution leads.
    Scores are review priorities, never probabilities of identity.
    """
    entities = {item["id"]: item for item in payload.get("entities", [])}
    sources = {item["id"]: item for item in payload.get("sources", [])}
    observations = payload.get("evidence", [])
    primary_by_id, grouped_clues, grouped_by_primary = _detect_duplicates_and_dependencies(observations, sources)
    index: dict[tuple[str, str], dict[str, list[tuple[dict[str, Any], float, float]]]] = defaultdict(lambda: defaultdict(list))

    def add(signal_name: str, value: Any, observation: dict[str, Any], linked_entities: list[str]) -> None:
        if observation.get("id") in primary_by_id:
            # Grouped duplicate or dependent record; do not index as a separate corroborating signal
            return
        normalized = str(value).strip().casefold()
        if not normalized:
            return
        reliability = float(sources.get(observation.get("source_id"), {}).get("reliability", 0))
        record_text = " ".join(_normalized_record_values(observation))
        details = observation.get("details") or {}
        explicit_caveat = isinstance(details, dict) and any(details.get(field) is True for field in ("common", "shared_publicly", "boilerplate", "counter_evidence"))
        generic_caveat = bool(re.search(r"shared by many|common (?:template|banner|phrase|identifier)|default (?:icon|banner|credential)|boilerplate|unrelated organisation|unrelated organization|no funds (?:move|transfer)|not the same|different (?:owner|operator)|shared hosting", record_text, re.IGNORECASE))
        match_strength = 0.20 if explicit_caveat or generic_caveat else 1.0
        for linked_entity in set(linked_entities):
            if linked_entity in entities:
                index[(signal_name, normalized)][linked_entity].append((observation, reliability, match_strength))

    asset_markers: dict[str, dict[str, str]] = {"key": {}, "wallet": {}}
    for entity_id, entity in entities.items():
        kind = entity.get("type")
        label = str(entity.get("display_label", ""))
        if kind == "pgp_key":
            for marker in re.findall(r"\b[A-Z]{2,}\d+\b", label, re.IGNORECASE):
                asset_markers["key"][marker.casefold()] = entity_id
        elif kind == "wallet":
            for marker in re.findall(r"\bW\d+\b", label, re.IGNORECASE):
                asset_markers["wallet"][marker.casefold()] = entity_id

    for observation in observations:
        details = enrich_observation_details(observation, entities)
        owner = observation.get("entity_id")
        owner_type = entities.get(owner, {}).get("type")
        summary = str(observation.get("summary", ""))
        handle_ids = _handle_mentions(summary, entities)
        # Scan every scalar detail/summary independent of the detail-key name;
        # importer-compatible bundles need not call fields "key" or "wallet".
        all_tokens = {token for value in _normalized_record_values(observation) for token in _identifier_tokens(value)}
        for token in all_tokens:
            asset_type = _asset_indicator_type(token)
            if asset_type:
                linked_entities = handle_ids or ([owner] if owner in entities and owner_type not in IDENTIFIER_TYPES else [])
                add("shared_pgp_key" if asset_type == "key" else "shared_wallet", token, observation, linked_entities)
        for field, (signal_name, _category) in MATCH_FIELDS.items():
            value = details.get(field)
            if value is None and field in {"key", "wallet"}:
                for marker, asset_id in asset_markers[field].items():
                    if re.search(rf"(?<![\w]){re.escape(marker)}(?![\w])", summary, re.IGNORECASE):
                        value = asset_id
                        break
            if value is None and field in {"certificate", "ip"}:
                match = re.search(r"\bCS-\d+\b", summary, re.IGNORECASE) if field == "certificate" else re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", summary)
                value = match.group(0) if match else None
            if value is None:
                continue
            if field in {"key", "wallet"}:
                linked_entities = handle_ids or ([owner] if owner_type not in IDENTIFIER_TYPES else [])
                # A normalized asset reference is the canonical match key across summary-only records.
                if str(value) in entities and entities[str(value)].get("type") == ("pgp_key" if field == "key" else "wallet"):
                    value = f"entity:{value}"
                add(signal_name, value, observation, linked_entities)
            else:
                linked_entities = [owner] if owner in entities else []
                add(signal_name, value, observation, linked_entities)

    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for (signal_name, _), owners in index.items():
        entity_ids = sorted(owners)
        for i, left in enumerate(entity_ids):
            for right in entity_ids[i + 1:]:
                key = (left, right)
                row = pairs.setdefault(key, {"from_entity_id": left, "to_entity_id": right, "signals": {}, "evidence_ids": set(), "categories": set()})
                left_record, left_reliability, left_match = max(owners[left], key=lambda item: item[1] * float(item[0].get("confidence", 0.75)) * item[2])
                right_record, right_reliability, right_match = max(owners[right], key=lambda item: item[1] * float(item[0].get("confidence", 0.75)) * item[2])
                left_confidence = float(left_record.get("confidence", 0.75))
                right_confidence = float(right_record.get("confidence", 0.75))
                row["signals"][signal_name] = (min(left_match, right_match), min(left_reliability, right_reliability), min(left_confidence, right_confidence))
                row["categories"].add(SIGNAL_CATEGORY[signal_name])
                row["evidence_ids"].update(record["id"] for entity_id in (left, right) for record, _reliability, _match in owners[entity_id])

    suggestions = []
    exact_infrastructure_associations = []
    for pair in pairs.values():
        score, breakdown = score_link(pair["signals"])
        left, right = pair["from_entity_id"], pair["to_entity_id"]
        if pair["categories"] == {"infrastructure"} and "certificate_serial_match" not in pair["signals"]:
            # A shared IP alone is graph context, not an attribution candidate.
            exact_infrastructure_associations.append({
                "from_entity_id": left, "to_entity_id": right,
                "from_label": entities[left]["display_label"], "to_label": entities[right]["display_label"],
                "relation": "evidence_association", "score": score, "signals": breakdown,
                "evidence_ids": sorted(pair["evidence_ids"]),
                "caution": "Shared address alone is contextual infrastructure evidence; it can reflect hosting, reassignment, or shared services.",
                "is_attribution_candidate": False,
            })
            continue
        suggestions.append({
            "from_entity_id": left,
            "to_entity_id": right,
            "from_label": entities[left]["display_label"],
            "to_label": entities[right]["display_label"],
            "relation": "shared_synthetic_identifier" if "identifier" in pair["categories"] else "shared_synthetic_infrastructure",
            "score": score,
            "priority": priority_label(score),
            "signals": breakdown,
            "evidence_ids": sorted(pair["evidence_ids"]),
            "review_status": "needs_more_evidence" if score < 0.60 else "unreviewed",
            "score_is_probability": False,
            "caution": "Exact-value match in synthetic records. This is a lead for human review, not identity proof.",
            "is_attribution_candidate": True,
            "score_explanation": "Independent typed-indicator signals are combined after discounting source reliability, record confidence, and explicit commonness or contradictory-context warnings.",
        })
    # Add bounded path leads. Direct evidence associations remain in their
    # separate collection and are never inserted into the review queue.
    reference_analysis = _reference_leads(payload, entities, sources)
    association_by_pair = {
        tuple(sorted((item["from_entity_id"], item["to_entity_id"]))): item
        for item in reference_analysis["associations"]
    }
    for association in exact_infrastructure_associations:
        key = tuple(sorted((association["from_entity_id"], association["to_entity_id"])))
        if key in association_by_pair:
            association_by_pair[key]["evidence_ids"] = sorted(set(association_by_pair[key]["evidence_ids"]) | set(association["evidence_ids"]))
            association_by_pair[key]["signals"].extend(association["signals"])
        else:
            association_by_pair[key] = association
    evidence_associations = list(association_by_pair.values())
    # Merge pairs
    # already found by exact-value matching so the review queue stays deduped.
    suggestion_by_pair = {(item["from_entity_id"], item["to_entity_id"]): item for item in suggestions}
    for lead in reference_analysis["leads"]:
        pair = (lead["from_entity_id"], lead["to_entity_id"])
        existing = suggestion_by_pair.get(pair) or suggestion_by_pair.get(pair[::-1])
        if existing:
            existing["evidence_ids"] = sorted(set(existing["evidence_ids"]) | set(lead["evidence_ids"]))
            existing["signals"] = existing["signals"] + [signal for signal in lead["signals"] if signal not in existing["signals"]]
            if lead["score"] > existing["score"]:
                existing["score"] = lead["score"]
                existing["priority"] = lead["priority"]
                existing["relation"] = lead["relation"]
                existing["caution"] = lead["caution"]
                existing["review_status"] = lead["review_status"]
        else:
            lead["evidence_ids"] = sorted(lead["evidence_ids"])
            suggestions.append(lead)
            suggestion_by_pair[pair] = lead
    suggestions.sort(key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"]))
    exact_pairs = {(row["from_entity_id"], row["to_entity_id"]) for row in suggestions}
    behavioral_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _activity_leads(payload, entities, sources) + _explicit_style_leads(payload, entities, sources) + _raw_text_style_leads(payload, entities, sources):
        pair = (row["from_entity_id"], row["to_entity_id"])
        if pair in exact_pairs:
            existing = suggestion_by_pair[pair]
            existing["score"] = round(1 - (1 - existing["score"]) * (1 - row["score"]), 4)
            existing["priority"] = priority_label(existing["score"])
            if existing["score"] >= 0.60 and existing["review_status"] == "needs_more_evidence":
                existing["review_status"] = "unreviewed"
            existing["evidence_ids"] = sorted(set(existing["evidence_ids"]) | set(row["evidence_ids"]))
            existing["signals"].extend(signal for signal in row["signals"] if signal not in existing["signals"])
            existing["caution"] += " A separate behavioural clue also overlaps; it is weak and does not establish authorship."
            continue
        previous = behavioral_by_pair.get(pair)
        if previous:
            previous["evidence_ids"] = sorted(set(previous["evidence_ids"]) | set(row["evidence_ids"]))
            if row["score"] > previous["score"]:
                row["evidence_ids"] = previous["evidence_ids"]
                behavioral_by_pair[pair] = row
        else:
            behavioral_by_pair[pair] = row
    behavioral_leads = sorted(behavioral_by_pair.values(), key=lambda item: (-item["score"], item["from_entity_id"], item["to_entity_id"]))

    for s in suggestions:
        dossier = build_candidate_dossier(s["from_entity_id"], s["to_entity_id"], entities, sources, s, observations, grouped_by_primary)
        s["dossier"] = dossier
        s["has_conflicts"] = dossier["has_conflicts"]
    for b in behavioral_leads:
        dossier = build_candidate_dossier(b["from_entity_id"], b["to_entity_id"], entities, sources, b, observations, grouped_by_primary)
        b["dossier"] = dossier
        b["has_conflicts"] = dossier["has_conflicts"]

    return {
        "case_id": payload.get("case", {}).get("id"),
        "synthetic_data_only": True,
        "read_only": True,
        "method": "generic typed-indicator extraction, evidence-only associations, reliability- and record-confidence adjusted exact matches, bounded uncertainty-discounted paths, and capped style/activity analysis",
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "evidence_associations": evidence_associations,
        "behavioral_leads": behavioral_leads,
        "limitations": [
            "No live crawling or external lookups are performed.",
            "Activity, reported style, and raw-text style similarities are weak clues capped at 45%; they do not establish common control.",
            "Indicator extraction scans labels, supported attributes, summaries, and scalar detail values for typed IP, domain, onion, key, wallet, certificate, and synthetic identifiers; ambiguous or unstructured references may still be missed.",
            "Evidence associations are separate graph edges. Only exact shared indicators or eligible bounded paths become attribution candidates.",
            "Common or contradictory indicators are discounted, and each additional inference hop lowers the review score.",
            "The review score combines match strength, source reliability, and record confidence; it is not a calibrated probability.",
            "Raw-text stylometry is an untrained local similarity heuristic that needs explicitly supplied samples; it is not author identification.",
            "No live collection, external lookups, trained ML model, or LLM is used.",
            "Scores are review-priority values, not probabilities of identity.",
            "Suggestions require an explicit analyst action to add to the review queue and are never automatically accepted.",
        ],
    }
