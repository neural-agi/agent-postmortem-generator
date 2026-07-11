"""Validation issues for canonical traces.

Validation issues are part of the canonical document so non-fatal structural
problems can be preserved alongside the run data.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.domain.kinds import ValidationIssueSeverity
from agent_postmortem.domain.provenance import ProvenanceRef


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Structural problem or warning associated with the canonical document."""

    issue_id: str
    severity: ValidationIssueSeverity
    field_path: str
    message: str
    source_ref: ProvenanceRef | None = None

    def __post_init__(self) -> None:
        if not self.issue_id:
            msg = "issue_id must be a non-empty string"
            raise ValueError(msg)
        if not self.field_path:
            msg = "field_path must be a non-empty string"
            raise ValueError(msg)
        if not self.message:
            msg = "message must be a non-empty string"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization for validation reporting."""

        data: dict[str, object] = {
            "issue_id": self.issue_id,
            "severity": self.severity.value,
            "field_path": self.field_path,
            "message": self.message,
        }
        if self.source_ref is not None:
            data["source_ref"] = self.source_ref.to_dict()
        return data
