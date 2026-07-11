from __future__ import annotations

from pathlib import Path

from agent_postmortem.validation import DiagnosticCode, validate_from_path

FIXTURES = Path("tests/fixtures")


def test_integration_valid_trace() -> None:
    result = validate_from_path(FIXTURES / "valid_minimal_trace.json")

    assert result.report.success is True
    assert result.document is not None
    assert result.document.envelope.document_id == "doc-1"
    assert result.report.diagnostics == ()


def test_integration_duplicate_event_id_failure() -> None:
    result = validate_from_path(FIXTURES / "duplicate_event_id.json")

    assert result.report.success is False
    assert result.report.diagnostics[0].code == DiagnosticCode.DUPLICATE_IDENTIFIER
