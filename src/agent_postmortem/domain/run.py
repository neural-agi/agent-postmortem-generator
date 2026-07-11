"""Run metadata for canonical traces.

This module holds the per-run execution envelope only. It does not perform
validation beyond local invariants and it serializes deterministically in UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agent_postmortem.common.datetime import serialize_datetime_utc
from agent_postmortem.domain.provenance import ProvenanceRef
from agent_postmortem.domain.status import RunStatus


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Describes the execution run without framework-specific behavior.

    The run metadata carries the document-level execution identity and timing
    data. It remains frozen and serializes with explicit field ordering.
    """

    run_id: str
    status: RunStatus
    source_format: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    environment: str | None = None
    provenance: ProvenanceRef | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            msg = "run_id must be a non-empty string"
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

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization for run fixtures."""

        data: dict[str, object] = {
            "run_id": self.run_id,
            "status": self.status.value,
        }
        if self.source_format is not None:
            data["source_format"] = self.source_format
        if self.started_at is not None:
            data["started_at"] = serialize_datetime_utc(self.started_at)
        if self.ended_at is not None:
            data["ended_at"] = serialize_datetime_utc(self.ended_at)
        if self.environment is not None:
            data["environment"] = self.environment
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data
