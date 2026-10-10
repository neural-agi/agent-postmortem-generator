"""Immutable intermediate representation for deterministic execution graphs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GraphNodeKind(StrEnum):
    """Kinds of graph nodes supported by the canonical graph view."""

    EVENT = "event"


class GraphEdgeKind(StrEnum):
    """Relationships that may be represented without inference."""

    SEQUENCE = "sequence"
    PARENT = "parent"
    RETRY = "retry"
    CAUSAL = "causal"


class GraphGroupKind(StrEnum):
    """Deterministic display group kinds."""

    EXECUTION_SCOPE = "execution_scope"
    RETRY_GROUP = "retry_group"


class GraphAnnotationType(StrEnum):
    """Analysis facts that may annotate graph elements."""

    FIRST_FAULT = "first_fault"
    TERMINAL_FAILURE = "terminal_failure"
    RETRY = "retry"
    PROPAGATION = "propagation"


class GraphDiagnosticSeverity(StrEnum):
    """Severity of a graph-generation diagnostic."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One canonical event projected into the graph."""

    node_id: str
    event_id: str
    kind: GraphNodeKind
    label: str
    status: str
    order_index: int
    scope_id: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One explicit or chronological relationship between graph nodes."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    kind: GraphEdgeKind
    label: str
    evidence_refs: tuple[str, ...] = ()
    style_hint: str | None = None


@dataclass(frozen=True, slots=True)
class GraphGroup:
    """Stable grouping of related graph nodes for downstream display."""

    group_id: str
    kind: GraphGroupKind
    label: str
    member_node_ids: tuple[str, ...]
    order_index: int


@dataclass(frozen=True, slots=True)
class GraphAnnotation:
    """An analysis-backed marker attached to exactly one graph target."""

    target_id: str
    annotation_type: GraphAnnotationType
    label: str
    severity: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphDiagnostic:
    """Structured explanation of degraded or rejected graph input."""

    code: str
    severity: GraphDiagnosticSeverity
    message: str
    related_ids: tuple[str, ...] = ()
    recoverable: bool = True


@dataclass(frozen=True, slots=True)
class GraphMetadata:
    """Stable graph metadata used by snapshot tests and later serializers."""

    graph_version: str
    source_trace_id: str
    analysis_id: str
    node_count: int
    edge_count: int
    determinism_hash: str


@dataclass(frozen=True, slots=True)
class GraphDocument:
    """Canonical graph artifact consumed by renderers and report assembly."""

    graph_id: str
    source_trace_id: str
    analysis_id: str
    version: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    groups: tuple[GraphGroup, ...]
    annotations: tuple[GraphAnnotation, ...]
    diagnostics: tuple[GraphDiagnostic, ...]
    metadata: GraphMetadata


class GraphContractError(ValueError):
    """Raised when graph generation receives an unresolvable hard reference."""
