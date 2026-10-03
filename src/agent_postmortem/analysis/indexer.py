"""Canonical trace contract checks and deterministic timeline indexing."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from agent_postmortem.analysis.models import (
    AnalysisContractError,
    DiagnosticIssue,
    ExecutionNodeView,
    IssueCode,
    IssueSeverity,
)
from agent_postmortem.domain import (
    CanonicalTraceDocument,
    EventKind,
    NodeStatus,
    TraceEvent,
    TraceNode,
)


@dataclass(frozen=True, slots=True)
class TraceIndex:
    """Read-only indexes used by subsequent analysis stages."""

    events_by_id: Mapping[str, TraceEvent]
    nodes_by_id: Mapping[str, TraceNode]
    views_by_id: Mapping[str, ExecutionNodeView]
    event_view_ids: Mapping[str, str]
    timeline_event_ids: tuple[str, ...]
    timeline_rank: Mapping[str, int]
    diagnostics: tuple[DiagnosticIssue, ...]


def build_trace_index(document: CanonicalTraceDocument) -> TraceIndex:
    """Validate canonical references and build stable views and event order."""

    events_by_id = _unique_index(document.events, lambda event: event.event_id, "event_id")
    nodes_by_id = _unique_index(document.nodes, lambda node: node.node_id, "node_id")
    evidence_by_id = _unique_index(
        document.evidence, lambda evidence: evidence.evidence_id, "evidence_id"
    )

    events_by_node: dict[str, list[TraceEvent]] = {node_id: [] for node_id in nodes_by_id}
    for event in document.events:
        if event.node_id is not None:
            if event.node_id not in nodes_by_id:
                raise AnalysisContractError(
                    f"event {event.event_id!r} references unknown node {event.node_id!r}"
                )
            events_by_node[event.node_id].append(event)
        for evidence_id in event.evidence_refs:
            if evidence_id not in evidence_by_id:
                raise AnalysisContractError(
                    f"event {event.event_id!r} references unknown evidence {evidence_id!r}"
                )

    for node in document.nodes:
        if node.parent_node_id is not None and node.parent_node_id not in nodes_by_id:
            raise AnalysisContractError(
                f"node {node.node_id!r} references unknown parent {node.parent_node_id!r}"
            )

    timeline = tuple(
        event.event_id
        for event in sorted(
            document.events,
            key=lambda event: _event_order_key(event, nodes_by_id),
        )
    )
    timeline_rank = {event_id: index for index, event_id in enumerate(timeline)}
    timeline_events_by_node: dict[str, list[TraceEvent]] = {
        node_id: sorted(events, key=lambda event: timeline_rank[event.event_id])
        for node_id, events in events_by_node.items()
    }

    diagnostics: list[DiagnosticIssue] = []
    views: list[ExecutionNodeView] = []
    event_view_ids: dict[str, str] = {}
    for node in document.nodes:
        node_events = timeline_events_by_node[node.node_id]
        kinds = tuple(dict.fromkeys(event.kind for event in node_events))
        event_type = kinds[0] if len(kinds) == 1 else EventKind.UNKNOWN
        if len(kinds) > 1:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.AMBIGUOUS_EVENT_TYPES,
                    message="multiple canonical event kinds map to one execution node",
                    related_node_ids=(node.node_id,),
                    related_event_ids=tuple(event.event_id for event in node_events),
                )
            )
        event_times = tuple(event.timestamp for event in node_events if event.timestamp is not None)
        start_timestamp = node.started_at or (min(event_times) if event_times else None)
        end_timestamp = node.ended_at or (max(event_times) if event_times else None)
        if node.started_at is not None and any(
            event.timestamp is not None and event.timestamp != node.started_at
            for event in node_events
        ):
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.CONFLICTING_TIMESTAMPS,
                    message="node start timestamp differs from an associated event timestamp",
                    related_node_ids=(node.node_id,),
                    related_event_ids=tuple(
                        event.event_id
                        for event in node_events
                        if event.timestamp is not None and event.timestamp != node.started_at
                    ),
                )
            )
        if start_timestamp is None and end_timestamp is None:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.MISSING_TIMESTAMPS,
                    message="timestamps are absent; explicit sequence remains the ordering key",
                    related_node_ids=(node.node_id,),
                    related_event_ids=tuple(event.event_id for event in node_events),
                )
            )
        views.append(
            ExecutionNodeView(
                node_id=node.node_id,
                event_type=event_type,
                status=node.status,
                sequence_index=node.sequence_index,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                event_ids=tuple(event.event_id for event in node_events),
                series_id=node.series_id,
                attempt_index=node.attempt_index,
            )
        )
        for event in node_events:
            event_view_ids[event.event_id] = node.node_id

    for event_id in timeline:
        event = events_by_id[event_id]
        if event.node_id is not None:
            continue
        if event.event_id in nodes_by_id:
            raise AnalysisContractError(
                f"standalone event id {event.event_id!r} collides with a canonical node id"
            )
        if event.timestamp is None:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.MISSING_TIMESTAMPS,
                    message="event timestamp is absent; explicit sequence remains the ordering key",
                    related_node_ids=(event.event_id,),
                    related_event_ids=(event.event_id,),
                )
            )
        views.append(
            ExecutionNodeView(
                node_id=event.event_id,
                event_type=event.kind,
                status=NodeStatus.UNKNOWN,
                sequence_index=event.sequence_index,
                start_timestamp=event.timestamp,
                end_timestamp=None,
                event_ids=(event.event_id,),
            )
        )
        event_view_ids[event.event_id] = event.event_id

    if len({view.node_id for view in views}) != len(views):
        raise AnalysisContractError("execution view identifiers are not unique")
    diagnostics.extend(
        DiagnosticIssue(
            severity=IssueSeverity.WARNING,
            code=IssueCode.UNSUPPORTED_EVENT_KIND,
            message="unknown canonical event kind cannot be semantically classified",
            related_node_ids=(event_view_ids[event_id],),
            related_event_ids=(event_id,),
        )
        for event_id in timeline
        if events_by_id[event_id].kind is EventKind.UNKNOWN
    )

    return TraceIndex(
        events_by_id=MappingProxyType(events_by_id),
        nodes_by_id=MappingProxyType(nodes_by_id),
        views_by_id=MappingProxyType({view.node_id: view for view in views}),
        event_view_ids=MappingProxyType(event_view_ids),
        timeline_event_ids=timeline,
        timeline_rank=MappingProxyType(timeline_rank),
        diagnostics=tuple(diagnostics),
    )


def _unique_index[T](items: tuple[T, ...], key: Callable[[T], str], field: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in items:
        identifier = key(item)
        if identifier in result:
            raise AnalysisContractError(f"duplicate canonical {field}: {identifier!r}")
        result[identifier] = item
    return result


def _event_order_key(
    event: TraceEvent, nodes: Mapping[str, TraceNode]
) -> tuple[int, datetime, datetime, str]:
    node = nodes.get(event.node_id) if event.node_id is not None else None
    start = node.started_at if node is not None else event.timestamp
    end = node.ended_at if node is not None else None
    return (
        event.sequence_index,
        start or datetime.max.replace(tzinfo=UTC),
        end or datetime.max.replace(tzinfo=UTC),
        event.event_id,
    )
