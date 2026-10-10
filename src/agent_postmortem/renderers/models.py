"""Immutable contracts for deterministic Part 7 rendering and export."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from agent_postmortem.graph.models import GraphDocument
from agent_postmortem.postmortem.models import PostmortemReport


class OutputFormat(StrEnum):
    """Formats supported by the MVP export layer."""

    MARKDOWN = "markdown"
    JSON = "json"
    MERMAID = "mermaid"


@dataclass(frozen=True, slots=True)
class ReportBundle:
    """Final report and optional already-derived graph payload."""

    report: PostmortemReport
    graph: GraphDocument | None = None


@dataclass(frozen=True, slots=True)
class ExportPlan:
    """Validated export targets, naming, destination, and overwrite policy."""

    output_dir: Path
    targets: tuple[OutputFormat, ...]
    filename_stem: str = "postmortem"
    overwrite: bool = False
    allowed_base: Path | None = None


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    """Receipt for one emitted artifact."""

    kind: OutputFormat
    path: Path
    bytes_written: int
    sha256: str
    content_type: str


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Receipt for an export attempt and its produced artifacts."""

    success: bool
    artifacts: tuple[RenderedArtifact, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class ExportError(ValueError):
    """Raised when export preconditions or filesystem operations fail."""
