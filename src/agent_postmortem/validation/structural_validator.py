"""Structural validation for parsed trace payloads."""

from __future__ import annotations

from collections.abc import Mapping

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity
from agent_postmortem.validation.event_validator import EventValidator
from agent_postmortem.validation.root_validator import RootValidator
from agent_postmortem.validation.timestamp_validator import TimestampValidator
from agent_postmortem.validation.trace_document import TraceEnvelope


class StructuralValidator:
    """Validate the top-level trace shape and event collection."""

    def __init__(self) -> None:
        self._root_validator = RootValidator()
        self._event_validator = EventValidator()
        self._timestamp_validator = TimestampValidator()

    def validate(
        self, root: Mapping[str, object]
    ) -> tuple[TraceEnvelope | None, list[Mapping[str, object]], tuple[Diagnostic, ...]]:
        diagnostics: list[Diagnostic] = []
        envelope, root_diagnostics = self._root_validator.validate(root)
        diagnostics.extend(root_diagnostics)
        if envelope is None:
            return None, [], tuple(diagnostics)

        raw_events = root.get("events")
        if not isinstance(raw_events, list):
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=DiagnosticCode.MISSING_REQUIRED_FIELD,
                    field_path="/events",
                    message="events is required and must be a list",
                )
            )
            return envelope, [], tuple(diagnostics)

        validated_events, event_diagnostics = self._event_validator.validate(raw_events)
        diagnostics.extend(event_diagnostics)
        diagnostics.extend(self._timestamp_validator.validate(validated_events))
        return envelope, validated_events, tuple(diagnostics)
