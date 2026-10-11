from __future__ import annotations

from pathlib import Path

from agent_postmortem.parsing import (
    read_input_from_bytes,
    read_input_from_path,
    read_input_from_string,
)
from agent_postmortem.validation import (
    DiagnosticCode,
    V2ValidatedTraceDocument,
    parse_and_validate_input,
    validate_from_path,
)

FIXTURES = Path("tests/fixtures")


def test_parse_success_preserves_unknown_fields() -> None:
    result = validate_from_path(FIXTURES / "valid_unknown_fields_trace.json")

    assert result.report.success is True
    assert result.document is not None
    assert result.document.raw_fields == (("unknown_root_field", "kept"),)
    assert result.document.events[0].raw_fields == (("extra_event_field", "kept"),)


def test_duplicate_event_id_is_fatal() -> None:
    result = validate_from_path(FIXTURES / "duplicate_event_id.json")

    assert result.report.success is False
    assert [item.code for item in result.report.diagnostics] == [
        DiagnosticCode.DUPLICATE_IDENTIFIER
    ]
    assert result.document is None


def test_non_object_root_is_fatal() -> None:
    result = validate_from_path(FIXTURES / "non_object_root.json")

    assert result.report.success is False
    assert result.report.diagnostics[0].code == DiagnosticCode.NON_OBJECT_ROOT


def test_malformed_json_is_fatal() -> None:
    result = validate_from_path(FIXTURES / "malformed.json")

    assert result.report.success is False
    assert result.report.diagnostics[0].code == DiagnosticCode.INVALID_JSON


def test_out_of_order_events_are_reported_deterministically() -> None:
    payload = (
        b'{"document_id":"doc-4","trace_version":"v1","run_id":"run-4","events":['
        b'{"event_id":"event-1","sequence_index":1,"timestamp":"2026-07-11T10:31:00Z"},'
        b'{"event_id":"event-2","sequence_index":0,"timestamp":"2026-07-11T10:30:00Z"}]}'
    )
    result = parse_and_validate_input(payload)

    assert result.report.success is False
    assert result.report.diagnostics[0].code == DiagnosticCode.OUT_OF_ORDER_EVENTS


def test_input_readers_produce_deterministic_raw_inputs(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    path.write_text('{"x":1}', encoding="utf-8")

    assert read_input_from_path(path).text == '{"x":1}'
    assert read_input_from_string('{"x":1}').text == '{"x":1}'
    assert read_input_from_bytes(b'{"x":1}').text == '{"x":1}'


def _v2_payload() -> str:
    return """{
        "document_id": "doc-v2",
        "trace_version": "v2",
        "run_id": "run-v2",
        "run": {"status": "failure"},
        "nodes": [{
            "node_id": "node-1",
            "kind": "tool_call",
            "status": "failure",
            "sequence_index": 0,
            "attributes": {"z": "last", "a": "first"}
        }],
        "evidence": [{
            "evidence_id": "e-1",
            "evidence_type": "inline_text",
            "content_summary": "tool failed"
        }],
        "events": [{
            "event_id": "event-1",
            "sequence_index": 0,
            "kind": "error",
            "severity": "error",
            "node_id": "node-1",
            "payload": "failed",
            "evidence_refs": ["e-1"],
            "unknown_event_field": "preserved"
        }],
        "unknown_root_field": "preserved"
    }"""


def test_valid_v2_returns_typed_document_and_preserves_unknown_fields() -> None:
    result = parse_and_validate_input(_v2_payload())

    assert result.report.success is True
    assert result.document is None
    assert isinstance(result.v2_document, V2ValidatedTraceDocument)
    assert result.v2_document.nodes[0].attributes == (("a", "first"), ("z", "last"))
    assert result.v2_document.raw_fields == (("unknown_root_field", "preserved"),)
    assert result.v2_document.events[0].raw_fields == (("unknown_event_field", "preserved"),)


def test_v2_unsupported_version_is_rejected_without_v1_interpretation() -> None:
    result = parse_and_validate_input(
        '{"document_id":"doc","trace_version":"v3","run_id":"run","events":[]}'
    )

    assert result.report.success is False
    assert result.report.diagnostics[0].code is DiagnosticCode.UNSUPPORTED_VERSION


def test_v2_rejects_duplicate_reference_and_retry_ids() -> None:
    payload = """{
        "document_id": "doc",
        "trace_version": "v2",
        "run_id": "run",
        "nodes": [
            {"node_id":"node","sequence_index":0,"series_id":"s","attempt_index":0},
            {"node_id":"node","sequence_index":1,"series_id":"s","attempt_index":0}
        ],
        "events": [{"event_id":"event","sequence_index":0,"node_id":"missing"}]
    }"""
    result = parse_and_validate_input(payload)

    assert result.report.success is False
    assert [item.code for item in result.report.diagnostics] == [
        DiagnosticCode.DUPLICATE_IDENTIFIER,
        DiagnosticCode.BROKEN_REFERENCE,
        DiagnosticCode.INVALID_RETRY_METADATA,
    ]


def test_v2_rejects_parent_cycles() -> None:
    payload = """{
        "document_id":"doc", "trace_version":"v2", "run_id":"run",
        "nodes":[
            {"node_id":"a","sequence_index":0,"parent_node_id":"b"},
            {"node_id":"b","sequence_index":1,"parent_node_id":"a"}
        ],
        "events":[]
    }"""
    result = parse_and_validate_input(payload)

    assert result.report.success is False
    assert result.report.diagnostics[0].code is DiagnosticCode.PARENT_CYCLE


def test_v2_event_parent_does_not_override_explicit_node_parent() -> None:
    payload = """{
        "document_id":"doc", "trace_version":"v2", "run_id":"run",
        "nodes":[
            {"node_id":"root","sequence_index":0},
            {"node_id":"child","sequence_index":1,"parent_node_id":"root"}
        ],
        "events":[
            {"event_id":"parent-event","sequence_index":0,"node_id":"root"},
            {"event_id":"child-event","sequence_index":1,"node_id":"child","parent_id":"parent-event"}
        ]
    }"""
    result = parse_and_validate_input(payload)

    assert result.report.success is True
    assert result.v2_document is not None
    assert result.v2_document.nodes[1].parent_node_id == "root"


def test_v2_diagnostics_are_deterministic() -> None:
    payload = (
        _v2_payload()
        .replace('"node_id": "node-1"', '"node_id": "missing"')
        .replace(
            '"node_id": "node-1",\n            "payload"',
            '"node_id": "missing",\n            "payload"',
        )
    )
    first = parse_and_validate_input(payload).report.diagnostics
    second = parse_and_validate_input(payload).report.diagnostics

    assert first == second
