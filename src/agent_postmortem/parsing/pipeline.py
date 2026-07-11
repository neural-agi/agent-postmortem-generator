"""Parser pipeline for generic JSON trace input."""

from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import BinaryIO, TextIO

from agent_postmortem.parsing.input import InputKind, InputMetadata, RawInput
from agent_postmortem.parsing.json_decoder import decode_json
from agent_postmortem.parsing.reader import read_raw_input
from agent_postmortem.parsing.result import ParseResult
from agent_postmortem.validation.diagnostics import Diagnostic, DiagnosticCode, DiagnosticSeverity


def parse_input(source: str | bytes | Path | TextIO | BinaryIO | RawInput) -> ParseResult:
    """Read and decode a supported input source."""

    try:
        raw_input = read_raw_input(source)
    except UnicodeDecodeError as exc:
        diagnostic = Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code=DiagnosticCode.INVALID_ENCODING,
            field_path="",
            message=str(exc),
        )
        return ParseResult(
            raw_input=RawInput(text="", metadata=_source_metadata(source)),
            document=None,
            diagnostics=(diagnostic,),
        )
    try:
        parsed = decode_json(raw_input)
    except JSONDecodeError as exc:
        diagnostic = Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code=DiagnosticCode.INVALID_JSON,
            field_path="",
            message=exc.msg,
            line=exc.lineno,
            column=exc.colno,
        )
        return ParseResult(raw_input=raw_input, document=None, diagnostics=(diagnostic,))
    return ParseResult(raw_input=raw_input, document=parsed, diagnostics=())


def _source_metadata(source: str | bytes | Path | TextIO | BinaryIO | RawInput) -> InputMetadata:
    if isinstance(source, RawInput):
        return source.metadata
    if isinstance(source, bytes):
        return InputMetadata(kind=InputKind.BYTES, source_name="<bytes>")
    if isinstance(source, Path):
        return InputMetadata(kind=InputKind.FILE_PATH, source_name=str(source))
    return InputMetadata(kind=InputKind.STRING, source_name="<string>")
