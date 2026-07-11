"""Event field validation for generic trace documents."""

from __future__ import annotations

from collections.abc import Mapping

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity


class EventValidator:
    """Validate the required event fields and local event types."""

    def validate(
        self, events: list[object]
    ) -> tuple[list[Mapping[str, object]], tuple[Diagnostic, ...]]:
        diagnostics: list[Diagnostic] = []
        validated: list[Mapping[str, object]] = []
        for index, item in enumerate(events):
            field_path = f"/events/{index}"
            if not isinstance(item, Mapping):
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.INVALID_FIELD_TYPE,
                        field_path=field_path,
                        message="each event must be an object",
                    )
                )
                continue
            event_id = item.get("event_id")
            sequence_index = item.get("sequence_index")
            parent_id = item.get("parent_id")
            if not isinstance(event_id, str) or not event_id:
                diagnostics.append(
                    _missing(
                        f"{field_path}/event_id",
                        "event_id is required and must be a non-empty string",
                    )
                )
                continue
            if not isinstance(sequence_index, int):
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.INVALID_FIELD_TYPE,
                        field_path=f"{field_path}/sequence_index",
                        message="sequence_index must be an integer",
                    )
                )
                continue
            if parent_id is not None and not isinstance(parent_id, str):
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.INVALID_FIELD_TYPE,
                        field_path=f"{field_path}/parent_id",
                        message="parent_id must be a string when provided",
                    )
                )
                continue
            validated.append(item)
        return validated, tuple(diagnostics)


def _missing(field_path: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=DiagnosticCode.MISSING_REQUIRED_FIELD,
        field_path=field_path,
        message=message,
    )
