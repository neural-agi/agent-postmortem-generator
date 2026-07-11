"""Semantic validation for generic trace payloads.

This stage validates cross-event invariants after structural checks have
confirmed the event collection is well formed.
"""

from __future__ import annotations

from collections.abc import Mapping

from agent_postmortem.validation.diagnostics import Diagnostic
from agent_postmortem.validation.ordering_validator import OrderingValidator
from agent_postmortem.validation.reference_validator import ReferenceValidator


class SemanticValidator:
    """Validate deterministic invariants over validated event objects."""

    def __init__(self) -> None:
        self._reference_validator = ReferenceValidator()
        self._ordering_validator = OrderingValidator()

    def validate(self, events: list[Mapping[str, object]]) -> tuple[Diagnostic, ...]:
        diagnostics = list(self._reference_validator.validate(events))
        diagnostics.extend(self._ordering_validator.validate(events))
        return tuple(diagnostics)
