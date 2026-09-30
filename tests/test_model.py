import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rox_dox.cli import main
from rox_dox.model import Page


def test_valid_page_passes_check_command(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "root.json").write_text(json.dumps(page_data), encoding="utf-8")

    exit_code = main(["check", str(pages_dir), "--repo", str(git_repo[0])])

    assert exit_code == 0
    assert "1 pages OK" in capsys.readouterr().out


def test_edge_endpoint_must_name_declared_node(
    page_data: dict[str, object],
) -> None:
    block = page_data["block"]
    assert isinstance(block, dict)
    edges = block["edges"]
    assert isinstance(edges, list)
    edge = edges[0]
    assert isinstance(edge, dict)
    edge["dst"] = "cache"

    with pytest.raises(ValidationError, match="block edge api->cache"):
        Page.model_validate(page_data)


def test_node_ids_must_be_unique(page_data: dict[str, object]) -> None:
    block = page_data["block"]
    assert isinstance(block, dict)
    nodes = block["nodes"]
    assert isinstance(nodes, list)
    duplicate_node = dict(nodes[0])
    nodes.append(duplicate_node)

    with pytest.raises(ValidationError, match="duplicate node id 'api'"):
        Page.model_validate(page_data)


def test_summary_table_rows_must_match_column_count(
    page_data: dict[str, object],
) -> None:
    tldr = page_data["tldr"]
    assert isinstance(tldr, dict)
    table = tldr["table"]
    assert isinstance(table, dict)
    table["rows"] = [["API", "extra"]]

    with pytest.raises(ValidationError, match="row 1 has 2 cells"):
        Page.model_validate(page_data)


def test_related_item_requires_exactly_one_target(
    page_data: dict[str, object],
) -> None:
    related = page_data["related"]
    assert isinstance(related, list)
    related.append(
        {
            "label": "Storage",
            "page": "storage",
            "url": "https://example.com/storage",
            "source": {"path": "pkg/a.py", "lines": [1, 3]},
        }
    )

    with pytest.raises(ValidationError, match="exactly one of page or url"):
        Page.model_validate(page_data)
