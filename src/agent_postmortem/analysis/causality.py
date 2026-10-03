"""Build the analysis causal graph from explicit canonical links."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import pairwise

from agent_postmortem.analysis.indexer import TraceIndex
from agent_postmortem.analysis.models import (
    AnalysisContractError,
    CausalEdge,
    CausalEdgeKind,
    DiagnosticIssue,
    ExecutionNodeView,
    IssueCode,
    IssueSeverity,
)
from agent_postmortem.domain import EventKind, ProvenanceRef
from agent_postmortem.normalization.models import NormalizationResult, RelationType


@dataclass(frozen=True, slots=True)
class CausalityResult:
    """Resolved explicit edges, annotated views, and recoverable findings."""

    edges: tuple[CausalEdge, ...]
    views: tuple[ExecutionNodeView, ...]
    diagnostics: tuple[DiagnosticIssue, ...]


def resolve_causality(index: TraceIndex, normalized: NormalizationResult | None) -> CausalityResult:
    edges_by_key: dict[tuple[str, str, CausalEdgeKind], CausalEdge] = {}
    explicit_parents: dict[str, set[str]] = defaultdict(set)
    for view in index.views_by_id.values():
        node = index.nodes_by_id.get(view.node_id)
        if node is None or node.parent_node_id is None:
            continue
        _validate_node_reference(index, node.parent_node_id, node.node_id)
        explicit_parents[node.node_id].add(node.parent_node_id)
        _add_parent_edge(
            edges_by_key,
            child_id=node.node_id,
            parent_id=node.parent_node_id,
            source_of_truth="TraceNode.parent_node_id",
            source_ref=node.provenance,
        )

    if normalized is not None:
        for relation in normalized.relations:
            if relation.relation_type is not RelationType.PARENT:
                raise AnalysisContractError(
                    f"unsupported canonical relation type: {relation.relation_type!r}"
                )
            _validate_node_reference(index, relation.from_id, "relation source")
            _validate_node_reference(index, relation.to_id, "relation target")
            explicit_parents[relation.from_id].add(relation.to_id)
            _add_parent_edge(
                edges_by_key,
                child_id=relation.from_id,
                parent_id=relation.to_id,
                source_of_truth="NormalizationResult.CanonicalRelation",
                source_ref=relation.source_ref,
            )

    for child_id, parents in explicit_parents.items():
        node = index.nodes_by_id.get(child_id)
        if node is not None and node.parent_node_id is not None:
            other_parents = parents - {node.parent_node_id}
            if other_parents:
                raise AnalysisContractError(
                    f"node {child_id!r} has conflicting explicit parent relationships"
                )

    diagnostics: list[DiagnosticIssue] = []
    series: dict[str, list[ExecutionNodeView]] = defaultdict(list)
    for view in index.views_by_id.values():
        if view.series_id is not None and view.attempt_index is not None:
            series[view.series_id].append(view)
    for series_id, attempts in series.items():
        ordered = sorted(
            attempts, key=lambda view: (view.attempt_index, view.sequence_index, view.node_id)
        )
        indices = [view.attempt_index for view in ordered]
        if len(set(indices)) != len(indices):
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.UNSUPPORTED_CAUSAL_PATTERN,
                    message=f"attempt indexes are ambiguous for series {series_id!r}; retry edges omitted",
                    related_node_ids=tuple(view.node_id for view in ordered),
                    related_event_ids=tuple(
                        event_id for view in ordered for event_id in view.event_ids
                    ),
                )
            )
            continue
        for previous, current in pairwise(ordered):
            if previous.attempt_index is None or current.attempt_index is None:
                continue
            if current.attempt_index <= previous.attempt_index:
                continue
            edges_by_key[(previous.node_id, current.node_id, CausalEdgeKind.RETRY)] = CausalEdge(
                from_node_id=previous.node_id,
                to_node_id=current.node_id,
                edge_kind=CausalEdgeKind.RETRY,
                source_of_truth="TraceNode.series_id+attempt_index",
                source_ref=index.nodes_by_id[current.node_id].provenance,
            )

    edges = tuple(
        sorted(
            edges_by_key.values(),
            key=lambda edge: (
                index.views_by_id[edge.from_node_id].sequence_index,
                edge.from_node_id,
                index.views_by_id[edge.to_node_id].sequence_index,
                edge.to_node_id,
                edge.edge_kind.value,
            ),
        )
    )
    _ensure_acyclic(index, edges)

    parent_ids: dict[str, set[str]] = defaultdict(set)
    child_ids: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        parent_ids[edge.to_node_id].add(edge.from_node_id)
        child_ids[edge.from_node_id].add(edge.to_node_id)
    views = tuple(
        replace(
            view,
            parent_ids=tuple(sorted(parent_ids[view.node_id])),
            child_ids=tuple(sorted(child_ids[view.node_id])),
        )
        for view in sorted(
            index.views_by_id.values(),
            key=lambda item: (item.sequence_index, item.node_id),
        )
    )

    retry_view_ids = {
        node_id
        for edge in edges
        if edge.edge_kind is CausalEdgeKind.RETRY
        for node_id in (edge.from_node_id, edge.to_node_id)
    }
    for event_id in index.timeline_event_ids:
        event = index.events_by_id[event_id]
        view_id = index.event_view_ids[event_id]
        if event.kind is EventKind.RETRY and view_id not in retry_view_ids:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.UNSUPPORTED_CAUSAL_PATTERN,
                    message="retry event has no explicit attempt-series relationship",
                    related_node_ids=(view_id,),
                    related_event_ids=(event_id,),
                )
            )
    return CausalityResult(edges=edges, views=views, diagnostics=tuple(diagnostics))


def _add_parent_edge(
    edges: dict[tuple[str, str, CausalEdgeKind], CausalEdge],
    *,
    child_id: str,
    parent_id: str,
    source_of_truth: str,
    source_ref: ProvenanceRef | None,
) -> None:
    key = (parent_id, child_id, CausalEdgeKind.PARENT)
    existing = edges.get(key)
    if existing is not None:
        sources = set(existing.source_of_truth.split(" + "))
        sources.add(source_of_truth)
        edges[key] = replace(
            existing,
            source_of_truth=" + ".join(sorted(sources)),
            source_ref=existing.source_ref or source_ref,
        )
        return
    edges[key] = CausalEdge(
        from_node_id=parent_id,
        to_node_id=child_id,
        edge_kind=CausalEdgeKind.PARENT,
        source_of_truth=source_of_truth,
        source_ref=source_ref,
    )


def _validate_node_reference(index: TraceIndex, node_id: str, referring_id: str) -> None:
    if node_id not in index.nodes_by_id:
        raise AnalysisContractError(
            f"causal reference from {referring_id!r} points to unknown node {node_id!r}"
        )


def _ensure_acyclic(index: TraceIndex, edges: tuple[CausalEdge, ...]) -> None:
    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        children[edge.from_node_id].append(edge.to_node_id)
    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        state[node_id] = 1
        for child_id in sorted(children[node_id]):
            if state.get(child_id) == 1:
                raise AnalysisContractError(
                    f"causal graph contains a cycle through node {child_id!r}"
                )
            if state.get(child_id, 0) == 0:
                visit(child_id)
        state[node_id] = 2

    for node_id in sorted(index.views_by_id):
        if state.get(node_id, 0) == 0:
            visit(node_id)
