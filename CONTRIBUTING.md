# Contributing to Agent Postmortem Generator

Agent Postmortem Generator (APG) is an open-source, local-first tool for deterministic, evidence-based analysis of AI agent execution traces.

Contributions are welcome. The project's priorities are correctness, reproducibility, explicit boundaries, and maintainable architecture. A feature is not an improvement if it introduces unsupported inference or unnecessary complexity.

## Engineering Principles

Contributions should preserve these principles:

- **Determinism:** Equivalent inputs should produce reproducible analysis and artifacts.
- **Evidence over assumptions:** Findings must be supported by the trace. Missing evidence must not become an invented conclusion.
- **Explicit validation:** Invalid inputs and unsupported states should be handled deliberately, with useful diagnostics.
- **Clear boundaries:** Parsing, validation, normalization, analysis, postmortem generation, graph generation, rendering, and CLI orchestration have distinct responsibilities.
- **Strong typing:** Use the project's existing type system and avoid unnecessary untyped interfaces.
- **Testability:** New behavior must be verifiable through focused automated tests.
- **Minimal complexity:** Prefer small, cohesive changes over speculative abstractions or premature optimization.

Avoid hidden behavior, silent error recovery, duplicated pipeline logic, framework-specific assumptions in the generic trace pipeline, and abstractions without a demonstrated need.

## Before You Start

Before opening a pull request:

1. Check existing issues and pull requests for related work.
2. Review the relevant architecture and contract documentation under `docs/`.
3. Keep the change focused on one problem or feature.
4. For changes to trace semantics or architecture, explain the intended behavior and compatibility implications before expanding the implementation.

For changes involving the V2 generic trace contract, consult:

- `docs/roadmap/agent_postmortem_generic_trace_contract_v2.md`
- `docs/roadmap/agent_postmortem_generic_trace_contract_v2_test_coverage.md`

## Development Setup

### Requirements

- Python 3.13 or later
- [uv](https://docs.astral.sh/uv/)

### Clone and install

```bash
git clone https://github.com/neural-agi/agent-postmortem-generator.git
cd agent-postmortem-generator
uv sync
```

### Run the checks

Run the test suite and static checks before submitting changes:

```bash
uv run pytest
uv run mypy src
uv run ruff check .
uv run ruff format --check .
uv build
```

All checks should pass. If a check fails because of your changes, fix the underlying issue rather than suppressing it without justification.

## Architecture and Code Organization

APG follows a staged processing pipeline:

```text
Generic JSON Trace
        |
        v
Parsing and Validation
        |
        v
Canonical Trace Model
        |
        v
Normalization
        |
        v
Analysis
        |
        v
Postmortem Generation
        |
        v
Graph Generation
        |
        v
Rendering and Export
```

The CLI orchestrates this pipeline. It should not duplicate trace interpretation, analysis rules, or output-generation logic.

Place new code in the existing module responsible for that behavior. Avoid introducing new top-level abstractions or reorganizing modules unless the change has a clear architectural justification.

## Testing Requirements

Tests are part of the implementation, not an optional follow-up.

### Add or update tests when you:

- Introduce or modify trace validation rules.
- Change normalization or canonical-model behavior.
- Add analysis rules or alter outcome and retry semantics.
- Modify postmortem content, graph generation, or exported artifacts.
- Change CLI arguments, diagnostics, exit codes, or filesystem behavior.
- Fix a bug or address a previously uncovered edge case.

### Test expectations

- Test the intended behavior and relevant failure cases.
- Include boundary cases where they affect correctness.
- Keep tests deterministic and independent of network services.
- Preserve existing V1 behavior unless a change explicitly intends otherwise.
- For V2 contract changes, update the relevant fixtures, acceptance tests, and contract-to-test coverage documentation.
- Update golden outputs when output changes are intentional and justified. Do not regenerate them merely to make failing tests pass.

## Trace Compatibility

APG supports generic V1 and V2 trace workflows. Changes to shared pipeline components must account for both versions.

Do not silently change established V1 behavior while implementing V2 features. When a contract or semantic change is necessary:

1. Document the intended behavior.
2. Identify the compatibility impact.
3. Add or update tests for the affected versions.
4. Update the relevant contract and coverage documentation.

Analysis must distinguish known outcomes from unknown outcomes. Retry recovery, cancellation, and competing-failure semantics must follow the evidence and supported contract rather than unsupported inference.

## Error Handling and Diagnostics

Errors should be explicit, actionable, and consistent with existing behavior.

- Reject malformed or invalid traces at the appropriate stage.
- Preserve useful diagnostic context.
- Do not silently discard evidence or replace invalid data with invented defaults.
- Preserve the established CLI exit-code contract unless a deliberate, documented change is required.
- Test both the failure condition and its observable CLI behavior where applicable.

## Documentation

Update documentation when changes affect user-visible behavior, trace contracts, CLI usage, architecture, limitations, or development workflows.

Keep examples consistent with the implementation. Clearly distinguish supported behavior from planned or deferred capabilities.

## Pull Requests

A good pull request should:

- Describe the problem and the proposed change.
- Explain relevant design decisions and trade-offs.
- Include focused tests and any necessary fixture or documentation updates.
- Report the checks you ran.
- Identify compatibility implications or known limitations.

Keep changes reviewable. Avoid unrelated formatting changes, broad refactors, or generated-file churn that obscures the actual implementation.

## Commit Messages

Use clear, concise commit messages. Prefer Conventional Commit-style prefixes where appropriate:

```text
feat: add explicit terminal outcome handling
fix: reject invalid parent references
test: cover retry recovery edge cases
docs: update V2 trace contract
refactor: simplify normalization flow
```

The message should describe the change, not merely the file modified.

## Scope and Roadmap

APG prioritizes a reliable generic trace pipeline before adding broader integrations.

Framework adapters, batch processing, new rendering targets, remote services, and other deferred capabilities should not be introduced incidentally. Larger features should have a clear use case, defined scope, tests, and an architectural rationale.

## Final Checklist

Before submitting a pull request:

- [ ] The change has a clear, focused purpose.
- [ ] Existing behavior is preserved where required.
- [ ] Relevant tests have been added or updated.
- [ ] `uv run pytest` passes.
- [ ] `uv run mypy src` passes.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run ruff format --check .` passes.
- [ ] `uv build` succeeds.
- [ ] Documentation and fixtures are updated where necessary.
- [ ] No unrelated changes or accidental generated files are included.

Thank you for helping make APG more reliable, reproducible, and easier to maintain.
