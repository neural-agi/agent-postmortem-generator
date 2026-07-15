# Contributing to Agent Postmortem Generator

First off, thank you for considering contributing.

Agent Postmortem Generator aims to become reliable infrastructure for debugging AI agent systems. That means maintainability, determinism, and clean architecture matter just as much as adding new features.

Before opening an issue or pull request, please read this document.

---

# Philosophy

This project favors:

- Deterministic behavior
- Explicit validation
- Small, focused modules
- Strong typing
- Testability
- Clear documentation
- Evidence-based design

This project avoids:

- Hidden magic
- Silent error recovery
- Framework-specific assumptions
- Large monolithic modules
- Premature optimization
- Unnecessary abstractions

If a feature makes the architecture more complicated without providing significant value, it probably does not belong in the project.

---

# Repository Structure

```
src/
    agent_postmortem/
        parsing/
        validation/
        domain/
        normalization/
        analysis/
        postmortem/
        graph/
        renderers/

tests/
docs/
examples/
```

Please keep new code within the appropriate module.

---

# Before You Start

Please check existing:

- Issues
- Discussions
- Pull Requests

If you're planning a significant architectural change, open a discussion first.

Small bug fixes do not require prior discussion.

---

# Development Setup

Clone the repository.

```bash
git clone https://github.com/neural-agi/agent-postmortem-generator.git

cd agent-postmortem-generator
```

Create the development environment.

```bash
uv sync
```

Run the test suite.

```bash
uv run pytest
```

Run formatting.

```bash
uv run ruff format .
```

Run linting.

```bash
uv run ruff check .
```

Run type checking.

```bash
uv run mypy src
```

---

# Coding Standards

## Python

- Python 3.13+
- Strong typing
- Strict mypy
- Ruff formatting
- Small functions
- Clear names

---

## Architecture

Each module should have one responsibility.

Avoid:

- giant utility files
- circular imports
- mixed responsibilities
- deeply nested control flow

If you find yourself writing a file larger than roughly 250–300 lines, consider whether it should be split.

---

## Documentation

Public classes and functions should include useful docstrings.

Complex algorithms should explain **why**, not simply **what**.

Avoid redundant comments.

---

# Testing

Every new feature should include appropriate tests.

We currently use:

- Unit tests
- Integration tests
- Fixtures

New behavior should be deterministic.

Tests should never depend on:

- internet access
- randomness
- local machine configuration
- wall-clock timing

---

# Pull Requests

A good pull request should:

- have one clear purpose
- include tests when appropriate
- update documentation if needed
- pass formatting, linting, and type checking
- keep unrelated changes out

Please keep pull requests focused.

Small, reviewable PRs are preferred over very large ones.

---

# Commit Messages

Use Conventional Commits whenever possible.

Examples:

```
feat(parser): add JSON reader

fix(validation): detect duplicate node IDs

refactor(domain): split canonical trace model

test(parser): improve malformed trace coverage

docs(readme): update project roadmap
```

---

# Reporting Bugs

Please include:

- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant logs or trace files

If possible, attach a minimal reproducible example.

---

# Feature Requests

Feature requests are welcome.

Please explain:

- the problem you're solving
- why existing behavior is insufficient
- possible alternatives
- expected benefits

Features should align with the project's philosophy.

---

# Architectural Changes

Large architectural changes should reference the corresponding design documents in:

```
docs/roadmap/
```

If the proposed implementation significantly changes an existing design, explain the reasoning before submitting a pull request.

---

# Code of Conduct

By participating in this project, you agree to follow the project's Code of Conduct.

Please read:

```
CODE_OF_CONDUCT.md
```

---

# Questions

If you're unsure where something belongs, open a GitHub Discussion before writing a large amount of code.

It is much easier to review an idea than to review a thousand-line pull request.

---

Thank you for helping make Agent Postmortem Generator a reliable, deterministic, and maintainable tool for the AI engineering community.
