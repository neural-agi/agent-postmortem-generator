from __future__ import annotations

from agent_postmortem.analysis import AnalysisEngine, IssueCode, TerminalOutcome
from agent_postmortem.normalization import NormalizationEngine
from agent_postmortem.parsing.input import InputKind, InputMetadata
from agent_postmortem.validation import parse_and_validate_input
from agent_postmortem.validation.trace_document import (
    TraceEnvelope,
    TraceEvent,
    ValidatedTraceDocument,
)


def _analyze_v2(payload: str):
    validation = parse_and_validate_input(payload)
    assert validation.report.success
    assert validation.v2_document is not None
    normalized = NormalizationEngine().normalize(validation.v2_document)
    return AnalysisEngine().analyze(normalized)


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


def test_v2_unknown_end_is_not_success_or_failure() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"events":[{"event_id":"end","sequence_index":0,"kind":"end"}]}'
    )

    assert result.terminal_outcome is TerminalOutcome.UNKNOWN_OUTCOME
    assert result.first_fault is None
    assert any(item.code is IssueCode.UNKNOWN_TERMINAL_OUTCOME for item in result.diagnostics)


def test_v2_unknown_failed_node_does_not_become_failed_run() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"nodes":[{"node_id":"tool","kind":"tool_call","status":"failure",'
        '"sequence_index":0}],"events":[]}'
    )

    assert result.terminal_outcome is TerminalOutcome.UNKNOWN_OUTCOME
    assert result.first_fault is None
    assert any(item.code is IssueCode.UNKNOWN_TERMINAL_OUTCOME for item in result.diagnostics)


def test_v2_explicit_success_retains_failed_node_evidence() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"run":{"status":"success"},'
        '"nodes":[{"node_id":"tool","kind":"tool_call","status":"failure",'
        '"sequence_index":0}],"events":[]}'
    )

    assert result.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
    assert result.first_fault is None
    assert any(item.field_path == "nodes/tool/status" for item in result.evidence)
    assert any(item.code is IssueCode.CONFLICTING_TERMINAL_SIGNALS for item in result.diagnostics)


def test_v2_retry_recovery_is_successful_and_failure_is_retained() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"run":{"status":"success"},"nodes":['
        '{"node_id":"a0","kind":"tool_call","status":"failure","sequence_index":0,'
        '"series_id":"s","attempt_index":0},'
        '{"node_id":"a1","kind":"tool_call","status":"success","sequence_index":1,'
        '"series_id":"s","attempt_index":1}],"events":['
        '{"event_id":"error","sequence_index":0,"kind":"error","node_id":"a0",'
        '"payload":"failed"},{"event_id":"retry","sequence_index":1,"kind":"retry",'
        '"node_id":"a1"}]}'
    )

    assert result.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
    assert result.first_fault is None
    assert any(edge.edge_kind.value == "retry" for edge in result.causal_edges)
    assert any(item.field_path == "nodes/a0/status" for item in result.evidence)


def test_v2_explicit_failure_without_error_has_insufficient_fault_evidence() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"run":{"status":"failure"},"events":[]}'
    )

    assert result.terminal_outcome is TerminalOutcome.EXPLICIT_FAILURE
    assert result.first_fault is None
    assert any(item.code is IssueCode.INSUFFICIENT_FAULT_EVIDENCE for item in result.diagnostics)


def test_v2_cancellation_after_fault_preserves_fault_candidate() -> None:
    result = _analyze_v2(
        '{"document_id":"doc","trace_version":"v2","run_id":"run",'
        '"run":{"status":"cancelled"},"nodes":['
        '{"node_id":"root","kind":"agent_step","status":"failure","sequence_index":0},'
        '{"node_id":"child","kind":"agent_step","status":"cancelled","sequence_index":1,'
        '"parent_node_id":"root"}],"events":['
        '{"event_id":"error","sequence_index":0,"kind":"error","node_id":"root",'
        '"payload":"failed"},{"event_id":"cancel","sequence_index":1,"kind":"cancellation",'
        '"node_id":"child"}]}'
    )

    assert result.terminal_outcome is TerminalOutcome.CANCELLATION
    assert result.first_fault is not None
    assert result.first_fault.node_id == "root"
