"""Immutable, render-agnostic report intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from agent_postmortem.common.datetime import serialize_datetime_utc


class SectionId(StrEnum):
    """The fixed canonical v1 postmortem sections."""

    EXECUTIVE_SUMMARY = "executive_summary"
    FAILURE_CHAIN = "failure_chain"
    PRIMARY_FAULT = "primary_fault"
    CONTRIBUTING_FACTORS = "contributing_factors"
    EVIDENCE = "evidence"
    RECOMMENDED_FOLLOW_UPS = "recommended_follow_ups"


class ClaimSource(StrEnum):
    """Whether a block is an analysis conclusion, evidence, or placeholder."""

    EVIDENCE = "evidence"
    ANALYSIS_CONCLUSION = "analysis_conclusion"
    PLACEHOLDER = "placeholder"


class ContentBlockType(StrEnum):
    """Render-neutral content forms supported by report v1."""

    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    TABLE = "table"


class CitationStatus(StrEnum):
    """Whether a requested canonical evidence record was available."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID_REFERENCE = "invalid_reference"


class DiagnosticSeverity(StrEnum):
    """Report-level diagnostic severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(StrEnum):
    """Stable machine-readable report diagnostic categories."""

    MISSING_EVIDENCE = "missing_evidence"
    UNRESOLVED_AMBIGUITY = "unresolved_ambiguity"
    INCOMPLETE_ANALYSIS = "incomplete_analysis"
    CONTRADICTION = "contradiction"
    UNSUPPORTED_INFORMATION = "unsupported_information"
    CONSISTENCY_VIOLATION = "consistency_violation"
    UPSTREAM_DIAGNOSTIC = "upstream_diagnostic"


class ReportOutputVariant(StrEnum):
    """The only output variant implemented in report generation v1."""

    MARKDOWN = "markdown"


class VerbosityLevel(StrEnum):
    """The concise verbosity supported by the canonical v1 template."""

    CONCISE = "concise"


@dataclass(frozen=True, slots=True)
class ReportConfiguration:
    """Small, explicit set of supported report presentation settings."""

    title: str | None = None
    generated_at: datetime | None = None
    output_variant: ReportOutputVariant = ReportOutputVariant.MARKDOWN
    verbosity: VerbosityLevel = VerbosityLevel.CONCISE

    def __post_init__(self) -> None:
        if self.title is not None and not self.title.strip():
            raise ValueError("title must be non-empty when provided")
        if self.generated_at is not None and self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware when provided")
        if not isinstance(self.output_variant, ReportOutputVariant):
            raise TypeError("output_variant must be a ReportOutputVariant")
        if not isinstance(self.verbosity, VerbosityLevel):
            raise TypeError("verbosity must be a VerbosityLevel")


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Trace and module provenance carried by every generated report."""

    project_name: str
    module_part: str
    generated_at: datetime | None
    trace_id: str
    run_id: str
    analysis_version: str | None

    def to_dict(self) -> dict[str, object]:
        """Serialize fields in stable order with normalized UTC time."""

        return {
            "project_name": self.project_name,
            "module_part": self.module_part,
            "generated_at": (
                serialize_datetime_utc(self.generated_at) if self.generated_at is not None else None
            ),
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "analysis_version": self.analysis_version,
        }


@dataclass(frozen=True, slots=True)
class EvidenceCitation:
    """Link a report claim to canonical evidence or an explicit evidence gap."""

    evidence_id: str | None
    trace_node_id: str | None
    event_index: int | None
    snippet: str
    note: str
    status: CitationStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "row_type": "evidence_citation",
            "evidence_id": self.evidence_id,
            "trace_node_id": self.trace_node_id,
            "event_index": self.event_index,
            "snippet": self.snippet,
            "note": self.note,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class FindingSummary:
    """A fault candidate or finding already ordered by the Analysis Engine."""

    finding_id: str
    label: str
    description: str
    confidence: str | None
    evidence_refs: tuple[EvidenceCitation, ...]
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "row_type": "finding",
            "finding_id": self.finding_id,
            "label": self.label,
            "description": self.description,
            "confidence": self.confidence,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class CausalChainStep:
    """One ordered cause/effect transition from the upstream failure chain."""

    step_id: str
    sequence: int
    cause: str
    effect: str
    evidence_refs: tuple[EvidenceCitation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "row_type": "causal_chain_step",
            "step_id": self.step_id,
            "sequence": self.sequence,
            "cause": self.cause,
            "effect": self.effect,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class ActionItem:
    """An explicitly supplied follow-up; generation never invents actions."""

    item_id: str
    priority: str | None
    recommendation: str
    rationale: str
    evidence_refs: tuple[EvidenceCitation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "row_type": "action_item",
            "item_id": self.item_id,
            "priority": self.priority,
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
        }


type ReportRow = FindingSummary | CausalChainStep | EvidenceCitation | ActionItem


@dataclass(frozen=True, slots=True)
class ContentBlock:
    """Typed report content with evidence links kept separate from rendering."""

    type: ContentBlockType
    text: str
    bullets: tuple[str, ...] = field(default_factory=tuple)
    rows: tuple[ReportRow, ...] = field(default_factory=tuple)
    evidence_refs: tuple[EvidenceCitation, ...] = field(default_factory=tuple)
    claim_source: ClaimSource = ClaimSource.ANALYSIS_CONCLUSION

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type.value,
            "text": self.text,
            "bullets": list(self.bullets),
            "rows": [item.to_dict() for item in self.rows],
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "claim_source": self.claim_source.value,
        }


@dataclass(frozen=True, slots=True)
class ReportSection:
    """One fixed v1 section containing only ordered content blocks."""

    section_id: SectionId
    title: str
    order: int
    blocks: tuple[ContentBlock, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id.value,
            "title": self.title,
            "order": self.order,
            "blocks": [item.to_dict() for item in self.blocks],
        }


@dataclass(frozen=True, slots=True)
class DiagnosticEntry:
    """Report-generation or upstream-analysis diagnostic surfaced to readers."""

    code: DiagnosticCode
    severity: DiagnosticSeverity
    message: str
    related_refs: tuple[str, ...] = field(default_factory=tuple)
    section_id: SectionId | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "related_refs": list(self.related_refs),
            "section_id": self.section_id.value if self.section_id is not None else None,
        }


@dataclass(frozen=True, slots=True)
class PostmortemReport:
    """Complete immutable report IR, independent of any output format."""

    report_id: str
    title: str
    metadata: ReportMetadata
    sections: tuple[ReportSection, ...]
    diagnostics: tuple[DiagnosticEntry, ...]
    version: str = "v1"

    def to_dict(self) -> dict[str, object]:
        """Return the stable, snapshot-friendly report representation."""

        return {
            "report_id": self.report_id,
            "title": self.title,
            "metadata": self.metadata.to_dict(),
            "sections": [item.to_dict() for item in self.sections],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class PostmortemGenerationResult:
    """The verified structured report and its deterministic Markdown body."""

    report: PostmortemReport
    markdown: str


class ReportStructureError(ValueError):
    """Raised when a report violates a hard v1 template invariant."""
