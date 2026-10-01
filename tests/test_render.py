from __future__ import annotations

import copy
import re
from pathlib import Path

from rox_dox.links import source_url
from rox_dox.model import Page
from rox_dox.repo_tree import RepoEntry
from rox_dox.render import page_href, render_page
from rox_dox.tree import build_tree

REPO_URL = "https://github.com/Rox-AI/rox-core"


def _empty_page(data: dict[str, object]) -> Page:
    payload = copy.deepcopy(data)
    payload["block"]["nodes"] = []
    payload["block"]["edges"] = []
    payload["data"]["sql_tables"] = []
    payload["data"]["nosql"] = []
    payload["sequences"] = []
    payload["states"] = []
    return Page.model_validate(payload)


def test_tldr_claim_and_table_citations_link_to_numbered_sources(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["tldr"]["summary"][0]["sources"].append(
        {"path": "pkg/a.py", "lines": [4, 5]}
    )
    page = _empty_page(payload)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    first_source_url = source_url(
        page.tldr.summary[0].sources[0],
        repo_url=REPO_URL,
        commit=page.commit,
    )
    second_source_url = source_url(
        page.tldr.summary[0].sources[1],
        repo_url=REPO_URL,
        commit=page.commit,
    )
    table_source_url = source_url(
        page.tldr.table.sources[0],
        repo_url=REPO_URL,
        commit=page.commit,
    )
    assert f'<a href="{first_source_url}">[1]</a>' in document
    assert f'<a href="{second_source_url}">[2]</a>' in document
    assert f'<a href="{table_source_url}">[1]</a>' in document
    assert re.search(r"<h3>Summary</h3>.*?<h3>Key Points</h3>", document, re.DOTALL)
    assert "<h3>Table</h3>" in document
    assert "<h3>Interesting Notes</h3>" in document


def test_related_page_links_are_relative_and_external_targets_link_out(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["id"] = "a/b"
    payload["block"]["nodes"] = []
    payload["block"]["edges"] = []
    payload["data"]["sql_tables"] = []
    payload["data"]["nosql"] = []
    payload["sequences"] = []
    payload["states"] = []
    payload["related"] = [
        {
            "label": "Nested sibling",
            "page": "a/c/d",
            "source": {"path": "pkg/a.py", "lines": [1, 3]},
        },
        {
            "label": "External guide",
            "url": "https://docs.example.test/guide",
            "source": {"notion": "https://www.notion.so/rox/Foo-123"},
        },
    ]
    page = _empty_page(payload)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    assert page_href("a/b", "a/c/d") == "c/d.html"
    assert '<a href="c/d.html">Nested sibling</a>' in document
    assert '<a href="https://docs.example.test/guide">External guide</a>' in document
    assert (
        '<a href="https://github.com/Rox-AI/rox-core/blob/'
        f'{page.commit}/pkg/a.py#L1-L3">[1]</a>'
    ) in document
    assert '<a href="https://www.notion.so/rox/Foo-123">[1]</a>' in document


def test_empty_key_points_show_module_placeholder(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    page = _empty_page(page_data)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    assert (
        '<h3>Key Points</h3><p class="empty">Nothing to show for this module.</p>'
        in document
    )


def test_empty_notes_show_module_placeholder(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["tldr"]["notes"] = []
    page = _empty_page(payload)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    assert (
        '<h3>Interesting Notes</h3><p class="empty">Nothing to show for this module.</p>'
        in document
    )


def test_page_text_is_html_escaped(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["title"] = 'Page <script>alert("unsafe")</script>'
    payload["tldr"]["summary"][0]["text"] = "Claim <img src=x>"
    page = _empty_page(payload)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    assert "<script>" not in document
    assert "&lt;script&gt;" in document
    assert "Claim &lt;img src=x&gt;" in document


def test_same_title_diagrams_only_list_their_own_sources(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
    plantuml_jar: Path,
) -> None:
    _, commit = git_repo
    payload = copy.deepcopy(page_data)
    payload["block"]["nodes"] = []
    payload["block"]["edges"] = []
    payload["data"]["sql_tables"] = []
    payload["data"]["nosql"] = []
    payload["related"] = []
    second_sequence = copy.deepcopy(payload["sequences"][0])
    second_sequence["participants"][0]["source"]["lines"] = [2, 3]
    second_sequence["participants"][1]["source"]["lines"] = [3, 4]
    second_sequence["steps"][0]["source"]["lines"] = [5, 6]
    payload["sequences"].append(second_sequence)
    second_state_machine = copy.deepcopy(payload["states"][0])
    second_state_machine["states"][0]["source"]["lines"] = [2, 3]
    second_state_machine["states"][1]["source"]["lines"] = [3, 4]
    second_state_machine["transitions"][0]["source"]["lines"] = [5, 6]
    payload["states"].append(second_state_machine)
    page = Page.model_validate(payload)
    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )

    sequence_cards = re.findall(
        r'<article class="diagram-card">(.*?)</article>',
        re.search(r'<section id="sequences">.*?</section>', document, re.DOTALL)[0],
        re.DOTALL,
    )
    state_cards = re.findall(
        r'<article class="diagram-card">(.*?)</article>',
        re.search(r'<section id="states">.*?</section>', document, re.DOTALL)[0],
        re.DOTALL,
    )
    first_sequence_url = source_url(
        page.sequences[0].participants[0].source,
        repo_url=REPO_URL,
        commit=commit,
    )
    second_sequence_url = source_url(
        page.sequences[1].participants[0].source,
        repo_url=REPO_URL,
        commit=commit,
    )
    first_state_url = source_url(
        page.states[0].states[0].source,
        repo_url=REPO_URL,
        commit=commit,
    )
    second_state_url = source_url(
        page.states[1].states[0].source,
        repo_url=REPO_URL,
        commit=commit,
    )
    assert len(sequence_cards) == 2
    assert first_sequence_url in sequence_cards[0]
    assert second_sequence_url not in sequence_cards[0]
    assert second_sequence_url in sequence_cards[1]
    assert first_sequence_url not in sequence_cards[1]
    assert len(state_cards) == 2
    assert first_state_url in state_cards[0]
    assert second_state_url not in state_cards[0]
    assert second_state_url in state_cards[1]
    assert first_state_url not in state_cards[1]


def test_block_sources_table_includes_group_and_detail_citations(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    block = payload["block"]
    group_source = {"path": "pkg/a.py", "lines": [4, 5]}
    detail_source = {"path": "pkg/a.py", "lines": [6, 7]}
    block["groups"] = [
        {
            "id": "backend",
            "label": "Backend",
            "source": group_source,
        }
    ]
    block["nodes"][0]["group"] = "backend"
    block["nodes"][0]["details"] = [
        {
            "text": "Handles requests",
            "sources": [detail_source],
        }
    ]
    payload["data"]["sql_tables"] = []
    payload["data"]["nosql"] = []
    payload["sequences"] = []
    payload["states"] = []
    page = Page.model_validate(payload)

    document = render_page(
        page,
        tree=build_tree([page]),
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
    )
    block_section = re.search(r'<section id="block">.*?</section>', document, re.DOTALL)
    assert block_section is not None
    block_html = block_section.group()

    group_url = source_url(
        page.block.groups[0].source,
        repo_url=REPO_URL,
        commit=page.commit,
    )
    detail_url = source_url(
        page.block.nodes[0].details[0].sources[0],
        repo_url=REPO_URL,
        commit=page.commit,
    )
    assert '<th scope="row">block group backend</th>' in block_html
    assert '<th scope="row">block node api detail 1</th>' in block_html
    assert f'<a href="{group_url}">Source</a>' in block_html
    assert f'<a href="{detail_url}">Source</a>' in block_html


def test_explorer_shows_documented_pages_and_pending_repository_entries(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["data"]["sql_tables"] = []
    payload["data"]["nosql"] = []
    payload["sequences"] = []
    payload["states"] = []
    root = Page.model_validate(payload)
    child_payload = copy.deepcopy(payload)
    child_payload.update(
        {
            "id": "rox-core/pkg",
            "title": "pkg",
            "parent": "rox-core",
            "paths": ["pkg"],
        }
    )
    child = Page.model_validate(child_payload)
    tree = build_tree([root, child])
    entries = {
        root.id: [
            RepoEntry(path="pkg", is_dir=True),
            RepoEntry(path="models", is_dir=True),
            RepoEntry(path="README.md", is_dir=False),
            RepoEntry(path="pyproject.toml", is_dir=False),
        ],
        child.id: [],
    }

    document = render_page(
        root,
        tree=tree,
        repo_url=REPO_URL,
        tables={},
        jar=plantuml_jar,
        entries=entries,
    )
    site_nav = re.search(
        r'<nav id="site-nav" aria-label="Site navigation">(.*?)</nav>',
        document,
        re.DOTALL,
    )
    assert site_nav is not None
    nav_html = site_nav.group(1)
    rows = []
    for match in re.finditer(
        r'<a class="row ([^"]+)" href="([^"]+)"[^>]*>(.*?)</a>',
        nav_html,
        re.DOTALL,
    ):
        label = re.search(r"<span>(.*?)</span>", match.group(3), re.DOTALL)
        assert label is not None
        rows.append((match.group(1), match.group(2), label.group(1)))

    assert any(
        "page" in classes and href == page_href(root.id, child.id) and label == "pkg"
        for classes, href, label in rows
    )
    assert any(
        "pending" in classes
        and href == f"{REPO_URL}/tree/{root.commit}/models"
        and label == "models"
        for classes, href, label in rows
    )
    assert any(
        "file" in classes
        and href == f"{REPO_URL}/blob/{root.commit}/README.md"
        and label == "README.md"
        for classes, href, label in rows
    )
    assert 'aria-current="page"' in nav_html
    folder_positions = [
        nav_html.index(f"<span>{label}</span>") for label in ("pkg", "models")
    ]
    file_positions = [
        nav_html.index(f"<span>{label}</span>")
        for label in ("README.md", "pyproject.toml")
    ]
    assert max(folder_positions) < min(file_positions)
