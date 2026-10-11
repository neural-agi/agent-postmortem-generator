from __future__ import annotations

from pathlib import Path

from agent_postmortem.domain import CanonicalTraceDocument
from agent_postmortem.normalization import NormalizationEngine
from agent_postmortem.validation import parse_and_validate_input, validate_from_path


def test_validated_parser_output_normalizes_to_canonical_document() -> None:
    validation = validate_from_path(Path("tests/fixtures/valid_unknown_fields_trace.json"))

    assert validation.report.success
    assert validation.document is not None
    result = NormalizationEngine().normalize(validation.document)

    assert isinstance(result.canonical_trace, CanonicalTraceDocument)
    assert result.canonical_trace.document_id == "doc-2"
    assert result.canonical_trace.run.run_id == "run-2"
    assert len(result.canonical_trace.events) == 1
    assert len(result.canonical_trace.evidence) == 2
    assert result.canonical_trace.evidence[-1].content_summary is not None
    assert '"unknown_root_field":"kept"' in result.canonical_trace.evidence[-1].content_summary
    assert '"kind":"file_path"' in result.canonical_trace.evidence[-1].content_summary


def test_parser_preserves_timestamp_candidates_for_normalization_precedence() -> None:
    validation = parse_and_validate_input(
        '{"document_id":"doc","trace_version":"v1","run_id":"run","events":['
        '{"event_id":"event","sequence_index":0,'
        '"created_at":"2026-10-03T08:00:00Z",'
        '"started_at":"2026-10-03T08:01:00Z",'
        '"timestamp":"2026-10-03T08:02:00Z"}]}'
    )

    assert validation.document is not None
    assert dict(validation.document.events[0].raw_fields)["created_at"] == "2026-10-03T08:00:00Z"
    normalized = NormalizationEngine().normalize(validation.document)

    assert normalized.canonical_trace.events[0].timestamp.isoformat() == "2026-10-03T08:00:00+00:00"


def test_v2_parser_output_normalizes_explicit_canonical_fields() -> None:
    validation = parse_and_validate_input(
        """{
            "document_id": "doc-v2",
            "trace_version": "v2",
            "run_id": "run-v2",
            "run": {
                "status": "failure",
                "started_at": "2026-10-03T08:00:00Z",
                "ended_at": "2026-10-03T08:02:00Z",
                "source_format": "generic-json"
            },
            "nodes": [
                {"node_id": "root", "kind": "agent_step", "status": "success", "sequence_index": 0},
                {"node_id": "tool", "kind": "tool_call", "status": "failure", "sequence_index": 1,
                 "parent_node_id": "root", "series_id": "tool-series", "attempt_index": 0,
                 "attributes": {"z": "2", "a": "1"}}
            ],
            "evidence": [{"evidence_id": "source-error", "evidence_type": "inline_text",
                          "content_summary": "tool failed"}],
            "events": [
                {"event_id": "error", "sequence_index": 1, "kind": "error", "severity": "error",
                 "node_id": "tool", "payload": "failed", "evidence_refs": ["source-error"],
                 "created_at": "2026-10-03T08:01:00Z"}
            ]
        }"""
    )

    assert validation.report.success
    assert validation.v2_document is not None
    first = NormalizationEngine().normalize(validation.v2_document)
    second = NormalizationEngine().normalize(validation.v2_document)

    assert first == second
    assert first.canonical_trace.run.status.value == "failure"
    assert first.canonical_trace.run.source_format == "generic-json"
    tool = next(node for node in first.canonical_trace.nodes if node.node_id == "tool")
    assert tool.status.value == "failure"
    assert tool.kind.value == "tool_call"
    assert tool.parent_node_id == "root"
    assert tool.series_id == "tool-series"
    assert tool.attempt_index == 0
    assert tool.attributes == (("a", "1"), ("z", "2"))
    event = first.canonical_trace.events[0]
    assert event.payload == "failed"
    assert event.severity.value == "error"
    assert event.evidence_refs[0] == "source-error"
    assert any(record.evidence_id == "source-error" for record in first.canonical_trace.evidence)
