"""Coordinate the report compiler stages and return IR plus Markdown."""

from __future__ import annotations

from agent_postmortem.analysis import AnalysisResult
from agent_postmortem.domain import CanonicalTraceDocument
from agent_postmortem.postmortem.context import build_report_context
from agent_postmortem.postmortem.evidence import bind_evidence
from agent_postmortem.postmortem.guard import check_report
from agent_postmortem.postmortem.markdown import render_markdown
from agent_postmortem.postmortem.models import (
    DiagnosticCode,
    DiagnosticEntry,
    DiagnosticSeverity,
    PostmortemGenerationResult,
    ReportConfiguration,
)
from agent_postmortem.postmortem.narrative import assemble_narrative
from agent_postmortem.postmortem.planner import plan_sections


class PostmortemEngine:
    """Compile Part 4 conclusions and Part 1 evidence into a stable report."""

    def generate(
        self,
        analysis: AnalysisResult,
        trace: CanonicalTraceDocument,
        configuration: ReportConfiguration | None = None,
    ) -> PostmortemGenerationResult:
        """Generate the fixed v1 report IR and its Markdown representation."""

        settings = configuration or ReportConfiguration()
        context = build_report_context(analysis, trace, settings)
        plan = plan_sections(context)
        narrative = assemble_narrative(context, plan)
        report_id = f"postmortem:v1:{trace.document_id}:{analysis.run_id}"
        bound_report = bind_evidence(
            context,
            narrative,
            report_id,
            _analysis_diagnostics(analysis),
        )
        report = check_report(bound_report, trace, analysis)
        return PostmortemGenerationResult(
            report=report,
            markdown=render_markdown(report),
        )


def generate_postmortem(
    analysis: AnalysisResult,
    trace: CanonicalTraceDocument,
    configuration: ReportConfiguration | None = None,
) -> PostmortemGenerationResult:
    """Convenience entry point for deterministic v1 postmortem generation."""

    return PostmortemEngine().generate(analysis, trace, configuration)


def _analysis_diagnostics(analysis: AnalysisResult) -> tuple[DiagnosticEntry, ...]:
    output: list[DiagnosticEntry] = []
    for issue in analysis.diagnostics:
        code = issue.code.value
        if code in {
            "ambiguous_terminal",
            "parallel_failure_branches",
            "unknown_cancellation_cause",
        }:
            diagnostic_code = DiagnosticCode.UNRESOLVED_AMBIGUITY
        elif code == "conflicting_terminal_signals":
            diagnostic_code = DiagnosticCode.CONTRADICTION
        elif code in {"incomplete_trace", "insufficient_fault_evidence"}:
            diagnostic_code = DiagnosticCode.INCOMPLETE_ANALYSIS
        elif code in {
            "unsupported_event_kind",
            "unsupported_causal_pattern",
            "missing_timestamps",
            "conflicting_timestamps",
            "ambiguous_event_types",
        }:
            diagnostic_code = DiagnosticCode.UNSUPPORTED_INFORMATION
        else:
            diagnostic_code = DiagnosticCode.UPSTREAM_DIAGNOSTIC
        refs = tuple(f"node:{node_id}" for node_id in issue.related_node_ids) + tuple(
            f"event:{event_id}" for event_id in issue.related_event_ids
        )
        output.append(
            DiagnosticEntry(
                code=diagnostic_code,
                severity=(
                    DiagnosticSeverity.ERROR
                    if issue.severity.value == "error"
                    else DiagnosticSeverity.WARNING
                ),
                message=f"Analysis: {issue.message}",
                related_refs=refs,
            )
        )
    return tuple(output)
