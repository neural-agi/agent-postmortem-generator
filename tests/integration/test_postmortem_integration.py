from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_postmortem.analysis import AnalysisEngine
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
from agent_postmortem.postmortem import PostmortemEngine

GOLDEN = Path(__file__).parents[1] / "golden"


def _successful_trace() -> CanonicalTraceDocument:
    started = datetime(2026, 10, 3, 8, tzinfo=UTC)
    ended = started + timedelta(seconds=1)
    return CanonicalTraceDocument(
        document_id="trace-success",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(
            run_id="success-run",
            status=RunStatus.SUCCESS,
            started_at=started,
            ended_at=ended,
        ),
        events=(
            TraceEvent("start", 0, EventKind.START, started),
            TraceEvent("end", 1, EventKind.END, ended),
        ),
    )


def _failed_trace() -> CanonicalTraceDocument:
    timestamp = datetime(2026, 10, 3, 8, tzinfo=UTC)
    source = ProvenanceRef(source_record_id="record-tool-error")
    return CanonicalTraceDocument(
        document_id="trace-failure",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(
            run_id="failure-run",
            status=RunStatus.FAILURE,
            started_at=timestamp,
            ended_at=timestamp,
        ),
        nodes=(
            TraceNode(
                "tool-node",
                NodeKind.TOOL_CALL,
                0,
                NodeStatus.FAILURE,
                started_at=timestamp,
                provenance=source,
            ),
        ),
        events=(
            TraceEvent(
                "tool-error",
                0,
                EventKind.ERROR,
                timestamp,
                node_id="tool-node",
                payload="connection reset",
                provenance=source,
                evidence_refs=("evidence-tool-error",),
            ),
        ),
        evidence=(
            EvidenceRecord(
                "evidence-tool-error",
                EvidenceType.INLINE_TEXT,
                content_summary="Tool reported connection reset.",
                provenance=source,
            ),
        ),
    )


def test_success_report_ir_and_markdown_match_golden_files() -> None:
    trace = _successful_trace()
    generated = PostmortemEngine().generate(AnalysisEngine().analyze(trace), trace)
    actual_ir = json.dumps(generated.report.to_dict(), indent=2, ensure_ascii=False) + "\n"

    assert actual_ir == (GOLDEN / "postmortem_success_v1.json").read_text(encoding="utf-8")
    assert generated.markdown == (GOLDEN / "postmortem_success_v1.md").read_text(encoding="utf-8")


def test_analysis_and_canonical_evidence_integrate_into_a_bound_report() -> None:
    trace = _failed_trace()
    analysis = AnalysisEngine().analyze(trace)

    result = PostmortemEngine().generate(analysis, trace)

    primary_block = result.report.sections[2].blocks[-1]
    assert primary_block.rows[0].evidence_refs[0].evidence_id == "evidence-tool-error"
    assert (
        result.report.sections[2]
        .blocks[-1]
        .rows[0]
        .description.startswith("The analysis retained tool-node/tool-error")
    )
    assert "## Failure Chain" in result.markdown
    assert "connection reset" in result.markdown
