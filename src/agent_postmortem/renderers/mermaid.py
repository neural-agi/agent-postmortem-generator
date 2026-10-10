"""Deterministic Mermaid source emission for the Part 6 graph IR."""

from __future__ import annotations

from agent_postmortem.graph.models import GraphDocument


def render_mermaid(graph: GraphDocument) -> str:
    """Render graph topology and annotations without deriving new relationships."""

    node_ids = {node.node_id: f"n{index}" for index, node in enumerate(graph.nodes)}
    lines = ["graph TD"]
    for node in graph.nodes:
        label = f"{node.label} [{node.event_id}]"
        lines.append(f'    {node_ids[node.node_id]}["{_escape(label)}"]')
    for group in graph.groups:
        members = [node_ids[item] for item in group.member_node_ids if item in node_ids]
        if members:
            lines.append(f"    subgraph {_escape(group.label)}")
            for member in members:
                lines.append(f"        {member}")
            lines.append("    end")
    for edge in graph.edges:
        arrow = "-.->" if edge.style_hint == "dashed" else "-->"
        label = f"|{_escape(edge.label)}|" if edge.label else ""
        lines.append(
            f"    {node_ids[edge.from_node_id]} {arrow}{label} {node_ids[edge.to_node_id]}"
        )
    for annotation in graph.annotations:
        target = node_ids.get(annotation.target_id)
        if target:
            lines.append(f"    %% {target}: {_escape(annotation.label)}")
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r\n", " ").replace("\n", " ")
