<div align="center">

<br/>

# 🔍 Agent Postmortem Generator

### Turn failed AI agent traces into blameless, SRE-style incident reports.

<br/>

**A deterministic debugging tool for LangGraph, CrewAI, OpenAI Agents SDK, AutoGen, and generic JSON traces.**

<br/>

[![Status](https://img.shields.io/badge/status-early%20development-yellow?style=for-the-badge)](https://github.com/neural-agi/agent-postmortem-generator)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)
[![uv](https://img.shields.io/badge/package%20manager-uv-purple?style=for-the-badge)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/badge/lint-ruff-red?style=for-the-badge)](https://github.com/astral-sh/ruff)

<!-- TODO: Add CI badge once GitHub Actions is configured -->
<!-- TODO: Add test count badge once suite stabilizes -->

<br/>

**[🤔 Why This Exists](#-why-this-exists) · [✨ What Makes It Different](#-what-makes-it-different) · [🏗 Pipeline](#-pipeline-architecture) · [📄 Example Output](#-example-output) · [🚀 Quick Start](#-quick-start) · [🗺 Roadmap](#-roadmap)**

</div>

---

## 🤔 Why This Exists

Debugging AI agents is a mess.

A trace tells you **what happened** — but not always **why it failed**, **where the failure chain started**, or **what to fix next**. As agent systems get more complex, the debugging problem gets worse: nested calls, retries, tool failures, bad state transitions, malformed logs, and unclear root causes buried in a wall of JSON.

**Agent Postmortem Generator** converts failed execution traces into structured postmortems that explain:

| Section | What It Answers |
|---|---|
| Executive Summary | What happened, in plain language |
| Root Cause | The actual underlying failure, not just the symptom |
| Failure Chain | The sequence of events from trigger to failure |
| Patient Zero | Where the failure chain actually started |
| Timeline | Chronological reconstruction of the incident |
| Contributing Factors | Secondary conditions that made it worse |
| Suggested Fixes | Concrete, actionable remediation steps |
| Confidence Score | How certain the analysis is — no false precision |
| Visual Execution Graph | Mermaid diagram of the full execution path |
| Action Items | What to change before this happens again |

The goal is simple: **make multi-agent debugging dramatically easier.**

---

## ✨ What Makes It Different

Most tracing tools show you logs. This project aims to show you **incident analysis.**

|  | Typical Trace Viewers | Agent Postmortem Generator |
|---|---|---|
| **Output** | Raw logs / span trees | Structured incident report |
| **Root cause** | You infer it manually | Explicitly identified with confidence score |
| **Ambiguous input** | Best-effort guessing | Fails clearly — no invented meaning |
| **Framework coverage** | Usually single-framework | Framework-agnostic canonical model |
| **Analysis approach** | Heuristic pattern matching | Deterministic, evidence-based |
| **Failure explanation** | "Something went wrong here" | Failure chain from patient zero forward |

---

## 🏗 Pipeline Architecture

Every stage has exactly one job. No stage guesses on behalf of another.

```
Raw Trace
      │
      ▼
Parser & Validation
      │  rejects malformed input early, preserves diagnostics
      ▼
Canonical Trace Model
      │  one stable internal contract, framework-agnostic
      ▼
Normalization
      │  converts framework-specific traces into the canonical model
      ▼
Analysis Engine
      │  detects failure chains and meaningful relationships
      ▼
Postmortem Generator
      │  turns evidence into a readable incident report
      ▼
Renderers
      │  exports to Markdown, PDF, graphs, and diagrams
      ▼
Incident Report
```

> No guesswork. No hidden repair magic. No "maybe the model can infer it."

**Component breakdown:**

| Component | Role | Status |
|---|---|---|
| **Canonical Trace Model** | Immutable internal schema — the stable contract every other stage relies on | ✅ |
| **Parser & Validation Engine** | Structural + semantic validation, preserves unknown fields, stable diagnostic ordering | ✅ |
| **Normalization Engine** | Converts LangGraph / CrewAI / AutoGen / OpenAI traces into the canonical model | 🔜 |
| **Analysis Engine** | Failure chain detection, patient-zero identification, contributing factor analysis | 🔜 |
| **Postmortem Generator** | Evidence → structured incident report with confidence scoring | 🔜 |
| **Renderers** | Markdown, PDF, Mermaid graph, and interactive export | 🔜 |

---

## 📊 Current Status

### ✅ Completed

- Canonical Trace Model
- Parser & Validation Engine
- Repository scaffolding
- Tooling, tests, and documentation structure

### 📋 Planned Next

- Normalization Engine
- Analysis Engine
- Postmortem Generator
- Graph rendering and export
- CLI improvements
- Adapter support for multiple agent frameworks

---

## 💡 Core Philosophy

This project is built with a few strong opinions:

- **Determinism over heuristics** — the same trace always produces the same postmortem
- **Validation before analysis** — malformed input is rejected before it can corrupt downstream reasoning
- **Immutable internal models** — the canonical trace model never mutates once constructed
- **Framework-agnostic core** — framework-specific logic lives in adapters, never in the core
- **Small, testable modules** — each pipeline stage is independently verifiable
- **Evidence-based reporting** — every claim in a postmortem traces back to specific trace data
- **Local-first execution** — no external service required to generate a postmortem

> If the input is ambiguous, the system fails clearly instead of inventing meaning.

---

## 📄 Example Output

A postmortem may look something like this:

```markdown
# Incident Summary

**Patient Zero:** Tool call `search_docs` timed out.

**Failure Chain:** Timeout → retry loop → context overflow → planner hallucination

**Root Cause:** Missing timeout backoff policy

**Suggested Fixes:**
- Add bounded retries
- Enforce tool timeout budgets
- Reduce planner context growth
- Add trace-level validation for retry storms
```

No vague "an error occurred somewhere." A specific chain, a specific cause, specific fixes.

---

## 🎯 Supported Sources

| Source | Status |
|---|---|
| Generic JSON logs | ✅ MVP target |
| LangGraph | 📋 Planned |
| CrewAI | 📋 Planned |
| OpenAI Agents SDK | 📋 Planned |
| AutoGen | 📋 Planned |
| OpenTelemetry traces | 📋 Planned |

The MVP starts with generic JSON input, then expands outward through adapters — the canonical model stays the same regardless of source.

---

## 🚀 Quick Start

### Install

```bash
git clone https://github.com/neural-agi/agent-postmortem-generator.git
cd agent-postmortem-generator
uv sync
```

### Run Tests

```bash
uv run pytest
```

### Lint and Format

```bash
uv run ruff format .
uv run ruff check .
```

### Type Check

```bash
uv run mypy src
```

### Usage *(evolving)*

The CLI and full normalization pipeline are still under active development. The intended workflow:

```bash
apg analyze path/to/trace.json
```

Eventually, this will produce:

- A validated canonical trace
- A structured postmortem report
- A Mermaid execution graph
- Exportable Markdown/PDF artifacts

---

## 📁 Repository Structure

```
agent-postmortem-generator/
│
├── docs/
│   └── roadmap/                  # phased development roadmap
│
├── examples/                      # example traces and expected output
├── scripts/                       # dev tooling
│
├── src/
│   └── agent_postmortem/
│       ├── parsing/                # raw trace ingestion
│       ├── validation/             # structural + semantic validation
│       ├── domain/                 # canonical trace model
│       ├── normalization/          # framework-specific adapters
│       ├── analysis/               # failure chain + root cause detection
│       ├── postmortem/             # report generation
│       └── renderers/              # Markdown / PDF / Mermaid export
│
└── tests/                          # unit + integration test suite
```

---

## 🧪 Testing Philosophy

Tests are not decoration here. They are part of the contract.

| Test Type | Purpose |
|---|---|
| **Unit tests** | Model and validator behavior in isolation |
| **Integration tests** | End-to-end parsing and validation flow |
| **Fixtures** | Stable contracts — not just sample data, but pinned expected behavior |
| **Deterministic diagnostics** | Every validation failure reproduces identically on every run |

---

## 🗺 Roadmap

| Part | Focus | Status |
|---|---|---|
| 1 | Canonical Trace Model | ✅ Complete |
| 2 | Parser & Validation Engine | ✅ Complete |
| 3 | Normalization Engine | 📋 Planned |
| 4 | Analysis Engine | 📋 Planned |
| 5 | Postmortem Generator | 📋 Planned |
| 6 | Graph Generation | 📋 Planned |
| 7 | Renderers and Export | 📋 Planned |
| 8 | CLI and Developer UX | 📋 Planned |

**Later / exploratory:**
- VS Code extension
- GitHub Action
- OpenTelemetry ingestion
- Interactive graph viewer
- Drift detection integration
- More adapter support

---

## ⚠️ Design Principles — What This Project Avoids

This project intentionally avoids:

- Heuristic recovery from malformed input
- Silent input repair
- Mixed responsibilities within a single module
- Giant monolithic modules
- Framework-specific logic in the core

It emphasizes clean contracts, deterministic outputs, explicit validation, stable diagnostics, and easy-to-test behavior.

---

## 🤝 Contributing

Contributions are welcome, especially if they improve:

| Area | Why It Matters |
|---|---|
| **Parser correctness** | The foundation everything else depends on |
| **Validation quality** | Bad validation produces misleading postmortems downstream |
| **Deterministic analysis** | The core value proposition — this must never regress |
| **Adapter support** | Each new framework adapter expands real-world usability |
| **Tests and fixtures** | Tests are the contract here, not an afterthought |
| **Docs and examples** | Lowers the bar for the next contributor |

Before contributing, please read:
- **[CONTRIBUTING.md](CONTRIBUTING.md)**
- **[docs/roadmap/](docs/roadmap/)**
- **[SECURITY.md](SECURITY.md)**

The project is designed to stay strict, boring, and dependable — in the best possible way.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

<div align="center">

Built by [@neural-agi](https://github.com/neural-agi)

</div>
