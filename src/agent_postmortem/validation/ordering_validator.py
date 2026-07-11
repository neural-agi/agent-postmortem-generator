"""Deterministic ordering validation for trace events."""

from __future__ import annotations

from collections.abc import Mapping

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity


class OrderingValidator:
    """Validate explicit event ordering constraints."""

    def validate(self, events: list[Mapping[str, object]]) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        previous = -1
        for index, event in enumerate(events):
            sequence_index = event.get("sequence_index")
            if not isinstance(sequence_index, int):
                continue
            if sequence_index < previous:
                diagnostics.append(
                    Diagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code=DiagnosticCode.OUT_OF_ORDER_EVENTS,
                        field_path=f"/events/{index}/sequence_index",
                        message="events must be in deterministic sequence order",
                    )
                )
            previous = sequence_index
        return tuple(diagnostics)
