"""Input reading for the parser pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, TextIO, cast

from agent_postmortem.parsing.input import (
    RawInput,
    read_input_from_bytes,
    read_input_from_path,
    read_input_from_stdin,
    read_input_from_string,
)


def read_raw_input(source: str | bytes | Path | TextIO | BinaryIO | RawInput) -> RawInput:
    """Coerce supported local inputs into a raw text buffer."""

    if isinstance(source, RawInput):
        return source
    if isinstance(source, bytes):
        return read_input_from_bytes(source)
    if isinstance(source, Path):
        return read_input_from_path(source)
    if hasattr(source, "read"):
        return read_input_from_stdin(cast(TextIO | BinaryIO, source))
    return read_input_from_string(source)


def read_raw_input_from_stdin(stdin: TextIO | BinaryIO) -> RawInput:
    """Read parser input from stdin."""

    return read_input_from_stdin(stdin)
