"""Normalization of trusted Generic Trace Contract v2 documents."""

from __future__ import annotations

from datetime import UTC, datetime

from agent_postmortem.domain import (
    CanonicalTraceDocument,
    CanonicalTraceSchemaVersion,
    EventKind,
    EventSeverity,
    EvidenceRecord,
    EvidenceType,
    NodeKind,
    NodeStatus,
    ProvenanceRef,
    RunMetadata,
    RunStatus,
    TraceEvent,
    TraceNode,
)
from agent_postmortem.normalization.helpers import canonical_json, fingerprint, stable_id
from agent_postmortem.normalization.models import (
    CanonicalRelation,
    NormalizationCode,
    NormalizationDiagnostic,
    NormalizationResult,
    NormalizationSeverity,
    NormalizationSummary,
    ProvenanceEntry,
    RelationType,
)
from agent_postmortem.validation.v2_document import (
    V2Event,
    V2ValidatedTraceDocument,
)


def normalize_v2(document: V2ValidatedTraceDocument) -> NormalizationResult:
    """Convert a validated v2 document without reparsing or inferring facts."""

    diagnostics: list[NormalizationDiagnostic] = []
    provenance_index: list[ProvenanceEntry] = []
    source_name = document.source_metadata.source_name
    root_ref = _provenance(document.run_id, source_name, "", ("run_id",))
    evidence: list[EvidenceRecord] = []
    evidence_ids: set[str] = set()

    for index, evidence_source in enumerate(document.evidence):
        source_ref = _provenance(
            evidence_source.evidence_id,
            source_name,
            f"/evidence/{index}",
            ("evidence", str(index)),
        )
        record = EvidenceRecord(
            evidence_id=evidence_source.evidence_id,
            evidence_type=_evidence_type(evidence_source.evidence_type),
            content_ref=evidence_source.content_ref,
            content_summary=evidence_source.content_summary
            or canonical_json(dict(evidence_source.raw_fields)),
            provenance=source_ref,
        )
        evidence.append(record)
        evidence_ids.add(record.evidence_id)
        provenance_index.append(
            _entry(
                f"evidence/{record.evidence_id}/evidence_id",
                evidence_source.evidence_id,
                index,
                "evidence_id",
                evidence_source.evidence_id,
                "evidence",
            )
        )

    explicit_nodes = bool(document.nodes)
    node_ids = {node.node_id for node in document.nodes}
    nodes: list[TraceNode] = []
    relations: list[CanonicalRelation] = []
    for index, node_source in enumerate(document.nodes):
        source_ref = _provenance(
            node_source.node_id,
            source_name,
            f"/nodes/{index}",
            ("nodes", str(index)),
        )
        nodes.append(
            TraceNode(
                node_id=node_source.node_id,
                kind=_node_kind(node_source.kind),
                sequence_index=node_source.sequence_index,
                status=_node_status(node_source.status),
                parent_node_id=node_source.parent_node_id,
                series_id=node_source.series_id,
                attempt_index=node_source.attempt_index,
                started_at=node_source.started_at,
                ended_at=node_source.ended_at,
                attributes=node_source.attributes,
                provenance=source_ref,
            )
        )
        provenance_index.extend(
            (
                _entry(
                    f"nodes/{node_source.node_id}/node_id",
                    node_source.node_id,
                    index,
                    "node_id",
                    node_source.node_id,
                    "nodes",
                ),
                _entry(
                    f"nodes/{node_source.node_id}/sequence_index",
                    node_source.node_id,
                    index,
                    "sequence_index",
                    node_source.sequence_index,
                    "nodes",
                ),
                _entry(
                    f"nodes/{node_source.node_id}/status",
                    node_source.node_id,
                    index,
                    "status",
                    node_source.status,
                    "nodes",
                ),
                _entry(
                    f"nodes/{node_source.node_id}/kind",
                    node_source.node_id,
                    index,
                    "kind",
                    node_source.kind,
                    "nodes",
                ),
            )
        )
        if node_source.parent_node_id is not None:
            relations.append(
                CanonicalRelation(
                    relation_type=RelationType.PARENT,
                    from_id=node_source.node_id,
                    to_id=node_source.parent_node_id,
                    source_ref=source_ref,
                )
            )

    events: list[TraceEvent] = []
    generated_count = 0
    for index, event_source in enumerate(document.events):
        source_ref = _provenance(
            event_source.event_id,
            source_name,
            f"/events/{index}",
            ("events", str(index)),
        )
        node_id = event_source.node_id
        if not explicit_nodes:
            node_id = stable_id("node", document.run_id, event_source.event_id)
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append(
                    TraceNode(
                        node_id=node_id,
                        kind=NodeKind.UNKNOWN,
                        sequence_index=event_source.sequence_index,
                        status=NodeStatus.UNKNOWN,
                        provenance=source_ref,
                    )
                )
                generated_count += 1
            if event_source.parent_id is not None:
                parent_node_id = stable_id("node", document.run_id, event_source.parent_id)
                relations.append(
                    CanonicalRelation(
                        relation_type=RelationType.PARENT,
                        from_id=node_id,
                        to_id=parent_node_id,
                        source_ref=source_ref,
                    )
                )
        event_evidence_id = stable_id("v2-event-evidence", document.run_id, event_source.event_id)
        if event_evidence_id in evidence_ids:
            diagnostics.append(
                NormalizationDiagnostic(
                    severity=NormalizationSeverity.ERROR,
                    code=NormalizationCode.CONFLICTING_DUPLICATE,
                    message="generated event evidence ID collides with source evidence ID",
                    affected_ids=(event_source.event_id, event_evidence_id),
                    source_ref=source_ref,
                )
            )
        else:
            evidence_ids.add(event_evidence_id)
            evidence.append(
                EvidenceRecord(
                    evidence_id=event_evidence_id,
                    evidence_type=EvidenceType.INLINE_JSON,
                    content_summary=canonical_json(_event_record(event_source)),
                    provenance=source_ref,
                )
            )
        refs = (*event_source.evidence_refs, event_evidence_id)
        events.append(
            TraceEvent(
                event_id=event_source.event_id,
                sequence_index=event_source.sequence_index,
                kind=_event_kind(event_source.kind),
                timestamp=event_source.timestamp,
                node_id=node_id,
                payload=event_source.payload,
                severity=_event_severity(event_source.severity),
                provenance=source_ref,
                evidence_refs=refs,
            )
        )
        provenance_index.extend(
            (
                _entry(
                    f"events/{event_source.event_id}/event_id",
                    event_source.event_id,
                    index,
                    "event_id",
                    event_source.event_id,
                    "events",
                ),
                _entry(
                    f"events/{event_source.event_id}/sequence_index",
                    event_source.event_id,
                    index,
                    "sequence_index",
                    event_source.sequence_index,
                    "events",
                ),
                _entry(
                    f"events/{event_source.event_id}/kind",
                    event_source.event_id,
                    index,
                    "kind",
                    event_source.kind,
                    "events",
                ),
                _entry(
                    f"events/{event_source.event_id}/timestamp",
                    event_source.event_id,
                    index,
                    "timestamp",
                    event_source.timestamp,
                    "events",
                ),
            )
        )

    root_evidence_id = stable_id("evidence", document.run_id, "root")
    evidence.append(
        EvidenceRecord(
            evidence_id=root_evidence_id,
            evidence_type=EvidenceType.INLINE_JSON,
            content_summary=canonical_json(
                {
                    "document_id": document.document_id,
                    "trace_version": document.trace_version,
                    "run_id": document.run_id,
                    "source_metadata": {
                        "kind": document.source_metadata.kind.value,
                        "source_name": document.source_metadata.source_name,
                    },
                    "fields": dict(document.raw_fields),
                }
            ),
            provenance=root_ref,
        )
    )
    run = document.run
    canonical = CanonicalTraceDocument(
        document_id=document.document_id,
        schema_version=CanonicalTraceSchemaVersion.V1,
        run=RunMetadata(
            run_id=document.run_id,
            status=_run_status(run.status if run is not None else None),
            source_format=run.source_format if run is not None else None,
            started_at=run.started_at if run is not None else None,
            ended_at=run.ended_at if run is not None else None,
            provenance=root_ref,
        ),
        nodes=tuple(sorted(nodes, key=lambda item: (item.sequence_index, item.node_id))),
        events=tuple(sorted(events, key=lambda item: (item.sequence_index, item.event_id))),
        evidence=tuple(evidence),
    )
    diagnostics.sort(key=_diagnostic_key)
    return NormalizationResult(
        normalization_schema_version="v2",
        canonical_trace=canonical,
        diagnostics=tuple(diagnostics),
        summary=NormalizationSummary(
            input_records=len(document.events),
            canonical_entities=len(nodes) + len(events),
            duplicates=0,
            dropped_edges=0,
            opaque_records=0,
        ),
        relations=tuple(
            sorted(relations, key=lambda item: (item.from_id, item.to_id, item.relation_type.value))
        ),
        provenance_index=tuple(sorted(provenance_index, key=lambda item: item.canonical_field)),
    )


def _event_record(event: V2Event) -> dict[str, object]:
    data: dict[str, object] = {
        "event_id": event.event_id,
        "sequence_index": event.sequence_index,
        "kind": event.kind,
        "severity": event.severity,
        "node_id": event.node_id,
        "parent_id": event.parent_id,
        "payload": event.payload,
        "evidence_refs": list(event.evidence_refs),
        "timestamp_candidates": [
            (name, value.astimezone(UTC).isoformat().replace("+00:00", "Z"))
            for name, value in event.timestamp_candidates
        ],
    }
    data.update(dict(event.raw_fields))
    return data


def _enum_value(value: str | None, allowed: type[object], fallback: object) -> object:
    if value is None:
        return fallback
    try:
        return allowed(value)  # type: ignore[call-arg]
    except ValueError:
        return fallback


def _run_status(value: str | None) -> RunStatus:
    return _enum_value(value, RunStatus, RunStatus.UNKNOWN)  # type: ignore[return-value]


def _node_kind(value: str | None) -> NodeKind:
    return _enum_value(value, NodeKind, NodeKind.UNKNOWN)  # type: ignore[return-value]


def _node_status(value: str | None) -> NodeStatus:
    return _enum_value(value, NodeStatus, NodeStatus.UNKNOWN)  # type: ignore[return-value]


def _event_kind(value: str | None) -> EventKind:
    return _enum_value(value, EventKind, EventKind.UNKNOWN)  # type: ignore[return-value]


def _event_severity(value: str | None) -> EventSeverity:
    return _enum_value(value, EventSeverity, EventSeverity.UNKNOWN)  # type: ignore[return-value]


def _evidence_type(value: str) -> EvidenceType:
    return _enum_value(value, EvidenceType, EvidenceType.UNKNOWN)  # type: ignore[return-value]


def _provenance(
    source_id: str, source_name: str, source_path: str, raw_key_path: tuple[str, ...]
) -> ProvenanceRef:
    return ProvenanceRef(
        source_record_id=source_id,
        source_path=source_path or None,
        source_file=source_name if not source_name.startswith("<") else None,
        raw_key_path=raw_key_path,
    )


def _entry(
    field: str, source_id: str, index: int, raw_field: str, value: object, collection: str
) -> ProvenanceEntry:
    if isinstance(value, datetime):
        value = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return ProvenanceEntry(
        canonical_field=field,
        source_record_id=source_id,
        source_path=f"/{collection}/{index}/{raw_field}",
        raw_value_fingerprint=fingerprint(value),
    )


def _diagnostic_key(item: NormalizationDiagnostic) -> tuple[str, str, tuple[str, ...], str]:
    source_path = item.source_ref.source_path if item.source_ref is not None else ""
    return source_path or "", item.code.value, item.affected_ids, item.message
