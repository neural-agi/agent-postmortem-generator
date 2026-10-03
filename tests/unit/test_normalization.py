from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

from agent_postmortem.domain import CanonicalTraceSchemaVersion, EventKind
from agent_postmortem.normalization import (
    NormalizationCode,
    NormalizationEngine,
)
from agent_postmortem.parsing.input import InputKind, InputMetadata
from agent_postmortem.validation.trace_document import (
    TraceEnvelope,
    TraceEvent,
    ValidatedTraceDocument,
)


def _document(*events: TraceEvent) -> ValidatedTraceDocument:
    return ValidatedTraceDocument(
        envelope=TraceEnvelope(document_id="doc", trace_version="v1", run_id="run"),
        events=events,
        raw_fields=(("source_note", {"z": 2, "a": 1}),),
        source_metadata=InputMetadata(kind=InputKind.STRING, source_name="<string>"),
        diagnostics=(),
    )


def test_normalization_is_deterministic_and_matches_canonical_contract() -> None:
    document = _document(
        TraceEvent(event_id="evt-a", sequence_index=0, timestamp="2026-10-03T12:00:00+02:00")
    )
    normalizer = NormalizationEngine()

    first = normalizer.normalize(document)
    second = normalizer.normalize(document)

    assert first == second
    assert first.canonical_trace.schema_version is CanonicalTraceSchemaVersion.V1
    assert first.canonical_trace.run.started_at.isoformat() == "2026-10-03T10:00:00+00:00"
    assert first.canonical_trace.events[0].kind is EventKind.UNKNOWN
    assert first.canonical_trace.events[0].evidence_refs
    assert first.canonical_trace.evidence[-1].content_summary is not None
    assert first.summary.canonical_entities == 2


def test_normalization_preserves_source_order_when_timestamps_are_missing() -> None:
    document = _document(
        TraceEvent(event_id="evt-b", sequence_index=1),
        TraceEvent(event_id="evt-a", sequence_index=0),
    )

    result = NormalizationEngine().normalize(document)

    assert [event.sequence_index for event in result.canonical_trace.events] == [1, 0]
    assert [item.code for item in result.diagnostics] == [
        NormalizationCode.MISSING_TIMESTAMP,
        NormalizationCode.MISSING_TIMESTAMP,
    ]
    assert result.canonical_trace.run.started_at is None
    assert result.canonical_trace.run.ended_at is None


def test_explicit_parent_becomes_a_canonical_relation() -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(event_id="child", sequence_index=0, parent_id="parent"),
            TraceEvent(event_id="parent", sequence_index=1),
        )
    )
    child = next(
        node
        for node in result.canonical_trace.nodes
        if node.provenance and node.provenance.source_record_id == "child"
    )

    assert child.parent_node_id == result.canonical_trace.nodes[1].node_id
    assert len(result.relations) == 1
    assert result.relations[0].from_id == child.node_id


def test_parent_cycle_drops_later_source_order_edge() -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(event_id="first", sequence_index=0, parent_id="second"),
            TraceEvent(event_id="second", sequence_index=1, parent_id="first"),
        )
    )

    assert len(result.relations) == 1
    assert result.summary.dropped_edges == 1
    assert [item.code for item in result.diagnostics].count(
        NormalizationCode.CYCLE_EDGE_DROPPED
    ) == 1
    assert result.canonical_trace.nodes[1].parent_node_id is None


def test_missing_parent_is_reported_without_inference() -> None:
    result = NormalizationEngine().normalize(
        _document(TraceEvent(event_id="child", sequence_index=0, parent_id="absent"))
    )

    assert result.canonical_trace.nodes[0].parent_node_id is None
    assert result.relations == ()
    assert result.diagnostics[0].code is NormalizationCode.MISSING_PARENT


def test_duplicates_keep_first_and_report_identical_or_conflicting_payloads() -> None:
    identical = TraceEvent(event_id="same", sequence_index=0)
    same_result = NormalizationEngine().normalize(_document(identical, identical))
    conflicting_result = NormalizationEngine().normalize(
        _document(identical, TraceEvent(event_id="same", sequence_index=1))
    )

    assert len(same_result.canonical_trace.events) == 1
    assert any(
        item.code is NormalizationCode.IDENTICAL_DUPLICATE for item in same_result.diagnostics
    )
    assert any(
        item.code is NormalizationCode.CONFLICTING_DUPLICATE
        for item in conflicting_result.diagnostics
    )
    assert conflicting_result.summary.duplicates == 1
    assert conflicting_result.canonical_trace.events[0].sequence_index == 0


def test_unknown_kind_is_kept_as_opaque_evidence_and_provenance_is_indexed() -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(
                event_id="opaque",
                sequence_index=0,
                raw_fields=(("kind", "future_step"), ("payload", {"x": [1, 2]})),
            )
        )
    )

    assert result.canonical_trace.events[0].kind is EventKind.UNKNOWN
    assert result.summary.opaque_records == 1
    assert any(item.code is NormalizationCode.UNKNOWN_RECORD_KIND for item in result.diagnostics)
    serialized_evidence = result.canonical_trace.evidence[0].content_summary
    assert serialized_evidence is not None
    assert '"payload":{"x":[1,2]}' in serialized_evidence
    assert {entry.canonical_field.rsplit("/", 1)[-1] for entry in result.provenance_index} >= {
        "event_id",
        "kind",
        "timestamp",
        "sequence_index",
        "parent_node_id",
    }


def test_normalization_outputs_are_frozen() -> None:
    result = NormalizationEngine().normalize(_document())

    with pytest.raises(FrozenInstanceError):
        result.summary.input_records = 4  # type: ignore[misc]


def test_empty_event_collection_produces_a_valid_empty_canonical_trace() -> None:
    result = NormalizationEngine().normalize(_document())

    assert result.canonical_trace.events == ()
    assert result.canonical_trace.nodes == ()
    assert result.summary.input_records == 0
    assert result.summary.canonical_entities == 0
    assert result.diagnostics == ()
    assert len(result.canonical_trace.evidence) == 1


def test_timestamp_sorting_is_stable() -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(event_id="later", sequence_index=0, timestamp="2026-10-03T12:02:00Z"),
            TraceEvent(event_id="earlier", sequence_index=1, timestamp="2026-10-03T12:01:00Z"),
        )
    )

    assert [node.provenance.source_record_id for node in result.canonical_trace.nodes] == [
        "earlier",
        "later",
    ]


def test_timestamp_precedence_uses_pdf_order_and_records_conflicts() -> None:
    raw_times = {
        "created_at": "2026-10-03T08:00:00Z",
        "started_at": "2026-10-03T08:01:00Z",
        "ended_at": "2026-10-03T08:02:00Z",
        "observed_at": "2026-10-03T08:03:00Z",
    }
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(
                event_id="timed",
                sequence_index=0,
                timestamp="2026-10-03T08:04:00Z",
                raw_fields=tuple(raw_times.items()),
            )
        )
    )

    assert result.canonical_trace.events[0].timestamp.isoformat() == "2026-10-03T08:00:00+00:00"
    assert any(item.code is NormalizationCode.CONFLICTING_TIMESTAMPS for item in result.diagnostics)
    event_id = result.canonical_trace.events[0].event_id
    time_entry = next(
        entry
        for entry in result.provenance_index
        if entry.canonical_field == f"events/{event_id}/timestamp"
    )
    assert time_entry.source_path == "/events/0/created_at"
    assert time_entry.raw_value_fingerprint == hashlib.sha256(b'"2026-10-03T08:00:00Z"').hexdigest()


def test_provenance_fingerprints_use_source_ids_and_source_kinds() -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(
                event_id="source-id",
                sequence_index=0,
                raw_fields=(("kind", "start"),),
            )
        )
    )
    canonical_event_id = result.canonical_trace.events[0].event_id
    id_entry = next(
        entry
        for entry in result.provenance_index
        if entry.canonical_field == f"events/{canonical_event_id}/event_id"
    )
    kind_entry = next(
        entry
        for entry in result.provenance_index
        if entry.canonical_field == f"events/{canonical_event_id}/kind"
    )

    assert id_entry.raw_value_fingerprint == hashlib.sha256(b'"source-id"').hexdigest()
    assert kind_entry.raw_value_fingerprint == hashlib.sha256(b'"start"').hexdigest()


@pytest.mark.parametrize("kind", tuple(EventKind))
def test_supported_event_kinds_are_classified_without_opaque_diagnostics(kind: EventKind) -> None:
    result = NormalizationEngine().normalize(
        _document(
            TraceEvent(
                event_id="event",
                sequence_index=0,
                raw_fields=(("kind", kind.value),),
            )
        )
    )

    assert result.canonical_trace.events[0].kind is kind
    assert result.summary.opaque_records == 0
    assert all(
        item.code is not NormalizationCode.UNKNOWN_RECORD_KIND for item in result.diagnostics
    )
