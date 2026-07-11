"""Canonical trace outcome enums.

These enums capture only the run and node outcomes supported by the design.
"""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """Outcome for the overall execution run."""

    UNKNOWN = "unknown"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class NodeStatus(StrEnum):
    """Outcome for an execution node."""

    UNKNOWN = "unknown"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
