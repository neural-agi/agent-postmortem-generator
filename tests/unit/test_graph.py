from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agent_postmortem.analysis import AnalysisEngine
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
from agent_postmortem.graph import (
    GraphAnnotationType,
    GraphContractError,
    GraphEdgeKind,
    GraphEngine,
)


def _document() -> CanonicalTraceDocument:
    return CanonicalTraceDocument(
        document_id="doc",
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(run_id="run", status=RunStatus.FAILURE),
        nodes=(
            TraceNode("root", NodeKind.AGENT_STEP, 0),
            TraceNode("tool", NodeKind.TOOL_CALL, 1, NodeStatus.FAILURE, "root"),
        ),
        events=(
            TraceEvent("start", 0, EventKind.START, node_id="root"),
            TraceEvent("error", 1, EventKind.ERROR, node_id="tool", payload="failed"),
        ),
    )


def test_graph_is_deterministic_and_preserves_explicit_relationships() -> None:
    trace = _document()
    analysis = AnalysisEngine().analyze(trace)

    first = GraphEngine().generate(trace, analysis)
    second = GraphEngine().generate(trace, analysis)

    assert first == second
    assert [node.event_id for node in first.nodes] == ["start", "error"]
    assert any(edge.kind is GraphEdgeKind.SEQUENCE for edge in first.edges)
    assert any(edge.kind is GraphEdgeKind.PARENT for edge in first.edges)
    assert any(
        item.annotation_type is GraphAnnotationType.FIRST_FAULT for item in first.annotations
    )


def test_graph_models_are_immutable() -> None:
    graph = GraphEngine().generate(_document(), AnalysisEngine().analyze(_document()))

    with pytest.raises(FrozenInstanceError):
        graph.graph_id = "changed"  # type: ignore[misc]


def test_unknown_analysis_reference_is_a_hard_failure() -> None:
    trace = _document()
    analysis = AnalysisEngine().analyze(trace)
    broken = analysis.__class__(
        run_id=analysis.run_id,
        terminal_outcome=analysis.terminal_outcome,
        terminal_failure=analysis.terminal_failure,
        first_fault=analysis.first_fault,
        alternative_candidates=analysis.alternative_candidates,
        failure_chain=analysis.failure_chain,
        execution_index=("missing",),
        execution_views=analysis.execution_views,
        causal_edges=analysis.causal_edges,
        evidence=analysis.evidence,
        diagnostics=analysis.diagnostics,
    )

    with pytest.raises(GraphContractError):
        GraphEngine().generate(trace, broken)
