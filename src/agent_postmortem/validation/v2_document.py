"""Immutable validated input structures for Generic Trace Contract v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent_postmortem.parsing.input import InputMetadata
from agent_postmortem.validation.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class V2Run:
    """Explicit v2 run metadata."""

    status: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    source_format: str | None = None


@dataclass(frozen=True, slots=True)
class V2Node:
    """Explicit v2 execution node."""

    node_id: str
    kind: str | None
    status: str | None
    sequence_index: int
    parent_node_id: str | None = None
    series_id: str | None = None
    attempt_index: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    raw_fields: tuple[tuple[str, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class V2Event:
    """Explicit v2 timeline event."""

    event_id: str
    sequence_index: int
    timestamp: datetime | None
    kind: str | None
    severity: str | None
    node_id: str | None = None
    parent_id: str | None = None
    payload: str | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    timestamp_candidates: tuple[tuple[str, datetime], ...] = field(default_factory=tuple)
    raw_fields: tuple[tuple[str, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class V2Evidence:
    """Explicit source evidence record."""

    evidence_id: str
    evidence_type: str
    content_ref: str | None = None
    content_summary: str | None = None
    raw_fields: tuple[tuple[str, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class V2ValidatedTraceDocument:
    """Trusted, typed v2 input ready for a later normalization stage."""

    document_id: str
    trace_version: str
    run_id: str
    run: V2Run | None
    nodes: tuple[V2Node, ...]
    events: tuple[V2Event, ...]
    evidence: tuple[V2Evidence, ...]
    raw_fields: tuple[tuple[str, object], ...]
    source_metadata: InputMetadata
    diagnostics: tuple[Diagnostic, ...]
