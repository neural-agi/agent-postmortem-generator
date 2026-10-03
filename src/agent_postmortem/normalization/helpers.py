"""Deterministic ID, timestamp, and source-value helpers."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime

from agent_postmortem.validation.trace_document import TraceEvent

# The PDF lists these candidates in this order without assigning another rank.
# The Part 2 typed `timestamp` is retained as a compatibility fallback.
_TIMESTAMP_PRECEDENCE = ("created_at", "started_at", "ended_at", "observed_at")


def stable_id(role: str, run_id: str, source_id: str) -> str:
    """Derive a stable, role-separated identifier from explicit source identity."""

    seed = json.dumps([role, run_id, source_id], ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"{role}_{digest}"


def canonical_json(value: object) -> str:
    """Serialize JSON-compatible input with sorted keys and stable separators."""

    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(value: object) -> str:
    """Return a stable SHA-256 fingerprint for a JSON-compatible value."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a validated ISO timestamp and return its UTC-normalized value."""

    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("validated timestamps must include a timezone")
    return parsed.astimezone(UTC)


def resolve_event_timestamp(
    event: TraceEvent,
) -> tuple[datetime | None, str | None, object, tuple[str, ...], tuple[str, ...]]:
    """Select the highest-precedence usable timestamp and report anomalies.

    The return value contains the normalized timestamp, its source field and raw
    value, followed by invalid and conflicting candidate field names.
    """

    raw_fields = dict(event.raw_fields)
    candidates: list[tuple[str, object]] = [
        (field, raw_fields[field])
        for field in _TIMESTAMP_PRECEDENCE
        if field in raw_fields and raw_fields[field] is not None
    ]
    if event.timestamp is not None:
        candidates.append(("timestamp", event.timestamp))

    valid: list[tuple[str, object, datetime]] = []
    invalid_fields: list[str] = []
    for field, raw_value in candidates:
        if not isinstance(raw_value, str):
            invalid_fields.append(field)
            continue
        try:
            parsed = parse_timestamp(raw_value)
        except ValueError:
            invalid_fields.append(field)
            continue
        if parsed is not None:
            valid.append((field, raw_value, parsed))

    if not valid:
        return None, None, None, tuple(invalid_fields), ()

    selected_field, selected_raw, selected_time = valid[0]
    conflicting_fields = (
        tuple(field for field, _, parsed in valid if parsed != selected_time)
        if any(parsed != selected_time for _, _, parsed in valid[1:])
        else ()
    )
    return (
        selected_time,
        selected_field,
        selected_raw,
        tuple(invalid_fields),
        conflicting_fields,
    )


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("source values must be finite JSON numbers")
        return value
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("source object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    raise ValueError(f"unsupported source value type: {type(value).__name__}")
