"""Map analysis conclusions into the fixed v1 report section plan."""

from __future__ import annotations

from dataclasses import dataclass

from agent_postmortem.analysis import AnalysisResult, EvidenceItem, FaultCandidate
from agent_postmortem.postmortem.context import ReportContext
from agent_postmortem.postmortem.models import SectionId


@dataclass(frozen=True, slots=True)
class PlannedFinding:
    """An upstream fault candidate placed without changing its order."""

    candidate: FaultCandidate
    order: int


@dataclass(frozen=True, slots=True)
class PlannedChainStep:
    """An explicit upstream causal edge and its directly linked evidence."""

    sequence: int
    cause_node_id: str
    effect_node_id: str
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True, slots=True)
class PlannedBlock:
    """Fixed-template narrative text and the upstream evidence it may cite."""

    text: str
    evidence: tuple[EvidenceItem, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """Facts assigned to one fixed section before narrative assembly."""

    section_id: SectionId
    findings: tuple[PlannedFinding, ...] = ()
    chain_steps: tuple[PlannedChainStep, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    blocks: tuple[PlannedBlock, ...] = ()


@dataclass(frozen=True, slots=True)
class ReportPlan:
    """Complete ordered report template populated only with upstream facts."""

    analysis: AnalysisResult
    sections: tuple[SectionPlan, ...]


def plan_sections(context: ReportContext) -> ReportPlan:
    """Select fixed section contents while preserving AnalysisResult order."""

    analysis = context.analysis
    ambiguity = any(item.code.value == "ambiguous_terminal" for item in analysis.diagnostics)
    partial = any(item.code.value == "incomplete_trace" for item in analysis.diagnostics)
    explicit_failure = analysis.terminal_outcome.value == "explicit_failure"
    summary: list[PlannedBlock] = []
    if analysis.terminal_outcome.value == "explicit_failure":
        summary.append(PlannedBlock("The analysis classified this run as an explicit failure."))
    elif analysis.terminal_outcome.value == "successful_completion":
        summary.append(PlannedBlock("The analysis classified this run as a successful completion."))
    else:
        summary.append(
            PlannedBlock(
                f"The analysis classified this run as "
                f"{analysis.terminal_outcome.value.replace('_', ' ')}."
            )
        )
    if partial:
        summary.append(
            PlannedBlock(
                "The failure is only partially observed in the available trace."
                if explicit_failure
                else "The terminal behavior is only partially observed in the available trace."
            )
        )
    if ambiguity:
        summary.append(PlannedBlock("Cause ambiguity remains unresolved in the analysis."))
    if analysis.first_fault is None:
        summary.append(PlannedBlock("The analysis did not identify a primary fault."))
    else:
        summary.append(
            PlannedBlock(
                "The analysis selected candidate "
                f"{analysis.first_fault.node_id}/{analysis.first_fault.event_id} "
                "as the primary fault.",
                analysis.first_fault.supporting_evidence,
            )
        )

    chain_steps: list[PlannedChainStep] = []
    path = analysis.failure_chain.ordered_node_ids
    for sequence, edge in enumerate(analysis.failure_chain.propagation_steps):
        if edge.from_node_id not in path or edge.to_node_id not in path:
            continue
        directly_supporting = tuple(item for item in analysis.evidence if item.relation == edge)
        chain_steps.append(
            PlannedChainStep(
                sequence=sequence,
                cause_node_id=edge.from_node_id,
                effect_node_id=edge.to_node_id,
                evidence=directly_supporting,
            )
        )

    candidates = (analysis.first_fault,) if analysis.first_fault is not None else ()
    primary_findings = tuple(
        PlannedFinding(candidate, order) for order, candidate in enumerate(candidates)
    )
    alternatives = tuple(
        PlannedFinding(candidate, order)
        for order, candidate in enumerate(analysis.alternative_candidates)
    )
    fixed = (
        SectionPlan(SectionId.EXECUTIVE_SUMMARY, blocks=tuple(summary)),
        SectionPlan(
            SectionId.FAILURE_CHAIN,
            chain_steps=tuple(chain_steps),
        ),
        SectionPlan(SectionId.PRIMARY_FAULT, findings=primary_findings),
        SectionPlan(SectionId.CONTRIBUTING_FACTORS, findings=alternatives),
        SectionPlan(SectionId.EVIDENCE, evidence=analysis.evidence),
        SectionPlan(SectionId.RECOMMENDED_FOLLOW_UPS),
    )
    return ReportPlan(analysis=analysis, sections=fixed)
