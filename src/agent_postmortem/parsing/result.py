"""Parser result types."""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.parsing.input import RawInput
from agent_postmortem.parsing.json_decoder import ParsedJsonDocument
from agent_postmortem.validation.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Immutable result of the parsing stage."""

    raw_input: RawInput
    document: ParsedJsonDocument | None
    diagnostics: tuple[Diagnostic, ...]
