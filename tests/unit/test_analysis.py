from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from agent_postmortem.analysis import (
    AnalysisContractError,
    AnalysisEngine,
    IssueCode,
    TerminalOutcome,
)
from agent_postmortem.domain import (
    CanonicalTraceDocument,
    CanonicalTraceSchemaVersion,
    EventKind,
    NodeKind,
    NodeStatus,
    RunMetadata,
    RunStatus,
    TraceEvent,
    TraceNode,
)


def _document(
    *,
    status: RunStatus = RunStatus.UNKNOWN,
    nodes: tuple[TraceNode, ...] = (),
    events: tuple[TraceEvent, ...] = (),
) -> CanonicalTraceDocument:
    return CanonicalTraceDocument(
        document_id="doc",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(run_id="run", status=status),
        nodes=nodes,
        events=events,
    )


def test_execution_order_uses_sequence_then_time_then_event_id() -> None:
    start = datetime(2026, 10, 3, tzinfo=UTC)
    trace = _document(
        events=(
            TraceEvent("z", 1, EventKind.LOG, start + timedelta(seconds=2)),
            TraceEvent("b", 1, EventKind.LOG, start),
            TraceEvent("a", 1, EventKind.LOG, start),
            TraceEvent("earlier-sequence", 0, EventKind.LOG),
        )
    )

    result = AnalysisEngine().analyze(trace)

    assert result.execution_index == ("earlier-sequence", "a", "b", "z")
    assert result == AnalysisEngine().analyze(trace)


def test_run_status_classifies_success_and_failure_without_guessing_timeout() -> None:
    success = AnalysisEngine().analyze(_document(status=RunStatus.SUCCESS))
    failure = AnalysisEngine().analyze(_document(status=RunStatus.FAILURE))

    assert success.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
    assert failure.terminal_outcome is TerminalOutcome.EXPLICIT_FAILURE
    assert failure.first_fault is None
    assert any(item.code is IssueCode.INSUFFICIENT_FAULT_EVIDENCE for item in failure.diagnostics)


def test_failed_node_with_concrete_error_yields_evidence_and_chain() -> None:
    trace = _document(
        nodes=(
            TraceNode("root", NodeKind.AGENT_STEP, 0),
            TraceNode("child", NodeKind.TOOL_CALL, 1, NodeStatus.FAILURE, "root"),
        ),
        events=(
            TraceEvent("ev-root", 0, EventKind.START, node_id="root"),
            TraceEvent("ev-error", 1, EventKind.ERROR, node_id="child", payload="tool failed"),
        ),
    )

    result = AnalysisEngine().analyze(trace)

    assert result.terminal_outcome is TerminalOutcome.EXPLICIT_FAILURE
    assert result.first_fault is not None
    assert result.first_fault.node_id == "child"
    assert result.failure_chain.ordered_node_ids == ("root", "child")
    assert result.failure_chain.propagation_steps == result.causal_edges
    assert any(item.field_path == "events/ev-error/payload" for item in result.evidence)
    assert any(item.relation is not None for item in result.evidence)


def test_parallel_failures_are_preserved_as_alternatives_deterministically() -> None:
    trace = _document(
        nodes=(
            TraceNode("a", NodeKind.TOOL_CALL, 0, NodeStatus.FAILURE),
            TraceNode("b", NodeKind.TOOL_CALL, 1, NodeStatus.FAILURE),
        ),
        events=(
            TraceEvent("err-a", 0, EventKind.ERROR, node_id="a", payload="A failed"),
            TraceEvent("err-b", 1, EventKind.ERROR, node_id="b", payload="B failed"),
        ),
    )
    engine = AnalysisEngine()

    result = engine.analyze(trace)

    assert result.first_fault is not None
    assert result.first_fault.node_id == "a"
    assert [candidate.node_id for candidate in result.alternative_candidates] == ["b"]
    assert any(item.code is IssueCode.PARALLEL_FAILURE_BRANCHES for item in result.diagnostics)
    assert result == engine.analyze(trace)


def test_cancellation_without_explicit_failed_ancestor_is_not_attributed() -> None:
    trace = _document(
        status=RunStatus.CANCELLED,
        nodes=(TraceNode("cancelled", NodeKind.AGENT_STEP, 0, NodeStatus.CANCELLED),),
        events=(TraceEvent("cancel", 0, EventKind.CANCELLATION, node_id="cancelled"),),
    )

    result = AnalysisEngine().analyze(trace)

    assert result.terminal_outcome is TerminalOutcome.CANCELLATION
    assert result.first_fault is None
    assert any(item.code is IssueCode.UNKNOWN_CANCELLATION_CAUSE for item in result.diagnostics)


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        ((), TerminalOutcome.STRUCTURALLY_INCOMPLETE),
        ((TraceEvent("start", 0, EventKind.START),), TerminalOutcome.PARTIAL_TERMINATION),
        ((TraceEvent("end", 0, EventKind.END),), TerminalOutcome.STRUCTURALLY_INCOMPLETE),
    ],
)
def test_incomplete_terminal_shapes_are_diagnosed(
    events: tuple[TraceEvent, ...], expected: TerminalOutcome
) -> None:
    result = AnalysisEngine().analyze(_document(events=events))

    assert result.terminal_outcome is expected
    assert any(item.code is IssueCode.INCOMPLETE_TRACE for item in result.diagnostics)


def test_missing_timestamps_preserve_sequence_order_and_emit_diagnostic() -> None:
    result = AnalysisEngine().analyze(
        _document(
            events=(TraceEvent("second", 1, EventKind.LOG), TraceEvent("first", 0, EventKind.LOG))
        )
    )

    assert result.execution_index == ("first", "second")
    assert any(item.code is IssueCode.MISSING_TIMESTAMPS for item in result.diagnostics)


def test_timestamp_conflict_is_reported_without_reordering_events() -> None:
    trace = _document(
        nodes=(
            TraceNode(
                "node",
                NodeKind.AGENT_STEP,
                0,
                started_at=datetime(2026, 10, 3, tzinfo=UTC),
            ),
        ),
        events=(
            TraceEvent(
                "event",
                0,
                EventKind.LOG,
                datetime(2026, 10, 3, 0, 1, tzinfo=UTC),
                node_id="node",
            ),
        ),
    )

    result = AnalysisEngine().analyze(trace)

    assert result.execution_index == ("event",)
    assert any(item.code is IssueCode.CONFLICTING_TIMESTAMPS for item in result.diagnostics)


def test_explicit_attempt_metadata_yields_retry_edge_and_retry_evidence() -> None:
    trace = _document(
        nodes=(
            TraceNode(
                "attempt-1",
                NodeKind.TOOL_CALL,
                0,
                NodeStatus.FAILURE,
                series_id="tool-series",
                attempt_index=0,
            ),
            TraceNode(
                "attempt-2",
                NodeKind.TOOL_CALL,
                1,
                NodeStatus.FAILURE,
                series_id="tool-series",
                attempt_index=1,
            ),
        ),
        events=(
            TraceEvent("error-1", 0, EventKind.ERROR, node_id="attempt-1", payload="failed"),
            TraceEvent("retry-1", 1, EventKind.RETRY, node_id="attempt-2"),
            TraceEvent("error-2", 2, EventKind.ERROR, node_id="attempt-2", payload="failed"),
        ),
    )

    result = AnalysisEngine().analyze(trace)

    assert any(edge.edge_kind.value == "retry" for edge in result.causal_edges)
    assert result.first_fault is not None
    assert result.first_fault.node_id == "attempt-1"
    assert result.first_fault.retry_event_ids == ("retry-1",)


def test_input_reference_errors_fail_closed_and_result_is_immutable() -> None:
    invalid = _document(events=(TraceEvent("event", 0, EventKind.LOG, node_id="missing"),))
    with pytest.raises(AnalysisContractError):
        AnalysisEngine().analyze(invalid)

    result = AnalysisEngine().analyze(_document(status=RunStatus.SUCCESS))
    with pytest.raises(FrozenInstanceError):
        result.run_id = "changed"  # type: ignore[misc]
