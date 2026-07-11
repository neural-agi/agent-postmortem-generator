"""Validated generic trace document types."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_postmortem.parsing.input import InputMetadata
from agent_postmortem.validation.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class TraceEnvelope:
    """Validated root-level trace metadata."""

    document_id: str
    trace_version: str
    run_id: str


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Validated generic trace event in input order."""

    event_id: str
    sequence_index: int
    timestamp: str | None = None
    parent_id: str | None = None
    raw_fields: tuple[tuple[str, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ValidatedTraceDocument:
    """Parsed and validated trace payload accepted by normalization."""

    envelope: TraceEnvelope
    events: tuple[TraceEvent, ...]
    raw_fields: tuple[tuple[str, object], ...]
    source_metadata: InputMetadata
    diagnostics: tuple[Diagnostic, ...]
