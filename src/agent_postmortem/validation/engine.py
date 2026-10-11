"""Parser and validation engine for the generic MVP trace contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TextIO, cast

from agent_postmortem.parsing.input import RawInput
from agent_postmortem.validation.diagnostics import (
    Diagnostic,
    DiagnosticCode,
    DiagnosticSeverity,
    ValidationReport,
)
from agent_postmortem.validation.semantic_validator import SemanticValidator
from agent_postmortem.validation.structural_validator import StructuralValidator
from agent_postmortem.validation.trace_document import (
    TraceEvent,
    ValidatedTraceDocument,
)
from agent_postmortem.validation.v2_document import V2ValidatedTraceDocument
from agent_postmortem.validation.v2_validator import V2Validator


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Immutable parser outcome."""

    report: ValidationReport
    document: ValidatedTraceDocument | None
    v2_document: V2ValidatedTraceDocument | None = None


class ValidationEngine:
    """Coordinate parsing and validation for generic trace input."""

    def __init__(self) -> None:
        self._structural_validator = StructuralValidator()
        self._semantic_validator = SemanticValidator()
        self._v2_validator = V2Validator()

    def validate(
        self, source: str | bytes | Path | TextIO | BinaryIO | RawInput
    ) -> ValidationResult:
        from agent_postmortem.parsing.pipeline import parse_input

        parse_result = parse_input(source)
        if parse_result.document is None:
            report = ValidationReport(success=False, diagnostics=parse_result.diagnostics)
            return ValidationResult(report=report, document=None)

        parsed_root = parse_result.document.data
        if not isinstance(parsed_root, Mapping):
            diagnostic = Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=DiagnosticCode.NON_OBJECT_ROOT,
                field_path="",
                message="top-level JSON value must be an object",
            )
            report = ValidationReport(success=False, diagnostics=(diagnostic,))
            return ValidationResult(report=report, document=None)

        version = parsed_root.get("trace_version")
        if isinstance(version, str) and version == "v2":
            v2_document, v2_diagnostics = self._v2_validator.validate(
                parsed_root, parse_result.raw_input.metadata
            )
            diagnostics = list(parse_result.diagnostics)
            diagnostics.extend(v2_diagnostics)
            report = ValidationReport(
                success=v2_document is not None
                and not any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics),
                diagnostics=tuple(diagnostics),
            )
            return ValidationResult(
                report=report,
                document=None,
                v2_document=v2_document if report.success else None,
            )

        if isinstance(version, str) and version and version != "v1":
            diagnostic = Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code=DiagnosticCode.UNSUPPORTED_VERSION,
                field_path="/trace_version",
                message="trace_version must be 'v1' or 'v2'",
            )
            report = ValidationReport(
                success=False, diagnostics=(*parse_result.diagnostics, diagnostic)
            )
            return ValidationResult(report=report, document=None)

        envelope, events, structural_diagnostics = self._structural_validator.validate(parsed_root)
        diagnostics = list(parse_result.diagnostics)
        diagnostics.extend(structural_diagnostics)
        if envelope is None:
            report = ValidationReport(success=False, diagnostics=tuple(diagnostics))
            return ValidationResult(report=report, document=None)

        semantic_diagnostics = self._semantic_validator.validate(events)
        diagnostics.extend(semantic_diagnostics)
        if any(item.severity == DiagnosticSeverity.ERROR for item in diagnostics):
            report = ValidationReport(success=False, diagnostics=tuple(diagnostics))
            return ValidationResult(report=report, document=None)

        raw_fields = tuple(
            (key, value)
            for key, value in parsed_root.items()
            if key not in {"document_id", "trace_version", "run_id", "events"}
        )
        validated_events = tuple(
            TraceEvent(
                event_id=cast(str, item["event_id"]),
                sequence_index=cast(int, item["sequence_index"]),
                timestamp=cast(str | None, item.get("timestamp")),
                parent_id=cast(str | None, item.get("parent_id")),
                raw_fields=tuple(
                    (key, value)
                    for key, value in item.items()
                    if key not in {"event_id", "sequence_index", "timestamp", "parent_id"}
                ),
            )
            for item in events
        )
        document = ValidatedTraceDocument(
            envelope=envelope,
            events=validated_events,
            raw_fields=raw_fields,
            source_metadata=parse_result.raw_input.metadata,
            diagnostics=tuple(diagnostics),
        )
        report = ValidationReport(success=True, diagnostics=tuple(diagnostics))
        return ValidationResult(report=report, document=document)


def parse_and_validate_input(
    source: str | bytes | Path | TextIO | BinaryIO | RawInput,
) -> ValidationResult:
    """Parse and validate a trace payload from a supported input source."""

    return ValidationEngine().validate(source)


def validate_from_path(path: str | Path) -> ValidationResult:
    """Read, parse, and validate a file path."""

    return parse_and_validate_input(path)


def validate_from_stdin(stdin: TextIO) -> ValidationResult:
    """Read, parse, and validate stdin."""

    return parse_and_validate_input(stdin)
