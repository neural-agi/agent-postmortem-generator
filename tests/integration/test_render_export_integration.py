from __future__ import annotations

from agent_postmortem.graph import GraphDocument, GraphMetadata, GraphNode, GraphNodeKind
from agent_postmortem.postmortem.models import (
    PostmortemReport,
    ReportMetadata,
    ReportSection,
    SectionId,
)
from agent_postmortem.renderers import ExportPlan, OutputFormat, export_bundle
from agent_postmortem.renderers.models import ReportBundle


def _bundle() -> ReportBundle:
    report = PostmortemReport(
        "report",
        "Failure summary",
        ReportMetadata("project", "Part 5", None, "trace", "run", None),
        tuple(ReportSection(item, item.value, index, ()) for index, item in enumerate(SectionId)),
        (),
    )
    graph = GraphDocument(
        "graph",
        "trace",
        "analysis",
        "v1",
        (GraphNode("event-a", "a", GraphNodeKind.EVENT, "a", "unknown", 0),),
        (),
        (),
        (),
        (),
        GraphMetadata("v1", "trace", "analysis", 1, 0, "digest"),
    )
    return ReportBundle(report, graph)


def test_export_receipt_matches_files_and_mermaid_golden(tmp_path) -> None:
    result = export_bundle(
        _bundle(),
        ExportPlan(tmp_path, (OutputFormat.MARKDOWN, OutputFormat.JSON, OutputFormat.MERMAID)),
    )

    assert result.success
    assert all(artifact.path.exists() for artifact in result.artifacts)
    assert (tmp_path / "postmortem.mmd").read_text(encoding="utf-8") == (
        'graph TD\n    n0["a [a]"]\n'
    )
