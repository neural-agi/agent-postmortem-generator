"""Reference integrity validation for trace events."""

from __future__ import annotations

from collections.abc import Mapping

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity


class ReferenceValidator:
    """Validate parent references and related cross-record links."""

    def validate(self, events: list[Mapping[str, object]]) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        seen_ids: set[str] = set()
        for index, event in enumerate(events):
            event_id = event.get("event_id")
            if not isinstance(event_id, str):
                continue
            if event_id in seen_ids:
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.DUPLICATE_IDENTIFIER,
                        field_path=f"/events/{index}/event_id",
                        message="event_id values must be unique",
                    )
                )
                continue
            seen_ids.add(event_id)
        for index, event in enumerate(events):
            parent_id = event.get("parent_id")
            if not isinstance(parent_id, str):
                continue
            if parent_id not in seen_ids:
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.BROKEN_REFERENCE,
                        field_path=f"/events/{index}/parent_id",
                        message="parent_id must reference an existing event_id",
                    )
                )
        return tuple(diagnostics)
