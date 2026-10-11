"""Structural and semantic validation for Generic Trace Contract v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum

from agent_postmortem.domain.kinds import EventKind, EventSeverity, EvidenceType, NodeKind
from agent_postmortem.domain.status import NodeStatus, RunStatus
from agent_postmortem.parsing.input import InputMetadata
from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity
from agent_postmortem.validation.v2_document import (
    V2Event,
    V2Evidence,
    V2Node,
    V2Run,
    V2ValidatedTraceDocument,
)

_ROOT_FIELDS = {"document_id", "trace_version", "run_id", "run", "nodes", "events", "evidence"}
_RUN_FIELDS = {"status", "started_at", "ended_at", "source_format"}
_NODE_FIELDS = {
    "node_id",
    "kind",
    "status",
    "sequence_index",
    "parent_node_id",
    "series_id",
    "attempt_index",
    "started_at",
    "ended_at",
    "attributes",
}
_EVENT_FIELDS = {
    "event_id",
    "sequence_index",
    "timestamp",
    "created_at",
    "started_at",
    "ended_at",
    "observed_at",
    "kind",
    "severity",
    "node_id",
    "parent_id",
    "payload",
    "evidence_refs",
}
_EVIDENCE_FIELDS = {"evidence_id", "evidence_type", "content_ref", "content_summary"}
_TIMESTAMP_FIELDS = ("created_at", "started_at", "ended_at", "observed_at", "timestamp")


class V2Validator:
    """Validate and type a v2 root without normalizing it."""

    def validate(
        self, root: Mapping[str, object], metadata: InputMetadata
    ) -> tuple[V2ValidatedTraceDocument | None, tuple[Diagnostic, ...]]:
        diagnostics: list[Diagnostic] = []
        document_id = _required_string(root, "document_id", "", diagnostics)
        run_id = _required_string(root, "run_id", "", diagnostics)
        if root.get("trace_version") != "v2":
            diagnostics.append(
                _error(
                    DiagnosticCode.UNSUPPORTED_VERSION,
                    "/trace_version",
                    "trace_version must be 'v2'",
                )
            )
        run = self._run(root.get("run"), diagnostics)
        nodes = self._nodes(root.get("nodes"), diagnostics)
        events = self._events(root.get("events"), diagnostics)
        evidence = self._evidence(root.get("evidence"), diagnostics)
        diagnostics.extend(self._semantic(nodes, events, evidence))
        if any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics):
            return None, tuple(diagnostics)
        raw_fields = tuple((key, value) for key, value in root.items() if key not in _ROOT_FIELDS)
        return V2ValidatedTraceDocument(
            document_id=document_id or "",
            trace_version="v2",
            run_id=run_id or "",
            run=run,
            nodes=tuple(nodes),
            events=tuple(events),
            evidence=tuple(evidence),
            raw_fields=raw_fields,
            source_metadata=metadata,
            diagnostics=tuple(diagnostics),
        ), tuple(diagnostics)

    def _run(self, value: object, diagnostics: list[Diagnostic]) -> V2Run | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            diagnostics.append(_type_error("/run", "run must be an object"))
            return None
        status = _optional_enum(value, "status", RunStatus, "/run", diagnostics)
        started = _optional_timestamp(value, "started_at", "/run", diagnostics)
        ended = _optional_timestamp(value, "ended_at", "/run", diagnostics)
        source_format = _optional_string(value, "source_format", "/run", diagnostics)
        if started is not None and ended is not None and ended < started:
            diagnostics.append(
                _error(
                    DiagnosticCode.INVALID_TIMESTAMP,
                    "/run/ended_at",
                    "ended_at cannot be earlier than started_at",
                )
            )
        return V2Run(status, started, ended, source_format)

    def _nodes(self, value: object, diagnostics: list[Diagnostic]) -> list[V2Node]:
        if value is None:
            return []
        if not isinstance(value, list):
            diagnostics.append(_type_error("/nodes", "nodes must be an array"))
            return []
        result: list[V2Node] = []
        for index, item in enumerate(value):
            path = f"/nodes/{index}"
            if not isinstance(item, Mapping):
                diagnostics.append(_type_error(path, "node must be an object"))
                continue
            node_id = _required_string(item, "node_id", path, diagnostics)
            sequence = _nonnegative_int(item, "sequence_index", path, diagnostics)
            kind = _optional_enum(item, "kind", NodeKind, path, diagnostics)
            status = _optional_enum(item, "status", NodeStatus, path, diagnostics)
            parent = _optional_string(item, "parent_node_id", path, diagnostics)
            series = _optional_string(item, "series_id", path, diagnostics)
            attempt = _optional_nonnegative(item, "attempt_index", path, diagnostics)
            started = _optional_timestamp(item, "started_at", path, diagnostics)
            ended = _optional_timestamp(item, "ended_at", path, diagnostics)
            attributes = _attributes(item.get("attributes"), f"{path}/attributes", diagnostics)
            if started is not None and ended is not None and ended < started:
                diagnostics.append(
                    _error(
                        DiagnosticCode.INVALID_TIMESTAMP,
                        f"{path}/ended_at",
                        "ended_at cannot be earlier than started_at",
                    )
                )
            if (series is None) != (attempt is None):
                diagnostics.append(
                    _error(
                        DiagnosticCode.INVALID_RETRY_METADATA,
                        path,
                        "series_id and attempt_index must be supplied together",
                    )
                )
            result.append(
                V2Node(
                    node_id or "",
                    kind,
                    status,
                    sequence,
                    parent,
                    series,
                    attempt,
                    started,
                    ended,
                    attributes,
                    _raw(item, _NODE_FIELDS),
                )
            )
        return result

    def _events(self, value: object, diagnostics: list[Diagnostic]) -> list[V2Event]:
        if not isinstance(value, list):
            diagnostics.append(
                _error(
                    DiagnosticCode.MISSING_REQUIRED_FIELD,
                    "/events",
                    "events is required and must be an array",
                )
            )
            return []
        result: list[V2Event] = []
        for index, item in enumerate(value):
            path = f"/events/{index}"
            if not isinstance(item, Mapping):
                diagnostics.append(_type_error(path, "event must be an object"))
                continue
            event_id = _required_string(item, "event_id", path, diagnostics)
            sequence = _nonnegative_int(item, "sequence_index", path, diagnostics)
            candidates: list[tuple[str, datetime]] = []
            for field_name in _TIMESTAMP_FIELDS:
                parsed = _optional_timestamp(item, field_name, path, diagnostics)
                if parsed is not None:
                    candidates.append((field_name, parsed))
            timestamp = next((parsed for name, parsed in candidates if name == "timestamp"), None)
            for field_name in _TIMESTAMP_FIELDS:
                if field_name != "timestamp":
                    timestamp = next(
                        (parsed for name, parsed in candidates if name == field_name), timestamp
                    )
                    if timestamp is not None:
                        break
            node_id = _optional_string(item, "node_id", path, diagnostics)
            parent_id = _optional_string(item, "parent_id", path, diagnostics)
            payload = _optional_string(item, "payload", path, diagnostics)
            refs = _string_array(item.get("evidence_refs"), f"{path}/evidence_refs", diagnostics)
            kind = _optional_enum(item, "kind", EventKind, path, diagnostics)
            severity = _optional_enum(item, "severity", EventSeverity, path, diagnostics)
            result.append(
                V2Event(
                    event_id or "",
                    sequence,
                    timestamp,
                    kind,
                    severity,
                    node_id,
                    parent_id,
                    payload,
                    tuple(refs),
                    tuple(candidates),
                    _raw(item, _EVENT_FIELDS),
                )
            )
        return result

    def _evidence(self, value: object, diagnostics: list[Diagnostic]) -> list[V2Evidence]:
        if value is None:
            return []
        if not isinstance(value, list):
            diagnostics.append(_type_error("/evidence", "evidence must be an array"))
            return []
        result: list[V2Evidence] = []
        for index, item in enumerate(value):
            path = f"/evidence/{index}"
            if not isinstance(item, Mapping):
                diagnostics.append(_type_error(path, "evidence record must be an object"))
                continue
            evidence_id = _required_string(item, "evidence_id", path, diagnostics)
            evidence_type = _required_string(item, "evidence_type", path, diagnostics)
            if evidence_type and evidence_type not in {item.value for item in EvidenceType}:
                diagnostics.append(
                    _warning(
                        DiagnosticCode.INVALID_ENUM_VALUE,
                        f"{path}/evidence_type",
                        "unknown evidence_type preserved as opaque value",
                    )
                )
            content_ref = _optional_string(item, "content_ref", path, diagnostics)
            summary = _optional_string(item, "content_summary", path, diagnostics)
            if content_ref is None and summary is None:
                diagnostics.append(
                    _error(
                        DiagnosticCode.MISSING_REQUIRED_FIELD,
                        path,
                        "content_ref or content_summary is required for canonical evidence",
                    )
                )
            result.append(
                V2Evidence(
                    evidence_id or "",
                    evidence_type or "",
                    content_ref,
                    summary,
                    _raw(item, _EVIDENCE_FIELDS),
                )
            )
        return result

    def _semantic(
        self, nodes: list[V2Node], events: list[V2Event], evidence: list[V2Evidence]
    ) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        node_ids = _unique_ids((node.node_id for node in nodes), "/nodes", diagnostics)
        event_ids = _unique_ids((event.event_id for event in events), "/events", diagnostics)
        evidence_ids = _unique_ids(
            (record.evidence_id for record in evidence), "/evidence", diagnostics
        )
        for index, node in enumerate(nodes):
            if node.parent_node_id is not None and node.parent_node_id not in node_ids:
                diagnostics.append(
                    _error(
                        DiagnosticCode.BROKEN_REFERENCE,
                        f"/nodes/{index}/parent_node_id",
                        "parent_node_id must reference a declared node",
                    )
                )
        for index, event in enumerate(events):
            if event.node_id is not None and nodes and event.node_id not in node_ids:
                diagnostics.append(
                    _error(
                        DiagnosticCode.BROKEN_REFERENCE,
                        f"/events/{index}/node_id",
                        "node_id must reference a declared node",
                    )
                )
            if event.parent_id is not None and event.parent_id not in event_ids:
                diagnostics.append(
                    _error(
                        DiagnosticCode.BROKEN_REFERENCE,
                        f"/events/{index}/parent_id",
                        "parent_id must reference an existing event_id",
                    )
                )
            for ref in event.evidence_refs:
                if ref not in evidence_ids:
                    diagnostics.append(
                        _error(
                            DiagnosticCode.BROKEN_REFERENCE,
                            f"/events/{index}/evidence_refs",
                            f"evidence reference {ref!r} does not resolve",
                        )
                    )
        series: dict[str, set[int]] = {}
        for index, node in enumerate(nodes):
            if node.series_id is not None and node.attempt_index is not None:
                indexes = series.setdefault(node.series_id, set())
                if node.attempt_index in indexes:
                    diagnostics.append(
                        _error(
                            DiagnosticCode.INVALID_RETRY_METADATA,
                            f"/nodes/{index}/attempt_index",
                            "attempt_index must be unique within series_id",
                        )
                    )
                indexes.add(node.attempt_index)
        diagnostics.extend(_cycles(nodes))
        if nodes:
            node_for_event = {
                event.event_id: event.node_id for event in events if event.node_id is not None
            }
            for index, event in enumerate(events):
                if event.parent_id is None or event.node_id is None:
                    continue
                target_node = node_for_event.get(event.parent_id)
                parent = next((node for node in nodes if node.node_id == event.node_id), None)
                if (
                    target_node is not None
                    and parent is not None
                    and parent.parent_node_id not in {None, target_node}
                ):
                    diagnostics.append(
                        _error(
                            DiagnosticCode.CONFLICTING_RELATIONSHIP,
                            f"/events/{index}/parent_id",
                            "event parent conflicts with authoritative parent_node_id",
                        )
                    )
        previous = -1
        for index, event in enumerate(events):
            if event.sequence_index < previous:
                diagnostics.append(
                    _error(
                        DiagnosticCode.OUT_OF_ORDER_EVENTS,
                        f"/events/{index}/sequence_index",
                        "sequence_index values must not decrease",
                    )
                )
            previous = event.sequence_index
        return tuple(diagnostics)


def _raw(item: Mapping[str, object], known: set[str]) -> tuple[tuple[str, object], ...]:
    return tuple((key, value) for key, value in item.items() if key not in known)


def _unique_ids(values: Iterable[str], path: str, diagnostics: list[Diagnostic]) -> set[str]:
    result: set[str] = set()
    for index, value in enumerate(values):
        if value in result:
            diagnostics.append(
                _error(
                    DiagnosticCode.DUPLICATE_IDENTIFIER,
                    f"{path}/{index}",
                    "identifiers must be unique",
                )
            )
        result.add(value)
    return result


def _cycles(nodes: list[V2Node]) -> tuple[Diagnostic, ...]:
    parents = {node.node_id: node.parent_node_id for node in nodes}
    diagnostics: list[Diagnostic] = []
    for node in nodes:
        path: list[str] = []
        current: str | None = node.node_id
        while current is not None:
            if current in path:
                start = path.index(current)
                cycle = [*path[start:], current]
                diagnostics.append(
                    _error(
                        DiagnosticCode.PARENT_CYCLE,
                        f"/nodes/{node.node_id}/parent_node_id",
                        f"parent cycle: {' -> '.join(cycle)}",
                    )
                )
                break
            path.append(current)
            current = parents.get(current)
    return tuple(diagnostics)


def _required_string(
    item: Mapping[str, object], name: str, path: str, diagnostics: list[Diagnostic]
) -> str | None:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        diagnostics.append(
            _error(
                DiagnosticCode.MISSING_REQUIRED_FIELD,
                f"{path}/{name}",
                f"{name} is required and must be a non-empty string",
            )
        )
        return None
    return value


def _optional_string(
    item: Mapping[str, object], name: str, path: str, diagnostics: list[Diagnostic]
) -> str | None:
    value = item.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(_type_error(f"{path}/{name}", f"{name} must be a string or null"))
        return None
    return value


def _nonnegative_int(
    item: Mapping[str, object], name: str, path: str, diagnostics: list[Diagnostic]
) -> int:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        diagnostics.append(
            _error(
                DiagnosticCode.MISSING_REQUIRED_FIELD,
                f"{path}/{name}",
                f"{name} is required and must be a non-negative integer",
            )
        )
        return 0
    if value < 0:
        diagnostics.append(
            _error(
                DiagnosticCode.INVALID_FIELD_TYPE, f"{path}/{name}", f"{name} must be non-negative"
            )
        )
    return value


def _optional_nonnegative(
    item: Mapping[str, object], name: str, path: str, diagnostics: list[Diagnostic]
) -> int | None:
    value = item.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        diagnostics.append(
            _error(
                DiagnosticCode.INVALID_RETRY_METADATA,
                f"{path}/{name}",
                f"{name} must be a non-negative integer or null",
            )
        )
        return None
    return value


def _optional_enum(
    item: Mapping[str, object],
    name: str,
    enum_type: type[StrEnum],
    path: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    value = item.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(_type_error(f"{path}/{name}", f"{name} must be a string or null"))
        return None
    values = {member.value for member in enum_type}
    if value not in values:
        diagnostics.append(
            _warning(
                DiagnosticCode.INVALID_ENUM_VALUE,
                f"{path}/{name}",
                f"unknown {name} preserved as opaque value",
            )
        )
    return value


def _optional_timestamp(
    item: Mapping[str, object], name: str, path: str, diagnostics: list[Diagnostic]
) -> datetime | None:
    value = item.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(
            _error(
                DiagnosticCode.INVALID_TIMESTAMP,
                f"{path}/{name}",
                "timestamp must be a string or null",
            )
        )
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        diagnostics.append(
            _error(
                DiagnosticCode.INVALID_TIMESTAMP,
                f"{path}/{name}",
                "timestamp must be valid ISO-8601",
            )
        )
        return None
    if parsed.tzinfo is None:
        diagnostics.append(
            _error(
                DiagnosticCode.INVALID_TIMESTAMP,
                f"{path}/{name}",
                "timestamp must include an explicit timezone offset",
            )
        )
        return None
    return parsed.astimezone(UTC)


def _attributes(
    value: object, path: str, diagnostics: list[Diagnostic]
) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        diagnostics.append(_type_error(path, "attributes must be an object of string values"))
        return ()
    result: list[tuple[str, str]] = []
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not key or not item:
            diagnostics.append(
                _type_error(path, "attributes must contain non-empty string keys and values")
            )
            continue
        result.append((key, item))
    return tuple(sorted(result))


def _string_array(value: object, path: str, diagnostics: list[Diagnostic]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        diagnostics.append(_type_error(path, "value must be an array of non-empty strings"))
        return []
    return list(value)


def _error(code: DiagnosticCode, path: str, message: str) -> Diagnostic:
    return Diagnostic(DiagnosticSeverity.ERROR, code, path, message)


def _warning(code: DiagnosticCode, path: str, message: str) -> Diagnostic:
    return Diagnostic(DiagnosticSeverity.WARNING, code, path, message)


def _type_error(path: str, message: str) -> Diagnostic:
    return _error(DiagnosticCode.INVALID_FIELD_TYPE, path, message)
