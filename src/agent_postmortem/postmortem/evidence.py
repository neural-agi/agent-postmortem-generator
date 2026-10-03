"""Bind analysis evidence pointers to canonical evidence without fabricating it."""

from __future__ import annotations

from agent_postmortem.analysis import EvidenceItem
from agent_postmortem.postmortem.context import ReportContext
from agent_postmortem.postmortem.models import (
    CausalChainStep,
    CitationStatus,
    ClaimSource,
    ContentBlock,
    ContentBlockType,
    DiagnosticCode,
    DiagnosticEntry,
    DiagnosticSeverity,
    EvidenceCitation,
    FindingSummary,
    PostmortemReport,
    ReportSection,
)
from agent_postmortem.postmortem.narrative import (
    DraftFinding,
    DraftStep,
    NarrativeDraft,
    section_title,
)


def bind_evidence(
    context: ReportContext,
    draft: NarrativeDraft,
    report_id: str,
    diagnostics: tuple[DiagnosticEntry, ...],
) -> PostmortemReport:
    """Attach evidence IDs, source nodes, stable event indices, and snippets."""

    issues = list(diagnostics)
    bound_sections: list[ReportSection] = []
    for order, section in enumerate(draft.sections):
        blocks = [
            _bind_block(block.text, block.claim_source, block.evidence, context, issues)
            for block in section.blocks
        ]
        if section.findings:
            blocks.append(
                ContentBlock(
                    type=ContentBlockType.TABLE,
                    text="",
                    rows=tuple(_bind_finding(item, context, issues) for item in section.findings),
                    claim_source=ClaimSource.ANALYSIS_CONCLUSION,
                )
            )
        if section.chain_steps:
            blocks.append(
                ContentBlock(
                    type=ContentBlockType.TABLE,
                    text="",
                    rows=tuple(_bind_step(item, context, issues) for item in section.chain_steps),
                    claim_source=ClaimSource.ANALYSIS_CONCLUSION,
                )
            )
        if section.evidence:
            blocks.append(
                ContentBlock(
                    type=ContentBlockType.TABLE,
                    text="",
                    rows=_bind_items(section.evidence, context, issues),
                    claim_source=ClaimSource.EVIDENCE,
                )
            )
        bound_sections.append(
            ReportSection(
                section_id=section.section_id,
                title=section_title(section.section_id),
                order=order,
                blocks=tuple(blocks),
            )
        )

    report = PostmortemReport(
        report_id=report_id,
        title=draft.title,
        metadata=draft.metadata,
        sections=tuple(bound_sections),
        diagnostics=_unique_diagnostics(issues),
    )
    return report


def _bind_block(
    text: str,
    source: ClaimSource,
    items: tuple[EvidenceItem, ...],
    context: ReportContext,
    issues: list[DiagnosticEntry],
) -> ContentBlock:
    return ContentBlock(
        type=ContentBlockType.PARAGRAPH,
        text=text,
        claim_source=source,
        evidence_refs=_bind_items(items, context, issues),
    )


def _bind_finding(
    item: DraftFinding, context: ReportContext, issues: list[DiagnosticEntry]
) -> FindingSummary:
    return FindingSummary(
        finding_id=item.finding_id,
        label=item.title,
        description=item.description,
        confidence=item.confidence,
        status=item.status,
        evidence_refs=_bind_items(item.evidence, context, issues),
    )


def _bind_step(
    item: DraftStep, context: ReportContext, issues: list[DiagnosticEntry]
) -> CausalChainStep:
    return CausalChainStep(
        step_id=item.step_id,
        sequence=item.sequence,
        cause=item.cause,
        effect=item.effect,
        evidence_refs=_bind_items(item.evidence, context, issues),
    )


def _bind_items(
    items: tuple[EvidenceItem, ...],
    context: ReportContext,
    issues: list[DiagnosticEntry],
) -> tuple[EvidenceCitation, ...]:
    citations: list[EvidenceCitation] = []
    for item in items:
        requested_ids: list[str] = []
        if item.evidence_id is not None:
            requested_ids.append(item.evidence_id)
        if item.source_event_id is not None:
            event = context.events_by_id.get(item.source_event_id)
            if event is not None:
                requested_ids.extend(
                    evidence_id
                    for evidence_id in event.evidence_refs
                    if evidence_id not in requested_ids
                )
        if not requested_ids:
            citation = _unavailable(item, context)
            if not _append_unique(citations, citation):
                issues.append(_duplicate_evidence_issue(citation))
            issues.append(
                DiagnosticEntry(
                    code=DiagnosticCode.MISSING_EVIDENCE,
                    severity=DiagnosticSeverity.WARNING,
                    message="An analysis claim has no canonical evidence identifier.",
                    related_refs=_related_refs(item),
                )
            )
            continue
        for evidence_id in requested_ids:
            citation, issue = _citation(evidence_id, item, context)
            if not _append_unique(citations, citation):
                issues.append(_duplicate_evidence_issue(citation))
            if issue is not None:
                issues.append(issue)
    return tuple(citations)


def _citation(
    evidence_id: str, item: EvidenceItem, context: ReportContext
) -> tuple[EvidenceCitation, DiagnosticEntry | None]:
    event = context.events_by_id.get(item.source_event_id or "")
    node_id = item.source_node_id
    if node_id is not None and node_id not in context.node_ids:
        node_id = None
    if event is not None and event.node_id is not None:
        node_id = event.node_id
    event_index = event.sequence_index if event is not None else None
    record = context.evidence_by_id.get(evidence_id)
    if record is None:
        citation = EvidenceCitation(
            evidence_id=evidence_id,
            trace_node_id=node_id,
            event_index=event_index,
            snippet="[evidence unavailable]",
            note="The referenced evidence ID is not present in the canonical document.",
            status=CitationStatus.INVALID_REFERENCE,
        )
        issue = DiagnosticEntry(
            code=DiagnosticCode.MISSING_EVIDENCE,
            severity=DiagnosticSeverity.WARNING,
            message=f"Canonical evidence {evidence_id!r} was referenced but not found.",
            related_refs=(f"evidence:{evidence_id}", *_related_refs(item)),
        )
        return citation, issue

    snippet = record.content_summary
    note = item.note
    if snippet is None:
        snippet = "[canonical record contains a content reference]"
        note = f"{note} Canonical content was referenced but not loaded.".strip()
    return (
        EvidenceCitation(
            evidence_id=evidence_id,
            trace_node_id=node_id,
            event_index=event_index,
            snippet=snippet,
            note=note,
            status=CitationStatus.AVAILABLE,
        ),
        None,
    )


def _unavailable(item: EvidenceItem, context: ReportContext) -> EvidenceCitation:
    node_id = item.source_node_id
    if node_id is not None and node_id not in context.node_ids:
        node_id = None
    event = context.events_by_id.get(item.source_event_id or "")
    if event is not None and event.node_id is not None:
        node_id = event.node_id
    return EvidenceCitation(
        evidence_id=None,
        trace_node_id=node_id,
        event_index=event.sequence_index if event is not None else None,
        snippet="[evidence unavailable]",
        note="No canonical evidence identifier was supplied by the analysis.",
        status=CitationStatus.UNAVAILABLE,
    )


def _append_unique(citations: list[EvidenceCitation], citation: EvidenceCitation) -> bool:
    key = (citation.evidence_id, citation.event_index)
    if all((existing.evidence_id, existing.event_index) != key for existing in citations):
        citations.append(citation)
        return True
    return False


def _duplicate_evidence_issue(citation: EvidenceCitation) -> DiagnosticEntry:
    refs = (f"evidence:{citation.evidence_id}",) if citation.evidence_id is not None else ()
    return DiagnosticEntry(
        code=DiagnosticCode.CONSISTENCY_VIOLATION,
        severity=DiagnosticSeverity.WARNING,
        message="Duplicate evidence was deduplicated by evidence ID and event index.",
        related_refs=refs,
    )


def _related_refs(item: EvidenceItem) -> tuple[str, ...]:
    refs: list[str] = []
    if item.source_node_id is not None:
        refs.append(f"node:{item.source_node_id}")
    if item.source_event_id is not None:
        refs.append(f"event:{item.source_event_id}")
    return tuple(refs)


def _unique_diagnostics(
    issues: list[DiagnosticEntry],
) -> tuple[DiagnosticEntry, ...]:
    unique: list[DiagnosticEntry] = []
    seen: set[DiagnosticEntry] = set()
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique.append(issue)
    return tuple(unique)
