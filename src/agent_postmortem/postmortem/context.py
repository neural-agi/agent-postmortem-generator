"""Build a narrow report context from Part 4 output and canonical evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from agent_postmortem.analysis import AnalysisResult
from agent_postmortem.domain import CanonicalTraceDocument, EvidenceRecord, TraceEvent
from agent_postmortem.postmortem.models import (
    ReportConfiguration,
    ReportMetadata,
)


@dataclass(frozen=True, slots=True)
class ReportContext:
    """Validated lookup indexes and source facts used by planning stages."""

    analysis: AnalysisResult
    trace: CanonicalTraceDocument
    configuration: ReportConfiguration
    metadata: ReportMetadata
    evidence_by_id: Mapping[str, EvidenceRecord]
    events_by_id: Mapping[str, TraceEvent]
    node_ids: frozenset[str]


def build_report_context(
    analysis: AnalysisResult,
    trace: CanonicalTraceDocument,
    configuration: ReportConfiguration,
) -> ReportContext:
    """Index canonical records and capture supported report metadata."""

    if analysis.run_id != trace.run.run_id:
        raise ValueError("analysis run_id does not match the canonical trace run_id")

    evidence: dict[str, EvidenceRecord] = {}
    for record in trace.evidence:
        if record.evidence_id in evidence:
            raise ValueError(f"duplicate canonical evidence id: {record.evidence_id!r}")
        evidence[record.evidence_id] = record

    events: dict[str, TraceEvent] = {}
    for event in trace.events:
        if event.event_id in events:
            raise ValueError(f"duplicate canonical event id: {event.event_id!r}")
        events[event.event_id] = event

    metadata = ReportMetadata(
        project_name="Agent Postmortem Generator",
        module_part="Part 5",
        generated_at=_utc(configuration.generated_at),
        trace_id=trace.document_id,
        run_id=analysis.run_id,
        analysis_version=None,
    )
    return ReportContext(
        analysis=analysis,
        trace=trace,
        configuration=configuration,
        metadata=metadata,
        evidence_by_id=MappingProxyType(evidence),
        events_by_id=MappingProxyType(events),
        node_ids=frozenset(node.node_id for node in trace.nodes),
    )


def _utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None
