"""Stable JSON serialization for the public report and graph IRs."""

from __future__ import annotations

import json

from agent_postmortem.graph.models import GraphDocument
from agent_postmortem.renderers.models import ReportBundle

type JsonValue = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]


def render_json(bundle: ReportBundle) -> str:
    """Serialize the report bundle with stable keys, arrays, and LF endings."""

    payload: dict[str, object] = {"report": bundle.report.to_dict()}
    if bundle.graph is not None:
        payload["graph"] = _graph_dict(bundle.graph)
    return json.dumps(payload, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n"


def _graph_dict(graph: GraphDocument) -> dict[str, object]:
    return {
        "graph_id": graph.graph_id,
        "source_trace_id": graph.source_trace_id,
        "analysis_id": graph.analysis_id,
        "version": graph.version,
        "nodes": [_dataclass_dict(node) for node in graph.nodes],
        "edges": [_dataclass_dict(edge) for edge in graph.edges],
        "groups": [_dataclass_dict(group) for group in graph.groups],
        "annotations": [_dataclass_dict(item) for item in graph.annotations],
        "diagnostics": [_dataclass_dict(item) for item in graph.diagnostics],
        "metadata": _dataclass_dict(graph.metadata),
    }


def _dataclass_dict(value: object) -> JsonValue:
    from dataclasses import fields, is_dataclass

    if not is_dataclass(value):
        raise TypeError("JSON renderer received a non-public graph model")
    result = {field.name: getattr(value, field.name) for field in fields(value)}
    normalized = _normalize(result)
    if not isinstance(normalized, dict):
        raise TypeError("graph model did not serialize to an object")
    return normalized


def _normalize(value: object) -> JsonValue:
    from enum import StrEnum

    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
