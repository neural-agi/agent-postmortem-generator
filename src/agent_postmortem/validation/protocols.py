"""Common validation contracts."""

from __future__ import annotations

from typing import Protocol

from agent_postmortem.validation.diagnostics import Diagnostic


class Validator(Protocol):
    """Lightweight contract shared by validator components."""

    def validate(self, *args: object, **kwargs: object) -> tuple[Diagnostic, ...]:
        """Return deterministic diagnostics for the supplied input."""
