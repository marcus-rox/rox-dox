from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from rox_dox.diagrams import (
    block_plantuml,
    emit_diagram_warnings,
    schema_plantuml,
    sequence_plantuml,
    state_plantuml,
)
from rox_dox.links import source_url
from rox_dox.model import Page
from rox_dox.plantuml import DiagramError, render_svg
from rox_dox.schema import extract_tables

REPO_URL = "https://github.com/Rox-AI/rox-core"


def _page(data: dict[str, object]) -> Page:
    return Page.model_validate(copy.deepcopy(data))


def _links(svg: str) -> set[str]:
    return {
        href
        for href in re.findall(r'(?:xlink:)?href="([^"]+)"', svg)
        if not href.startswith("data:")
    }


def test_node_kind_defaults_to_component(page_data: dict[str, object]) -> None:
    page = _page(page_data)

    assert page.block.nodes[0].kind == "component"


def test_block_diagram_maps_kinds_and_links_nodes_and_edges(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
    plantuml_jar: Path,
) -> None:
    _, commit = git_repo
    payload = copy.deepcopy(page_data)
    nodes = payload["block"]["nodes"]
    nodes[0].update(
        {
            "id": "api/backend.v2",
            "kind": "component",
            "link": "other/module",
        }
    )
    nodes[1].update(
        {
            "id": "cache-1",
            "kind": "store",
            "source": {"path": "pkg/a.py", "lines": [2, 3]},
        }
    )
    nodes.extend(
        [
            {
                "id": "external.node",
                "label": "External",
                "kind": "external",
                "source": {"path": "pkg/a.py", "lines": [2, 3]},
            },
            {
                "id": "worker_q",
                "label": "Queue",
                "kind": "queue",
                "source": {"path": "pkg/a.py", "lines": [2, 3]},
            },
        ]
    )
    payload["block"]["edges"][0].update(
        {
            "src": "api/backend.v2",
            "dst": "cache-1",
            "source": {"path": "pkg/a.py", "lines": [4, 5]},
        }
    )
    page = _page(payload)

    source = block_plantuml(page, repo_url=REPO_URL)
    svg = render_svg(source, plantuml_jar)

    assert "rectangle" in source
    assert "database" in source
    assert "cloud" in source
    assert "queue" in source
    assert "as api/backend.v2" not in source
    links = _links(svg)
    assert "other/module.html" in links
    assert (
        source_url(
            page.block.nodes[1].source,
            repo_url=REPO_URL,
            commit=commit,
        )
        in links
    )
    assert (
        source_url(
            page.block.edges[0].source,
            repo_url=REPO_URL,
            commit=commit,
        )
        in links
    )


def test_quoted_multiline_diagram_labels_render(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    payload["block"]["nodes"][0]["label"] = 'API "primary"\nroute'
    payload["block"]["edges"][0]["label"] = 'reads "state"\nthen writes'
    page = _page(payload)

    svg = render_svg(block_plantuml(page, repo_url=REPO_URL), plantuml_jar)

    assert svg.startswith("<svg")


def test_block_plantuml_emits_nested_groups_details_and_direction(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
) -> None:
    _, commit = git_repo
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 3]}
    payload["block"]["groups"] = [
        {"id": "backend", "label": "Backend", "source": source},
        {
            "id": "workers",
            "label": "Workers",
            "source": source,
            "parent": "backend",
        },
    ]
    nodes = payload["block"]["nodes"]
    nodes[0].update({"label": "API", "group": "backend"})
    nodes[1].update(
        {
            "id": "worker-a",
            "label": "Worker A",
            "group": "workers",
            "details": [
                {"text": "Consumes messages", "sources": [source]},
            ],
        }
    )
    payload["block"]["edges"][0]["dst"] = "worker-a"
    page = _page(payload)

    plantuml = block_plantuml(page, repo_url=REPO_URL)

    backend_start = plantuml.index('rectangle "Backend" as group_0 #F7F9FC {')
    workers_start = plantuml.index('rectangle "Workers" as group_1 #F7F9FC {')
    worker_start = plantuml.index(
        'rectangle "**Worker A**\\n<size:11>Consumes messages</size>" as node_1'
    )
    workers_close = plantuml.index("  }", workers_start)
    api_node = plantuml.index('  rectangle "API" as node_0')
    assert backend_start < workers_start < worker_start < workers_close < api_node
    assert "left to right direction" in plantuml
    assert (
        f"url of group_0 is [[{source_url(page.block.groups[0].source, repo_url=REPO_URL, commit=commit)}]]"
        in plantuml
    )

    payload["block"]["direction"] = "top-down"

    assert "left to right direction" not in block_plantuml(
        _page(payload),
        repo_url=REPO_URL,
    )


def test_nested_groups_and_cross_boundary_edges_render_with_smetana(
    page_data: dict[str, object],
    plantuml_jar: Path,
) -> None:
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 3]}
    payload["block"]["groups"] = [
        {"id": "backend", "label": "Backend", "source": source},
        {
            "id": "workers",
            "label": "Workers",
            "source": source,
            "parent": "backend",
        },
    ]
    nodes = payload["block"]["nodes"]
    nodes[0].update({"id": "api", "label": "API", "group": "backend"})
    nodes[1].update(
        {
            "id": "worker-a",
            "label": "Worker A",
            "group": "workers",
            "details": [
                {"text": "Consumes commands", "sources": [source]},
            ],
        }
    )
    nodes.extend(
        [
            {
                "id": "worker-b",
                "label": "Worker B",
                "group": "workers",
                "details": [{"text": "Persists results", "sources": [source]}],
                "source": source,
            },
            {
                "id": "external",
                "label": "External",
                "kind": "external",
                "source": source,
            },
        ]
    )
    edges = payload["block"]["edges"]
    edges[0].update({"src": "worker-a", "dst": "external"})
    edges.append(
        {
            "src": "api",
            "dst": "worker-b",
            "label": "dispatches",
            "source": source,
        }
    )
    page = _page(payload)

    svg = render_svg(block_plantuml(page, repo_url=REPO_URL), plantuml_jar)

    assert all(
        label in svg
        for label in (
            "Backend",
            "Workers",
            "API",
            "Worker A",
            "Worker B",
            "External",
            "Consumes commands",
            "Persists results",
        )
    )


def test_schema_diagram_links_tables_stores_and_in_scope_foreign_keys(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
    plantuml_jar: Path,
) -> None:
    repo, commit = git_repo
    page = _page(page_data)
    tables = extract_tables(repo, commit)
    source = schema_plantuml(page, repo_url=REPO_URL, tables=tables)
    svg = render_svg(source, plantuml_jar)

    assert "hide circle" in source
    assert "hide empty methods" in source
    assert "id: Integer <<PK>>" in source
    assert "user_id: Integer <<FK>>" in source
    assert all(marker in svg for marker in ("PK", "FK", "redis"))
    assert "sql_1 --> sql_0" in source
    assert "  key" in source
    assert "  value" in source
    assert (
        f"sql_1 --> sql_0 : [[{source_url(tables['sessions'].source, repo_url=REPO_URL, commit=commit)}"
        in source
    )
    assert all(
        source_url(tables[name].source, repo_url=REPO_URL, commit=page.commit)
        in _links(svg)
        for name in ("users", "sessions")
    )
    assert source_url(
        page.data.nosql[0].source,
        repo_url=REPO_URL,
        commit=page.commit,
    ) in _links(svg)

    page.data.sql_tables = ["sessions"]
    out_of_scope_source = schema_plantuml(
        page,
        repo_url=REPO_URL,
        tables=tables,
    )
    assert "sql_0 -->" not in out_of_scope_source


def test_sequence_diagram_autonumbers_and_links_participants_and_steps(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
    plantuml_jar: Path,
) -> None:
    _, commit = git_repo
    payload = copy.deepcopy(page_data)
    sequence = payload["sequences"][0]
    sequence["participants"][0]["source"]["lines"] = [1, 2]
    sequence["participants"][1]["source"]["lines"] = [2, 3]
    sequence["steps"][0]["source"]["lines"] = [4, 5]
    page = _page(payload)

    source = sequence_plantuml(page, page.sequences[0], repo_url=REPO_URL)
    svg = render_svg(source, plantuml_jar)

    assert "autonumber" in source
    assert "!pragma layout smetana" not in source
    assert all(color in svg for color in ("#E8F0FE", "#3B6FD8", "#9AA4B2"))
    assert {
        source_url(
            participant.source,
            repo_url=REPO_URL,
            commit=commit,
        )
        for participant in page.sequences[0].participants
    }.issubset(_links(svg))
    assert source_url(
        page.sequences[0].steps[0].source,
        repo_url=REPO_URL,
        commit=commit,
    ) in _links(svg)


def test_state_diagram_links_states_initial_arrow_and_transitions(
    page_data: dict[str, object],
    git_repo: tuple[Path, str],
    plantuml_jar: Path,
) -> None:
    _, commit = git_repo
    payload = copy.deepcopy(page_data)
    state_machine = payload["states"][0]
    state_machine["states"][0]["source"]["lines"] = [1, 2]
    state_machine["states"][1]["source"]["lines"] = [2, 3]
    state_machine["transitions"][0]["source"]["lines"] = [4, 5]
    page = _page(payload)

    source = state_plantuml(page, page.states[0], repo_url=REPO_URL)
    svg = render_svg(source, plantuml_jar)

    first_state_url = source_url(
        page.states[0].states[0].source,
        repo_url=REPO_URL,
        commit=commit,
    )
    assert f"[*] --> state_0 : [[{first_state_url}" in source
    assert all(color in svg for color in ("#E8F0FE", "#3B6FD8"))
    assert {
        source_url(state.source, repo_url=REPO_URL, commit=commit)
        for state in page.states[0].states
    }.issubset(_links(svg))
    assert source_url(
        page.states[0].transitions[0].source,
        repo_url=REPO_URL,
        commit=commit,
    ) in _links(svg)


def test_large_block_sequence_and_state_diagrams_warn(
    page_data: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 3]}
    payload["block"]["nodes"].extend(
        {
            "id": f"extra-{index}",
            "label": f"Extra {index}",
            "source": source,
        }
        for index in range(11)
    )
    payload["sequences"][0]["participants"].extend(
        {
            "id": f"participant-{index}",
            "label": f"Participant {index}",
            "source": source,
        }
        for index in range(11)
    )
    payload["states"][0]["states"].extend(
        {
            "id": f"state-{index}",
            "label": f"State {index}",
            "source": source,
        }
        for index in range(11)
    )

    emit_diagram_warnings(_page(payload))

    warning_output = capsys.readouterr().err
    assert "block diagram has 13 nodes" in warning_output
    assert "sequence 'send message' has 13 participants" in warning_output
    assert "state machine 'message lifecycle' has 13 states" in warning_output


def test_diagram_size_guide_does_not_warn_at_twelve(
    page_data: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = copy.deepcopy(page_data)
    source = {"path": "pkg/a.py", "lines": [1, 3]}
    payload["block"]["nodes"].extend(
        {
            "id": f"extra-{index}",
            "label": f"Extra {index}",
            "source": source,
        }
        for index in range(10)
    )
    payload["sequences"][0]["participants"].extend(
        {
            "id": f"participant-{index}",
            "label": f"Participant {index}",
            "source": source,
        }
        for index in range(10)
    )
    payload["states"][0]["states"].extend(
        {
            "id": f"state-{index}",
            "label": f"State {index}",
            "source": source,
        }
        for index in range(10)
    )

    emit_diagram_warnings(_page(payload))

    assert capsys.readouterr().err == ""


def test_schema_size_does_not_emit_a_size_warning(
    page_data: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = copy.deepcopy(page_data)
    payload["data"]["sql_tables"] = [f"table_{index}" for index in range(13)]

    emit_diagram_warnings(_page(payload))

    assert capsys.readouterr().err == ""


def test_invalid_plantuml_syntax_raises_diagram_error(plantuml_jar: Path) -> None:
    with pytest.raises(DiagramError, match="Syntax Error"):
        render_svg("@startuml\nnot valid\n@enduml", plantuml_jar)


def test_missing_plantuml_jar_points_to_fetch_script(tmp_path: Path) -> None:
    with pytest.raises(DiagramError, match="scripts/fetch_plantuml.sh"):
        render_svg("@startuml\n@enduml", tmp_path / "missing.jar")
