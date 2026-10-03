"""Immutable result types for deterministic canonical-trace analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum

from agent_postmortem.domain import EventKind, NodeStatus, ProvenanceRef


class TerminalOutcome(StrEnum):
    """Run termination class supported by the analysis contract."""

    SUCCESSFUL_COMPLETION = "successful_completion"
    EXPLICIT_FAILURE = "explicit_failure"
    CANCELLATION = "cancellation"
    TIMEOUT = "timeout"
    PARTIAL_TERMINATION = "partial_termination"
    STRUCTURALLY_INCOMPLETE = "structurally_incomplete_termination"


class CausalEdgeKind(StrEnum):
    """Supported explicit causal edge kinds."""

    PARENT = "parent"
    RETRY = "retry"


class FaultPrecedence(IntEnum):
    """Fixed first-fault ordering from the Part 4 design."""

    EXPLICIT_EXCEPTION = 1
    FAILED_STEP_WITH_ERROR = 2
    SUPPORTED_TIMEOUT = 3
    CANCELLATION_AFTER_FAULT = 4
    MISSING_OUTPUT_OR_INVALID_STATE = 5


class FaultReason(StrEnum):
    """Fault candidate classes currently expressible by the canonical model."""

    FAILED_STEP_WITH_ERROR = "failed_step_with_error"
    CANCELLATION_AFTER_FAULT = "cancellation_after_fault"


class IssueSeverity(StrEnum):
    """Severity for an analysis diagnostic."""

    WARNING = "warning"
    ERROR = "error"


class IssueCode(StrEnum):
    """Stable diagnostic codes emitted by the analysis engine."""

    MISSING_TIMESTAMPS = "missing_timestamps"
    CONFLICTING_TIMESTAMPS = "conflicting_timestamps"
    AMBIGUOUS_EVENT_TYPES = "ambiguous_event_types"
    UNSUPPORTED_EVENT_KIND = "unsupported_event_kind"
    UNSUPPORTED_CAUSAL_PATTERN = "unsupported_causal_pattern"
    UNKNOWN_CANCELLATION_CAUSE = "unknown_cancellation_cause"
    INSUFFICIENT_FAULT_EVIDENCE = "insufficient_fault_evidence"
    AMBIGUOUS_TERMINAL = "ambiguous_terminal"
    PARALLEL_FAILURE_BRANCHES = "parallel_failure_branches"
    CONFLICTING_TERMINAL_SIGNALS = "conflicting_terminal_signals"
    INCOMPLETE_TRACE = "incomplete_trace"
    UPSTREAM_NORMALIZATION_ISSUE = "upstream_normalization_issue"


@dataclass(frozen=True, slots=True)
class ExecutionNodeView:
    """Analysis-facing view of a canonical node and its associated events."""

    node_id: str
    event_type: EventKind
    status: NodeStatus
    sequence_index: int
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    event_ids: tuple[str, ...]
    parent_ids: tuple[str, ...] = ()
    child_ids: tuple[str, ...] = ()
    series_id: str | None = None
    attempt_index: int | None = None


@dataclass(frozen=True, slots=True)
class CausalEdge:
    """Directed cause-to-effect link backed by an explicit trace fact."""

    from_node_id: str
    to_node_id: str
    edge_kind: CausalEdgeKind
    source_of_truth: str
    source_ref: ProvenanceRef | None = None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One canonical field, record, or relation supporting a conclusion."""

    field_path: str
    value: str | int | bool | None
    source_node_id: str | None
    source_event_id: str | None
    note: str
    source_ref: ProvenanceRef | None = None
    evidence_id: str | None = None
    relation: CausalEdge | None = None


@dataclass(frozen=True, slots=True)
class FaultCandidate:
    """Ranked, evidence-backed candidate for the first meaningful fault."""

    node_id: str
    event_id: str
    reason: FaultReason
    precedence_rank: FaultPrecedence
    supporting_evidence: tuple[EvidenceItem, ...]
    retry_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FailureChain:
    """Causal path, ordered from supported upstream cause to terminal node."""

    ordered_node_ids: tuple[str, ...]
    terminal_node_id: str | None
    propagation_steps: tuple[CausalEdge, ...]


@dataclass(frozen=True, slots=True)
class DiagnosticIssue:
    """Structured warning or limitation associated with trace entities."""

    severity: IssueSeverity
    code: IssueCode
    message: str
    related_node_ids: tuple[str, ...] = ()
    related_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Stable structured analysis output for one canonical run."""

    run_id: str
    terminal_outcome: TerminalOutcome
    terminal_failure: ExecutionNodeView | None
    first_fault: FaultCandidate | None
    alternative_candidates: tuple[FaultCandidate, ...]
    failure_chain: FailureChain
    execution_index: tuple[str, ...]
    execution_views: tuple[ExecutionNodeView, ...]
    causal_edges: tuple[CausalEdge, ...]
    evidence: tuple[EvidenceItem, ...]
    diagnostics: tuple[DiagnosticIssue, ...]


class AnalysisContractError(ValueError):
    """Raised when canonical references or causal graph structure are invalid."""
