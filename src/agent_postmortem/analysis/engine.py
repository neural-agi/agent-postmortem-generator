"""Coordinate deterministic analysis stages over trusted canonical traces."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from agent_postmortem.analysis.causality import resolve_causality
from agent_postmortem.analysis.indexer import TraceIndex, build_trace_index
from agent_postmortem.analysis.models import (
    AnalysisResult,
    CausalEdge,
    CausalEdgeKind,
    DiagnosticIssue,
    EvidenceItem,
    ExecutionNodeView,
    FailureChain,
)
from agent_postmortem.analysis.rules import RuleResult, classify_and_select
from agent_postmortem.domain import CanonicalTraceDocument, TraceEvent
from agent_postmortem.normalization.models import NormalizationResult


@dataclass(frozen=True, slots=True)
class AnalysisEngine:
    """Run the Part 4 index, causality, classification, and evidence stages."""

    def analyze(self, trace: CanonicalTraceDocument | NormalizationResult) -> AnalysisResult:
        if isinstance(trace, NormalizationResult):
            normalized: NormalizationResult | None = trace
            document = trace.canonical_trace
        else:
            normalized = None
            document = trace
        index = build_trace_index(document)
        causality = resolve_causality(index, normalized)
        rules = classify_and_select(index, causality.views, causality.edges, normalized, document)
        chain = _failure_chain(index, causality.views, causality.edges, rules)
        evidence = _collect_evidence(index, causality.views, causality.edges, rules, chain)
        diagnostics = _ordered_diagnostics(
            (*index.diagnostics, *causality.diagnostics, *rules.diagnostics)
        )
        first_fault = rules.candidates[0] if rules.candidates else None
        return AnalysisResult(
            run_id=document.run.run_id,
            terminal_outcome=rules.outcome,
            terminal_failure=rules.terminal,
            first_fault=first_fault,
            alternative_candidates=rules.candidates[1:],
            failure_chain=chain,
            execution_index=index.timeline_event_ids,
            execution_views=causality.views,
            causal_edges=causality.edges,
            evidence=evidence,
            diagnostics=diagnostics,
        )


def analyze(trace: CanonicalTraceDocument | NormalizationResult) -> AnalysisResult:
    """Analyze a canonical document or Part 3 result with deterministic rules."""

    return AnalysisEngine().analyze(trace)


def _failure_chain(
    index: TraceIndex,
    views: tuple[ExecutionNodeView, ...],
    edges: tuple[CausalEdge, ...],
    rules: RuleResult,
) -> FailureChain:
    terminal = rules.terminal
    if terminal is None:
        return FailureChain((), None, ())
    candidate = rules.candidates[0] if rules.candidates else None
    ancestors: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.edge_kind is CausalEdgeKind.PARENT:
            ancestors[edge.to_node_id].append(edge.from_node_id)
    path: list[str] = [terminal.node_id]
    current = terminal.node_id
    seen = {current}
    while ancestors[current]:
        eligible = sorted(
            (node_id for node_id in ancestors[current] if node_id not in seen),
            key=lambda node_id: (
                _view_by_id(views, node_id).sequence_index,
                node_id,
            ),
        )
        if not eligible:
            break
        current = eligible[-1]
        seen.add(current)
        path.append(current)
    path.reverse()
    if candidate is None:
        path = [terminal.node_id]
    path_edges = tuple(
        edge
        for source, target in pairwise(path)
        for edge in edges
        if edge.from_node_id == source and edge.to_node_id == target
    )
    return FailureChain(tuple(path), terminal.node_id, path_edges)


def _collect_evidence(
    index: TraceIndex,
    views: tuple[ExecutionNodeView, ...],
    edges: tuple[CausalEdge, ...],
    rules: RuleResult,
    chain: FailureChain,
) -> tuple[EvidenceItem, ...]:
    by_id = {view.node_id: view for view in views}
    collected: list[EvidenceItem] = []
    for node_id in chain.ordered_node_ids:
        node = index.nodes_by_id.get(node_id)
        view = by_id[node_id]
        if node is not None:
            collected.append(
                EvidenceItem(
                    field_path=f"nodes/{node_id}/status",
                    value=node.status.value,
                    source_node_id=node_id,
                    source_event_id=None,
                    note="canonical node status",
                    source_ref=node.provenance,
                )
            )
        for event_id in view.event_ids:
            event = index.events_by_id[event_id]
            collected.extend(_event_facts(event, node_id))
    for edge in chain.propagation_steps:
        collected.append(
            EvidenceItem(
                field_path=f"relations/{edge.from_node_id}/{edge.to_node_id}",
                value=edge.edge_kind.value,
                source_node_id=edge.to_node_id,
                source_event_id=None,
                note=f"explicit causal edge: {edge.source_of_truth}",
                source_ref=edge.source_ref,
                relation=edge,
            )
        )
    for candidate in rules.candidates:
        collected.extend(candidate.supporting_evidence)
    unique: dict[tuple[str, str | None, str | None, str | None], EvidenceItem] = {}
    for item in collected:
        key = (item.field_path, item.source_node_id, item.source_event_id, item.evidence_id)
        unique.setdefault(key, item)
    return tuple(
        unique[key] for key in sorted(unique, key=lambda key: tuple(part or "" for part in key))
    )


def _event_facts(event: TraceEvent, node_id: str) -> tuple[EvidenceItem, ...]:
    values: list[tuple[str, str | int | bool | None]] = [
        ("kind", event.kind.value),
        ("sequence_index", event.sequence_index),
        ("severity", event.severity.value),
    ]
    if event.timestamp is not None:
        values.append(("timestamp", event.timestamp.isoformat()))
    if event.payload is not None:
        values.append(("payload", event.payload))
    return tuple(
        EvidenceItem(
            field_path=f"events/{event.event_id}/{field}",
            value=value,
            source_node_id=node_id,
            source_event_id=event.event_id,
            note="canonical event field",
            source_ref=event.provenance,
            evidence_id=event.evidence_refs[0] if event.evidence_refs else None,
        )
        for field, value in values
    )


def _view_by_id(views: tuple[ExecutionNodeView, ...], node_id: str) -> ExecutionNodeView:
    return next(view for view in views if view.node_id == node_id)


def _ordered_diagnostics(items: tuple[DiagnosticIssue, ...]) -> tuple[DiagnosticIssue, ...]:
    unique = {
        (
            item.severity,
            item.code,
            item.message,
            item.related_node_ids,
            item.related_event_ids,
        ): item
        for item in items
    }
    return tuple(
        unique[key]
        for key in sorted(
            unique,
            key=lambda item: (
                item[1].value,
                tuple(item[3]),
                tuple(item[4]),
                item[2],
            ),
        )
    )
