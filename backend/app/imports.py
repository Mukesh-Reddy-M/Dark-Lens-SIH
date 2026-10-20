"""Validation and normalization for version 1 synthetic case bundles."""

from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


ENTITY_TYPES = {"persona", "handle", "pgp_key", "wallet", "marketplace", "service", "infrastructure"}
MAX_SOURCES = 100
MAX_ENTITIES = 500
MAX_OBSERVATIONS = 2000
MAX_TEXT = 4000
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,79}$")


class BundleValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("Case bundle validation failed")
        self.errors = errors


def _text(value: Any, path: str, errors: list[str], *, required: bool = True, maximum: int = MAX_TEXT) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: must be a non-empty string")
        return None
    value = value.strip()
    if len(value) > maximum:
        errors.append(f"{path}: must be {maximum} characters or fewer")
    return value


def _identifier(value: Any, path: str, errors: list[str], *, generated: str | None = None) -> str | None:
    if value is None and generated:
        return generated
    result = _text(value, path, errors, maximum=80)
    if result and not ID_PATTERN.fullmatch(result):
        errors.append(f"{path}: use 2-80 letters, numbers, dots, underscores, colons, or hyphens; start with a letter or number")
    return result


def _array(value: Any, path: str, maximum: int, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path}: must be an array")
        return []
    if len(value) > maximum:
        errors.append(f"{path}: may contain at most {maximum} records")
    return value


def _object(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return {}
    return value


def _unit_interval(value: Any, path: str, errors: list[str]) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{path}: must be a number between 0 and 1")
        return None
    result = float(value)
    if not 0 <= result <= 1:
        errors.append(f"{path}: must be between 0 and 1")
    return result


def _utc_timestamp(value: Any, path: str, errors: list[str], *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    result = _text(value, path, errors, maximum=64)
    if not result:
        return None
    try:
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            errors.append(f"{path}: timestamp must include a timezone, such as Z")
            return result
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        errors.append(f"{path}: must be an ISO 8601 timestamp")
        return result


def normalize_case_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate a bundle and return normalized DB-ready data; never trusts links."""
    errors: list[str] = []
    if not isinstance(bundle, dict):
        raise BundleValidationError(["bundle: must be a JSON object"])
    try:
        raw_json = json.dumps(bundle, ensure_ascii=False)
        if len(raw_json) > 5 * 1024 * 1024:
            errors.append("bundle: file must be 5 MB or smaller")
    except (TypeError, ValueError):
        errors.append("bundle: must contain JSON-compatible values")
    if bundle.get("schema_version") != "1.0":
        errors.append("schema_version: expected '1.0'")
    if bundle.get("data_mode") != "synthetic":
        errors.append("data_mode: this prototype currently accepts synthetic data only")
    if "links" in bundle:
        errors.append("links: do not include proposed links; DarkLens derives candidates from observations")

    raw_case = _object(bundle.get("case"), "case", errors)
    case_title = _text(raw_case.get("title"), "case.title", errors, maximum=160)
    case_id = _identifier(raw_case.get("id"), "case.id", errors, generated=f"CASE-{uuid4().hex[:10].upper()}")
    case_description = _text(raw_case.get("description"), "case.description", errors, required=False, maximum=2000) or ""

    raw_sources = _array(bundle.get("sources"), "sources", MAX_SOURCES, errors)
    raw_entities = _array(bundle.get("entities"), "entities", MAX_ENTITIES, errors)
    raw_observations = _array(bundle.get("observations"), "observations", MAX_OBSERVATIONS, errors)
    if not raw_sources:
        errors.append("sources: provide at least one source")
    if not raw_entities:
        errors.append("entities: provide at least one entity")
    if not raw_observations:
        errors.append("observations: provide at least one observation")

    sources: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for index, raw in enumerate(raw_sources):
        path = f"sources[{index}]"
        item = _object(raw, path, errors)
        source_id = _identifier(item.get("id"), f"{path}.id", errors)
        name = _text(item.get("name"), f"{path}.name", errors, maximum=160)
        source_type = _text(item.get("source_type"), f"{path}.source_type", errors, maximum=80)
        reliability = _unit_interval(item.get("reliability"), f"{path}.reliability", errors)
        if source_id:
            if source_id in source_ids:
                errors.append(f"{path}.id: duplicate source ID '{source_id}'")
            source_ids.add(source_id)
        sources.append({"id": source_id, "name": name, "source_type": source_type, "reliability": reliability})

    entities: list[dict[str, Any]] = []
    entity_ids: set[str] = set()
    for index, raw in enumerate(raw_entities):
        path = f"entities[{index}]"
        item = _object(raw, path, errors)
        entity_id = _identifier(item.get("id"), f"{path}.id", errors)
        entity_type = _text(item.get("type"), f"{path}.type", errors, maximum=40)
        if entity_type and entity_type not in ENTITY_TYPES:
            errors.append(f"{path}.type: choose one of {', '.join(sorted(ENTITY_TYPES))}")
        label = _text(item.get("display_label"), f"{path}.display_label", errors, maximum=200)
        attributes = _object(item.get("attributes"), f"{path}.attributes", errors)
        first_seen = _utc_timestamp(item.get("first_seen"), f"{path}.first_seen", errors, required=False)
        last_seen = _utc_timestamp(item.get("last_seen"), f"{path}.last_seen", errors, required=False)
        if entity_id:
            if entity_id in entity_ids:
                errors.append(f"{path}.id: duplicate entity ID '{entity_id}'")
            entity_ids.add(entity_id)
        entities.append({"id": entity_id, "type": entity_type, "display_label": label, "first_seen": first_seen, "last_seen": last_seen, "attributes": attributes})

    observations: list[dict[str, Any]] = []
    observation_ids: set[str] = set()
    for index, raw in enumerate(raw_observations):
        path = f"observations[{index}]"
        item = _object(raw, path, errors)
        observation_id = _identifier(item.get("id"), f"{path}.id", errors, generated=f"OBS-{uuid4().hex[:12].upper()}")
        source_id = _identifier(item.get("source_id"), f"{path}.source_id", errors)
        entity_id = item.get("entity_id")
        if entity_id is not None:
            entity_id = _identifier(entity_id, f"{path}.entity_id", errors)
        observed_at = _utc_timestamp(item.get("observed_at"), f"{path}.observed_at", errors)
        evidence_type = _text(item.get("evidence_type"), f"{path}.evidence_type", errors, maximum=80)
        summary = _text(item.get("summary"), f"{path}.summary", errors, maximum=MAX_TEXT)
        confidence = _unit_interval(item.get("confidence"), f"{path}.confidence", errors)
        details = _object(item.get("details"), f"{path}.details", errors)
        if observation_id:
            if observation_id in observation_ids:
                errors.append(f"{path}.id: duplicate observation ID '{observation_id}'")
            observation_ids.add(observation_id)
        if source_id and source_id not in source_ids:
            errors.append(f"{path}.source_id: unknown source '{source_id}'")
        if entity_id and entity_id not in entity_ids:
            errors.append(f"{path}.entity_id: unknown entity '{entity_id}'")
        observations.append({"id": observation_id, "source_id": source_id, "entity_id": entity_id, "observed_at": observed_at, "evidence_type": evidence_type, "summary": summary, "confidence": confidence, "details": details})

    if errors:
        raise BundleValidationError(errors)
    return {
        "case": {"id": case_id, "title": case_title, "description": case_description},
        "sources": sources,
        "entities": entities,
        "observations": observations,
    }
