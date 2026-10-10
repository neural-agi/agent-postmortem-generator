"""Build the Part 6 graph IR from canonical trace and analysis contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

from agent_postmortem.analysis.models import AnalysisResult, CausalEdgeKind, FaultCandidate
from agent_postmortem.domain import CanonicalTraceDocument, TraceEvent, TraceNode
from agent_postmortem.graph.models import (
    GraphAnnotation,
    GraphAnnotationType,
    GraphContractError,
    GraphDiagnostic,
    GraphDiagnosticSeverity,
    GraphDocument,
    GraphEdge,
    GraphEdgeKind,
    GraphGroup,
    GraphGroupKind,
    GraphMetadata,
    GraphNode,
    GraphNodeKind,
)


@dataclass(frozen=True, slots=True)
class GraphEngine:
    """Generate one deterministic graph document without rendering it."""

    graph_version: str = "v1"

    def generate(self, trace: CanonicalTraceDocument, analysis: AnalysisResult) -> GraphDocument:
        """Project canonical events and explicit analysis relationships into the IR."""

        if analysis.run_id != trace.run.run_id:
            raise GraphContractError("analysis run_id does not match canonical trace run_id")
        events = _ordered_events(trace, analysis)
        event_ids = {event.event_id for event in trace.events}
        _validate_analysis_references(analysis, event_ids, {node.node_id for node in trace.nodes})
        nodes, event_to_node, node_to_event = _nodes(events, trace)
        groups = _groups(trace, events, event_to_node)
        edges = _edges(trace, analysis, events, event_to_node, node_to_event)
        annotations = _annotations(trace, analysis, event_to_node, node_to_event)
        diagnostics = _diagnostics(trace, analysis, events, event_to_node)
        analysis_id = _analysis_id(analysis)
        graph_id = f"graph-{trace.run.run_id}-{analysis_id}"
        metadata = GraphMetadata(
            graph_version=self.graph_version,
            source_trace_id=trace.document_id,
            analysis_id=analysis_id,
            node_count=len(nodes),
            edge_count=len(edges),
            determinism_hash=_digest(nodes, edges, groups, annotations, diagnostics),
        )
        return GraphDocument(
            graph_id=graph_id,
            source_trace_id=trace.document_id,
            analysis_id=analysis_id,
            version=self.graph_version,
            nodes=nodes,
            edges=edges,
            groups=groups,
            annotations=annotations,
            diagnostics=diagnostics,
            metadata=metadata,
        )


def generate_graph(trace: CanonicalTraceDocument, analysis: AnalysisResult) -> GraphDocument:
    """Generate a deterministic graph document using the default graph version."""

    return GraphEngine().generate(trace, analysis)


def _ordered_events(
    trace: CanonicalTraceDocument, analysis: AnalysisResult
) -> tuple[TraceEvent, ...]:
    by_id = {event.event_id: event for event in trace.events}
    ids = analysis.execution_index or tuple(event.event_id for event in trace.events)
    if set(ids) != set(by_id) or len(ids) != len(by_id):
        raise GraphContractError("analysis execution index does not match canonical events")
    return tuple(by_id[event_id] for event_id in ids)


def _validate_analysis_references(
    analysis: AnalysisResult, event_ids: set[str], node_ids: set[str]
) -> None:
    referenced_events = {
        event_id for item in analysis.evidence if (event_id := item.source_event_id) is not None
    }
    referenced_events.update(
        event_id for candidate in _candidates(analysis) for event_id in (candidate.event_id,)
    )
    missing_events = sorted(referenced_events - event_ids)
    if missing_events:
        raise GraphContractError(f"analysis references unknown event ids: {missing_events!r}")
    referenced_nodes = set(analysis.execution_index)
    referenced_nodes.update(
        node_id for view in analysis.execution_views for node_id in (view.node_id,)
    )
    referenced_nodes.update(
        node_id
        for edge in analysis.causal_edges
        for node_id in (edge.from_node_id, edge.to_node_id)
    )
    missing_nodes = sorted(referenced_nodes - event_ids - node_ids)
    if missing_nodes:
        raise GraphContractError(f"analysis references unknown node ids: {missing_nodes!r}")


def _candidates(analysis: AnalysisResult) -> tuple[FaultCandidate, ...]:
    return tuple(
        candidate
        for candidate in (analysis.first_fault, *analysis.alternative_candidates)
        if candidate
    )


def _nodes(
    events: tuple[TraceEvent, ...], trace: CanonicalTraceDocument
) -> tuple[tuple[GraphNode, ...], dict[str, str], dict[str, str]]:
    nodes_by_id = {node.node_id: node for node in trace.nodes}
    event_to_node: dict[str, str] = {}
    node_to_event: dict[str, str] = {}
    result: list[GraphNode] = []
    for index, event in enumerate(events):
        graph_id = f"event-{event.event_id}"
        scope = event.node_id
        result.append(
            GraphNode(
                graph_id,
                event.event_id,
                GraphNodeKind.EVENT,
                event.kind.value,
                _status(event, nodes_by_id),
                index,
                scope,
                event.evidence_refs,
            )
        )
        event_to_node[event.event_id] = graph_id
        if scope is not None and scope not in node_to_event:
            node_to_event[scope] = graph_id
    return tuple(result), event_to_node, node_to_event


def _status(event: TraceEvent, nodes: Mapping[str, TraceNode]) -> str:
    node = nodes.get(event.node_id) if event.node_id else None
    return node.status.value if node is not None else "unknown"


def _groups(
    trace: CanonicalTraceDocument, events: tuple[TraceEvent, ...], event_to_node: dict[str, str]
) -> tuple[GraphGroup, ...]:
    by_scope: dict[str, list[str]] = {}
    for event in events:
        if event.node_id is not None:
            by_scope.setdefault(event.node_id, []).append(event_to_node[event.event_id])
    groups = [
        GraphGroup(f"scope-{scope}", GraphGroupKind.EXECUTION_SCOPE, scope, tuple(ids), i)
        for i, (scope, ids) in enumerate(sorted(by_scope.items()))
    ]
    series: dict[str, list[str]] = {}
    nodes = {node.node_id: node for node in trace.nodes}
    for event in events:
        if event.node_id and (series_id := nodes[event.node_id].series_id):
            series.setdefault(series_id, []).append(event_to_node[event.event_id])
    offset = len(groups)
    groups.extend(
        GraphGroup(
            f"retry-{series_id}", GraphGroupKind.RETRY_GROUP, series_id, tuple(ids), offset + i
        )
        for i, (series_id, ids) in enumerate(sorted(series.items()))
    )
    return tuple(groups)


def _edges(
    trace: CanonicalTraceDocument,
    analysis: AnalysisResult,
    events: tuple[TraceEvent, ...],
    event_to_node: dict[str, str],
    node_to_event: dict[str, str],
) -> tuple[GraphEdge, ...]:
    edges: dict[tuple[str, str, GraphEdgeKind], GraphEdge] = {}

    def add(
        source: str,
        target: str,
        kind: GraphEdgeKind,
        label: str,
        refs: tuple[str, ...] = (),
        style: str | None = None,
    ) -> None:
        if source == target:
            return
        key = (source, target, kind)
        edges.setdefault(
            key,
            GraphEdge(
                f"edge-{kind.value}-{source}-{target}",
                source,
                target,
                kind,
                label,
                tuple(refs),
                style,
            ),
        )

    for previous, current in pairwise(events):
        add(
            event_to_node[previous.event_id],
            event_to_node[current.event_id],
            GraphEdgeKind.SEQUENCE,
            "next",
        )
    for node in trace.nodes:
        if (
            node.parent_node_id
            and node.node_id in node_to_event
            and node.parent_node_id in node_to_event
        ):
            add(
                node_to_event[node.parent_node_id],
                node_to_event[node.node_id],
                GraphEdgeKind.PARENT,
                "parent",
            )
    for edge in analysis.causal_edges:
        source = _graph_target(edge.from_node_id, event_to_node, node_to_event)
        target = _graph_target(edge.to_node_id, event_to_node, node_to_event)
        if source is not None and target is not None:
            kind = (
                GraphEdgeKind.RETRY
                if edge.edge_kind is CausalEdgeKind.RETRY
                else GraphEdgeKind.CAUSAL
            )
            add(
                source,
                target,
                kind,
                edge.source_of_truth,
                (),
                "dashed",
            )
    return tuple(
        sorted(
            edges.values(),
            key=lambda edge: (edge.from_node_id, edge.to_node_id, edge.kind.value, edge.edge_id),
        )
    )


def _annotations(
    trace: CanonicalTraceDocument,
    analysis: AnalysisResult,
    event_to_node: dict[str, str],
    node_to_event: dict[str, str],
) -> tuple[GraphAnnotation, ...]:
    annotations: list[GraphAnnotation] = []
    if analysis.first_fault and analysis.first_fault.event_id in event_to_node:
        annotations.append(
            GraphAnnotation(
                event_to_node[analysis.first_fault.event_id],
                GraphAnnotationType.FIRST_FAULT,
                "first meaningful fault",
                evidence_refs=tuple(
                    item.evidence_id
                    for item in analysis.first_fault.supporting_evidence
                    if item.evidence_id
                ),
            )
        )
    if analysis.terminal_failure:
        target = _graph_target(analysis.terminal_failure.node_id, event_to_node, node_to_event)
        if target:
            annotations.append(
                GraphAnnotation(target, GraphAnnotationType.TERMINAL_FAILURE, "terminal failure")
            )
    for edge in analysis.causal_edges:
        target = _graph_target(edge.to_node_id, event_to_node, node_to_event)
        if target and edge.edge_kind is CausalEdgeKind.RETRY:
            annotations.append(GraphAnnotation(target, GraphAnnotationType.RETRY, "retry attempt"))
        elif target:
            annotations.append(
                GraphAnnotation(target, GraphAnnotationType.PROPAGATION, "analysis propagation")
            )
    return tuple(
        sorted(
            annotations, key=lambda item: (item.target_id, item.annotation_type.value, item.label)
        )
    )


def _graph_target(
    identifier: str, event_to_node: dict[str, str], node_to_event: dict[str, str]
) -> str | None:
    """Resolve either a canonical node identifier or a standalone event id."""

    return node_to_event.get(identifier) or event_to_node.get(identifier)


def _diagnostics(
    trace: CanonicalTraceDocument,
    analysis: AnalysisResult,
    events: tuple[TraceEvent, ...],
    event_to_node: dict[str, str],
) -> tuple[GraphDiagnostic, ...]:
    result = [
        GraphDiagnostic(
            "analysis_diagnostic",
            GraphDiagnosticSeverity.WARNING
            if issue.severity.value == "warning"
            else GraphDiagnosticSeverity.ERROR,
            issue.message,
            issue.related_node_ids + issue.related_event_ids,
        )
        for issue in analysis.diagnostics
    ]
    missing = [event.event_id for event in events if event.timestamp is None]
    if missing:
        result.append(
            GraphDiagnostic(
                "missing_timestamp",
                GraphDiagnosticSeverity.WARNING,
                "timestamp absent; canonical execution order is preserved",
                tuple(missing),
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (item.severity.value, item.code, item.related_ids, item.message),
        )
    )


def _analysis_id(analysis: AnalysisResult) -> str:
    return hashlib.sha256(
        json.dumps(_analysis_fingerprint(analysis), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def _analysis_fingerprint(analysis: AnalysisResult) -> dict[str, object]:
    return {
        "run_id": analysis.run_id,
        "outcome": analysis.terminal_outcome.value,
        "execution_index": analysis.execution_index,
        "edges": [(e.from_node_id, e.to_node_id, e.edge_kind.value) for e in analysis.causal_edges],
        "fault": analysis.first_fault.event_id if analysis.first_fault else None,
    }


def _digest(*parts: object) -> str:
    return hashlib.sha256(repr(parts).encode()).hexdigest()
