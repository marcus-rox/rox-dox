import copy
import json
import subprocess
from pathlib import Path

import pytest

import rox_dox.cli as cli
from rox_dox.schema import extract_tables


def _add_duplicate_table(repo: Path) -> str:
    (repo / "z_duplicate.py").write_text(
        'class Duplicate:\n    __tablename__ = "users"\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", "z_duplicate.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add duplicate table"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_extracts_sqlalchemy_tables_and_column_metadata(
    git_repo: tuple[Path, str],
) -> None:
    repo, commit = git_repo

    tables = extract_tables(repo, commit)

    assert set(tables) == {"users", "sessions"}
    users = tables["users"]
    assert [
        (column.name, column.type, column.primary_key) for column in users.columns
    ] == [
        ("id", "Integer", True),
        ("email", "String", False),
    ]
    sessions = tables["sessions"]
    assert [(column.name, column.type) for column in sessions.columns] == [
        ("id", "Integer"),
        ("user_id", "Integer"),
        ("token", "str"),
    ]
    assert sessions.columns[1].foreign_key == "users.id"
    assert sessions.columns[2].foreign_key is None


def test_schema_table_source_covers_class_lines(
    git_repo: tuple[Path, str],
) -> None:
    repo, commit = git_repo

    tables = extract_tables(repo, commit)

    assert tables["users"].source.path == "models/user.py"
    assert tables["users"].source.lines == (4, 7)
    assert tables["sessions"].source.lines == (9, 13)


def test_duplicate_table_paths_are_collected_without_warning(
    git_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = git_repo
    commit = _add_duplicate_table(repo)

    tables = extract_tables(repo, commit)

    assert tables["users"].source.path == "models/user.py"
    assert tables["users"].duplicate_paths == ["z_duplicate.py"]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_build_warns_only_for_requested_duplicate_tables(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = git_repo
    commit = _add_duplicate_table(repo)
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    requested_page = copy.deepcopy(page_data)
    requested_page["commit"] = commit
    requested_page["data"]["sql_tables"] = ["users"]
    unrequested_page = copy.deepcopy(page_data)
    unrequested_page["id"] = "sessions"
    unrequested_page["commit"] = commit
    unrequested_page["data"]["sql_tables"] = ["sessions"]
    (pages_dir / "requested.json").write_text(
        json.dumps(requested_page),
        encoding="utf-8",
    )
    (pages_dir / "unrequested.json").write_text(
        json.dumps(unrequested_page),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "render_page", lambda page, **kwargs: "<!doctype html>")

    exit_code = cli.main(
        [
            "build",
            str(pages_dir),
            "--repo",
            str(repo),
            "--repo-url",
            "https://github.com/Rox-AI/rox-core",
            "--out",
            str(output_dir),
            "--plantuml-jar",
            str(plantuml_jar),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().err == (
        f"warning: {pages_dir / 'requested.json'}: SQL table 'users' also declared "
        "in z_duplicate.py; using models/user.py\n"
    )


def test_build_fails_when_sql_table_is_missing(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    data = page_data["data"]
    assert isinstance(data, dict)
    data["sql_tables"] = ["missing_table"]
    (pages_dir / "root.json").write_text(json.dumps(page_data), encoding="utf-8")

    exit_code = cli.main(
        [
            "build",
            str(pages_dir),
            "--repo",
            str(git_repo[0]),
            "--repo-url",
            "https://github.com/Rox-AI/rox-core",
            "--out",
            str(output_dir),
            "--plantuml-jar",
            str(plantuml_jar),
        ]
    )

    assert exit_code == 1
    assert "SQL table 'missing_table' not found" in capsys.readouterr().out
    assert not output_dir.exists()
