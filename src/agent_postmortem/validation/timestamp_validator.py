"""Timestamp validation for generic trace events.

This validator owns parseability and timezone checks for event timestamps so
event structure validation remains focused on shape and field types.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity


class TimestampValidator:
    """Validate timestamp parseability, timezone awareness, and comparability."""

    def validate(self, events: list[Mapping[str, object]]) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        for index, event in enumerate(events):
            timestamp = event.get("timestamp")
            if timestamp is None:
                continue
            field_path = f"/events/{index}/timestamp"
            if not isinstance(timestamp, str):
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.INVALID_TIMESTAMP,
                        field_path=field_path,
                        message="timestamp must be a string when provided",
                    )
                )
                continue
            try:
                _parse_timestamp(timestamp)
            except ValueError as exc:
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.INVALID_TIMESTAMP,
                        field_path=field_path,
                        message=str(exc),
                    )
                )
        return tuple(diagnostics)


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an explicit timezone offset")
    return parsed.astimezone(UTC)
