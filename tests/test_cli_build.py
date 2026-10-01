from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

import rox_dox.cli as cli
import rox_dox.render as render
from rox_dox.plantuml import DiagramError
from rox_dox.schema import extract_tables

REPO_URL = "https://github.com/Rox-AI/rox-core"


def _build_args(
    pages_dir: Path,
    repo: Path,
    output_dir: Path,
    plantuml_jar: Path,
) -> list[str]:
    return [
        "build",
        str(pages_dir),
        "--repo",
        str(repo),
        "--repo-url",
        REPO_URL,
        "--out",
        str(output_dir),
        "--plantuml-jar",
        str(plantuml_jar),
    ]


def _write_page(pages_dir: Path, filename: str, page: dict[str, object]) -> None:
    (pages_dir / filename).write_text(json.dumps(page), encoding="utf-8")


def test_build_writes_complete_page_under_page_id_path(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    payload = copy.deepcopy(page_data)
    payload["id"] = "domain/root"
    _write_page(pages_dir, "root.json", payload)

    exit_code = cli.main(_build_args(pages_dir, git_repo[0], output_dir, plantuml_jar))

    output_file = output_dir / "domain/root.html"
    assert exit_code == 0
    assert "1 pages written to" in capsys.readouterr().out
    assert output_file.is_file()
    document = output_file.read_text(encoding="utf-8")
    assert re.search(r'<section id="tldr">', document)
    assert "<svg" in document


def test_build_renders_all_pages_before_writing_any(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    first_page = copy.deepcopy(page_data)
    first_page["id"] = "first"
    first_page["block"]["nodes"] = []
    first_page["block"]["edges"] = []
    first_page["data"]["sql_tables"] = []
    first_page["data"]["nosql"] = []
    first_page["sequences"] = []
    first_page["states"] = []
    second_page = copy.deepcopy(page_data)
    second_page["id"] = "second"
    second_page["parent"] = "first"
    second_page["paths"] = ["pkg"]
    _write_page(pages_dir, "a-first.json", first_page)
    _write_page(pages_dir, "z-second.json", second_page)

    def fail_diagram(source: str, jar: Path) -> str:
        raise DiagramError("synthetic syntax failure")

    monkeypatch.setattr(render, "render_svg", fail_diagram)

    exit_code = cli.main(_build_args(pages_dir, git_repo[0], output_dir, plantuml_jar))

    assert exit_code == 1
    assert "z-second.json: System overview: synthetic syntax failure" in (
        capsys.readouterr().out
    )
    assert not output_dir.exists()


def test_build_extracts_schema_once_per_commit(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    first_page = copy.deepcopy(page_data)
    first_page["id"] = "first"
    second_page = copy.deepcopy(page_data)
    second_page["id"] = "second"
    second_page["parent"] = "first"
    second_page["paths"] = ["pkg"]
    _write_page(pages_dir, "first.json", first_page)
    _write_page(pages_dir, "second.json", second_page)
    extraction_calls: list[tuple[Path, str]] = []

    def extract_once(repo: Path, commit: str):
        extraction_calls.append((repo, commit))
        return extract_tables(repo, commit)

    monkeypatch.setattr(cli, "extract_tables", extract_once)
    monkeypatch.setattr(cli, "render_page", lambda page, **kwargs: "<!doctype html>")

    exit_code = cli.main(_build_args(pages_dir, git_repo[0], output_dir, plantuml_jar))

    assert exit_code == 0
    assert extraction_calls == [(git_repo[0], page_data["commit"])]
    assert (output_dir / "first.html").is_file()
    assert (output_dir / "second.html").is_file()


def test_build_rejects_page_ids_outside_the_output_directory(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    payload = copy.deepcopy(page_data)
    payload["id"] = "../escape"
    _write_page(pages_dir, "root.json", payload)

    exit_code = cli.main(_build_args(pages_dir, git_repo[0], output_dir, plantuml_jar))

    assert exit_code == 1
    assert "would write outside output directory" in capsys.readouterr().out
    assert not output_dir.exists()
    assert not (tmp_path / "escape.html").exists()


def test_build_reports_all_preflight_problems_before_writing(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    stale_page = copy.deepcopy(page_data)
    stale_page["data"]["sql_tables"] = ["missing_table"]
    stale_page["block"]["edges"][0]["source"] = {
        "path": "pkg/a.py",
        "lines": [8, 20],
    }
    invalid_page = copy.deepcopy(page_data)
    del invalid_page["block"]["edges"][0]["source"]
    _write_page(pages_dir, "a-stale.json", stale_page)
    _write_page(pages_dir, "b-invalid.json", invalid_page)

    exit_code = cli.main(_build_args(pages_dir, git_repo[0], output_dir, plantuml_jar))

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "a-stale.json: block edge api->store" in output
    assert "a-stale.json: SQL table 'missing_table' not found" in output
    assert "b-invalid.json:" in output
    assert not output_dir.exists()
