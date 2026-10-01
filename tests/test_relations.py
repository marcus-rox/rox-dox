from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import rox_dox.cli as cli


def _commit_relation_fixture(repo: Path) -> str:
    sources = {
        "backend/src/models.py": (
            "from sqlalchemy.orm import Mapped, mapped_column, relationship\n"
            "\n"
            "class TaskRun:\n"
            '    __tablename__ = "task_run"\n'
            "    run_id: Mapped[str] = mapped_column()\n"
            "\n"
            "class TaskRunLog:\n"
            '    __tablename__ = "task_run_log"\n'
            '    run_id: Mapped[str] = mapped_column()  # ForeignKey("task_run.run_id")\n'
            "    task_run = relationship(\n"
            '        "TaskRun",\n'
            '        primaryjoin="foreign(TaskRunLog.run_id) == remote(TaskRun.run_id)",\n'
            "    )\n"
            "\n"
            "class Outside:\n"
            '    __tablename__ = "outside"\n'
            "    run_id: Mapped[str] = mapped_column()\n"
        ),
        "backend/src/queries.py": (
            "first = TaskRunLog.run_id == TaskRun.run_id\n"
            "filtered = TaskRunLog.run_id == Outside.run_id\n"
        ),
        "backend/src/z_queries.py": (
            "duplicate = TaskRunLog.run_id == TaskRun.run_id\n"
        ),
    }
    for relative_path, source in sources.items():
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    subprocess.run(
        ["git", "-C", str(repo), "add", *sources],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add relation fixture"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_relations_cli_reports_pinned_candidates_sorted_and_filtered(
    git_repo: tuple[Path, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = git_repo
    commit = _commit_relation_fixture(repo)
    uncommitted_path = repo / "backend/src/worktree.py"
    uncommitted_path.write_text(
        "uncommitted = TaskRunLog.run_id == TaskRun.run_id\n",
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "relations",
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--tables",
            "task_run,task_run_log",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out.splitlines() == [
        "task_run_log.run_id\ttask_run.run_id\tcommented_fk\tbackend/src/models.py:9",
        "task_run_log.run_id\ttask_run.run_id\tcomparison\tbackend/src/queries.py:1",
        "task_run_log.run_id\ttask_run.run_id\tprimaryjoin\tbackend/src/models.py:12",
    ]
    assert "outside.run_id" not in output.out
    assert "worktree.py" not in output.out
