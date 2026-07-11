"""Canonical trace controlled vocabularies.

The controlled vocabularies stay intentionally small so the canonical schema
remains stable and easy to snapshot-test.
"""

from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    """Controlled vocabulary for canonical trace nodes."""

    UNKNOWN = "unknown"
    AGENT_STEP = "agent_step"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    SUB_AGENT_STEP = "sub_agent_step"
    MESSAGE = "message"
    STATE = "state"


class EventKind(StrEnum):
    """Controlled vocabulary for canonical trace events."""

    UNKNOWN = "unknown"
    START = "start"
    END = "end"
    LOG = "log"
    ERROR = "error"
    MESSAGE = "message"
    INPUT = "input"
    OUTPUT = "output"
    RETRY = "retry"
    CANCELLATION = "cancellation"


class EventSeverity(StrEnum):
    """Severity for canonical trace events."""

    UNKNOWN = "unknown"
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EvidenceType(StrEnum):
    """Controlled vocabulary for evidence records."""

    UNKNOWN = "unknown"
    INLINE_TEXT = "inline_text"
    INLINE_JSON = "inline_json"
    REFERENCE = "reference"


class ValidationIssueSeverity(StrEnum):
    """Severity for validation issues."""

    WARNING = "warning"
    ERROR = "error"
