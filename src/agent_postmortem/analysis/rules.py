"""Deterministic terminal classification and evidence-backed fault selection."""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.analysis.indexer import TraceIndex
from agent_postmortem.analysis.models import (
    CausalEdge,
    CausalEdgeKind,
    DiagnosticIssue,
    EvidenceItem,
    ExecutionNodeView,
    FaultCandidate,
    FaultPrecedence,
    FaultReason,
    IssueCode,
    IssueSeverity,
    TerminalOutcome,
)
from agent_postmortem.domain import (
    CanonicalTraceDocument,
    EventKind,
    EventSeverity,
    NodeStatus,
    RunStatus,
    TraceEvent,
)
from agent_postmortem.normalization.models import NormalizationResult


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Rule-stage conclusions and their structured supporting material."""

    outcome: TerminalOutcome
    terminal: ExecutionNodeView | None
    candidates: tuple[FaultCandidate, ...]
    diagnostics: tuple[DiagnosticIssue, ...]


def classify_and_select(
    index: TraceIndex,
    views: tuple[ExecutionNodeView, ...],
    edges: tuple[CausalEdge, ...],
    normalized: NormalizationResult | None,
    document: CanonicalTraceDocument,
) -> RuleResult:
    diagnostics: list[DiagnosticIssue] = []
    if normalized is not None:
        diagnostics.extend(
            DiagnosticIssue(
                severity=IssueSeverity.WARNING,
                code=IssueCode.UPSTREAM_NORMALIZATION_ISSUE,
                message=f"normalization reported {item.code.value}: {item.message}",
                related_node_ids=item.affected_ids,
            )
            for item in normalized.diagnostics
        )

    run_status = document.run.status
    failures = tuple(view for view in views if view.status is NodeStatus.FAILURE)
    cancellations = tuple(view for view in views if view.status is NodeStatus.CANCELLED)
    error_events = tuple(
        index.events_by_id[event_id]
        for event_id in index.timeline_event_ids
        if index.events_by_id[event_id].kind is EventKind.ERROR
        or index.events_by_id[event_id].severity in (EventSeverity.ERROR, EventSeverity.CRITICAL)
    )
    cancel_events = tuple(
        index.events_by_id[event_id]
        for event_id in index.timeline_event_ids
        if index.events_by_id[event_id].kind is EventKind.CANCELLATION
    )
    ordered = {view.node_id: rank for rank, view in enumerate(views)}
    terminal_failure = _select_terminal(failures, ordered)
    if terminal_failure is None and error_events:
        terminal_failure = index.views_by_id[index.event_view_ids[error_events[-1].event_id]]
    terminal_cancel = _select_terminal(cancellations, ordered)
    if terminal_cancel is None and cancel_events:
        terminal_cancel = index.views_by_id[index.event_view_ids[cancel_events[-1].event_id]]

    if run_status is RunStatus.SUCCESS:
        outcome = TerminalOutcome.SUCCESSFUL_COMPLETION
    elif run_status is RunStatus.FAILURE or terminal_failure is not None:
        outcome = TerminalOutcome.EXPLICIT_FAILURE
    elif run_status is RunStatus.CANCELLED or terminal_cancel is not None:
        outcome = TerminalOutcome.CANCELLATION
    elif not views or any(
        index.events_by_id[event_id].kind is EventKind.END for event_id in index.timeline_event_ids
    ):
        outcome = TerminalOutcome.STRUCTURALLY_INCOMPLETE
    else:
        outcome = TerminalOutcome.PARTIAL_TERMINATION

    if terminal_failure is not None and terminal_cancel is not None:
        diagnostics.append(
            DiagnosticIssue(
                severity=IssueSeverity.WARNING,
                code=IssueCode.CONFLICTING_TERMINAL_SIGNALS,
                message="trace contains both failure and cancellation terminal signals",
                related_node_ids=tuple(sorted((terminal_failure.node_id, terminal_cancel.node_id))),
                related_event_ids=tuple(
                    sorted(
                        event_id
                        for view in (terminal_failure, terminal_cancel)
                        for event_id in view.event_ids
                    )
                ),
            )
        )
    if outcome in (TerminalOutcome.PARTIAL_TERMINATION, TerminalOutcome.STRUCTURALLY_INCOMPLETE):
        diagnostics.append(
            DiagnosticIssue(
                severity=IssueSeverity.WARNING,
                code=IssueCode.INCOMPLETE_TRACE,
                message="canonical trace does not establish a complete terminal outcome",
                related_node_ids=tuple(view.node_id for view in views),
                related_event_ids=index.timeline_event_ids,
            )
        )

    if outcome is TerminalOutcome.EXPLICIT_FAILURE:
        candidates = _fault_candidates(index, views, edges, failures, error_events, cancel_events)
        if not candidates:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.INSUFFICIENT_FAULT_EVIDENCE,
                    message="failure is explicit but canonical fields do not identify a supported fault candidate",
                    related_node_ids=(terminal_failure.node_id,) if terminal_failure else (),
                    related_event_ids=tuple(event.event_id for event in error_events),
                )
            )
        if len(failures) > 1:
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.PARALLEL_FAILURE_BRANCHES,
                    message="multiple nodes are explicitly marked failed; branches are preserved",
                    related_node_ids=tuple(view.node_id for view in failures),
                    related_event_ids=tuple(
                        event_id for view in failures for event_id in view.event_ids
                    ),
                )
            )
        if (
            candidates
            and len(candidates) > 1
            and candidates[0].precedence_rank == candidates[1].precedence_rank
        ):
            diagnostics.append(
                DiagnosticIssue(
                    severity=IssueSeverity.WARNING,
                    code=IssueCode.AMBIGUOUS_TERMINAL,
                    message="multiple equally ranked fault candidates are retained in deterministic order",
                    related_node_ids=tuple(candidate.node_id for candidate in candidates),
                    related_event_ids=tuple(candidate.event_id for candidate in candidates),
                )
            )
    else:
        candidates = ()

    if outcome is TerminalOutcome.CANCELLATION and not failures:
        diagnostics.append(
            DiagnosticIssue(
                severity=IssueSeverity.WARNING,
                code=IssueCode.UNKNOWN_CANCELLATION_CAUSE,
                message="cancellation has no explicit upstream failure cause",
                related_node_ids=(terminal_cancel.node_id,) if terminal_cancel else (),
                related_event_ids=tuple(event.event_id for event in cancel_events),
            )
        )
    terminal = (
        terminal_failure
        if outcome is TerminalOutcome.EXPLICIT_FAILURE
        else terminal_cancel
        if outcome is TerminalOutcome.CANCELLATION
        else None
    )
    diagnostics.sort(
        key=lambda item: (
            item.code.value,
            item.related_node_ids,
            item.related_event_ids,
            item.message,
        )
    )
    return RuleResult(outcome, terminal, candidates, tuple(diagnostics))


def _select_terminal(
    candidates: tuple[ExecutionNodeView, ...], order: dict[str, int]
) -> ExecutionNodeView | None:
    return max(candidates, key=lambda view: (order[view.node_id], view.node_id), default=None)


def _fault_candidates(
    index: TraceIndex,
    views: tuple[ExecutionNodeView, ...],
    edges: tuple[CausalEdge, ...],
    failures: tuple[ExecutionNodeView, ...],
    error_events: tuple[TraceEvent, ...],
    cancel_events: tuple[TraceEvent, ...],
) -> tuple[FaultCandidate, ...]:
    view_order = {view.node_id: rank for rank, view in enumerate(views)}
    parent: dict[str, str] = {
        edge.to_node_id: edge.from_node_id
        for edge in edges
        if edge.edge_kind is CausalEdgeKind.PARENT
    }
    failed_ids = {view.node_id for view in failures}
    items: list[FaultCandidate] = []
    for event in error_events:
        event_id = event.event_id
        node_id = index.event_view_ids[event_id]
        concrete = event.payload is not None and bool(event.payload.strip())
        if node_id not in failed_ids or not concrete:
            continue
        if event.payload is None:
            continue
        evidence = _event_evidence(event, node_id, "payload", event.payload)
        items.append(
            FaultCandidate(
                node_id=node_id,
                event_id=event_id,
                reason=FaultReason.FAILED_STEP_WITH_ERROR,
                precedence_rank=FaultPrecedence.FAILED_STEP_WITH_ERROR,
                supporting_evidence=evidence,
            )
        )
    for cancellation in cancel_events:
        node_id = index.event_view_ids[cancellation.event_id]
        ancestor = parent.get(node_id)
        visited: set[str] = set()
        while ancestor is not None and ancestor not in visited and ancestor not in failed_ids:
            visited.add(ancestor)
            ancestor = parent.get(ancestor)
        if ancestor in failed_ids:
            items.append(
                FaultCandidate(
                    node_id=node_id,
                    event_id=cancellation.event_id,
                    reason=FaultReason.CANCELLATION_AFTER_FAULT,
                    precedence_rank=FaultPrecedence.CANCELLATION_AFTER_FAULT,
                    supporting_evidence=_event_evidence(
                        cancellation, node_id, "kind", cancellation.kind.value
                    ),
                )
            )
    by_series: dict[str, list[FaultCandidate]] = {}
    for candidate in items:
        view = index.views_by_id[candidate.node_id]
        if view.series_id is not None:
            by_series.setdefault(view.series_id, []).append(candidate)
    discarded: set[str] = set()
    for series_candidates in by_series.values():
        if len(series_candidates) < 2:
            continue
        series_candidates.sort(key=lambda item: (view_order[item.node_id], item.event_id))
        retry_ids = tuple(
            event_id
            for view in views
            if view.series_id == index.views_by_id[series_candidates[0].node_id].series_id
            for event_id in view.event_ids
            if index.events_by_id[event_id].kind is EventKind.RETRY
        )
        earliest = series_candidates[0]
        items[items.index(earliest)] = FaultCandidate(
            node_id=earliest.node_id,
            event_id=earliest.event_id,
            reason=earliest.reason,
            precedence_rank=earliest.precedence_rank,
            supporting_evidence=earliest.supporting_evidence,
            retry_event_ids=retry_ids,
        )
        discarded.update(item.event_id for item in series_candidates[1:])
    items = [item for item in items if item.event_id not in discarded]
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.precedence_rank,
                view_order[item.node_id],
                item.event_id,
            ),
        )
    )


def _event_evidence(
    event: TraceEvent, node_id: str, field: str, value: str
) -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            field_path=f"events/{event.event_id}/{field}",
            value=value,
            source_node_id=node_id,
            source_event_id=event.event_id,
            note="canonical event field",
            source_ref=event.provenance,
            evidence_id=event.evidence_refs[0] if event.evidence_refs else None,
        ),
    )
