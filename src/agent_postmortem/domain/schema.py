"""Canonical trace schema versioning.

Versioning is kept separate so the document contract can evolve without
changing the rest of the domain model.
"""

from __future__ import annotations

from enum import StrEnum


class CanonicalTraceSchemaVersion(StrEnum):
    """Version marker for the canonical trace schema."""

    V1 = "v1"
