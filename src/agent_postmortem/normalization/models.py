"""Immutable output types owned by the normalization stage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent_postmortem.domain.document import CanonicalTraceDocument
from agent_postmortem.domain.provenance import ProvenanceRef


class NormalizationSeverity(StrEnum):
    """Severity of a deterministic normalization finding."""

    WARNING = "warning"
    ERROR = "error"


class NormalizationCode(StrEnum):
    """Machine-readable normalization outcomes."""

    IDENTICAL_DUPLICATE = "identical_duplicate"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    UNKNOWN_RECORD_KIND = "unknown_record_kind"
    MISSING_PARENT = "missing_parent"
    CYCLE_EDGE_DROPPED = "cycle_edge_dropped"
    MISSING_TIMESTAMP = "missing_timestamp"
    INVALID_TIMESTAMP_CANDIDATE = "invalid_timestamp_candidate"
    CONFLICTING_TIMESTAMPS = "conflicting_timestamps"


class RelationType(StrEnum):
    """Explicit relation kinds currently represented by the input contract."""

    PARENT = "parent"


@dataclass(frozen=True, slots=True)
class NormalizationDiagnostic:
    """One stable finding produced while converting validated records."""

    severity: NormalizationSeverity
    code: NormalizationCode
    message: str
    affected_ids: tuple[str, ...] = ()
    source_ref: ProvenanceRef | None = None


@dataclass(frozen=True, slots=True)
class CanonicalRelation:
    """Explicit source relationship resolved to canonical record identifiers."""

    relation_type: RelationType
    from_id: str
    to_id: str
    source_ref: ProvenanceRef


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    """Fingerprint and source location for one normalized canonical field."""

    canonical_field: str
    source_record_id: str
    source_path: str
    raw_value_fingerprint: str


@dataclass(frozen=True, slots=True)
class NormalizationSummary:
    """Deterministic counts describing the normalization pass."""

    input_records: int
    canonical_entities: int
    duplicates: int
    dropped_edges: int
    opaque_records: int


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Canonical trace plus diagnostics and traceability metadata."""

    normalization_schema_version: str
    canonical_trace: CanonicalTraceDocument
    diagnostics: tuple[NormalizationDiagnostic, ...]
    summary: NormalizationSummary
    relations: tuple[CanonicalRelation, ...]
    provenance_index: tuple[ProvenanceEntry, ...]
