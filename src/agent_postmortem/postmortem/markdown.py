"""Render a verified report IR as stable Markdown without filesystem effects."""

from __future__ import annotations

from agent_postmortem.postmortem.models import (
    ActionItem,
    CausalChainStep,
    ContentBlock,
    ContentBlockType,
    DiagnosticEntry,
    EvidenceCitation,
    FindingSummary,
    PostmortemReport,
    ReportSection,
)


def render_markdown(report: PostmortemReport) -> str:
    """Render report data in fixed section and upstream item order."""

    lines = [f"# {_inline(report.title)}", ""]
    lines.extend(
        (
            f"Project: {_inline(report.metadata.project_name)}",
            f"Module: {_inline(report.metadata.module_part)}",
            f"Trace: {_inline(report.metadata.trace_id)}",
            f"Run: {_inline(report.metadata.run_id)}",
        )
    )
    if report.metadata.generated_at is not None:
        lines.append(f"Generated at: {report.metadata.generated_at.isoformat()}")
    lines.append("")
    for section in report.sections:
        lines.extend(_render_section(section))
    if report.diagnostics:
        lines.extend(("Diagnostics:", ""))
        lines.extend(_render_diagnostic(item) for item in report.diagnostics)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_section(section: ReportSection) -> list[str]:
    lines = [f"## {_inline(section.title)}", ""]
    for block in section.blocks:
        lines.extend(_render_block(block))
    if len(lines) == 2:
        lines.append("Information unavailable.")
        lines.append("")
    return lines


def _render_block(block: ContentBlock) -> list[str]:
    lines: list[str] = []
    if block.type is ContentBlockType.PARAGRAPH:
        lines.append(_inline(block.text))
        lines.extend(_render_citations(block.evidence_refs))
        lines.append("")
    elif block.type is ContentBlockType.BULLET_LIST:
        lines.extend(f"- {_inline(item)}" for item in block.bullets)
        lines.extend(_render_citations(block.evidence_refs))
        lines.append("")
    else:
        for row in block.rows:
            lines.append(_render_row(row))
        lines.append("")
    return lines


def _render_row(
    row: FindingSummary | CausalChainStep | EvidenceCitation | ActionItem,
) -> str:
    if isinstance(row, FindingSummary):
        return (
            f"- {row.label}: {_inline(row.description)} "
            f"(status: `{_inline(row.status)}`)"
            f"{_citation_suffix(row.evidence_refs)}"
        )
    if isinstance(row, CausalChainStep):
        return (
            f"- {row.sequence + 1}. `{_inline(row.cause)}` -> `{_inline(row.effect)}`"
            f"{_citation_suffix(row.evidence_refs)}"
        )
    if isinstance(row, EvidenceCitation):
        return f"- {_citation_text(row)}"
    text = f"- {_inline(row.recommendation)} {_inline(row.rationale)}".rstrip()
    return f"{text}{_citation_suffix(row.evidence_refs)}"


def _render_citations(citations: tuple[EvidenceCitation, ...]) -> list[str]:
    return [f"- {_citation_text(item)}" for item in citations]


def _citation_suffix(citations: tuple[EvidenceCitation, ...]) -> str:
    if not citations:
        return ""
    values = ", ".join(item.evidence_id or "evidence unavailable" for item in citations)
    return f" [evidence: {values}]"


def _citation_text(citation: EvidenceCitation) -> str:
    reference = citation.evidence_id or "evidence unavailable"
    node = f"; node `{_inline(citation.trace_node_id)}`" if citation.trace_node_id else ""
    event = f"; event index {citation.event_index}" if citation.event_index is not None else ""
    return (
        f"`{_inline(reference)}` ({citation.status.value}{node}{event}): "
        f"{_inline(citation.snippet)}. {_inline(citation.note)}"
    )


def _render_diagnostic(item: DiagnosticEntry) -> str:
    refs = f" ({', '.join(item.related_refs)})" if item.related_refs else ""
    return f"- `{item.severity.value}/{item.code.value}` {_inline(item.message)}{_inline(refs)}"


def _inline(value: str) -> str:
    return value.replace("\r\n", " ").replace("\n", " ").replace("|", "\\|").strip()
