from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
import rox_dox.cli as cli
from rox_dox.rebuild import resolve_commit, run_rebuild

COMMIT = "a" * 40


class QueuedRunner:
    def __init__(self, results: list[subprocess.CompletedProcess[str]]) -> None:
        self.results = results
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return self.results.pop(0)


class RootFailureRunner:
    def __init__(self, commit: str) -> None:
        self.commit = commit
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, f"{self.commit}\n", "")
        if any("rox_core.py" in argument for argument in command):
            return subprocess.CompletedProcess(command, 1, "", "needle not found")
        if any("feature_map.py" in argument for argument in command):
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected command: {command}")


def _fixed_clock() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _project_root(path: Path) -> Path:
    (path / "pages" / "authoring").mkdir(parents=True)
    (path / "features").mkdir()
    return path


def test_resolve_commit_uses_explicit_commit_without_fetch(tmp_path: Path) -> None:
    runner = QueuedRunner([subprocess.CompletedProcess([], 0, f"{COMMIT}\n", "")])

    resolved = resolve_commit(
        tmp_path / "rox-core",
        "beef123",
        command_runner=runner,
    )

    assert resolved == COMMIT
    assert len(runner.commands) == 1
    assert runner.commands[0][3:5] == ["rev-parse", "--verify"]
    assert runner.commands[0][-1] == "beef123^{commit}"


def test_resolve_commit_fetches_origin_main_when_commit_is_omitted(
    tmp_path: Path,
) -> None:
    runner = QueuedRunner(
        [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, f"{COMMIT}\n", ""),
        ]
    )

    resolved = resolve_commit(
        tmp_path / "rox-core",
        None,
        command_runner=runner,
    )

    assert resolved == COMMIT
    assert runner.commands == [
        ["git", "-C", str(tmp_path / "rox-core"), "fetch", "origin", "main"],
        ["git", "-C", str(tmp_path / "rox-core"), "rev-parse", "origin/main"],
    ]


def test_cli_registers_rebuild_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_rebuild_mock = Mock(return_value=0)
    monkeypatch.setattr(cli, "run_rebuild", run_rebuild_mock)
    repo = tmp_path / "rox-core"
    output_dir = tmp_path / "site"

    exit_code = cli.main(
        [
            "rebuild",
            "--repo",
            str(repo),
            "--commit",
            COMMIT,
            "--out",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    arguments = run_rebuild_mock.call_args.kwargs
    assert arguments["repo"] == repo
    assert arguments["requested_commit"] == COMMIT
    assert arguments["output_dir"] == output_dir
    assert arguments["open_pr"] is False


def test_rebuild_skips_steps_depending_on_failed_root_page(
    tmp_path: Path,
) -> None:
    project_root = _project_root(tmp_path / "docs")
    output_dir = tmp_path / "site"
    runner = RootFailureRunner(COMMIT)

    exit_code = run_rebuild(
        repo=tmp_path / "rox-core",
        requested_commit=COMMIT,
        output_dir=output_dir,
        open_pr=False,
        project_root=project_root,
        command_runner=runner,
        clock=_fixed_clock,
        publisher=None,
    )

    report = json.loads((output_dir / "rebuild-report.json").read_text())
    statuses = {step["name"]: step["status"] for step in report["steps"]}
    assert exit_code == 1
    assert statuses["root page (pages/authoring/rox_core.py)"] == "failure"
    assert statuses["feature map (pages/authoring/feature_map.py)"] == "success"
    assert statuses["feature pages (pages/authoring/feature_pages.py)"] == "skipped"
    assert statuses["site build"] == "skipped"
    assert statuses["page commit validation"] == "skipped"
    assert "needle not found" in next(
        step["diagnostic"]
        for step in report["steps"]
        if step["name"] == "root page (pages/authoring/rox_core.py)"
    )
    assert not any(
        "feature_pages.py" in argument
        for command in runner.commands
        for argument in command
    )
    assert not any(
        "rox-dox" in argument for command in runner.commands for argument in command
    )
