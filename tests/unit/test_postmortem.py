from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from agent_postmortem.analysis import (
    AnalysisEngine,
)
from agent_postmortem.analysis import (
    DiagnosticIssue as AnalysisDiagnostic,
)
from agent_postmortem.analysis import (
    IssueCode as AnalysisIssueCode,
)
from agent_postmortem.analysis import (
    IssueSeverity as AnalysisIssueSeverity,
)
from agent_postmortem.domain import (
    CanonicalTraceDocument,
    CanonicalTraceSchemaVersion,
    EventKind,
    EvidenceRecord,
    EvidenceType,
    NodeKind,
    NodeStatus,
    ProvenanceRef,
    RunMetadata,
    RunStatus,
    TraceEvent,
    TraceNode,
)
from agent_postmortem.postmortem import (
    CitationStatus,
    DiagnosticCode,
    PostmortemEngine,
    ReportConfiguration,
    ReportStructureError,
    SectionId,
    VerbosityLevel,
)
from agent_postmortem.postmortem.guard import check_report


def _failure_trace(
    *,
    evidence: bool = True,
    candidate_count: int = 1,
    timestamps: bool = True,
    retries: bool = False,
) -> CanonicalTraceDocument:
    base = datetime(2026, 10, 3, 8, tzinfo=UTC) if timestamps else None
    nodes: list[TraceNode] = []
    events: list[TraceEvent] = []
    records: list[EvidenceRecord] = []
    for index in range(candidate_count):
        node_id = f"tool-{index + 1}"
        event_id = f"error-{index + 1}"
        evidence_id = f"evidence-{index + 1}"
        source = ProvenanceRef(source_record_id=event_id)
        nodes.append(
            TraceNode(
                node_id=node_id,
                kind=NodeKind.TOOL_CALL,
                sequence_index=index,
                status=NodeStatus.FAILURE,
                started_at=base,
                provenance=source,
            )
        )
        events.append(
            TraceEvent(
                event_id=event_id,
                sequence_index=index * (3 if retries else 1),
                kind=EventKind.ERROR,
                timestamp=base,
                node_id=node_id,
                payload="connection reset",
                provenance=source,
                evidence_refs=(evidence_id,) if evidence else (),
            )
        )
        if evidence:
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type=EvidenceType.INLINE_TEXT,
                    content_summary="Tool reported connection reset.",
                    provenance=source,
                )
            )
        if retries:
            retry_source = ProvenanceRef(source_record_id=f"retry-{index + 1}")
            events.append(
                TraceEvent(
                    event_id=f"retry-{index + 1}",
                    sequence_index=index * 3 + 1,
                    kind=EventKind.RETRY,
                    timestamp=base,
                    node_id=node_id,
                    provenance=retry_source,
                )
            )
            nodes[-1] = replace(nodes[-1], series_id="same-series", attempt_index=index)
    if retries and candidate_count == 1:
        retry_node = TraceNode(
            node_id="tool-2",
            kind=NodeKind.TOOL_CALL,
            sequence_index=1,
            status=NodeStatus.FAILURE,
            series_id="same-series",
            attempt_index=1,
            started_at=base,
            provenance=ProvenanceRef(source_record_id="error-2"),
        )
        nodes.append(retry_node)
        events.append(
            TraceEvent(
                event_id="error-2",
                sequence_index=2,
                kind=EventKind.ERROR,
                timestamp=base,
                node_id=retry_node.node_id,
                payload="connection reset",
                provenance=ProvenanceRef(source_record_id="error-2"),
                evidence_refs=("evidence-1",) if evidence else (),
            )
        )
    instant = base
    return CanonicalTraceDocument(
        document_id="trace-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(
            run_id="run-1",
            status=RunStatus.FAILURE,
            started_at=instant,
            ended_at=instant,
        ),
        nodes=tuple(nodes),
        events=tuple(events),
        evidence=tuple(records),
    )


def _failure_result(trace: CanonicalTraceDocument):
    return AnalysisEngine().analyze(trace)


def test_failure_report_preserves_selected_fault_and_binds_canonical_evidence() -> None:
    trace = _failure_trace()
    analysis = _failure_result(trace)

    result = PostmortemEngine().generate(analysis, trace)

    assert result.report.sections[2].blocks[0].rows[0].label == "Primary fault candidate"
    finding = result.report.sections[2].blocks[0].rows[0]
    assert finding.evidence_refs[0].evidence_id == "evidence-1"
    assert finding.evidence_refs[0].status is CitationStatus.AVAILABLE
    assert finding.evidence_refs[0].event_index == 0
    assert "connection reset" in finding.evidence_refs[0].snippet


def test_explicit_parent_relation_is_rendered_without_inferred_causality() -> None:
    trace = _failure_trace()
    failed = trace.nodes[0]
    parent = TraceNode(
        node_id="parent-node",
        kind=NodeKind.AGENT_STEP,
        sequence_index=0,
        status=NodeStatus.SUCCESS,
        started_at=failed.started_at,
        provenance=ProvenanceRef(source_record_id="parent-record"),
    )
    child = replace(failed, sequence_index=1, parent_node_id=parent.node_id)
    error = replace(trace.events[0], sequence_index=1)
    trace = replace(
        trace,
        nodes=(parent, child),
        events=(
            TraceEvent("start-parent", 0, EventKind.START, failed.started_at, "parent-node"),
            error,
        ),
    )
    result = PostmortemEngine().generate(_failure_result(trace), trace)

    chain_block = result.report.sections[1].blocks[0]
    step = chain_block.rows[0]
    assert step.cause == "parent-node"
    assert step.effect == child.node_id
    assert step.evidence_refs[0].status is CitationStatus.UNAVAILABLE
    assert "`parent-node` -> `tool-1`" in result.markdown


def test_success_report_keeps_all_six_sections_and_explicit_empty_sections() -> None:
    time = datetime(2026, 10, 3, 8, tzinfo=UTC)
    trace = CanonicalTraceDocument(
        document_id="trace-success",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(
            run_id="success-run",
            status=RunStatus.SUCCESS,
            started_at=time,
            ended_at=time + timedelta(seconds=1),
        ),
        events=(
            TraceEvent("start", 0, EventKind.START, time),
            TraceEvent("end", 1, EventKind.END, time + timedelta(seconds=1)),
        ),
    )
    result = PostmortemEngine().generate(AnalysisEngine().analyze(trace), trace)

    assert tuple(section.section_id for section in result.report.sections) == tuple(SectionId)
    assert all(section.blocks for section in result.report.sections)
    assert (
        result.report.sections[2].blocks[0].text
        == "A primary fault was not available from the analysis."
    )
    assert result.report.sections[5].blocks[0].text == (
        "No recommended follow-ups were provided by the analysis."
    )


def test_missing_evidence_is_an_explicit_citation_and_diagnostic() -> None:
    trace = _failure_trace(evidence=False)
    result = PostmortemEngine().generate(_failure_result(trace), trace)
    finding = result.report.sections[2].blocks[0].rows[0]

    assert finding.evidence_refs[0].status is CitationStatus.UNAVAILABLE
    assert finding.evidence_refs[0].snippet == "[evidence unavailable]"
    assert any(issue.code is DiagnosticCode.MISSING_EVIDENCE for issue in result.report.diagnostics)


def test_stale_analysis_evidence_reference_is_visible_and_diagnosed() -> None:
    trace = _failure_trace()
    analysis = _failure_result(trace)
    assert analysis.first_fault is not None
    item = analysis.first_fault.supporting_evidence[0]
    stale_item = replace(item, evidence_id="not-in-document")
    analysis = replace(
        analysis,
        first_fault=replace(analysis.first_fault, supporting_evidence=(stale_item,)),
        evidence=(stale_item,),
    )

    result = PostmortemEngine().generate(analysis, trace)

    citation = result.report.sections[2].blocks[0].rows[0].evidence_refs[0]
    assert citation.status is CitationStatus.INVALID_REFERENCE
    assert citation.evidence_id == "not-in-document"
    assert any(issue.code is DiagnosticCode.MISSING_EVIDENCE for issue in result.report.diagnostics)


def test_ordered_alternative_candidates_remain_unresolved() -> None:
    trace = _failure_trace(candidate_count=2)
    result = PostmortemEngine().generate(_failure_result(trace), trace)

    factors = result.report.sections[3].blocks[0].rows
    assert [item.finding_id for item in factors] == [
        "candidate:tool-2:error-2",
    ]
    assert factors[0].status == "unresolved_alternative"
    assert any(
        issue.code is DiagnosticCode.UNRESOLVED_AMBIGUITY for issue in result.report.diagnostics
    )
    assert any(
        issue.code is DiagnosticCode.CONSISTENCY_VIOLATION
        and "Duplicate canonical evidence content" in issue.message
        for issue in result.report.diagnostics
    )
    assert "ambiguity remains unresolved" in result.report.sections[0].blocks[1].text


def test_partial_observation_is_rendered_only_from_explicit_analysis_diagnostic() -> None:
    trace = _failure_trace()
    analysis = _failure_result(trace)
    analysis = replace(
        analysis,
        diagnostics=(
            *analysis.diagnostics,
            AnalysisDiagnostic(
                severity=AnalysisIssueSeverity.WARNING,
                code=AnalysisIssueCode.INCOMPLETE_TRACE,
                message="terminal evidence is incomplete",
                related_event_ids=("error-1",),
            ),
        ),
    )
    result = PostmortemEngine().generate(analysis, trace)

    assert result.report.sections[0].blocks[1].text == (
        "The failure is only partially observed in the available trace."
    )
    assert any(
        issue.code is DiagnosticCode.INCOMPLETE_ANALYSIS for issue in result.report.diagnostics
    )


def test_retry_ids_are_preserved_and_missing_timestamps_do_not_add_chronology() -> None:
    trace = _failure_trace(timestamps=False, retries=True)
    analysis = _failure_result(trace)
    result = PostmortemEngine().generate(analysis, trace)

    finding = result.report.sections[2].blocks[0].rows[0]
    assert "retry-1" in finding.description
    assert "Generated at:" not in result.markdown
    assert "event index 0" in result.markdown
    assert any(
        issue.code is DiagnosticCode.UNSUPPORTED_INFORMATION for issue in result.report.diagnostics
    )


def test_duplicate_evidence_is_deduplicated_by_id_and_event_index() -> None:
    trace = _failure_trace()
    analysis = _failure_result(trace)
    analysis = replace(analysis, evidence=(*analysis.evidence, *analysis.evidence))

    result = PostmortemEngine().generate(analysis, trace)
    rows = result.report.sections[4].blocks[-1].rows

    keys = [(row.evidence_id, row.event_index) for row in rows]
    assert len(keys) == len(set(keys))
    assert any(
        issue.code is DiagnosticCode.CONSISTENCY_VIOLATION and "deduplicated" in issue.message
        for issue in result.report.diagnostics
    )


def test_deterministic_ir_markdown_configuration_and_immutability() -> None:
    trace = _failure_trace()
    analysis = _failure_result(trace)
    config = ReportConfiguration(
        title="Reviewed incident",
        generated_at=datetime(2026, 10, 3, 10, tzinfo=UTC),
        verbosity=VerbosityLevel.CONCISE,
    )
    engine = PostmortemEngine()

    first = engine.generate(analysis, trace, config)
    second = engine.generate(analysis, trace, config)

    assert first == second
    assert first.report.title == "Reviewed incident"
    assert first.report.metadata.generated_at.isoformat() == "2026-10-03T10:00:00+00:00"
    with pytest.raises(FrozenInstanceError):
        first.report.title = "changed"  # type: ignore[misc]
    assert first.markdown == engine.generate(analysis, trace, config).markdown


def test_invalid_configuration_and_hard_template_invalidity_fail_deterministically() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReportConfiguration(generated_at=datetime(2026, 10, 3))
    with pytest.raises(TypeError, match="ReportOutputVariant"):
        ReportConfiguration(output_variant="html")  # type: ignore[arg-type]

    trace = _failure_trace()
    analysis = _failure_result(trace)
    report = PostmortemEngine().generate(analysis, trace).report
    invalid_section = replace(report.sections[0], order=1)
    invalid_report = replace(report, sections=(invalid_section, *report.sections[1:]))
    with pytest.raises(ReportStructureError, match="fixed v1 order"):
        check_report(invalid_report, trace, analysis)
    empty_section = replace(report.sections[0], blocks=())
    invalid_report = replace(report, sections=(empty_section, *report.sections[1:]))
    with pytest.raises(ReportStructureError, match="has no content"):
        check_report(invalid_report, trace, analysis)


def test_ir_has_no_dynamic_sections_and_serializes_sections_in_order() -> None:
    trace = _failure_trace()
    report = PostmortemEngine().generate(_failure_result(trace), trace).report

    snapshot = report.to_dict()
    assert [section["section_id"] for section in snapshot["sections"]] == [
        section.value for section in SectionId
    ]
    assert tuple(snapshot) == (
        "report_id",
        "title",
        "metadata",
        "sections",
        "diagnostics",
        "version",
    )
