from __future__ import annotations

from pathlib import Path

from agent_postmortem.parsing import (
    read_input_from_bytes,
    read_input_from_path,
    read_input_from_string,
)
from agent_postmortem.validation import (
    DiagnosticCode,
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
