"""Plan, render, and atomically write deterministic output artifacts."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from agent_postmortem.postmortem.markdown import render_markdown
from agent_postmortem.renderers.json_renderer import render_json
from agent_postmortem.renderers.mermaid import render_mermaid
from agent_postmortem.renderers.models import (
    ExportError,
    ExportPlan,
    ExportResult,
    OutputFormat,
    RenderedArtifact,
    ReportBundle,
)

_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_EXTENSIONS = {
    OutputFormat.MARKDOWN: (".md", "text/markdown; charset=utf-8"),
    OutputFormat.JSON: (".json", "application/json; charset=utf-8"),
    OutputFormat.MERMAID: (".mmd", "text/vnd.mermaid; charset=utf-8"),
}


def export_bundle(bundle: ReportBundle, plan: ExportPlan) -> ExportResult:
    """Render every requested artifact in memory, then write them atomically."""

    targets = _validate_plan(bundle, plan)
    rendered = tuple(_render(bundle, plan, target) for target in targets)
    temporary: list[tuple[Path, Path]] = []
    try:
        for artifact, content in rendered:
            temporary.append((_write_temp(artifact.path, content), artifact.path))
        for temporary_path, target_path in temporary:
            os.replace(temporary_path, target_path)
    except OSError as exc:
        for temporary_path, _ in temporary:
            temporary_path.unlink(missing_ok=True)
        raise ExportError(f"failed to write export artifact: {exc}") from exc
    return ExportResult(True, tuple(artifact for artifact, _ in rendered))


def _validate_plan(bundle: ReportBundle, plan: ExportPlan) -> tuple[OutputFormat, ...]:
    if not plan.targets or len(set(plan.targets)) != len(plan.targets):
        raise ExportError("targets must be a non-empty tuple of unique formats")
    if not _STEM.fullmatch(plan.filename_stem):
        raise ExportError("filename_stem contains unsupported characters")
    output_dir = plan.output_dir.resolve()
    if plan.allowed_base is not None:
        base = plan.allowed_base.resolve()
        if output_dir != base and base not in output_dir.parents:
            raise ExportError("output_dir is outside allowed_base")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        output_dir / f"{plan.filename_stem}{_EXTENSIONS[target][0]}" for target in plan.targets
    ]
    if not plan.overwrite:
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            raise ExportError(f"output already exists: {existing[0]}")
    if OutputFormat.MERMAID in plan.targets and bundle.graph is None:
        raise ExportError("Mermaid export requires a graph payload")
    return plan.targets


def _render(
    bundle: ReportBundle, plan: ExportPlan, target: OutputFormat
) -> tuple[RenderedArtifact, str]:
    if target is OutputFormat.MARKDOWN:
        content = render_markdown(bundle.report)
    elif target is OutputFormat.JSON:
        content = render_json(bundle)
    elif target is OutputFormat.MERMAID and bundle.graph is not None:
        content = render_mermaid(bundle.graph)
    else:
        raise ExportError(f"unsupported output target: {target!r}")
    path = plan.output_dir.resolve() / f"{plan.filename_stem}{_EXTENSIONS[target][0]}"
    encoded = content.encode("utf-8")
    return RenderedArtifact(
        target, path, len(encoded), hashlib.sha256(encoded).hexdigest(), _EXTENSIONS[target][1]
    ), content


def _write_temp(path: Path, content: str) -> Path:
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return Path(handle.name)
    except OSError as exc:
        raise ExportError(f"failed to stage export artifact {path}: {exc}") from exc
