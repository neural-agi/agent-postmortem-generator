"""Public domain exports for the canonical trace model.

This package exposes the immutable data contract used by downstream stages.
Validation remains in ``agent_postmortem.validation`` so the domain layer
stays data-only.
"""

from agent_postmortem.domain.document import CanonicalTraceDocument
from agent_postmortem.domain.event import TraceEvent
from agent_postmortem.domain.evidence import EvidenceRecord
from agent_postmortem.domain.issue import ValidationIssue
from agent_postmortem.domain.kinds import (
    EventKind,
    EventSeverity,
    EvidenceType,
    NodeKind,
    ValidationIssueSeverity,
)
from agent_postmortem.domain.node import TraceNode
from agent_postmortem.domain.provenance import ProvenanceRef
from agent_postmortem.domain.run import RunMetadata
from agent_postmortem.domain.schema import CanonicalTraceSchemaVersion
from agent_postmortem.domain.status import NodeStatus, RunStatus

__all__ = [
    "CanonicalTraceDocument",
    "CanonicalTraceSchemaVersion",
    "EventKind",
    "EventSeverity",
    "EvidenceRecord",
    "EvidenceType",
    "NodeKind",
    "NodeStatus",
    "ProvenanceRef",
    "RunMetadata",
    "RunStatus",
    "TraceEvent",
    "TraceNode",
    "ValidationIssue",
    "ValidationIssueSeverity",
]
