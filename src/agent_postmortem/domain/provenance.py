"""Provenance references for canonical trace facts.

Provenance keeps canonical facts tied back to the source records that produced
them. The model is intentionally small and serializes deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    """Reference back to source data for a canonical fact."""

    source_record_id: str
    source_path: str | None = None
    source_file: str | None = None
    raw_key_path: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.source_record_id:
            msg = "source_record_id must be a non-empty string"
            raise ValueError(msg)
        if any(part == "" for part in self.raw_key_path):
            msg = "raw_key_path entries must be non-empty strings"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, object]:
        """Return the stable snapshot serialization for source references."""

        data: dict[str, object] = {
            "source_record_id": self.source_record_id,
            "raw_key_path": list(self.raw_key_path),
        }
        if self.source_path is not None:
            data["source_path"] = self.source_path
        if self.source_file is not None:
            data["source_file"] = self.source_file
        return data
