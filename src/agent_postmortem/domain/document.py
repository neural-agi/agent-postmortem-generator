"""Top-level canonical trace document.

This module defines the immutable root object that downstream stages consume.
It owns only the document container shape and deterministic serialization.
Structural graph validation is intentionally handled in ``validation/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_postmortem.domain.event import TraceEvent
from agent_postmortem.domain.evidence import EvidenceRecord
from agent_postmortem.domain.issue import ValidationIssue
from agent_postmortem.domain.node import TraceNode
from agent_postmortem.domain.run import RunMetadata
from agent_postmortem.domain.schema import CanonicalTraceSchemaVersion


@dataclass(frozen=True, slots=True)
class CanonicalTraceDocument:
    """Immutable canonical document for one normalized execution run.

    The document preserves the ordered run, node, event, evidence, and issue
    collections exactly as supplied by validation/normalization. Ordering is
    explicit and preserved in serialization.
    """

    document_id: str
    schema_version: CanonicalTraceSchemaVersion
    run: RunMetadata
    nodes: tuple[TraceNode, ...] = field(default_factory=tuple)
    events: tuple[TraceEvent, ...] = field(default_factory=tuple)
    evidence: tuple[EvidenceRecord, ...] = field(default_factory=tuple)
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.document_id:
            msg = "document_id must be a non-empty string"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization for fixtures and diffs."""

        return {
            "document_id": self.document_id,
            "schema_version": self.schema_version.value,
            "run": self.run.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "events": [event.to_dict() for event in self.events],
            "evidence": [item.to_dict() for item in self.evidence],
            "issues": [issue.to_dict() for issue in self.issues],
        }
