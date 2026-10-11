<h1 align="center">◈ Agent Postmortem Generator</h1>

<p align="center">
  <strong>From agent execution traces to evidence-backed postmortems.</strong>
  <br>
  Deterministic analysis. Reproducible artifacts. Zero LLM dependency.
</p>

---



---

## ◈ Overview

Agent Postmortem Generator (APG) transforms generic JSON execution traces into structured analysis, evidence-backed postmortems, and deterministic execution graphs.

Instead of asking an LLM to reconstruct what happened, APG analyzes the evidence already present in a trace. Unknown outcomes remain unknown. Findings stay grounded in recorded events.

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>01 / Analyze</h3>
      Validate traces, normalize execution data, and identify supported outcomes and retry relationships.
    </td>
    <td width="50%" valign="top">
      <h3>02 / Explain</h3>
      Generate postmortems that distinguish recorded evidence from conclusions the trace cannot establish.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>03 / Visualize</h3>
      Build deterministic execution graphs with Mermaid.
    </td>
    <td width="50%" valign="top">
      <h3>04 / Export</h3>
      Produce Markdown reports, machine-readable JSON, and Mermaid diagrams.
    </td>
  </tr>
</table>

## ⌁ Quick Start

**Requirements:** Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/neural-agi/agent-postmortem-generator.git
cd agent-postmortem-generator

uv sync

uv run apg --help
uv run apg --version
uv run apg validate tests/fixtures/valid_minimal_trace.json
uv run apg analyze tests/fixtures/valid_minimal_trace.json --output-dir output
```

<details>
  <summary><strong>Output formats</strong></summary>

  By default, APG generates all three artifacts:

  ```text
  output/
  ├── postmortem.md
  ├── postmortem.json
  └── postmortem.mmd
  ```

  Generate a specific format:

  ```bash
  uv run apg analyze tests/fixtures/valid_minimal_trace.json --format markdown --output-dir output
  uv run apg analyze tests/fixtures/valid_minimal_trace.json --format json --output-dir output
  uv run apg analyze tests/fixtures/valid_minimal_trace.json --format mermaid --output-dir output
  ```

  Existing output files are preserved unless `--overwrite` is supplied.

</details>

## ⌘ Architecture

<p align="center">
  <strong>TRACE IN → EVIDENCE THROUGHOUT → ARTIFACTS OUT</strong>
</p>

```text
┌──────────────────────────────┐
│       Generic JSON Trace     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│      Parsing & Validation    │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│   Canonical Trace + Evidence │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│    Normalization & Analysis  │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│   Postmortem + Graph Output  │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│     Markdown / JSON / Mermaid│
└──────────────────────────────┘
```

Each stage has a defined responsibility. The CLI handles arguments, invokes the pipeline, reports diagnostics, and selects output destinations. Trace interpretation remains in the underlying pipeline.

## ◉ Design Principles

- **Deterministic by design.** The same inputs produce reproducible analysis and artifacts.
- **Evidence over speculation.** Conclusions are constrained by the available trace.
- **Explicit uncertainty.** Missing evidence does not become an invented success or failure.
- **Local-first execution.** No LLM inference, network calls, or remote storage is required.
- **Versioned contracts.** Supports the generic V1 and V2 trace workflows.

## ▣ Input Contract

APG accepts generic JSON traces under the supported V1 and V2 contracts.

A minimal V1 example:

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

Validation covers applicable structural and semantic constraints, including reference integrity and event ordering. See `tests/fixtures/` for executable examples and `docs/roadmap/` for the V2 contract and test-coverage matrix.

## ⚠ Limitations

APG deliberately avoids inferring behavior that the trace cannot establish.

| Capability | Current status |
|---|---|
| V1 and V2 generic trace workflows | Supported |
| Deterministic analysis and postmortems | Supported |
| Markdown, JSON, and Mermaid exports | Supported |
| Framework-specific adapters | Not implemented |
| Batch processing and stdin input | Not implemented |
| Timeout classification | Deferred |
| Retry-exhaustion inference without explicit evidence | Deferred |
| Structured errors and tool request/result correlation | Deferred |
| Sensitive-data redaction | Not provided |
| PDF, HTML, SVG, PNG, or web UI | Not implemented |

Exports are atomic per file, not transactional across the complete artifact set.

## ⌘ Development

```bash
uv sync
uv run pytest
uv run mypy src
uv run ruff check .
uv run ruff format --check .
uv build
```

---

<p align="center">
  <strong>Make agent failures explainable. Keep the evidence intact.</strong>
  <br />
  <sub>Built for reproducible, evidence-driven debugging of AI agent execution.</sub>
</p>
