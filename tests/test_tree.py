from __future__ import annotations

import copy
import json
from pathlib import Path

from rox_dox.cli import main
from rox_dox.model import Page
from rox_dox.tree import build_tree, tree_problems


def test_duplicate_page_ids_are_reported(page_data: dict[str, object]) -> None:
    duplicate = copy.deepcopy(page_data)

    problems = tree_problems(
        [Page.model_validate(page_data), Page.model_validate(duplicate)]
    )

    assert "duplicate page id 'rox-core'" in problems


def test_zero_root_pages_are_reported(page_data: dict[str, object]) -> None:
    payload = copy.deepcopy(page_data)
    payload["id"] = "child"
    payload["parent"] = "missing"
    payload["paths"] = ["pkg"]

    problems = tree_problems([Page.model_validate(payload)])

    assert "expected exactly one root page, found 0" in problems


def test_multiple_root_pages_are_reported(page_data: dict[str, object]) -> None:
    second_root = copy.deepcopy(page_data)
    second_root["id"] = "second-root"
    second_root["title"] = "Second root"

    problems = tree_problems(
        [
            Page.model_validate(page_data),
            Page.model_validate(second_root),
        ]
    )

    assert "expected exactly one root page, found 2" in problems


def test_missing_parent_names_child_and_parent(page_data: dict[str, object]) -> None:
    child = copy.deepcopy(page_data)
    child["id"] = "child"
    child["parent"] = "missing"
    child["paths"] = ["pkg"]

    problems = tree_problems([Page.model_validate(child)])

    assert "page 'child' has missing parent 'missing'" in problems


def test_parent_cycles_are_reported(page_data: dict[str, object]) -> None:
    first = copy.deepcopy(page_data)
    first["id"] = "first"
    first["parent"] = "second"
    first["paths"] = ["pkg"]
    second = copy.deepcopy(page_data)
    second["id"] = "second"
    second["parent"] = "first"
    second["paths"] = ["pkg/sub"]

    problems = tree_problems([Page.model_validate(first), Page.model_validate(second)])

    assert any(problem.startswith("parent cycle:") for problem in problems)


def test_missing_block_node_page_link_is_reported(
    page_data: dict[str, object],
) -> None:
    payload = copy.deepcopy(page_data)
    payload["block"]["nodes"][0]["link"] = "missing"

    problems = tree_problems([Page.model_validate(payload)])

    assert "block node api: link to missing page 'missing'" in problems


def test_missing_related_page_link_is_reported(
    page_data: dict[str, object],
) -> None:
    payload = copy.deepcopy(page_data)
    payload["related"] = [
        {
            "label": "Missing module",
            "page": "missing",
            "source": {"path": "pkg/a.py", "lines": [1, 3]},
        }
    ]

    problems = tree_problems([Page.model_validate(payload)])

    assert "related 'Missing module': link to missing page 'missing'" in problems


def test_root_paths_must_be_exactly_the_repository_root(
    page_data: dict[str, object],
) -> None:
    payload = copy.deepcopy(page_data)
    payload["paths"] = ["pkg"]

    problems = tree_problems([Page.model_validate(payload)])

    assert "root page 'rox-core' paths must be exactly ['.']" in problems


def test_child_paths_must_be_contained_by_parent_paths(
    page_data: dict[str, object],
) -> None:
    child = copy.deepcopy(page_data)
    child["id"] = "child"
    child["parent"] = "rox-core"
    child["paths"] = ["pkg"]
    leaf = copy.deepcopy(page_data)
    leaf["id"] = "leaf"
    leaf["parent"] = "child"
    leaf["paths"] = ["other"]

    problems = tree_problems(
        [
            Page.model_validate(page_data),
            Page.model_validate(child),
            Page.model_validate(leaf),
        ]
    )

    assert "page 'leaf' path 'other' is outside parent 'child' paths" in problems


def test_two_pages_cannot_claim_the_same_path(
    page_data: dict[str, object],
) -> None:
    first_child = copy.deepcopy(page_data)
    first_child["id"] = "first"
    first_child["parent"] = "rox-core"
    first_child["paths"] = ["pkg"]
    second_child = copy.deepcopy(first_child)
    second_child["id"] = "second"
    second_child["title"] = "Second"

    problems = tree_problems(
        [
            Page.model_validate(page_data),
            Page.model_validate(first_child),
            Page.model_validate(second_child),
        ]
    )

    assert any(
        "path 'pkg'" in problem
        and "page 'first'" in problem
        and "page 'second'" in problem
        for problem in problems
    )


def test_tree_orders_children_and_returns_root_first_ancestors(
    page_data: dict[str, object],
) -> None:
    middle = copy.deepcopy(page_data)
    middle["id"] = "middle"
    middle["parent"] = "rox-core"
    middle["paths"] = ["pkg"]
    first = copy.deepcopy(page_data)
    first["id"] = "z-page"
    first["title"] = "Same title"
    first["parent"] = "middle"
    first["paths"] = ["pkg/z"]
    second = copy.deepcopy(first)
    second["id"] = "a-page"
    second["paths"] = ["pkg/a"]
    root = Page.model_validate(page_data)
    pages = [
        root,
        Page.model_validate(middle),
        Page.model_validate(first),
        Page.model_validate(second),
    ]

    tree = build_tree(pages)

    assert tree.children_of("middle") == ["a-page", "z-page"]
    assert tree.ancestors("a-page") == ["rox-core", "middle"]


def test_check_reports_tree_problems(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    capsys,
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    payload = copy.deepcopy(page_data)
    payload["paths"] = ["pkg"]
    (pages_dir / "root.json").write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["check", str(pages_dir), "--repo", str(git_repo[0])])

    assert exit_code == 1
    assert "root page 'rox-core' paths must be exactly ['.']" in (
        capsys.readouterr().out
    )


def test_build_tree_problem_writes_nothing(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    plantuml_jar: Path,
    capsys,
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    payload = copy.deepcopy(page_data)
    payload["paths"] = ["pkg"]
    payload["data"]["sql_tables"] = []
    (pages_dir / "root.json").write_text(json.dumps(payload), encoding="utf-8")

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
    assert "root page 'rox-core' paths must be exactly ['.']" in (
        capsys.readouterr().out
    )
    assert not output_dir.exists()
