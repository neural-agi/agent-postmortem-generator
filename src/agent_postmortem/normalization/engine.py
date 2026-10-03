"""Deterministic conversion from validated generic traces to the canonical model."""

from __future__ import annotations

from collections.abc import Mapping
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
    TraceNode,
)
from agent_postmortem.domain import (
    TraceEvent as CanonicalEvent,
)
from agent_postmortem.normalization.helpers import (
    canonical_json,
    fingerprint,
    resolve_event_timestamp,
    stable_id,
)
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
from agent_postmortem.validation.trace_document import TraceEvent, ValidatedTraceDocument


class NormalizationEngine:
    """Normalize the Part 2 validated document into Part 1 canonical types."""

    def normalize(self, document: ValidatedTraceDocument) -> NormalizationResult:
        """Convert one validated input document into an immutable result."""

        root_ref = _provenance(
            document.envelope.run_id,
            document.source_metadata.source_name,
            "",
            ("run_id",),
        )
        indexed: list[tuple[int, TraceEvent, datetime | None, ProvenanceRef, str]] = []
        diagnostics: list[NormalizationDiagnostic] = []
        duplicate_count = 0
        seen: dict[str, tuple[str, int]] = {}
        timestamp_sources: dict[str, tuple[str | None, object]] = {}
        for source_index, event in enumerate(document.events):
            raw_record = _raw_event(event)
            serialized = canonical_json(raw_record)
            prior = seen.get(event.event_id)
            source_path = f"/events/{source_index}"
            source_ref = _provenance(
                event.event_id,
                document.source_metadata.source_name,
                source_path,
                ("events", str(source_index)),
            )
            if prior is not None:
                duplicate_count += 1
                identical = prior[0] == serialized
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=(
                            NormalizationCode.IDENTICAL_DUPLICATE
                            if identical
                            else NormalizationCode.CONFLICTING_DUPLICATE
                        ),
                        message=(
                            "identical duplicate record was deduplicated"
                            if identical
                            else "conflicting duplicate record was ignored; first record retained"
                        ),
                        affected_ids=(stable_id("evt", document.envelope.run_id, event.event_id),),
                        source_ref=source_ref,
                    )
                )
                continue
            seen[event.event_id] = (serialized, source_index)
            (
                normalized_timestamp,
                timestamp_field,
                raw_timestamp,
                invalid_timestamp_fields,
                conflicting_timestamp_fields,
            ) = resolve_event_timestamp(event)
            timestamp_sources[event.event_id] = (timestamp_field, raw_timestamp)
            if invalid_timestamp_fields:
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.INVALID_TIMESTAMP_CANDIDATE,
                        message=(
                            "invalid timestamp candidates were ignored: "
                            + ", ".join(invalid_timestamp_fields)
                        ),
                        affected_ids=(stable_id("evt", document.envelope.run_id, event.event_id),),
                        source_ref=source_ref,
                    )
                )
            if conflicting_timestamp_fields:
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.CONFLICTING_TIMESTAMPS,
                        message=(f"timestamp candidates disagree; {timestamp_field} was selected"),
                        affected_ids=(stable_id("evt", document.envelope.run_id, event.event_id),),
                        source_ref=source_ref,
                    )
                )
            indexed.append(
                (
                    source_index,
                    event,
                    normalized_timestamp,
                    source_ref,
                    serialized,
                )
            )

        canonical_ids = {
            event.event_id: stable_id("node", document.envelope.run_id, event.event_id)
            for _, event, _, _, _ in indexed
        }
        accepted_parents: dict[str, str] = {}
        relations: list[CanonicalRelation] = []
        dropped_edges = 0
        for _source_index, event, _, source_ref, _ in indexed:
            if event.parent_id is None:
                continue
            parent_node_id = canonical_ids.get(event.parent_id)
            child_node_id = canonical_ids[event.event_id]
            if parent_node_id is None:
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.MISSING_PARENT,
                        message="explicit parent reference does not resolve; relationship omitted",
                        affected_ids=(child_node_id,),
                        source_ref=source_ref,
                    )
                )
                continue
            if _closes_cycle(child_node_id, parent_node_id, accepted_parents):
                dropped_edges += 1
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.CYCLE_EDGE_DROPPED,
                        message="later source-order parent edge was dropped to break a cycle",
                        affected_ids=(child_node_id, parent_node_id),
                        source_ref=source_ref,
                    )
                )
                continue
            accepted_parents[child_node_id] = parent_node_id
            relations.append(
                CanonicalRelation(
                    relation_type=RelationType.PARENT,
                    from_id=child_node_id,
                    to_id=parent_node_id,
                    source_ref=source_ref,
                )
            )

        ordered = sorted(indexed, key=_ordering_key)
        nodes: list[TraceNode] = []
        events: list[CanonicalEvent] = []
        evidence: list[EvidenceRecord] = []
        provenance_index: list[ProvenanceEntry] = []
        opaque_count = 0
        all_timestamps: list[datetime] = []
        for source_index, event, timestamp, source_ref, serialized in ordered:
            canonical_node_id = canonical_ids[event.event_id]
            if timestamp is not None:
                all_timestamps.append(timestamp)
            elif event.timestamp is None:
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.MISSING_TIMESTAMP,
                        message="timestamp is absent; source sequence is retained as fallback",
                        affected_ids=(canonical_node_id,),
                        source_ref=source_ref,
                    )
                )

            raw_fields = dict(event.raw_fields)
            raw_kind = raw_fields.get("kind")
            kind, unsupported_kind = _event_kind(raw_kind)
            if raw_kind is not None and unsupported_kind:
                opaque_count += 1
                diagnostics.append(
                    NormalizationDiagnostic(
                        severity=NormalizationSeverity.WARNING,
                        code=NormalizationCode.UNKNOWN_RECORD_KIND,
                        message="unrecognized record kind was retained as opaque evidence",
                        affected_ids=(stable_id("evt", document.envelope.run_id, event.event_id),),
                        source_ref=source_ref,
                    )
                )

            evidence_id = stable_id("evidence", document.envelope.run_id, event.event_id)
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    evidence_type=EvidenceType.INLINE_JSON,
                    content_summary=serialized,
                    provenance=source_ref,
                )
            )
            nodes.append(
                TraceNode(
                    node_id=canonical_node_id,
                    kind=NodeKind.UNKNOWN,
                    sequence_index=event.sequence_index,
                    status=NodeStatus.UNKNOWN,
                    parent_node_id=accepted_parents.get(canonical_node_id),
                    started_at=timestamp,
                    provenance=source_ref,
                )
            )
            events.append(
                CanonicalEvent(
                    event_id=stable_id("evt", document.envelope.run_id, event.event_id),
                    sequence_index=event.sequence_index,
                    kind=kind,
                    timestamp=timestamp,
                    node_id=canonical_node_id,
                    severity=EventSeverity.UNKNOWN,
                    provenance=source_ref,
                    evidence_refs=(evidence_id,),
                )
            )
            event_id = stable_id("evt", document.envelope.run_id, event.event_id)
            provenance_index.extend(
                (
                    _provenance_entry(
                        f"nodes/{canonical_node_id}/node_id",
                        event.event_id,
                        source_index,
                        "event_id",
                        event.event_id,
                    ),
                    _provenance_entry(
                        f"nodes/{canonical_node_id}/sequence_index",
                        event.event_id,
                        source_index,
                        "sequence_index",
                        event.sequence_index,
                    ),
                    _provenance_entry(
                        f"nodes/{canonical_node_id}/parent_node_id",
                        event.event_id,
                        source_index,
                        "parent_id",
                        event.parent_id,
                    ),
                    _provenance_entry(
                        f"events/{event_id}/event_id",
                        event.event_id,
                        source_index,
                        "event_id",
                        event.event_id,
                    ),
                    _provenance_entry(
                        f"events/{event_id}/kind",
                        event.event_id,
                        source_index,
                        "kind",
                        raw_kind,
                    ),
                    _provenance_entry(
                        f"events/{event_id}/timestamp",
                        event.event_id,
                        source_index,
                        timestamp_sources[event.event_id][0] or "timestamp",
                        timestamp_sources[event.event_id][1],
                    ),
                )
            )

        root_evidence = EvidenceRecord(
            evidence_id=stable_id("evidence", document.envelope.run_id, "root"),
            evidence_type=EvidenceType.INLINE_JSON,
            content_summary=canonical_json(
                {
                    "document_id": document.envelope.document_id,
                    "trace_version": document.envelope.trace_version,
                    "run_id": document.envelope.run_id,
                    "source_metadata": {
                        "kind": document.source_metadata.kind.value,
                        "source_name": document.source_metadata.source_name,
                    },
                    "fields": dict(document.raw_fields),
                }
            ),
            provenance=root_ref,
        )
        evidence.append(root_evidence)

        run_times = sorted(all_timestamps)
        canonical = CanonicalTraceDocument(
            document_id=document.envelope.document_id,
            schema_version=CanonicalTraceSchemaVersion.V1,
            run=RunMetadata(
                run_id=document.envelope.run_id,
                status=RunStatus.UNKNOWN,
                started_at=run_times[0] if run_times else None,
                ended_at=run_times[-1] if run_times else None,
                provenance=root_ref,
            ),
            nodes=tuple(nodes),
            events=tuple(events),
            evidence=tuple(evidence),
        )
        diagnostics.sort(key=_diagnostic_key)
        return NormalizationResult(
            normalization_schema_version="v1",
            canonical_trace=canonical,
            diagnostics=tuple(diagnostics),
            summary=NormalizationSummary(
                input_records=len(document.events),
                canonical_entities=len(nodes) + len(events),
                duplicates=duplicate_count,
                dropped_edges=dropped_edges,
                opaque_records=opaque_count,
            ),
            relations=tuple(relations),
            provenance_index=tuple(sorted(provenance_index, key=lambda item: item.canonical_field)),
        )


def _provenance(
    source_record_id: str,
    source_name: str,
    source_path: str,
    raw_key_path: tuple[str, ...],
) -> ProvenanceRef:
    return ProvenanceRef(
        source_record_id=source_record_id,
        source_path=source_path or None,
        source_file=source_name if not source_name.startswith("<") else None,
        raw_key_path=raw_key_path,
    )


def _raw_event(event: TraceEvent) -> dict[str, object]:
    record = dict(event.raw_fields)
    record["event_id"] = event.event_id
    record["sequence_index"] = event.sequence_index
    if event.timestamp is not None:
        record["timestamp"] = event.timestamp
    else:
        record.pop("timestamp", None)
    if event.parent_id is not None:
        record["parent_id"] = event.parent_id
    else:
        record.pop("parent_id", None)
    return record


def _event_kind(value: object) -> tuple[EventKind, bool]:
    if not isinstance(value, str):
        return EventKind.UNKNOWN, value is not None
    try:
        return EventKind(value), False
    except ValueError:
        return EventKind.UNKNOWN, True


def _ordering_key(
    item: tuple[int, TraceEvent, datetime | None, ProvenanceRef, str],
) -> tuple[bool, datetime, int, int]:
    source_index, event, timestamp, _, _ = item
    return (
        timestamp is None,
        timestamp or datetime.max.replace(tzinfo=UTC),
        source_index,
        event.sequence_index,
    )


def _closes_cycle(child_id: str, parent_id: str, parents: Mapping[str, str]) -> bool:
    current = parent_id
    visited: set[str] = set()
    while current not in visited:
        if current == child_id:
            return True
        visited.add(current)
        next_parent = parents.get(current)
        if next_parent is None:
            return False
        current = next_parent
    return False


def _diagnostic_key(item: NormalizationDiagnostic) -> tuple[str, str, tuple[str, ...], str]:
    source_path = item.source_ref.source_path if item.source_ref is not None else ""
    return source_path or "", item.code.value, item.affected_ids, item.message


def _provenance_entry(
    canonical_field: str,
    source_record_id: str,
    source_index: int,
    raw_field: str,
    raw_value: object,
) -> ProvenanceEntry:
    return ProvenanceEntry(
        canonical_field=canonical_field,
        source_record_id=source_record_id,
        source_path=f"/events/{source_index}/{raw_field}",
        raw_value_fingerprint=fingerprint(raw_value),
    )
