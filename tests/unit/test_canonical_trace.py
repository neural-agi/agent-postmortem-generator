from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agent_postmortem.domain import (
    CanonicalTraceDocument,
    CanonicalTraceSchemaVersion,
    EventKind,
    EventSeverity,
    EvidenceRecord,
    EvidenceType,
    NodeKind,
    NodeStatus,
    ProvenanceRef,
    RunMetadata,
    RunStatus,
    TraceEvent,
    TraceNode,
    ValidationIssue,
    ValidationIssueSeverity,
)
from agent_postmortem.validation import validate_canonical_trace_document


def test_canonical_trace_document_is_immutable_and_serializable() -> None:
    provenance = ProvenanceRef(
        source_record_id="raw-1",
        source_path="/runs/1",
        source_file="trace.json",
        raw_key_path=("runs", "0"),
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-1",
        evidence_type=EvidenceType.INLINE_TEXT,
        content_summary="node started",
        provenance=provenance,
    )
    node = TraceNode(
        node_id="node-1",
        kind=NodeKind.AGENT_STEP,
        sequence_index=0,
        status=NodeStatus.SUCCESS,
        started_at=datetime(2026, 7, 11, 10, 30, tzinfo=UTC),
        ended_at=datetime(2026, 7, 11, 10, 31, tzinfo=UTC),
        attributes=(("agent", "planner"),),
        provenance=provenance,
    )
    event = TraceEvent(
        event_id="event-1",
        sequence_index=0,
        kind=EventKind.START,
        timestamp=datetime(2026, 7, 11, 10, 30, tzinfo=UTC),
        node_id="node-1",
        payload="started",
        severity=EventSeverity.INFORMATIONAL,
        provenance=provenance,
        evidence_refs=("evidence-1",),
    )
    run = RunMetadata(
        run_id="run-1",
        status=RunStatus.SUCCESS,
        source_format="langgraph",
        started_at=datetime(2026, 7, 11, 10, 30, tzinfo=UTC),
        ended_at=datetime(2026, 7, 11, 10, 32, tzinfo=UTC),
        environment="prod",
        provenance=provenance,
    )
    issue = ValidationIssue(
        issue_id="issue-1",
        severity=ValidationIssueSeverity.WARNING,
        field_path="events[0].payload",
        message="payload was inferred from source trace text",
        source_ref=provenance,
    )
    document = CanonicalTraceDocument(
        document_id="doc-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=run,
        nodes=(node,),
        events=(event,),
        evidence=(evidence,),
        issues=(issue,),
    )

    assert document.to_dict() == {
        "document_id": "doc-1",
        "schema_version": "v1",
        "run": {
            "run_id": "run-1",
            "status": "success",
            "source_format": "langgraph",
            "started_at": "2026-07-11T10:30:00Z",
            "ended_at": "2026-07-11T10:32:00Z",
            "environment": "prod",
            "provenance": {
                "source_record_id": "raw-1",
                "raw_key_path": ["runs", "0"],
                "source_path": "/runs/1",
                "source_file": "trace.json",
            },
        },
        "nodes": [
            {
                "node_id": "node-1",
                "kind": "agent_step",
                "sequence_index": 0,
                "status": "success",
                "started_at": "2026-07-11T10:30:00Z",
                "ended_at": "2026-07-11T10:31:00Z",
                "attributes": {"agent": "planner"},
                "provenance": {
                    "source_record_id": "raw-1",
                    "raw_key_path": ["runs", "0"],
                    "source_path": "/runs/1",
                    "source_file": "trace.json",
                },
            }
        ],
        "events": [
            {
                "event_id": "event-1",
                "sequence_index": 0,
                "kind": "start",
                "timestamp": "2026-07-11T10:30:00Z",
                "node_id": "node-1",
                "payload": "started",
                "severity": "informational",
                "provenance": {
                    "source_record_id": "raw-1",
                    "raw_key_path": ["runs", "0"],
                    "source_path": "/runs/1",
                    "source_file": "trace.json",
                },
                "evidence_refs": ["evidence-1"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "evidence-1",
                "evidence_type": "inline_text",
                "content_summary": "node started",
                "provenance": {
                    "source_record_id": "raw-1",
                    "raw_key_path": ["runs", "0"],
                    "source_path": "/runs/1",
                    "source_file": "trace.json",
                },
            }
        ],
        "issues": [
            {
                "issue_id": "issue-1",
                "severity": "warning",
                "field_path": "events[0].payload",
                "message": "payload was inferred from source trace text",
                "source_ref": {
                    "source_record_id": "raw-1",
                    "raw_key_path": ["runs", "0"],
                    "source_path": "/runs/1",
                    "source_file": "trace.json",
                },
            }
        ],
    }

    with pytest.raises((AttributeError, TypeError)):
        document.document_id = "doc-2"  # type: ignore[misc]


def test_structural_validation_rejects_duplicate_ids() -> None:
    node_a = TraceNode(node_id="node-1", kind=NodeKind.AGENT_STEP, sequence_index=0)
    node_b = TraceNode(node_id="node-1", kind=NodeKind.TOOL_CALL, sequence_index=1)
    run = RunMetadata(run_id="run-1", status=RunStatus.UNKNOWN)
    document = CanonicalTraceDocument(
        document_id="doc-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=run,
        nodes=(node_a, node_b),
    )

    with pytest.raises(ValueError, match="node_id values must be unique"):
        validate_canonical_trace_document(document)


def test_structural_validation_rejects_invalid_parent_links() -> None:
    node = TraceNode(
        node_id="node-1",
        kind=NodeKind.AGENT_STEP,
        sequence_index=0,
        parent_node_id="missing",
    )
    run = RunMetadata(run_id="run-1", status=RunStatus.UNKNOWN)
    document = CanonicalTraceDocument(
        document_id="doc-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=run,
        nodes=(node,),
    )

    with pytest.raises(ValueError, match="unknown parent_node_id"):
        validate_canonical_trace_document(document)


def test_structural_validation_rejects_cycles() -> None:
    parent = TraceNode(
        node_id="node-1",
        kind=NodeKind.AGENT_STEP,
        sequence_index=0,
        parent_node_id="node-2",
    )
    child = TraceNode(
        node_id="node-2",
        kind=NodeKind.SUB_AGENT_STEP,
        sequence_index=1,
        parent_node_id="node-1",
    )
    run = RunMetadata(run_id="run-1", status=RunStatus.UNKNOWN)
    document = CanonicalTraceDocument(
        document_id="doc-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=run,
        nodes=(parent, child),
    )

    with pytest.raises(ValueError, match="cycles in parent relationships"):
        validate_canonical_trace_document(document)


def test_structural_validation_rejects_unknown_event_node_refs() -> None:
    event = TraceEvent(
        event_id="event-1",
        sequence_index=0,
        kind=EventKind.ERROR,
        node_id="missing",
        severity=EventSeverity.ERROR,
    )
    run = RunMetadata(run_id="run-1", status=RunStatus.UNKNOWN)
    document = CanonicalTraceDocument(
        document_id="doc-1",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=run,
        events=(event,),
    )

    with pytest.raises(ValueError, match="unknown node_id"):
        validate_canonical_trace_document(document)
