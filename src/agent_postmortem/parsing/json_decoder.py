"""JSON decoding for parser input."""

from __future__ import annotations

import json
from dataclasses import dataclass

from agent_postmortem.parsing.input import RawInput


@dataclass(frozen=True, slots=True)
class ParsedJsonDocument:
    """Parsed JSON tree with source metadata."""

    data: object
    raw_input: RawInput


def decode_json(raw_input: RawInput) -> ParsedJsonDocument:
    """Decode a raw input buffer into an in-memory JSON tree."""

    data = json.loads(raw_input.text)
    return ParsedJsonDocument(data=data, raw_input=raw_input)
