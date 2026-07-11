"""Canonical trace events.

Events are atomic timeline facts. The model is immutable, keeps explicit
sequence ordering, and serializes deterministically in UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent_postmortem.common.datetime import serialize_datetime_utc
from agent_postmortem.domain.kinds import EventKind, EventSeverity
from agent_postmortem.domain.provenance import ProvenanceRef


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Atomic point-in-time fact in the canonical run timeline."""

    event_id: str
    sequence_index: int
    kind: EventKind
    timestamp: datetime | None = None
    node_id: str | None = None
    payload: str | None = None
    severity: EventSeverity = EventSeverity.UNKNOWN
    provenance: ProvenanceRef | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.event_id:
            msg = "event_id must be a non-empty string"
            raise ValueError(msg)
        if self.sequence_index < 0:
            msg = "sequence_index must be >= 0"
            raise ValueError(msg)
        if self.node_id == "":
            msg = "node_id must be non-empty when provided"
            raise ValueError(msg)
        if self.payload == "":
            msg = "payload must be non-empty when provided"
            raise ValueError(msg)
        if self.timestamp is not None and self.timestamp.tzinfo is None:
            msg = "timestamp must be timezone-aware when provided"
            raise ValueError(msg)
        if any(not ref for ref in self.evidence_refs):
            msg = "evidence_refs entries must be non-empty strings"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization in explicit sequence order."""

        data: dict[str, object] = {
            "event_id": self.event_id,
            "sequence_index": self.sequence_index,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "evidence_refs": list(self.evidence_refs),
        }
        if self.timestamp is not None:
            data["timestamp"] = serialize_datetime_utc(self.timestamp)
        if self.node_id is not None:
            data["node_id"] = self.node_id
        if self.payload is not None:
            data["payload"] = self.payload
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data
