"""Input sources for the parser and validation engine.

The parser accepts local, in-memory inputs only. This module converts those
entry points into deterministic raw text plus source metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, TextIO


class InputKind(StrEnum):
    """Supported raw input kinds."""

    FILE_PATH = "file_path"
    STDIN = "stdin"
    STRING = "string"
    BYTES = "bytes"


@dataclass(frozen=True, slots=True)
class InputMetadata:
    """Source metadata attached to a raw input buffer."""

    kind: InputKind
    source_name: str


@dataclass(frozen=True, slots=True)
class RawInput:
    """Decoded text buffer plus stable source metadata."""

    text: str
    metadata: InputMetadata


def read_input_from_path(path: str | Path) -> RawInput:
    """Read UTF-8 trace input from a local file path."""

    resolved = Path(path)
    text = resolved.read_text(encoding="utf-8")
    return RawInput(
        text=text,
        metadata=InputMetadata(kind=InputKind.FILE_PATH, source_name=str(resolved)),
    )


def read_input_from_string(text: str) -> RawInput:
    """Wrap an in-memory string as raw parser input."""

    return RawInput(
        text=text,
        metadata=InputMetadata(kind=InputKind.STRING, source_name="<string>"),
    )


def read_input_from_bytes(data: bytes) -> RawInput:
    """Decode a byte buffer as UTF-8 parser input."""

    text = data.decode("utf-8")
    return RawInput(
        text=text,
        metadata=InputMetadata(kind=InputKind.BYTES, source_name="<bytes>"),
    )


def read_input_from_stdin(stdin: TextIO | BinaryIO) -> RawInput:
    """Read UTF-8 parser input from stdin."""

    raw = stdin.read()
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return RawInput(
        text=text,
        metadata=InputMetadata(kind=InputKind.STDIN, source_name="<stdin>"),
    )
