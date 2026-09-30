from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    (repo / "pkg").mkdir()
    source_file = repo / "pkg" / "a.py"
    source_file.write_text(
        "\n".join(f"line {line_number}" for line_number in range(1, 11)) + "\n",
        encoding="utf-8",
    )
    models_dir = repo / "models"
    models_dir.mkdir()
    (models_dir / "user.py").write_text(
        "from sqlalchemy import Column, ForeignKey, Integer, String\n"
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "\n"
        "class User:\n"
        '    __tablename__ = "users"\n'
        "    id = Column(Integer, primary_key=True)\n"
        "    email = Column(String)\n"
        "\n"
        "class Session:\n"
        '    __tablename__ = "sessions"\n'
        "    id = Column(Integer, primary_key=True)\n"
        '    user_id = Column("user_id", Integer, ForeignKey("users.id"))\n'
        "    token: Mapped[str] = mapped_column()\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "add", "pkg/a.py", "models/user.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add source fixture"],
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, commit


@pytest.fixture
def page_data(git_repo: tuple[Path, str]) -> dict[str, object]:
    _, commit = git_repo
    code_source = {"path": "pkg/a.py", "lines": [1, 3]}
    notion_source = {"notion": "https://www.notion.so/rox/Foo-123"}
    return {
        "id": "rox-core",
        "title": "Rox Core",
        "commit": commit,
        "parent": None,
        "tldr": {
            "summary": [{"text": "Handles requests.", "sources": [code_source]}],
            "key_points": [],
            "table": {
                "columns": ["Component"],
                "rows": [["API"]],
                "sources": [code_source],
            },
            "notes": [{"text": "Design notes.", "sources": [notion_source]}],
        },
        "block": {
            "nodes": [
                {"id": "api", "label": "API", "source": code_source},
                {"id": "store", "label": "Store", "source": code_source},
            ],
            "edges": [
                {
                    "src": "api",
                    "dst": "store",
                    "label": "reads",
                    "source": code_source,
                }
            ],
        },
        "data": {
            "sql_tables": ["users", "sessions"],
            "nosql": [
                {
                    "name": "cache",
                    "kind": "redis",
                    "fields": ["key", "value"],
                    "source": code_source,
                }
            ],
        },
        "sequences": [
            {
                "title": "send message",
                "participants": [
                    {"id": "api", "label": "API", "source": code_source},
                    {"id": "store", "label": "Store", "source": code_source},
                ],
                "steps": [
                    {
                        "src": "api",
                        "dst": "store",
                        "message": "write",
                        "source": code_source,
                    }
                ],
            }
        ],
        "states": [
            {
                "title": "message lifecycle",
                "entity": "Message",
                "states": [
                    {"id": "queued", "label": "Queued", "source": code_source},
                    {"id": "sent", "label": "Sent", "source": code_source},
                ],
                "transitions": [
                    {
                        "src": "queued",
                        "dst": "sent",
                        "event": "deliver",
                        "source": code_source,
                    }
                ],
            }
        ],
        "related": [],
        "notion": [],
    }
