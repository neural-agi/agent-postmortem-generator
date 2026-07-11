"""Validation helpers for canonical trace documents.

Cross-entity validation lives outside the domain package so the canonical
models remain focused on data definition and local invariants only.
"""

from agent_postmortem.validation.canonical_trace import validate_canonical_trace_document
from agent_postmortem.validation.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    DiagnosticSeverity,
    ValidationReport,
)
from agent_postmortem.validation.engine import (
    ValidationResult,
    parse_and_validate_input,
    validate_from_path,
    validate_from_stdin,
)
from agent_postmortem.validation.trace_document import (
    TraceEnvelope,
    TraceEvent,
    ValidatedTraceDocument,
)

__all__ = [
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticSeverity",
    "TraceEnvelope",
    "TraceEvent",
    "ValidatedTraceDocument",
    "ValidationReport",
    "ValidationResult",
    "parse_and_validate_input",
    "validate_canonical_trace_document",
    "validate_from_path",
    "validate_from_stdin",
]
