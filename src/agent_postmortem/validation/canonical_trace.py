"""Structural validation for canonical trace documents.

Graph-wide checks live here rather than in domain models so the domain package
stays focused on immutable data definitions only.
"""

from __future__ import annotations

from agent_postmortem.domain.document import CanonicalTraceDocument


def validate_canonical_trace_document(document: CanonicalTraceDocument) -> None:
    """Validate cross-entity structural invariants for a canonical document."""

    _validate_unique_ids(document)
    _validate_parent_links(document)
    _validate_event_node_links(document)


def _validate_unique_ids(document: CanonicalTraceDocument) -> None:
    node_ids = {node.node_id for node in document.nodes}
    if len(node_ids) != len(document.nodes):
        msg = "node_id values must be unique within a document"
        raise ValueError(msg)

    event_ids = {event.event_id for event in document.events}
    if len(event_ids) != len(document.events):
        msg = "event_id values must be unique within a document"
        raise ValueError(msg)

    evidence_ids = {item.evidence_id for item in document.evidence}
    if len(evidence_ids) != len(document.evidence):
        msg = "evidence_id values must be unique within a document"
        raise ValueError(msg)

    issue_ids = {issue.issue_id for issue in document.issues}
    if len(issue_ids) != len(document.issues):
        msg = "issue_id values must be unique within a document"
        raise ValueError(msg)


def _validate_parent_links(document: CanonicalTraceDocument) -> None:
    node_ids = {node.node_id for node in document.nodes}
    for node in document.nodes:
        if node.parent_node_id is not None and node.parent_node_id not in node_ids:
            msg = f"node {node.node_id!r} references unknown parent_node_id {node.parent_node_id!r}"
            raise ValueError(msg)

    visiting: set[str] = set()
    visited: set[str] = set()
    parent_map = {node.node_id: node.parent_node_id for node in document.nodes}

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            msg = "cycles in parent relationships are not allowed"
            raise ValueError(msg)
        visiting.add(node_id)
        parent_id = parent_map[node_id]
        if parent_id is not None:
            visit(parent_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node in document.nodes:
        visit(node.node_id)


def _validate_event_node_links(document: CanonicalTraceDocument) -> None:
    node_ids = {node.node_id for node in document.nodes}
    for event in document.events:
        if event.node_id is not None and event.node_id not in node_ids:
            msg = f"event {event.event_id!r} references unknown node_id {event.node_id!r}"
            raise ValueError(msg)
