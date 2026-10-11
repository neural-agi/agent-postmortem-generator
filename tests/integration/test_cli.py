from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
VALID = ROOT / "tests" / "fixtures" / "valid_minimal_trace.json"
MALFORMED = ROOT / "tests" / "fixtures" / "malformed.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "apg", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_and_analyze_use_configured_entry_point(tmp_path: Path) -> None:
    validated = _run("validate", str(VALID))
    assert validated.returncode == 0
    assert validated.stdout == "Valid trace: valid_minimal_trace.json\n"

    analyzed = _run("analyze", str(VALID), "--output-dir", str(tmp_path))
    assert analyzed.returncode == 0
    assert [path.name for path in sorted(tmp_path.iterdir())] == [
        "postmortem.json",
        "postmortem.md",
        "postmortem.mmd",
    ]


def test_cli_reports_validation_and_usage_failures(tmp_path: Path) -> None:
    malformed = _run("validate", str(MALFORMED))
    assert malformed.returncode == 4
    assert "invalid_json" in malformed.stderr

    missing = _run("analyze", str(tmp_path / "missing.json"))
    assert missing.returncode == 3
    assert "does not exist" in missing.stderr

    unsupported = _run("analyze", str(VALID), "--format", "pdf")
    assert unsupported.returncode == 2
    assert "unsupported format" in unsupported.stderr


def test_cli_does_not_overwrite_without_flag(tmp_path: Path) -> None:
    first = _run("analyze", str(VALID), "--output-dir", str(tmp_path))
    second = _run("analyze", str(VALID), "--output-dir", str(tmp_path))

    assert first.returncode == 0
    assert second.returncode == 6
    assert "already exists" in second.stderr


def test_v2_cli_generates_unknown_outcome_artifacts(tmp_path: Path) -> None:
    trace = tmp_path / "v2.json"
    trace.write_text(
        '{"document_id":"doc-v2","trace_version":"v2","run_id":"run-v2",'
        '"events":[{"event_id":"end","sequence_index":0,"kind":"end"}]}',
        encoding="utf-8",
    )
    output = tmp_path / "artifacts"

    validated = _run("validate", str(trace))
    analyzed = _run("analyze", str(trace), "--output-dir", str(output))

    assert validated.returncode == 0
    assert "Valid trace: v2.json" in validated.stdout
    assert analyzed.returncode == 0
    assert {path.name for path in output.iterdir()} == {
        "postmortem.json",
        "postmortem.md",
        "postmortem.mmd",
    }
    assert "unknown outcome" in (output / "postmortem.md").read_text(encoding="utf-8")
    assert "unknown_terminal_outcome" in analyzed.stderr
