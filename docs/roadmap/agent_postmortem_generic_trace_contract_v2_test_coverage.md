# Generic Trace Contract v2 Test Coverage

This matrix records the acceptance boundary for the implemented v2 pipeline. "Tested" means the behavior is exercised through validation, normalization, analysis, postmortem generation, graph generation, or the configured CLI entry point as identified below.

| Contract requirement | Coverage | Evidence |
| --- | --- | --- |
| Explicit successful completion | Implemented and tested | `v2_success.json`; CLI golden test |
| Explicit terminal failure and evidence | Implemented and tested | `v2_failure.json`; pipeline and export assertions |
| Explicit cancellation | Implemented and tested | `v2_cancelled.json`; analysis acceptance test |
| Unknown outcome with observed `END` | Implemented and tested | `v2_unknown_end.json`; unknown-outcome golden |
| Unknown outcome with failed node | Implemented and tested | `v2_unknown_failed_node.json`; analysis acceptance test |
| Recovered retry attempt | Implemented and tested | `v2_retry_recovery.json`; retry edge and golden assertions |
| Multiple competing failures | Implemented and tested | `v2_parallel_failures.json`; explicit-failure acceptance test |
| Conflicting terminal signals | Implemented and tested | `v2_conflicting_terminal.json`; diagnostic assertion |
| Broken reference rejection | Implemented and tested | `v2_invalid_reference.json`; validation-boundary test |
| Parent-cycle rejection | Implemented and tested | `v2_parent_cycle.json`; validation-boundary test |
| Unknown enum preservation | Implemented and tested | `v2_unknown_enum.json`; canonical unknown mapping and provenance assertion |
| Structurally incomplete execution | Implemented and tested | `v2_incomplete.json`; incomplete-outcome acceptance test |
| Deterministic Markdown, JSON, and Mermaid output | Implemented and tested | repeated-render test and four committed golden sets |
| Evidence references through report and export | Implemented and tested | failure pipeline and golden assertions |
| V1 compatibility | Implemented and tested | existing v1 regression and golden suite |
| Timeout semantics | Deferred by design | Contract deferral; no fixture or classification |
| Retry exhaustion inference | Deferred by design | No explicit exhaustion signal in the current contract |
| Structured error objects | Deferred by design | Current payload model remains opaque text |
| Tool request/result correlation | Deferred by design | No canonical identity pair is available |
| Sensitive-data redaction | Unsupported by current MVP | Exports may contain evidence summaries; no redaction guarantee |
| Multi-file transactional export | Deferred by design | Export atomicity is per file, not bundle-wide |

The acceptance tests intentionally do not mark deferred semantics as supported merely because future fields could be added to the contract.
