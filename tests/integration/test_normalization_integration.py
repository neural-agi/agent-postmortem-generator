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
