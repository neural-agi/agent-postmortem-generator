"""Evidence records for canonical traces.

Evidence preserves concrete source material that analysis may cite later. The
records are frozen, traceable, and serialized without interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.domain.kinds import EvidenceType
from agent_postmortem.domain.provenance import ProvenanceRef


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Concrete evidence that may be cited later by analysis.

    Evidence remains attached to provenance so the canonical model does not
    flatten source identity into opaque text.
    """

    evidence_id: str
    evidence_type: EvidenceType
    content_ref: str | None = None
    content_summary: str | None = None
    provenance: ProvenanceRef | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id:
            msg = "evidence_id must be a non-empty string"
            raise ValueError(msg)
        if self.content_ref is None and self.content_summary is None:
            msg = "content_ref or content_summary must be provided"
            raise ValueError(msg)
        if self.content_ref is not None and self.content_ref == "":
            msg = "content_ref must be non-empty when provided"
            raise ValueError(msg)
        if self.content_summary is not None and self.content_summary == "":
            msg = "content_summary must be non-empty when provided"
            raise ValueError(msg)
        if self.provenance is None and self.evidence_type != EvidenceType.REFERENCE:
            msg = "provenance is required for meaningful evidence records"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization for evidence fixtures."""

        data: dict[str, object] = {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
        }
        if self.content_ref is not None:
            data["content_ref"] = self.content_ref
        if self.content_summary is not None:
            data["content_summary"] = self.content_summary
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data
