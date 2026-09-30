import json
import subprocess
from pathlib import Path

import pytest

from rox_dox.cli import main
from rox_dox.schema import extract_tables


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


def test_duplicate_table_name_keeps_first_path_and_warns(
    git_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = git_repo
    duplicate_file = repo / "z_duplicate.py"
    duplicate_file.write_text(
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
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    tables = extract_tables(repo, commit)

    assert tables["users"].source.path == "models/user.py"
    assert "duplicate SQL table 'users'" in capsys.readouterr().err


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

    exit_code = main(
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
