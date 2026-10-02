from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rox_dox.rebuild import run_rebuild


class SyntheticRunner:
    def __init__(
        self,
        project_root: Path,
        commit: str,
        pages: list[dict[str, object]],
        build_error: str | None = None,
    ) -> None:
        self.project_root = project_root
        self.commit = commit
        self.pages = pages
        self.build_error = build_error
        self.commands: list[list[str]] = []

    def _write_page(self, page: dict[str, object], relative_path: str) -> None:
        payload = copy.deepcopy(page)
        payload["commit"] = self.commit
        path = self.project_root / "pages" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def __call__(
        self,
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, f"{self.commit}\n", "")
        if any("rox_core.py" in argument for argument in command):
            self._write_page(self.pages[0], "rox-core.json")
            return subprocess.CompletedProcess(command, 0, "", "")
        if any("feature_map.py" in argument for argument in command):
            feature_map = {
                "commit": self.commit,
                "domain": "seq",
                "features": [{"id": "sequence"}],
                "counts": {"domain_files": 3},
                "uncovered": [],
            }
            path = self.project_root / "features" / "seq.json"
            path.write_text(json.dumps(feature_map), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        if any("feature_pages.py" in argument for argument in command):
            self._write_page(self.pages[1], "domains/seq.json")
            self._write_page(self.pages[2], "features/feature-seq-sequence.json")
            return subprocess.CompletedProcess(command, 0, "", "")
        if "rox-dox" in command and "build" in command:
            if self.build_error is not None:
                bad_page = (
                    self.project_root
                    / "pages"
                    / "features"
                    / "feature-seq-sequence.json"
                )
                return subprocess.CompletedProcess(
                    command,
                    1,
                    f"{bad_page}: {self.build_error}\n",
                    "",
                )
            return subprocess.CompletedProcess(command, 0, "3 pages written\n", "")
        raise AssertionError(f"unexpected command: {command}")


class FakePublisher:
    def __init__(self, has_changes: bool) -> None:
        self.changes = has_changes
        self.publish_reports: list[dict[str, object]] = []
        self.change_checks = 0

    def has_changes(self) -> bool:
        self.change_checks += 1
        return self.changes

    def publish(self, report: Mapping[str, object]) -> str:
        self.publish_reports.append(dict(report))
        return "https://github.com/marcus-rox/rox-dox/pull/123"


def _fixed_clock() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _project_root(path: Path) -> Path:
    pages_dir = path / "pages"
    (pages_dir / "authoring").mkdir(parents=True)
    (path / "features").mkdir()
    (pages_dir / "components.json").write_text(
        json.dumps([{"id": "api"}, {"id": "store"}]) + "\n",
        encoding="utf-8",
    )
    (path / "pages" / "authoring" / "COMMIT").write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )
    return path


def _run(
    project_root: Path,
    repo: Path,
    commit: str,
    output_dir: Path,
    pages: list[dict[str, object]],
    publisher: FakePublisher,
    build_error: str | None = None,
) -> int:
    runner = SyntheticRunner(project_root, commit, pages, build_error)
    return run_rebuild(
        repo=repo,
        requested_commit=commit,
        output_dir=output_dir,
        open_pr=True,
        project_root=project_root,
        command_runner=runner,
        clock=_fixed_clock,
        publisher=publisher,
    )


def test_R8_success_publishes_once_and_every_page_uses_run_commit(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    site_pages: list[dict[str, object]],
) -> None:
    repo, commit = git_repo
    project_root = _project_root(tmp_path / "docs")
    output_dir = tmp_path / "site"
    publisher = FakePublisher(has_changes=True)

    exit_code = _run(
        project_root,
        repo,
        commit,
        output_dir,
        site_pages,
        publisher,
    )

    pages_dir = project_root / "pages"
    generated_pages = sorted(
        page_file
        for page_file in pages_dir.rglob("*.json")
        if page_file != pages_dir / "components.json"
    )
    assert exit_code == 0
    assert len(publisher.publish_reports) == 1
    assert publisher.publish_reports[0]["commit"] == commit
    assert generated_pages
    assert all(
        json.loads(page.read_text(encoding="utf-8"))["commit"] == commit
        for page in generated_pages
    )
    assert (
        json.loads((output_dir / "rebuild-report.json").read_text())["publication"][
            "status"
        ]
        == "published"
    )


def test_R8_page_build_failure_is_reported_without_publishing(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    site_pages: list[dict[str, object]],
) -> None:
    repo, commit = git_repo
    project_root = _project_root(tmp_path / "docs")
    output_dir = tmp_path / "site"
    publisher = FakePublisher(has_changes=True)

    exit_code = _run(
        project_root,
        repo,
        commit,
        output_dir,
        site_pages,
        publisher,
        build_error="stale citation at pkg/a.py",
    )

    report = json.loads((output_dir / "rebuild-report.json").read_text())
    assert exit_code == 1
    assert publisher.publish_reports == []
    assert report["success"] is False
    assert {
        (failure["page"], message)
        for failure in report["failing_pages"]
        for message in failure["messages"]
    } == {
        (
            "pages/features/feature-seq-sequence.json",
            "stale citation at pkg/a.py",
        )
    }


def test_R8_no_generated_changes_does_not_publish(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    site_pages: list[dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, commit = git_repo
    project_root = _project_root(tmp_path / "docs")
    output_dir = tmp_path / "site"
    publisher = FakePublisher(has_changes=False)

    exit_code = _run(
        project_root,
        repo,
        commit,
        output_dir,
        site_pages,
        publisher,
    )

    assert exit_code == 0
    assert publisher.change_checks == 1
    assert publisher.publish_reports == []
    assert "no changes" in capsys.readouterr().out
    report = json.loads((output_dir / "rebuild-report.json").read_text())
    assert report["publication"]["status"] == "no_changes"
