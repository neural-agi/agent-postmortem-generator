"""Structured diagnostics for parser and validation failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DiagnosticSeverity(StrEnum):
    """Severity levels for parser and validation diagnostics."""

    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(StrEnum):
    """Machine-readable diagnostic codes."""

    INVALID_ENCODING = "invalid_encoding"
    INVALID_JSON = "invalid_json"
    NON_OBJECT_ROOT = "non_object_root"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FIELD_TYPE = "invalid_field_type"
    INVALID_TIMESTAMP = "invalid_timestamp"
    DUPLICATE_IDENTIFIER = "duplicate_identifier"
    BROKEN_REFERENCE = "broken_reference"
    OUT_OF_ORDER_EVENTS = "out_of_order_events"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Single structured diagnostic entry."""

    severity: DiagnosticSeverity
    code: DiagnosticCode
    field_path: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Ordered diagnostics plus overall parse outcome."""

    success: bool
    diagnostics: tuple[Diagnostic, ...]
