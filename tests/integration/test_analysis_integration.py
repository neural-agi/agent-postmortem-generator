from __future__ import annotations

from agent_postmortem.analysis import AnalysisEngine, IssueCode, TerminalOutcome
from agent_postmortem.normalization import NormalizationEngine
from agent_postmortem.parsing.input import InputKind, InputMetadata
from agent_postmortem.validation.trace_document import (
    TraceEnvelope,
    TraceEvent,
    ValidatedTraceDocument,
)


def test_validated_trace_normalization_result_is_analysis_input() -> None:
    validated = ValidatedTraceDocument(
        envelope=TraceEnvelope(document_id="doc", trace_version="v1", run_id="run"),
        events=(
            TraceEvent(event_id="started", sequence_index=0),
            TraceEvent(event_id="finished", sequence_index=1),
        ),
        raw_fields=(),
        source_metadata=InputMetadata(kind=InputKind.STRING, source_name="<analysis-test>"),
        diagnostics=(),
    )

    normalized = NormalizationEngine().normalize(validated)
    result = AnalysisEngine().analyze(normalized)

    assert result.run_id == "run"
    assert result.execution_index == tuple(
        event.event_id for event in normalized.canonical_trace.events
    )
    assert result.terminal_outcome is TerminalOutcome.PARTIAL_TERMINATION
    assert any(item.code is IssueCode.UPSTREAM_NORMALIZATION_ISSUE for item in result.diagnostics)
