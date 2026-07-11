"""Canonical trace nodes.

Nodes represent the logical execution structure used by downstream analysis.
They preserve explicit ordering, hierarchy, and provenance while remaining
immutable and framework-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent_postmortem.common.datetime import serialize_datetime_utc
from agent_postmortem.domain.kinds import NodeKind
from agent_postmortem.domain.provenance import ProvenanceRef
from agent_postmortem.domain.status import NodeStatus


@dataclass(frozen=True, slots=True)
class TraceNode:
    """Logical unit of execution in the canonical trace."""

    node_id: str
    kind: NodeKind
    sequence_index: int
    status: NodeStatus = NodeStatus.UNKNOWN
    parent_node_id: str | None = None
    series_id: str | None = None
    attempt_index: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    provenance: ProvenanceRef | None = None

    def __post_init__(self) -> None:
        if not self.node_id:
            msg = "node_id must be a non-empty string"
            raise ValueError(msg)
        if self.sequence_index < 0:
            msg = "sequence_index must be >= 0"
            raise ValueError(msg)
        if self.parent_node_id == "":
            msg = "parent_node_id must be non-empty when provided"
            raise ValueError(msg)
        if self.series_id == "":
            msg = "series_id must be non-empty when provided"
            raise ValueError(msg)
        if self.attempt_index is not None and self.attempt_index < 0:
            msg = "attempt_index must be >= 0 when provided"
            raise ValueError(msg)
        if self.started_at is not None and self.started_at.tzinfo is None:
            msg = "started_at must be timezone-aware when provided"
            raise ValueError(msg)
        if self.ended_at is not None and self.ended_at.tzinfo is None:
            msg = "ended_at must be timezone-aware when provided"
            raise ValueError(msg)
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            msg = "ended_at cannot be earlier than started_at"
            raise ValueError(msg)
        if any(key == "" or value == "" for key, value in self.attributes):
            msg = "attributes must contain non-empty keys and values"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization in document order."""

        data: dict[str, object] = {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "sequence_index": self.sequence_index,
            "status": self.status.value,
            "attributes": dict(self.attributes),
        }
        if self.parent_node_id is not None:
            data["parent_node_id"] = self.parent_node_id
        if self.series_id is not None:
            data["series_id"] = self.series_id
        if self.attempt_index is not None:
            data["attempt_index"] = self.attempt_index
        if self.started_at is not None:
            data["started_at"] = serialize_datetime_utc(self.started_at)
        if self.ended_at is not None:
            data["ended_at"] = serialize_datetime_utc(self.ended_at)
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data
