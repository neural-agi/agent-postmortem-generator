# Agent Postmortem Generator

Agent Postmortem Generator produces deterministic, evidence-based postmortem artifacts from generic JSON execution traces. It makes failed AI-agent executions easier to inspect without heuristic inference or external services.

## MVP Scope

The implemented MVP accepts the repository's generic JSON trace contract and produces a validated canonical trace, structured analysis, an evidence-bound postmortem, a deterministic execution graph, and Markdown, JSON, and Mermaid files.

The MVP does not include framework adapters, batch processing, stdin input, PDF/HTML/SVG/PNG rendering, a web UI, network calls, LLM calls, or remote storage. Explicit cancellation, retry recovery, and competing-failure semantics are supported where represented by the v2 contract and downstream models. Timeout semantics, retry exhaustion inference, structured errors, and tool request/result correlation remain deferred.

## Architecture

```text
Generic JSON trace
    -> Parser and Validation
    -> Canonical Trace Model
    -> Normalization
    -> Analysis
    -> Postmortem Generation
    -> Graph Generation
    -> Rendering and Export
    -> Markdown / JSON / Mermaid artifacts
```

The CLI only validates command-line input, calls these stages, reports diagnostics, and selects output targets. It does not interpret trace semantics or duplicate pipeline logic.

## Installation

Requirements: Python 3.13 and `uv`.

```bash
uv sync
```

## Quick Start

The committed minimal fixture is `tests/fixtures/valid_minimal_trace.json`.

```bash
apg --help
apg --version
apg validate tests/fixtures/valid_minimal_trace.json
apg analyze tests/fixtures/valid_minimal_trace.json --output-dir output
```

The default `analyze` command writes `output/postmortem.md`, `output/postmortem.json`, and `output/postmortem.mmd`.

Select one format with `--format`:

```bash
apg analyze tests/fixtures/valid_minimal_trace.json --format markdown --output-dir output
apg analyze tests/fixtures/valid_minimal_trace.json --format json --output-dir output
apg analyze tests/fixtures/valid_minimal_trace.json --format mermaid --output-dir output
```

The default is `--format all`. Existing files are not replaced unless `--overwrite` is supplied:

```bash
apg analyze tests/fixtures/valid_minimal_trace.json --output-dir output --overwrite
```

Output directories are created when possible. The CLI prints a concise artifact summary to stdout and diagnostics or warnings to stderr.

## Exit Codes

| Code | Meaning |
| ---: | --- |
| 0 | Command succeeded |
| 2 | Usage error or unsupported option |
| 3 | Input path does not exist, is not a file, or is unreadable |
| 4 | Input could not be parsed or validated |
| 5 | Normalization, analysis, postmortem, or graph pipeline failure |
| 6 | Output planning or filesystem export failure |

Malformed JSON, invalid roots, missing required fields, duplicate IDs, broken references, and invalid event ordering are validation failures. Incomplete but valid traces may still produce artifacts with explicit analysis warnings.

## Generic JSON Input

The MVP input is an object containing `document_id`, `trace_version`, `run_id`, and an `events` array. Each event requires `event_id` and `sequence_index`; `timestamp` and `parent_id` are optional. Unknown root and event fields are preserved where supported.

```json
{
  "document_id": "doc-1",
  "trace_version": "v1",
  "run_id": "run-1",
  "events": [
    {
      "event_id": "event-1",
      "sequence_index": 0,
      "timestamp": "2026-07-11T10:30:00Z"
    }
  ]
}
```

The generic contract does not claim framework-specific event meanings. Do not add timeout, cancellation, retry, or causal semantics unless the current parser, normalizer, and analysis models represent them explicitly.

## Development

Run the complete test suite and quality gates from the repository root:

```bash
uv run pytest
uv run mypy src
uv run ruff check .
uv run ruff format --check .
uv build
git diff --check
```

Tests include unit, integration, fixture, deterministic serialization, CLI, and export coverage. Golden report fixtures are stored under `tests/golden/`; input fixtures are under `tests/fixtures/`.

## Current Status

| Part | Component | Status |
| ---: | --- | --- |
| 1 | Canonical Trace Model | Implemented |
| 2 | Parser and Validation Engine | Implemented |
| 3 | Normalization Engine | Implemented for the generic contract |
| 4 | Analysis Engine | Implemented for supported explicit evidence and relationships |
| 5 | Postmortem Generation | Implemented |
| 6 | Graph Generation | Implemented |
| 7 | Rendering and Export | Implemented for Markdown, JSON, and Mermaid |
| 8 | CLI and Developer UX | Implemented for generic JSON |

## Planned and Deferred

- Framework adapters for LangGraph, CrewAI, OpenAI Agents SDK, and AutoGen.
- More expressive generic trace semantics for timeout, retry exhaustion, structured errors, tool correlation, and parallel failures.
- PDF, HTML, SVG, and image export.
- Batch execution, stdin support, machine-readable CLI results, and web UI features.
- Performance, scalability, and multi-run comparison work.

## Design Principles

- Deterministic output over heuristic completion.
- Validation before semantic analysis.
- Immutable canonical and intermediate models.
- Evidence and provenance preserved through downstream stages.
- Framework-specific logic outside the core pipeline.
- No silent repair or fabricated causal relationships.
