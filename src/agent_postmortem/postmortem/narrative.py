"""Assemble fixed, concise wording without interpreting analysis facts."""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.analysis import EvidenceItem
from agent_postmortem.postmortem.context import ReportContext
from agent_postmortem.postmortem.models import (
    ClaimSource,
    ReportMetadata,
    SectionId,
)
from agent_postmortem.postmortem.planner import PlannedFinding, ReportPlan, SectionPlan


@dataclass(frozen=True, slots=True)
class DraftBlock:
    text: str
    claim_source: ClaimSource
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True, slots=True)
class DraftFinding:
    finding_id: str
    section_id: SectionId
    title: str
    order: int
    description: str
    confidence: str | None
    status: str
    claim_source: ClaimSource
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True, slots=True)
class DraftStep:
    step_id: str
    sequence: int
    cause: str
    effect: str
    claim_source: ClaimSource
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True, slots=True)
class DraftSection:
    section_id: SectionId
    blocks: tuple[DraftBlock, ...]
    findings: tuple[DraftFinding, ...]
    chain_steps: tuple[DraftStep, ...]
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True, slots=True)
class NarrativeDraft:
    title: str
    metadata: ReportMetadata
    sections: tuple[DraftSection, ...]


_TITLES: dict[SectionId, str] = {
    SectionId.EXECUTIVE_SUMMARY: "Executive Summary",
    SectionId.FAILURE_CHAIN: "Failure Chain",
    SectionId.PRIMARY_FAULT: "Primary Fault",
    SectionId.CONTRIBUTING_FACTORS: "Contributing Factors",
    SectionId.EVIDENCE: "Evidence",
    SectionId.RECOMMENDED_FOLLOW_UPS: "Recommended Follow-ups",
}


def assemble_narrative(context: ReportContext, plan: ReportPlan) -> NarrativeDraft:
    """Apply reviewed wording patterns and explicit empty-section language."""

    sections = tuple(_assemble_section(section) for section in plan.sections)
    title = context.configuration.title or f"Postmortem for run {plan.analysis.run_id}"
    return NarrativeDraft(title=title, metadata=context.metadata, sections=sections)


def section_title(section_id: SectionId) -> str:
    """Return the fixed human-readable v1 section title."""

    return _TITLES[section_id]


def _assemble_section(section: SectionPlan) -> DraftSection:
    blocks = tuple(
        DraftBlock(block.text, ClaimSource.ANALYSIS_CONCLUSION, block.evidence)
        for block in section.blocks
    )
    findings = tuple(
        DraftFinding(
            finding_id=(f"candidate:{item.candidate.node_id}:{item.candidate.event_id}"),
            section_id=section.section_id,
            title=(
                "Primary fault candidate"
                if section.section_id is SectionId.PRIMARY_FAULT
                else f"Alternative fault candidate {item.order + 1}"
            ),
            order=item.order,
            description=_candidate_description(item),
            confidence=None,
            status=(
                "analysis_selected"
                if section.section_id is SectionId.PRIMARY_FAULT
                else "unresolved_alternative"
            ),
            claim_source=ClaimSource.ANALYSIS_CONCLUSION,
            evidence=item.candidate.supporting_evidence,
        )
        for item in section.findings
    )
    steps = tuple(
        DraftStep(
            step_id=f"chain:{item.sequence}:{item.cause_node_id}:{item.effect_node_id}",
            sequence=item.sequence,
            cause=item.cause_node_id,
            effect=item.effect_node_id,
            claim_source=ClaimSource.ANALYSIS_CONCLUSION,
            evidence=item.evidence,
        )
        for item in section.chain_steps
    )
    placeholders: tuple[str, ...] = ()
    if section.section_id is SectionId.FAILURE_CHAIN and not steps:
        placeholders = ("The analysis did not provide an ordered causal chain.",)
    elif section.section_id is SectionId.PRIMARY_FAULT and not findings:
        placeholders = ("A primary fault was not available from the analysis.",)
    elif section.section_id is SectionId.CONTRIBUTING_FACTORS and not findings:
        placeholders = ("The analysis provided no alternative fault candidates.",)
    elif section.section_id is SectionId.EVIDENCE and not section.evidence:
        placeholders = ("Canonical evidence was not available for this analysis.",)
    elif section.section_id is SectionId.RECOMMENDED_FOLLOW_UPS:
        placeholders = ("No recommended follow-ups were provided by the analysis.",)
    blocks = (*blocks, *(DraftBlock(text, ClaimSource.PLACEHOLDER, ()) for text in placeholders))
    return DraftSection(
        section_id=section.section_id,
        blocks=blocks,
        findings=findings,
        chain_steps=steps,
        evidence=section.evidence,
    )


def _candidate_description(item: PlannedFinding) -> str:
    candidate = item.candidate
    description = (
        f"The analysis retained {candidate.node_id}/{candidate.event_id} "
        f"for reason {candidate.reason.value}."
    )
    if candidate.retry_event_ids:
        retry_ids = ", ".join(candidate.retry_event_ids)
        description += f" Related retry event IDs: {retry_ids}."
    return description
