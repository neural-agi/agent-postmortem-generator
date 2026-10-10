from __future__ import annotations

import json

import pytest

from agent_postmortem.graph import (
    GraphDocument,
    GraphMetadata,
    GraphNode,
    GraphNodeKind,
)
from agent_postmortem.postmortem.models import (
    PostmortemReport,
    ReportMetadata,
    ReportSection,
    SectionId,
)
from agent_postmortem.renderers import (
    ExportError,
    ExportPlan,
    OutputFormat,
    ReportBundle,
    export_bundle,
    render_json,
    render_mermaid,
)


def _bundle() -> ReportBundle:
    report = PostmortemReport(
        report_id="report",
        title='Failure "summary"',
        metadata=ReportMetadata("project", "Part 5", None, "trace", "run", None),
        sections=tuple(
            ReportSection(section_id, section_id.value, index, ())
            for index, section_id in enumerate(SectionId)
        ),
        diagnostics=(),
    )
    graph = GraphDocument(
        "graph",
        "trace",
        "analysis",
        "v1",
        (GraphNode("event-a", "a", GraphNodeKind.EVENT, 'a"\n[b]', "unknown", 0),),
        (),
        (),
        (),
        (),
        GraphMetadata("v1", "trace", "analysis", 1, 0, "digest"),
    )
    return ReportBundle(report, graph)


def test_json_and_mermaid_are_stable_and_escape_labels() -> None:
    bundle = _bundle()

    assert render_json(bundle) == render_json(bundle)
    payload = json.loads(render_json(bundle))
    assert payload["graph"]["nodes"][0]["evidence_refs"] == []
    mermaid = render_mermaid(bundle.graph)
    assert '\\"' in mermaid
    assert 'a\\" [b]' in mermaid


def test_export_writes_fixed_names_and_is_repeatable(tmp_path) -> None:
    plan = ExportPlan(tmp_path, (OutputFormat.MARKDOWN, OutputFormat.JSON, OutputFormat.MERMAID))

    result = export_bundle(_bundle(), plan)

    assert result.success
    assert [artifact.path.name for artifact in result.artifacts] == [
        "postmortem.md",
        "postmortem.json",
        "postmortem.mmd",
    ]
    first = {artifact.path.name: artifact.path.read_bytes() for artifact in result.artifacts}
    second_dir = tmp_path / "second"
    export_bundle(_bundle(), ExportPlan(second_dir, plan.targets))
    assert first == {name: (second_dir / name).read_bytes() for name in first}


def test_mermaid_requires_graph_and_existing_files_require_overwrite(tmp_path) -> None:
    report_only = ReportBundle(_bundle().report)
    with pytest.raises(ExportError):
        export_bundle(report_only, ExportPlan(tmp_path, (OutputFormat.MERMAID,)))
    export_bundle(_bundle(), ExportPlan(tmp_path, (OutputFormat.JSON,)))
    with pytest.raises(ExportError):
        export_bundle(_bundle(), ExportPlan(tmp_path, (OutputFormat.JSON,)))
