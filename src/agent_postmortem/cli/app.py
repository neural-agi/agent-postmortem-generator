"""Thin command-line orchestration for the generic postmortem pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from typer import Context

from agent_postmortem.analysis import AnalysisEngine
from agent_postmortem.graph import GraphEngine
from agent_postmortem.normalization import NormalizationEngine
from agent_postmortem.postmortem import PostmortemEngine
from agent_postmortem.renderers import (
    ExportError,
    ExportPlan,
    OutputFormat,
    ReportBundle,
    export_bundle,
)
from agent_postmortem.validation import parse_and_validate_input
from agent_postmortem.validation.diagnostics import Diagnostic

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Generate deterministic postmortems from generic JSON execution traces.",
)

EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_VALIDATION = 4
EXIT_PIPELINE = 5
EXIT_OUTPUT = 6


@app.callback(invoke_without_command=True)
def _root(
    ctx: Context,
    version: Annotated[bool, typer.Option("--version", help="Show the CLI version.")] = False,
) -> None:
    """Run the Agent Postmortem Generator CLI."""

    if version:
        typer.echo("agent-postmortem-generator 0.1.0")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def validate(
    input_path: Annotated[Path, typer.Argument(help="Path to a generic JSON trace.")],
) -> None:
    """Parse and validate a generic JSON trace without writing artifacts."""

    path = _check_input(input_path)
    result = parse_and_validate_input(path)
    if not result.report.success:
        _print_diagnostics(result.report.diagnostics)
        raise typer.Exit(EXIT_VALIDATION)
    typer.echo(f"Valid trace: {path.name}")
    _print_warnings(result.report.diagnostics)


@app.command()
def analyze(
    input_path: Annotated[Path, typer.Argument(help="Path to a generic JSON trace.")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Directory for generated artifacts.")
    ] = Path("."),
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Artifact format: all, markdown, json, or mermaid.",
        ),
    ] = "all",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace existing artifacts.")
    ] = False,
) -> None:
    """Run the complete generic-trace pipeline and write artifacts."""

    path = _check_input(input_path)
    formats = _formats(output_format)
    if formats is None:
        typer.echo(f"Usage error: unsupported format '{output_format}'.", err=True)
        raise typer.Exit(EXIT_USAGE)
    try:
        result = parse_and_validate_input(path)
        if not result.report.success or (result.document is None and result.v2_document is None):
            _print_diagnostics(result.report.diagnostics)
            raise typer.Exit(EXIT_VALIDATION)
        validated = result.document if result.document is not None else result.v2_document
        if validated is None:
            raise typer.Exit(EXIT_VALIDATION)
        normalized = NormalizationEngine().normalize(validated)
        analysis = AnalysisEngine().analyze(normalized)
        generated = PostmortemEngine().generate(analysis, normalized.canonical_trace)
        graph = GraphEngine().generate(normalized.canonical_trace, analysis)
        exported = export_bundle(
            ReportBundle(generated.report, graph),
            ExportPlan(output_dir, formats, overwrite=overwrite),
        )
    except ExportError as exc:
        typer.echo(f"Output error: {exc}", err=True)
        raise typer.Exit(EXIT_OUTPUT) from exc
    except (OSError, ValueError) as exc:
        typer.echo(f"Pipeline error: {exc}", err=True)
        raise typer.Exit(EXIT_PIPELINE) from exc
    typer.echo(f"Generated {len(exported.artifacts)} artifact(s) in {output_dir.resolve()}")
    for artifact in exported.artifacts:
        typer.echo(f"- {artifact.path.name} ({artifact.bytes_written} bytes)")
    _print_warnings(result.report.diagnostics)
    for diagnostic in analysis.diagnostics:
        typer.echo(f"Warning: {diagnostic.code.value}: {diagnostic.message}", err=True)


def _check_input(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        typer.echo(f"Input error: input file does not exist: {path}", err=True)
        raise typer.Exit(EXIT_INPUT)
    if not resolved.is_file():
        typer.echo(f"Input error: input path is not a file: {path}", err=True)
        raise typer.Exit(EXIT_INPUT)
    try:
        with resolved.open("rb"):
            pass
    except OSError as exc:
        typer.echo(f"Input error: input file is not readable: {path}", err=True)
        raise typer.Exit(EXIT_INPUT) from exc
    return resolved


def _formats(value: str) -> tuple[OutputFormat, ...] | None:
    names = [item.strip().lower() for item in value.split(",") if item.strip()]
    if names == ["all"]:
        return (OutputFormat.MARKDOWN, OutputFormat.JSON, OutputFormat.MERMAID)
    mapping = {item.value: item for item in OutputFormat}
    if not names or any(name not in mapping for name in names) or len(set(names)) != len(names):
        return None
    return tuple(mapping[name] for name in names)


def _print_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        location = diagnostic.field_path or "<root>"
        typer.echo(
            f"Validation error [{diagnostic.code.value}] {location}: {diagnostic.message}",
            err=True,
        )


def _print_warnings(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        if diagnostic.severity.value == "warning":
            typer.echo(
                f"Warning [{diagnostic.code.value}] {diagnostic.field_path}: {diagnostic.message}",
                err=True,
            )
