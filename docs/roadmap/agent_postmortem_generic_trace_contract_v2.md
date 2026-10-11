# Generic Trace Contract v2

Status: design proposal only. This document changes no runtime behavior.

## 1. Purpose and scope

This document specifies the proposed expanded generic JSON contract for the
generic MVP path:

```text
generic JSON -> parsing -> validation -> normalization -> canonical trace
             -> analysis -> postmortem/graph -> rendering/export
```

The contract is deliberately narrower than a framework adapter contract. It
represents explicit run, node, event, relationship, retry metadata, and
evidence facts. It never infers tool semantics, causality, retry exhaustion,
or success from labels, payload text, or event order.

The existing `trace_version: "v1"` input is a legacy contract and keeps its
current interpretation. This document proposes `trace_version: "v2"` for the
expanded semantic shape below.

## 2. Verified repository facts

The following facts were checked against the current source and tests:

- [`validation/engine.py`](../../src/agent_postmortem/validation/engine.py)
  currently requires `document_id`, `trace_version`, `run_id`, and `events`.
- Current v1 events require `event_id` and `sequence_index`; `timestamp` and
  `parent_id` are optional.
- [`validation/trace_document.py`](../../src/agent_postmortem/validation/trace_document.py)
  preserves unknown root and event fields as raw fields.
- [`normalization/engine.py`](../../src/agent_postmortem/normalization/engine.py)
  creates evidence for accepted source records and preserves provenance, but
  currently defaults generic run and node status to `UNKNOWN`.
- Current generic normalization does not yet promote generic run status, node
  status, node attributes, event severity, event payload, or source evidence
  references into their canonical fields.
- The canonical model can represent run and node status, node kind, parent
  links, retry metadata, event kind, severity, payload, timestamps, evidence,
  and provenance. It has no dedicated timeout status, structured error object,
  tool-call identity, or request/result relation.
- [`analysis/rules.py`](../../src/agent_postmortem/analysis/rules.py) derives
  retry edges from explicit node `series_id` and `attempt_index`; it does not
  infer retry exhaustion from the last failed attempt.
- The current analysis implementation has an `END`-based incomplete-trace
  rule. The v2 proposal below makes the intended precedence explicit; analysis
  changes are implementation work, not behavior changed by this document.
- Existing v1 fixtures and golden outputs are not modified by this proposal.

## 3. Versioning and dispatch

### 3.1 Version values

| `trace_version` | Meaning | Action |
| --- | --- | --- |
| `v1` | Existing legacy root/event contract | Dispatch to the existing v1 parser and validators. Do not assign new semantics to opaque fields. |
| `v2` | This expanded contract | Dispatch to the v2 typed structural and semantic validators. |
| missing | No declared contract | Reject before normalization. |
| any other value | Unsupported or future contract | Reject deterministically with an unsupported-version diagnostic. |

`trace_version` is already the current parser's document-format discriminator;
it is not an execution identifier. The existing `run_id` remains the run
identity. No separate discriminator is required.

The v2 parser must dispatch before interpreting optional fields. A v1
document must never acquire v2 meanings merely because it contains an opaque
field named `run`, `nodes`, or `evidence`.

### 3.2 Compatibility policy

- Existing v1 documents remain valid under the v1 path.
- V1 unknown fields remain opaque evidence and are not reinterpreted.
- V2 may reject inputs that would have been accepted as opaque v1 data.
- V2 is additive with respect to canonical facts, but it is a new public input
  version and is not a silent v1 extension.
- A future incompatible contract uses a new version value and a new dispatcher
  branch. It must not reinterpret v2 fields.
- No automatic migration is performed by parsing, validation, or
  normalization. A migration tool may be proposed separately.

## 4. V2 schema

### 4.1 Root object

| Field | Type | Required | Validation and mapping |
| --- | --- | --- | --- |
| `document_id` | non-empty string | yes | Maps to `CanonicalTraceDocument.document_id`. |
| `trace_version` | literal `"v2"` | yes | Selects the v2 parser and validators. |
| `run_id` | non-empty string | yes | Maps to `RunMetadata.run_id`. |
| `run` | object | no | Maps explicit run metadata; omitted fields remain unknown. |
| `nodes` | array of objects | no | Declares explicit canonical nodes. IDs must be unique. |
| `events` | array of objects | yes | Declares observed events. IDs must be unique. |
| `evidence` | array of objects | no | Declares source evidence records. IDs must be unique. |
| other fields | JSON values | no | Preserved as opaque source evidence; never interpreted by v2 core logic. |

If `nodes` is absent, v2 may use the same opaque one-node-per-event fallback
as legacy normalization. Such generated nodes have unknown kind/status and do
not create retry metadata. Explicit node semantics require `nodes`.

### 4.2 Run object

| Field | Type | Required | Mapping and rules |
| --- | --- | --- | --- |
| `status` | `unknown`, `success`, `failure`, `cancelled` | no | Maps to `RunMetadata.status`; omission means `UNKNOWN`. |
| `started_at` | timezone-aware ISO-8601 string or null | no | Maps to `RunMetadata.started_at`. |
| `ended_at` | timezone-aware ISO-8601 string or null | no | Maps to `RunMetadata.ended_at`; not earlier than `started_at`. |
| `source_format` | string or null | no | Maps to `RunMetadata.source_format`. |

An explicit `null` means no value was supplied. It is not the same as the
`unknown` status enum. Missing status and `status: "unknown"` both map to
`RunStatus.UNKNOWN`, but diagnostics preserve whether the field was absent or
explicitly unknown when that distinction is useful.

### 4.3 Node object

| Field | Type | Required | Mapping and rules |
| --- | --- | --- | --- |
| `node_id` | non-empty string | yes | Maps to `TraceNode.node_id`; unique document-wide. |
| `kind` | canonical node-kind string or unknown string | no | Recognized values map to `TraceNode.kind`; unknown strings remain opaque with a warning. |
| `status` | canonical node-status string | no | Maps to `TraceNode.status`; omission means `UNKNOWN`. |
| `sequence_index` | non-negative integer | yes | Maps to `TraceNode.sequence_index`. Duplicate values are allowed; ordering then uses the deterministic tie-break rules below. |
| `parent_node_id` | string or null | no | Must resolve to a declared node; cycles are v2 validation errors. |
| `series_id` | non-empty string or null | no | Required when `attempt_index` is present. |
| `attempt_index` | non-negative integer or null | no | Required with `series_id`; unique within that series. |
| `started_at` | timezone-aware ISO-8601 string or null | no | Maps to `TraceNode.started_at`. |
| `ended_at` | timezone-aware ISO-8601 string or null | no | Maps to `TraceNode.ended_at`; not earlier than `started_at`. |
| `attributes` | object with string keys and string values | no | Canonicalized by sorted `(key, value)` pairs and mapped to canonical node attributes. No semantic inference is performed. |

`series_id` and `attempt_index` are an atomic pair. A node with only one of
them is invalid. Attempt indices may be sparse; gaps produce a warning, not an
inferred missing attempt. Duplicate indices in one series are hard errors.
Indices in different series may repeat. A series may span parent branches, but
each attempt remains one declared node. Cross-series parent links are allowed
unless they form a cycle.

When `nodes` is present, `parent_node_id` is authoritative and is the sole
source of canonical parent-node relationships. Event-level parent fields do
not override or create a node relationship in this mode. A conflicting event
parent is preserved as source evidence and produces a deterministic conflict
diagnostic.

### 4.4 Event object

| Field | Type | Required | Mapping and rules |
| --- | --- | --- | --- |
| `event_id` | non-empty string | yes | Stable source identity; unique document-wide. |
| `sequence_index` | non-negative integer | yes | Maps to canonical event sequence. Duplicate values are allowed. Decreasing input order is invalid for v2. |
| `timestamp` | timezone-aware ISO-8601 string or null | no | Legacy fallback timestamp. |
| `created_at`, `started_at`, `ended_at`, `observed_at` | timezone-aware ISO-8601 string or null | no | Timestamp candidates, selected by fixed precedence. All supplied candidates remain source evidence. |
| `kind` | canonical event-kind string or unknown string | no | Recognized values map to `TraceEvent.kind`; unknown strings remain opaque with a warning. |
| `severity` | canonical severity string | no | Maps to `TraceEvent.severity`; omission means `UNKNOWN`. |
| `node_id` | string or null | no | Must resolve to `nodes.node_id` when `nodes` is present. |
| `parent_id` | string or null | no | Legacy event-parent field. It may create a canonical parent relationship only in the fallback one-node-per-event path, where the target event maps uniquely to a generated node. When explicit `nodes` is present, it never creates or overrides a node relationship. |
| `payload` | string or null | no | Maps to canonical string payload and remains evidence-bearing. It is never parsed as a status or error type. |
| `evidence_refs` | array of non-empty strings | no | Every ID must resolve in root `evidence`. |
| other fields | JSON values | no | Preserved as opaque event evidence. |

V2 does not define tool request/result identity, tool names, token counts,
structured errors, or response correlation. A tool failure is representable
only as an explicitly failed `tool_call` node or an explicit error event with
supporting evidence. Those facts require the corresponding canonical fields
to be mapped by the implementation.

If both parent fields are supplied and identify different parents, v2 reports a
conflict at the event field path and retains both source values. It does not
resolve the conflict using event order.

### 4.5 Evidence object

| Field | Type | Required | Mapping and rules |
| --- | --- | --- | --- |
| `evidence_id` | non-empty string | yes | Maps to `EvidenceRecord.evidence_id`; unique document-wide. |
| `evidence_type` | canonical evidence-type string | yes | Maps to `EvidenceRecord.evidence_type`. |
| `content_ref` | string or null | no | Reference only; v2 does not dereference it. |
| `content_summary` | string or null | no | Source-provided summary; no generated claim may exceed it. |

Source records, unknown fields, and timestamp candidates remain available as
generated evidence/provenance. V2 does not promise redaction.

## 5. Canonical mapping and implementation status

The table distinguishes the proposed contract from the current implementation.

| Input field | Type/validation | Canonical destination | Current implementation status | Required implementation work | Compatibility |
| --- | --- | --- | --- | --- | --- |
| root identity | strings, required | document/run identity | Implemented | None for v1; add v2 dispatch | V1 unchanged |
| `run.status` | enum | `RunMetadata.status` | Representable but not mapped | Promote only in v2 normalization | V1 remains unknown |
| run timestamps | aware datetimes | `RunMetadata.started_at/ended_at` | Representable but not mapped | Map and validate bounds | V1 fallback unchanged |
| node identity/order | string/integer | `TraceNode` | Representable but not mapped | Add explicit-node path | V1 fallback unchanged |
| node kind/status | canonical enum | `TraceNode.kind/status` | Representable but not mapped | Map recognized values | Unknown values remain opaque |
| parent node | string reference | `TraceNode.parent_node_id` | Representable but not mapped | Validate before normalization | V1 cycle behavior preserved |
| retry metadata | pair of string/integer | `TraceNode.series_id/attempt_index` | Representable but not mapped | Add v2 retry validation/mapping | No v1 reinterpretation |
| event kind | enum or opaque string | `TraceEvent.kind` | Implemented for recognized legacy raw kind | Extend typed v2 path and diagnostics | V1 behavior retained |
| event severity | enum | `TraceEvent.severity` | Representable but not mapped | Promote in v2 normalization | V1 defaults unknown |
| event payload | string | `TraceEvent.payload` | Representable but not mapped | Promote in v2 normalization | V1 raw evidence retained |
| event timestamp candidates | aware datetimes | selected `TraceEvent.timestamp` | Implemented precedence in normalization | Preserve every candidate explicitly | V1 fallback retained |
| source evidence refs | ID array | `TraceEvent.evidence_refs` | Representable but not mapped | Resolve v2 evidence records | V1 generated evidence retained |
| evidence records | typed objects | `EvidenceRecord` | Representable but not mapped | Parse, validate, preserve provenance | V1 generated evidence retained |
| structured error object | object | none | Requires canonical-model change | Deferred; use string payload/evidence | No v1 effect |
| tool request/result identity | identifiers/relations | none | Requires canonical-model change | Deferred | No v1 effect |
| timeout | status/event | none | Requires canonical-model change | Deferred | No v1 effect |

## 6. Determinism, timestamps, and ordering

### 6.1 Timestamp selection

For each event, the selected timestamp is the first valid candidate in this
order:

1. `created_at`
2. `started_at`
3. `ended_at`
4. `observed_at`
5. legacy `timestamp`

All valid candidates are parsed with timezone awareness and normalized to UTC.
Invalid candidates produce field-specific diagnostics. Multiple valid values
produce a conflict diagnostic when they differ. The selected value maps to the
canonical timestamp; every supplied candidate remains in source evidence and
provenance.

### 6.2 Stable ordering

Canonical timeline ordering is:

1. explicit sequence index,
2. normalized start timestamp,
3. normalized end timestamp,
4. stable canonical identifier.

Missing timestamps do not cause fabricated chronology. Equal keys use the
next key. Collection order is never derived from hash-map iteration.

Attributes are sorted by key and then value. Evidence is ordered by explicit
source collection order when present, then evidence ID. Diagnostics are
ordered by source path, sequence index, code, and stable identifier.

Timestamp order is never causal proof. Only explicit parent links, explicit
retry metadata, and supported analysis relationships may create causal or
retry edges.

## 7. Terminal and failure semantics

`END` means that an end event was observed. It does not mean success.

### 7.1 Decision table

| Evidence | Classification | Notes |
| --- | --- | --- |
| `run.status: success` with no incompatible explicit terminal evidence | `SUCCESSFUL_COMPLETION` | Recovered node failures are allowed. |
| `run.status: success` with a later successful retry | `SUCCESSFUL_COMPLETION` | Retain the failed attempt as recovered-failure evidence. |
| `run.status: success` with an unrecovered failed node | `SUCCESSFUL_COMPLETION` | Emit a conflict/recovery diagnostic; do not select the node as the run outcome. |
| `run.status: failure` | `EXPLICIT_FAILURE` | Missing fault evidence yields an insufficient-evidence diagnostic, not an invented cause. |
| `run.status: cancelled` | `CANCELLATION` | A prior explicit fault may support cancellation-after-fault. |
| `run.status: unknown` with no failed/cancelled node and observed `END` | `UNKNOWN_OUTCOME` | `END` is observed termination only. |
| `run.status: unknown` with a failed node | `UNKNOWN_OUTCOME` | Preserve failed-node evidence and emit a diagnostic; do not infer failed run. |
| `run.status: unknown` with a cancelled node/event | `UNKNOWN_OUTCOME` | Do not infer run-level cancellation. |
| No terminal marker and no explicit terminal status | `PARTIAL_TERMINATION` | Emit an incomplete-trace diagnostic. |
| `END` without explicit terminal status and with structural incompleteness | `STRUCTURALLY_INCOMPLETE` | Preserve the observed end event. |
| Incompatible explicit statuses/signals | Explicit run-status classification | Emit a conflict diagnostic; event order never resolves the contradiction. |
| Failed retry attempts without explicit terminal failure | `UNKNOWN_OUTCOME` | Never classify retry exhaustion from absence of another attempt. |
| Timeout-like payload without canonical timeout representation | Independently established outcome, otherwise `UNKNOWN_OUTCOME` | Do not classify timeout; preserve evidence and emit an unsupported-semantics diagnostic. |

The current analysis enum has no `UNKNOWN_OUTCOME` member. Adding that member
is a required Milestone 3 dependency, not an existing capability. Until that
change is implemented, v2 must not claim complete-but-unknown classification.
No timeout semantics are added by v2.

### 7.2 Failure selection

The analysis candidate precedence remains:

1. explicit upstream exception with direct propagation,
2. failed tool/task step with concrete error,
3. supported timeout,
4. cancellation caused by a prior fault,
5. missing output or invalid downstream state.

Only candidates supported by canonical evidence are eligible. V2 does not add
timeout support or structured exceptions. Equal-precedence candidates retain
timeline order and all genuinely ambiguous candidates.

## 8. Retry semantics

- `series_id` and `attempt_index` must appear together.
- `series_id` is a non-empty string.
- `attempt_index` is a non-negative integer.
- Attempt indices must be unique within a series.
- Sparse indices are valid but produce a warning.
- Duplicate indices are hard errors.
- A retry series is ordered by attempt index, then node timeline order, then
  node ID.
- A later attempt is recovery only when its node status is explicitly
  `success`.
- Retry exhaustion requires an explicit failed run or explicit terminal failed
  node. A final failed attempt alone is insufficient.
- A retry event is evidence of an observed retry event only. It does not create
  a retry relationship or assign series metadata by itself.
- Truncated or missing attempts remain incomplete and are not repaired.

## 9. Validation and diagnostics

### 9.1 V2 validation pipeline

The v2 pipeline is staged and shares orchestration with v1 without sharing v1
field interpretation:

1. **Version dispatch:** validate `trace_version`, then select the v1 or v2
   parser and validator path.
2. **V2 structural validation:** validate root shape, object shapes, required
   fields, scalar types, enum scalar types, and timestamp syntax.
3. **V2 semantic validation:** validate IDs, references, parent cycles, retry
   pairs and indices, sequence ordering, timestamp bounds, and explicit parent
   conflicts.
4. **Normalization:** construct the trusted canonical model from v2 input,
   preserving unknown fields and provenance. Normalization does not repeat
   validation or repair rejected relationships.

Shared small validators may be reused, but v1 and v2 field rules must remain
version-specific. V1 keeps its current parser and normalization behavior.

### 9.2 Hard errors

- missing or unsupported `trace_version`,
- missing required fields,
- wrong JSON types,
- duplicate document, node, event, or evidence IDs,
- unresolved node, event, or evidence references,
- parent cycles in v2,
- negative sequence or attempt indices,
- duplicate attempt index within a series,
- invalid timezone-aware timestamps,
- invalid timestamp bounds,
- decreasing event sequence order in v2.

### 9.3 Recoverable diagnostics

- missing optional timestamps,
- conflicting valid timestamp candidates,
- unknown enum strings of the correct scalar type,
- omitted optional status or kind,
- sparse retry indices,
- incomplete terminal state,
- genuinely incompatible terminal evidence.

Unknown enum strings are not the same as invalid JSON types. A string with no
canonical enum mapping is preserved as opaque evidence with a warning. A
number, object, or array where a string enum is required is a structural error.
Missing and explicit `unknown` remain distinguishable source facts even when
they map to the same canonical enum value.

For v2, parent-cycle detection occurs in semantic validation before
normalization. The validator reports the offending edge deterministically and
normalization never repairs it. V1 retains its existing behavior until a
separate compatibility change is approved.

## 10. Evidence, provenance, and privacy

- Root, node, event, evidence, and unknown fields are preserved as source
  evidence according to their source path.
- Canonical IDs remain stable source IDs where the canonical model permits;
  generated fallback IDs use the existing deterministic normalization scheme.
- Selected timestamps, raw timestamp candidates, explicit evidence references,
  and diagnostics retain source paths through provenance.
- Markdown exports contain report claims, evidence citations, and evidence
  summaries. They do not contain an unrestricted dump of every raw field.
- JSON exports contain the structured report and graph representations,
  including the evidence fields and evidence-reference IDs required by those
  structures. They are not an unrestricted raw-trace export.
- Mermaid exports contain graph labels and selected graph annotations only;
  they do not contain the raw trace or unrestricted evidence payloads.
- Export writes are atomic per file/export operation. The renderer does not
  promise transactional rollback across the complete artifact set.
- No v2 redaction, masking, encryption, or sensitive-data classification is
  guaranteed. Sensitive input may appear in JSON or cited summaries.
- Redaction policy and opt-in raw evidence export remain future work.

## 11. Acceptance matrix

The four support columns are intentionally independent.

| Scenario | Contract expresses? | Canonical represents? | Current normalization? | Current analysis without inference? | Expected result/diagnostics |
| --- | --- | --- | --- | --- | --- |
| Successful run | yes | yes | no for v2 status mapping | yes when explicit status is supplied canonically | `SUCCESSFUL_COMPLETION`; no conflict diagnostic |
| Failed node with explicit error evidence | yes | yes using failed node, error event, payload/evidence | no for v2 status/payload mapping | partially; failed node plus error event is supported | `UNKNOWN_OUTCOME` until run-status precedence is implemented; failed-node evidence and diagnostic retained |
| Retry recovery | yes with explicit nodes/metadata | yes | no for v2 retry mapping | yes once metadata is canonical | `SUCCESSFUL_COMPLETION` if run succeeds; recovered failure retained |
| Retry exhaustion | yes only with explicit terminal failure | yes | no for v2 retry mapping | partially; exhaustion must not be inferred | `EXPLICIT_FAILURE` only with explicit terminal failure; otherwise `UNKNOWN_OUTCOME` |
| Independent failures | yes | yes | partially through explicit parent/event data | yes for explicit failed nodes; candidate ambiguity is diagnosed | `UNKNOWN_OUTCOME` without explicit run failure; alternatives preserved deterministically |
| Incomplete trace | yes | yes | yes as unknown/partial fallback | yes as partial/incomplete according to available markers | `PARTIAL_TERMINATION` without `END`; `STRUCTURALLY_INCOMPLETE` when structural incompleteness is established |
| Unknown outcome | yes | yes | yes when status absent | no; requires Milestone 3 `UNKNOWN_OUTCOME` support | `UNKNOWN_OUTCOME`; insufficient-evidence diagnostic |
| Conflicting terminal signals | yes | yes | no complete conflict mapping | partially; current analysis needs conflict coverage | explicit run-status classification plus conflict diagnostic |
| Malformed JSON | yes as invalid input | no | no | no | deterministic parse failure |
| Invalid reference | yes as invalid input | no trusted document | parent event refs only currently | no | path-specific validation failure |
| Parent cycle | yes as invalid input | no trusted v2 document | v2 rejection is proposed; v1 behavior retained | no | deterministic cycle diagnostic |
| Missing/conflicting timestamps | yes | yes with one selected timestamp plus evidence | precedence implemented | yes with timestamp diagnostic | stable ordering and conflict/missing diagnostic |

## 12. Valid and invalid examples

### Valid v2 successful run

```json
{
  "document_id": "doc-2",
  "trace_version": "v2",
  "run_id": "run-2",
  "run": {"status": "success"},
  "nodes": [
    {"node_id": "agent-1", "kind": "agent_step", "status": "success", "sequence_index": 0}
  ],
  "events": [
    {"event_id": "event-1", "sequence_index": 0, "kind": "start", "node_id": "agent-1"},
    {"event_id": "event-2", "sequence_index": 1, "kind": "end", "node_id": "agent-1"}
  ]
}
```

### Valid v2 retry recovery

```json
{
  "document_id": "doc-retry",
  "trace_version": "v2",
  "run_id": "run-retry",
  "run": {"status": "success"},
  "nodes": [
    {"node_id": "attempt-0", "kind": "tool_call", "status": "failure", "sequence_index": 0, "series_id": "tool-series", "attempt_index": 0},
    {"node_id": "attempt-1", "kind": "tool_call", "status": "success", "sequence_index": 1, "series_id": "tool-series", "attempt_index": 1}
  ],
  "events": [
    {"event_id": "error-0", "sequence_index": 0, "kind": "error", "node_id": "attempt-0", "payload": "tool returned an error"},
    {"event_id": "retry-1", "sequence_index": 1, "kind": "retry", "node_id": "attempt-1"}
  ]
}
```

### Invalid v2 duplicate retry index

```json
{
  "document_id": "bad-retry",
  "trace_version": "v2",
  "run_id": "bad-retry",
  "nodes": [
    {"node_id": "a", "sequence_index": 0, "series_id": "s", "attempt_index": 0},
    {"node_id": "b", "sequence_index": 1, "series_id": "s", "attempt_index": 0}
  ],
  "events": []
}
```

Expected result: hard validation diagnostic for duplicate attempt index in
series `s`; no canonical document is passed to analysis.

### Invalid v2 parent cycle

```json
{
  "document_id": "bad-cycle",
  "trace_version": "v2",
  "run_id": "bad-cycle",
  "nodes": [
    {"node_id": "a", "sequence_index": 0, "parent_node_id": "b"},
    {"node_id": "b", "sequence_index": 1, "parent_node_id": "a"}
  ],
  "events": []
}
```

Expected result: hard deterministic parent-cycle diagnostic identifying the
offending relationship; no repair or normalization occurs.

## 13. Implementation dependency sequence

1. Approve this v2 contract and the remaining unresolved decisions.
2. Add version dispatch before v1/v2 field interpretation.
3. Add typed v2 parsing and structural validation without changing v1.
4. Add v2 semantic validation for references, cycles, retry metadata, status
   conflicts, timestamps, and ordering.
5. Map only explicit v2 fields in normalization; retain deterministic v1
   fallback behavior.
6. Add `UNKNOWN_OUTCOME` to the analysis enum and implement the terminal
   precedence table. This is a required Milestone 3 dependency, not an
   existing capability.
7. Add analysis tests for terminal precedence, recovered failures, incomplete
   retries, and conflicting signals.
8. Add postmortem and graph assertions for evidence, provenance, and explicit
   relationships.
9. Add CLI fixtures and documentation only after runtime behavior is verified.
10. Add stable golden artifacts after the v2 output contract is fixed.

## 14. Unresolved decisions

These are intentionally not hidden inside the schema proposal:

1. Whether complete node trees plus `END` may ever establish success without
   `run.status: success`.
2. Whether timeout should extend canonical `EventKind`, `RunStatus`, or both.
3. Whether structured errors require a canonical field beyond string payload.
4. Whether tool request/result identity belongs in the generic contract or an
   adapter-owned extension.
5. Whether sensitive evidence requires redaction, opt-in export, or a warning.
6. Whether multi-file export must be atomic as a set or only per file.

Until these decisions are resolved, v2 must not claim universal timeout,
structured tool-correlation, structured-error, or redaction support.

## 15. Changelog from the rejected v1 proposal

- Renamed the expanded proposal to v2; legacy v1 meaning is preserved.
- Added explicit version dispatch and future-version rejection behavior.
- Removed claims of structured tool request/result support.
- Defined retry metadata, ordering, recovery, exhaustion, sparse indices, and
  retry-event behavior.
- Made v2 parent cycles hard validation errors while documenting the retained
  v1 compatibility behavior.
- Added a current-versus-proposed canonical mapping table.
- Added terminal outcome precedence and explicitly separated `END` from
  success.
- Distinguished missing values, explicit unknown values, unknown enum strings,
  and invalid JSON types.
- Defined attribute, evidence, diagnostic, and timestamp ordering.
- Documented evidence retention and format-specific export exposure.
- Added independent four-question acceptance coverage.
- Added valid and invalid v2 JSON examples.
