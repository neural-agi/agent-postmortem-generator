"""Acceptance coverage for the versioned generic trace v2 workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_postmortem.analysis import AnalysisEngine, IssueCode, TerminalOutcome
from agent_postmortem.graph import GraphEdgeKind, GraphEngine
from agent_postmortem.normalization import NormalizationEngine
from agent_postmortem.postmortem import PostmortemEngine, render_markdown
from agent_postmortem.renderers import ReportBundle, render_json, render_mermaid
from agent_postmortem.validation import DiagnosticCode, parse_and_validate_input

FIXTURES = Path(__file__).parents[1] / "fixtures"
GOLDENS = Path(__file__).parents[1] / "golden"
ROOT = Path(__file__).parents[2]


def _validated(name: str):
    result = parse_and_validate_input(FIXTURES / name)
    assert result.report.success, result.report.diagnostics
    assert result.v2_document is not None
    return result.v2_document


def _pipeline(name: str):
    normalized = NormalizationEngine().normalize(_validated(name))
    analysis = AnalysisEngine().analyze(normalized)
    report = PostmortemEngine().generate(analysis, normalized.canonical_trace)
    graph = GraphEngine().generate(normalized.canonical_trace, analysis)
    return normalized, analysis, report, graph


@pytest.mark.parametrize(
    ("fixture", "outcome"),
    [
        ("v2_success.json", TerminalOutcome.SUCCESSFUL_COMPLETION),
        ("v2_failure.json", TerminalOutcome.EXPLICIT_FAILURE),
        ("v2_cancelled.json", TerminalOutcome.CANCELLATION),
        ("v2_unknown_end.json", TerminalOutcome.UNKNOWN_OUTCOME),
        ("v2_unknown_failed_node.json", TerminalOutcome.UNKNOWN_OUTCOME),
        ("v2_retry_recovery.json", TerminalOutcome.SUCCESSFUL_COMPLETION),
        ("v2_parallel_failures.json", TerminalOutcome.EXPLICIT_FAILURE),
        ("v2_conflicting_terminal.json", TerminalOutcome.SUCCESSFUL_COMPLETION),
        ("v2_unknown_enum.json", TerminalOutcome.UNKNOWN_OUTCOME),
        ("v2_incomplete.json", TerminalOutcome.STRUCTURALLY_INCOMPLETE),
    ],
)
def test_v2_pipeline_classifies_representative_traces(
    fixture: str, outcome: TerminalOutcome
) -> None:
    normalized, analysis, report, graph = _pipeline(fixture)

    assert analysis.terminal_outcome is outcome
    assert report.report.sections
    assert graph.nodes or outcome is TerminalOutcome.STRUCTURALLY_INCOMPLETE
    assert normalized.normalization_schema_version == "v2"
    assert render_markdown(report.report)
    assert render_json(ReportBundle(report.report, graph))
    assert render_mermaid(graph)


def test_v2_failure_preserves_evidence_through_report_and_graph() -> None:
    _normalized, analysis, report, graph = _pipeline("v2_failure.json")

    assert analysis.first_fault is not None
    assert analysis.first_fault.supporting_evidence
    assert "err-1" in render_markdown(report.report)
    assert any(edge.kind is GraphEdgeKind.PARENT for edge in graph.edges) is False
    assert "err-1" in render_markdown(report.report)


def test_v2_retry_recovery_keeps_failed_attempt_visible_without_selecting_it_as_fault() -> None:
    _normalized, analysis, _report, graph = _pipeline("v2_retry_recovery.json")

    assert analysis.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
    assert analysis.first_fault is None
    assert any(edge.kind is GraphEdgeKind.RETRY for edge in graph.edges)
    assert any(view.status.value == "failure" for view in analysis.execution_views)


def test_v2_conflict_is_diagnostic_without_overriding_explicit_run_status() -> None:
    _normalized, analysis, report, _graph = _pipeline("v2_conflicting_terminal.json")

    assert analysis.terminal_outcome is TerminalOutcome.SUCCESSFUL_COMPLETION
    assert any(item.code is IssueCode.CONFLICTING_TERMINAL_SIGNALS for item in analysis.diagnostics)
    assert "conflicting" in render_markdown(report.report).lower()


def test_v2_unknown_enum_values_are_preserved_as_source_evidence() -> None:
    normalized, analysis, _report, _graph = _pipeline("v2_unknown_enum.json")

    assert analysis.terminal_outcome is TerminalOutcome.UNKNOWN_OUTCOME
    node = normalized.canonical_trace.nodes[0]
    assert node.kind.value == "unknown"
    assert any(entry.canonical_field.endswith("/kind") for entry in normalized.provenance_index)


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("v2_invalid_reference.json", DiagnosticCode.BROKEN_REFERENCE),
        ("v2_parent_cycle.json", DiagnosticCode.PARENT_CYCLE),
    ],
)
def test_v2_invalid_relationships_fail_before_normalization(
    fixture: str, code: DiagnosticCode
) -> None:
    result = parse_and_validate_input(FIXTURES / fixture)

    assert not result.report.success
    assert any(item.code is code for item in result.report.diagnostics)
    assert result.v2_document is None


def test_v2_export_serialization_is_repeatable() -> None:
    _normalized, _analysis, report, graph = _pipeline("v2_failure.json")

    markdown_a = render_markdown(report.report)
    markdown_b = render_markdown(report.report)
    json_a = render_json(ReportBundle(report.report, graph))
    json_b = render_json(ReportBundle(report.report, graph))
    mermaid_a = render_mermaid(graph)
    mermaid_b = render_mermaid(graph)

    assert markdown_a == markdown_b
    assert json_a == json_b
    assert mermaid_a == mermaid_b
    assert json.loads(json_a)["report"]["metadata"]["trace_id"] == "v2-failure-doc"


@pytest.mark.parametrize(
    "name", ("v2_failure", "v2_unknown_end", "v2_retry_recovery", "v2_success")
)
def test_v2_cli_exports_match_committed_goldens(tmp_path: Path, name: str) -> None:
    output = tmp_path / name
    result = subprocess.run(
        [
            "uv",
            "run",
            "apg",
            "analyze",
            str(FIXTURES / f"{name}.json"),
            "--format",
            "all",
            "--output-dir",
            str(output),
            "--overwrite",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for artifact in ("postmortem.md", "postmortem.json", "postmortem.mmd"):
        assert (output / artifact).read_bytes() == (GOLDENS / name / artifact).read_bytes()
