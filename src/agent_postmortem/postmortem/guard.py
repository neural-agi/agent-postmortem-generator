"""Check report structure and evidence consistency without rewriting content."""

from __future__ import annotations

from collections.abc import MutableSequence
from dataclasses import replace

from agent_postmortem.analysis import AnalysisResult, TerminalOutcome
from agent_postmortem.domain import CanonicalTraceDocument
from agent_postmortem.postmortem.models import (
    ActionItem,
    CausalChainStep,
    CitationStatus,
    ContentBlock,
    ContentBlockType,
    DiagnosticCode,
    DiagnosticEntry,
    DiagnosticSeverity,
    EvidenceCitation,
    FindingSummary,
    PostmortemReport,
    ReportRow,
    ReportStructureError,
    SectionId,
)
from agent_postmortem.postmortem.narrative import section_title

_SECTION_ORDER = (
    SectionId.EXECUTIVE_SUMMARY,
    SectionId.FAILURE_CHAIN,
    SectionId.PRIMARY_FAULT,
    SectionId.CONTRIBUTING_FACTORS,
    SectionId.EVIDENCE,
    SectionId.RECOMMENDED_FOLLOW_UPS,
)


def check_report(
    report: PostmortemReport,
    trace: CanonicalTraceDocument,
    analysis: AnalysisResult,
) -> PostmortemReport:
    """Validate required structure and add deterministic consistency findings."""

    expected = tuple((section_id, index) for index, section_id in enumerate(_SECTION_ORDER))
    actual = tuple((section.section_id, section.order) for section in report.sections)
    if actual != expected:
        raise ReportStructureError("report sections do not match the fixed v1 order")
    if not report.report_id or not report.title.strip() or report.version != "v1":
        raise ReportStructureError("report identity, title, or version is invalid")
    if (
        not report.metadata.project_name.strip()
        or not report.metadata.module_part.strip()
        or not report.metadata.trace_id.strip()
        or not report.metadata.run_id.strip()
        or (
            report.metadata.generated_at is not None
            and report.metadata.generated_at.utcoffset() is None
        )
    ):
        raise ReportStructureError("report metadata contains invalid required values")
    for section in report.sections:
        if section.title != section_title(section.section_id):
            raise ReportStructureError(
                f"section {section.section_id.value!r} has an invalid fixed title"
            )
        if not section.blocks:
            raise ReportStructureError(
                f"required section {section.section_id.value!r} has no content"
            )
        for block in section.blocks:
            if not _valid_block(block):
                raise ReportStructureError(
                    f"section {section.section_id.value!r} contains an invalid content block"
                )

    known_evidence = {item.evidence_id for item in trace.evidence}
    known_nodes = {node.node_id for node in trace.nodes}
    known_event_locations = {(event.node_id, event.sequence_index) for event in trace.events}
    known_chain_ids = known_nodes | {
        event.event_id for event in trace.events if event.node_id is None
    }
    issues: list[DiagnosticEntry] = []
    seen_text: set[str] = set()
    seen_content: set[str] = set()
    seen_evidence_locations: set[tuple[str | None, int | None]] = set()
    for section in report.sections:
        for block in section.blocks:
            if block.text and block.text in seen_text:
                issues.append(
                    _consistency_issue(
                        "Repeated narrative content appears in multiple report blocks.",
                        section.section_id,
                    )
                )
            if block.text:
                seen_text.add(block.text)
            if (
                block.claim_source.value == "evidence"
                and not block.evidence_refs
                and not any(isinstance(row, EvidenceCitation) for row in block.rows)
            ):
                issues.append(
                    _consistency_issue(
                        "An evidence-backed claim has no evidence references.",
                        section.section_id,
                    )
                )
            for citation in block.evidence_refs:
                _check_citation(
                    citation,
                    known_evidence,
                    known_nodes,
                    known_event_locations,
                    issues,
                    section.section_id,
                )
            for row in block.rows:
                _check_row(
                    row,
                    known_evidence,
                    known_nodes,
                    known_event_locations,
                    issues,
                    seen_text,
                    known_chain_ids,
                    section.section_id,
                )
                if isinstance(row, EvidenceCitation) and row.status is CitationStatus.AVAILABLE:
                    location = (row.evidence_id, row.event_index)
                    if location in seen_evidence_locations:
                        issues.append(
                            _consistency_issue(
                                "Duplicate evidence ID and event index appear in the evidence table.",
                                section.section_id,
                            )
                        )
                    seen_evidence_locations.add(location)
                    if row.snippet in seen_content:
                        issues.append(
                            DiagnosticEntry(
                                code=DiagnosticCode.CONSISTENCY_VIOLATION,
                                severity=DiagnosticSeverity.WARNING,
                                message="Duplicate canonical evidence content is cited more than once.",
                                related_refs=(f"evidence:{row.evidence_id}",),
                                section_id=section.section_id,
                            )
                        )
                    seen_content.add(row.snippet)

    if (
        analysis.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
        and analysis.first_fault is not None
    ):
        issues.append(
            DiagnosticEntry(
                code=DiagnosticCode.CONTRADICTION,
                severity=DiagnosticSeverity.WARNING,
                message="Analysis reports successful completion and a primary fault.",
                related_refs=(f"node:{analysis.first_fault.node_id}",),
            )
        )
    existing = set(report.diagnostics)
    appended = tuple(issue for issue in issues if issue not in existing)
    return replace(report, diagnostics=(*report.diagnostics, *appended))


def _valid_block(block: ContentBlock) -> bool:
    if block.type is ContentBlockType.PARAGRAPH:
        return bool(block.text.strip()) and not block.bullets and not block.rows
    if block.type is ContentBlockType.BULLET_LIST:
        return (
            not block.text
            and bool(block.bullets)
            and all(item.strip() for item in block.bullets)
            and not block.rows
        )
    return (
        not block.text
        and not block.bullets
        and bool(block.rows)
        and all(_valid_row(row) for row in block.rows)
    )


def _valid_row(row: ReportRow) -> bool:
    if isinstance(row, FindingSummary):
        return bool(
            row.finding_id.strip()
            and row.label.strip()
            and row.description.strip()
            and row.status.strip()
        )
    if isinstance(row, CausalChainStep):
        return bool(
            row.step_id.strip() and row.sequence >= 0 and row.cause.strip() and row.effect.strip()
        )
    if isinstance(row, ActionItem):
        return bool(row.item_id.strip() and row.recommendation.strip() and row.rationale.strip())
    return bool(
        row.snippet.strip()
        and row.note.strip()
        and (row.status is not CitationStatus.AVAILABLE or row.evidence_id)
        and (row.event_index is None or row.event_index >= 0)
    )


def _check_row(
    row: ReportRow,
    known_evidence: set[str],
    known_nodes: set[str],
    known_event_locations: set[tuple[str | None, int]],
    issues: list[DiagnosticEntry],
    seen_text: set[str],
    known_chain_ids: set[str],
    section_id: SectionId,
) -> None:
    if isinstance(row, FindingSummary):
        if row.description in seen_text:
            issues.append(
                _consistency_issue("Repeated finding content appears in the report.", section_id)
            )
        seen_text.add(row.description)
        if not row.evidence_refs and row.status not in {
            "analysis_selected",
            "unresolved_alternative",
        }:
            issues.append(
                _consistency_issue(
                    "A finding has neither evidence nor an unresolved analysis status.", section_id
                )
            )
        citations = row.evidence_refs
    elif isinstance(row, CausalChainStep):
        chain_text = f"{row.cause}->{row.effect}"
        if chain_text in seen_text:
            issues.append(
                _consistency_issue(
                    "Repeated causal-chain content appears in the report.", section_id
                )
            )
        seen_text.add(chain_text)
        if row.cause not in known_chain_ids or row.effect not in known_chain_ids:
            issues.append(
                _consistency_issue(
                    "A causal-chain step references an unknown trace entity.", section_id
                )
            )
        citations = row.evidence_refs
    elif isinstance(row, ActionItem):
        citations = row.evidence_refs
        if not citations:
            issues.append(
                _consistency_issue(
                    "An action item has no supporting evidence references.", section_id
                )
            )
    else:
        citations = (row,)
    for citation in citations:
        _check_citation(
            citation,
            known_evidence,
            known_nodes,
            known_event_locations,
            issues,
            section_id,
        )


def _check_citation(
    citation: EvidenceCitation,
    known_evidence: set[str],
    known_nodes: set[str],
    known_event_locations: set[tuple[str | None, int]],
    issues: MutableSequence[DiagnosticEntry],
    section_id: SectionId,
) -> None:
    if citation.status is CitationStatus.AVAILABLE and citation.evidence_id not in known_evidence:
        issues.append(
            _consistency_issue(
                "A citation marked available does not resolve in the canonical evidence bundle.",
                section_id,
            )
        )
    elif citation.status is not CitationStatus.AVAILABLE:
        issues.append(
            DiagnosticEntry(
                code=DiagnosticCode.MISSING_EVIDENCE,
                severity=DiagnosticSeverity.WARNING,
                message=citation.note,
                related_refs=(
                    (f"evidence:{citation.evidence_id}",)
                    if citation.evidence_id is not None
                    else ()
                ),
                section_id=section_id,
            )
        )
    if citation.trace_node_id is not None and citation.trace_node_id not in known_nodes:
        issues.append(
            _consistency_issue(
                "A citation references a trace node outside the canonical document.", section_id
            )
        )
    if (
        citation.event_index is not None
        and (
            citation.trace_node_id,
            citation.event_index,
        )
        not in known_event_locations
    ):
        issues.append(
            _consistency_issue(
                "A citation event index does not resolve to its canonical node.", section_id
            )
        )


def _consistency_issue(message: str, section_id: SectionId) -> DiagnosticEntry:
    return DiagnosticEntry(
        code=DiagnosticCode.CONSISTENCY_VIOLATION,
        severity=DiagnosticSeverity.WARNING,
        message=message,
        section_id=section_id,
    )
