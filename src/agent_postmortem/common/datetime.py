"""Shared datetime helpers for canonical serialization.

All canonical datetime serialization flows through this module so UTC output
is consistent and deterministic across the schema.
"""

from __future__ import annotations

from datetime import UTC, datetime


def serialize_datetime_utc(value: datetime) -> str:
    """Serialize a timezone-aware datetime in deterministic UTC form."""

    normalized = value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")
