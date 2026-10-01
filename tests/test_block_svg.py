from __future__ import annotations

import copy
import re
from xml.etree import ElementTree

from rox_dox.block_svg import ARROW_COLOR, CHANNEL_ARROW_COLOR, block_svg
from rox_dox.links import page_href, source_url
from rox_dox.model import Page
from rox_dox.render import PAGE_CSS

REPO_URL = "https://github.com/Rox-AI/rox-core"
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"


def _grouped_page_data(page_data: dict[str, object]) -> dict[str, object]:
    payload = copy.deepcopy(page_data)
    block = payload["block"]
    group_source = {"path": "pkg/a.py", "lines": [1, 2]}
    nested_group_source = {"path": "pkg/a.py", "lines": [2, 3]}
    api_source = {"path": "pkg/a.py", "lines": [3, 4]}
    worker_source = {"path": "pkg/a.py", "lines": [5, 6]}
    detail_source = {"path": "pkg/a.py", "lines": [7, 8]}
    edge_source = {"path": "pkg/a.py", "lines": [8, 9]}
    block["groups"] = [
        {"id": "backend", "label": "Backend", "source": group_source},
        {
            "id": "workers",
            "label": "Workers",
            "source": nested_group_source,
            "parent": "backend",
        },
    ]
    block["nodes"] = [
        {
            "id": "api",
            "label": "API",
            "source": api_source,
            "group": "backend",
        },
        {
            "id": "worker",
            "label": "Worker A",
            "source": worker_source,
            "group": "workers",
            "details": [
                {
                    "text": "Processes requests",
                    "sources": [detail_source],
                }
            ],
        },
    ]
    block["edges"] = [
        {
            "src": "api",
            "dst": "worker",
            "label": "calls worker",
            "source": edge_source,
        }
    ]
    return payload


def _anchors(svg: str) -> list[tuple[str, str]]:
    root = ElementTree.fromstring(svg)
    return [
        (anchor.attrib["href"], "".join(anchor.itertext()))
        for anchor in root.iter(f"{SVG_NAMESPACE}a")
    ]


def _page(data: dict[str, object]) -> Page:
    return Page.model_validate(copy.deepcopy(data))


def test_block_elements_show_labels_and_link_to_their_sources(
    page_data: dict[str, object],
) -> None:
    page = _page(_grouped_page_data(page_data))
    svg = block_svg(page, repo_url=REPO_URL)
    links = _anchors(svg)
    expected = [
        ("Backend", page.block.groups[0].source),
        ("Workers", page.block.groups[1].source),
        ("API", page.block.nodes[0].source),
        ("Worker A", page.block.nodes[1].source),
        ("Processes requests", page.block.nodes[1].details[0].sources[0]),
        ("calls worker", page.block.edges[0].source),
    ]

    for label, source in expected:
        expected_href = source_url(source, repo_url=REPO_URL, commit=page.commit)
        assert any(label in text and href == expected_href for href, text in links)
        assert label in svg


def test_node_links_use_relative_page_href(page_data: dict[str, object]) -> None:
    payload = copy.deepcopy(page_data)
    payload["block"]["nodes"][0]["link"] = "rox-core/pkg"
    page = _page(payload)

    assert any(
        href == page_href(page.id, "rox-core/pkg") and "API" in text
        for href, text in _anchors(block_svg(page, repo_url=REPO_URL))
    )


def test_nested_groups_render_as_sections_inside_their_parent_column(
    page_data: dict[str, object],
) -> None:
    page = _page(_grouped_page_data(page_data))
    root = ElementTree.fromstring(block_svg(page, repo_url=REPO_URL))
    section = next(
        element
        for element in root.iter(f"{SVG_NAMESPACE}rect")
        if element.attrib.get("stroke-dasharray") == "4 3"
    )
    worker_title = next(
        element
        for element in root.iter(f"{SVG_NAMESPACE}text")
        if "".join(element.itertext()) == "Worker A"
    )
    section_x = float(section.attrib["x"])
    section_y = float(section.attrib["y"])
    section_right = section_x + float(section.attrib["width"])
    section_bottom = section_y + float(section.attrib["height"])
    worker_x = float(worker_title.attrib["x"])
    worker_y = float(worker_title.attrib["y"])

    assert section_x < worker_x < section_right
    assert section_y < worker_y < section_bottom


def test_top_level_columns_are_numbered_in_group_order(
    page_data: dict[str, object],
) -> None:
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 2]}
    payload["block"]["groups"] = [
        {"id": "first", "label": "First", "source": source},
        {"id": "second", "label": "Second", "source": source},
    ]
    payload["block"]["nodes"][0]["group"] = "first"
    payload["block"]["nodes"][1]["group"] = "second"
    svg = block_svg(_page(payload), repo_url=REPO_URL)

    assert "1 · First" in svg
    assert "2 · Second" in svg
    assert svg.index("1 · First") < svg.index("2 · Second")


def test_block_svg_has_explicit_dimensions_and_is_not_width_constrained(
    page_data: dict[str, object],
) -> None:
    svg = block_svg(_page(page_data), repo_url=REPO_URL)
    root = ElementTree.fromstring(svg)

    assert int(root.attrib["width"]) > 0
    assert int(root.attrib["height"]) > 0
    assert re.fullmatch(
        rf"0 0 {root.attrib['width']} {root.attrib['height']}",
        root.attrib["viewBox"],
    )
    assert re.search(
        r"\.block-scroll\s+svg\s*{[^}]*max-width:\s*none\b",
        PAGE_CSS,
        re.DOTALL,
    )


def test_skipped_column_edges_use_the_channel_color(
    page_data: dict[str, object],
) -> None:
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 2]}
    payload["block"]["groups"] = [
        {"id": group_id, "label": label, "source": source}
        for group_id, label in (
            ("first", "First"),
            ("second", "Second"),
            ("third", "Third"),
        )
    ]
    payload["block"]["nodes"] = [
        {"id": node_id, "label": node_id.upper(), "source": source, "group": group_id}
        for node_id, group_id in (
            ("first_node", "first"),
            ("second_node", "second"),
            ("third_node", "third"),
        )
    ]
    payload["block"]["edges"] = [
        {
            "src": "first_node",
            "dst": "second_node",
            "label": "adjacent",
            "source": source,
        },
        {
            "src": "first_node",
            "dst": "third_node",
            "label": "skips a column",
            "source": source,
        },
    ]
    root = ElementTree.fromstring(block_svg(_page(payload), repo_url=REPO_URL))
    edge_paths = [
        element
        for element in root.iter(f"{SVG_NAMESPACE}path")
        if "marker-end" in element.attrib
    ]

    assert [path.attrib["stroke"] for path in edge_paths] == [
        ARROW_COLOR,
        CHANNEL_ARROW_COLOR,
    ]


def test_node_kinds_and_multiline_labels_render(page_data: dict[str, object]) -> None:
    payload = copy.deepcopy(page_data)
    nodes = payload["block"]["nodes"]
    nodes[0].update({"label": 'API "primary"\nroute', "kind": "component"})
    nodes[1].update({"label": "Cache", "kind": "store"})
    nodes.extend(
        [
            {
                "id": "external",
                "label": "External",
                "kind": "external",
                "source": {"path": "pkg/a.py", "lines": [2, 3]},
            },
            {
                "id": "queue",
                "label": "Queue",
                "kind": "queue",
                "source": {"path": "pkg/a.py", "lines": [3, 4]},
            },
        ]
    )
    svg = block_svg(_page(payload), repo_url=REPO_URL)
    root = ElementTree.fromstring(svg)
    rendered = "".join(root.itertext())

    assert 'API "primary"' in rendered
    assert "route" in rendered
    assert all(color in svg for color in ("#f5f8fe", "#fff8ef", "#fbf5ff", "#f1faf4"))
