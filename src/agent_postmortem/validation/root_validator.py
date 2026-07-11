"""Root envelope validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity
from agent_postmortem.validation.trace_document import TraceEnvelope


class RootValidator:
    """Validate the trace envelope fields."""

    def validate(
        self, root: Mapping[str, object]
    ) -> tuple[TraceEnvelope | None, tuple[Diagnostic, ...]]:
        diagnostics: list[Diagnostic] = []
        document_id = root.get("document_id")
        trace_version = root.get("trace_version")
        run_id = root.get("run_id")
        if not isinstance(document_id, str) or not document_id:
            diagnostics.append(
                _missing("/document_id", "document_id is required and must be a non-empty string")
            )
        if not isinstance(trace_version, str) or not trace_version:
            diagnostics.append(
                _missing(
                    "/trace_version", "trace_version is required and must be a non-empty string"
                )
            )
        if not isinstance(run_id, str) or not run_id:
            diagnostics.append(
                _missing("/run_id", "run_id is required and must be a non-empty string")
            )
        if diagnostics:
            return None, tuple(diagnostics)
        return TraceEnvelope(
            document_id=cast(str, document_id),
            trace_version=cast(str, trace_version),
            run_id=cast(str, run_id),
        ), ()


def _missing(field_path: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=DiagnosticCode.MISSING_REQUIRED_FIELD,
        field_path=field_path,
        message=message,
    )
