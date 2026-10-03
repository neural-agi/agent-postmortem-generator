"""Deterministic, evidence-backed analysis of normalized canonical traces."""

from agent_postmortem.analysis.engine import AnalysisEngine, analyze
from agent_postmortem.analysis.models import (
    AnalysisContractError,
    AnalysisResult,
    CausalEdge,
    CausalEdgeKind,
    DiagnosticIssue,
    EvidenceItem,
    ExecutionNodeView,
    FailureChain,
    FaultCandidate,
    FaultPrecedence,
    FaultReason,
    IssueCode,
    IssueSeverity,
    TerminalOutcome,
)

__all__ = [
    "AnalysisContractError",
    "AnalysisEngine",
    "AnalysisResult",
    "CausalEdge",
    "CausalEdgeKind",
    "DiagnosticIssue",
    "EvidenceItem",
    "ExecutionNodeView",
    "FailureChain",
    "FaultCandidate",
    "FaultPrecedence",
    "FaultReason",
    "IssueCode",
    "IssueSeverity",
    "TerminalOutcome",
    "analyze",
]
