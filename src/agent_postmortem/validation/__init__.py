"""Validation helpers for canonical trace documents.

Cross-entity validation lives outside the domain package so the canonical
models remain focused on data definition and local invariants only.
"""

from agent_postmortem.validation.canonical_trace import validate_canonical_trace_document

__all__ = ["validate_canonical_trace_document"]
