import json
from pathlib import Path

import pytest

from rox_dox.block_svg import MAX_LAYOUT_PROBLEMS, block_layout_problems
from rox_dox.feature_pages import feature_pages, layer_of
from rox_dox.features import (
    Feature,
    FeatureCounts,
    FeatureEvidence,
    FeatureFile,
    FeatureMap,
)
from rox_dox.model import CodeSource, Page
from rox_dox.schema import Column, Table


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("web/apps/web/src/app/routes.py", "web"),
        (".agents/skills/models.py", "skills"),
        (".github/workflows/jobs/routes.py", "deploy"),
        ("backend/src/routes/jobs/worker.py", "routes"),
        ("backend/src/temporal/tasks/worker.py", "workers"),
        ("backend/src/models/user.py", "models"),
        ("backend/src/services/send.py", "logic"),
    ],
)
def test_layer_classifier_uses_first_matching_rule(
    path: str,
    expected: str,
) -> None:
    assert layer_of(path) == expected


def test_generated_seq_pages_pass_block_layout() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    page_files = [
        repository_root / "pages" / "domains" / "seq.json",
        *sorted((repository_root / "pages" / "features").glob("feature-seq-*.json")),
    ]
    assert page_files[0].is_file()
    assert page_files[1:]

    for page_file in page_files:
        page = Page.model_validate(json.loads(page_file.read_text(encoding="utf-8")))
        diagrams = [page.block, *(figure.block for figure in page.block_figures)]
        for diagram in diagrams:
            problems = block_layout_problems(diagram)
            assert len(problems) <= MAX_LAYOUT_PROBLEMS, f"{page_file}: {problems}"


def test_feature_block_drops_low_volume_edges_with_a_cited_note() -> None:
    paths = {
        "routes": "backend/src/routes/api.py",
        "workers": "backend/src/workers/job.py",
        "logic": "backend/src/services/logic.py",
        "models": "backend/src/models/user.py",
    }
    layer_order = list(paths)
    files = []
    for source_index, (layer, path) in enumerate(paths.items()):
        evidence = []
        line = 1
        for target in layer_order[:source_index]:
            evidence.append(
                FeatureEvidence(
                    kind="call",
                    path=path,
                    line=line,
                    to=paths[target],
                )
            )
            line += 1
        if layer == "routes":
            evidence.append(
                FeatureEvidence(
                    kind="table",
                    path=path,
                    line=50,
                    table="users",
                )
            )
        files.append(
            FeatureFile(
                path=path,
                primary=True,
                reason="tables",
                evidence=evidence,
            )
        )

    table = Table(
        name="users",
        class_name="User",
        columns=[Column(name="id", type="Integer", primary_key=True)],
        source=CodeSource(path=paths["models"], lines=(1, 1)),
    )
    feature_map = FeatureMap(
        commit="a" * 40,
        domain="test",
        threshold=0.25,
        tables=["users"],
        features=[Feature(id="users", tables=["users"], files=files, table_links=[])],
        uncovered=[],
        unmapped_tags=[],
        counts=FeatureCounts(
            domain_files=4,
            primary_placed=4,
            shared=0,
            uncovered=0,
            web=0,
            deployment=0,
            skills=0,
            unparseable=0,
        ),
    )

    pages = feature_pages(
        feature_map,
        root_id="rox-core",
        domain_title="Test",
        names={"users": "Users"},
        tables={"users": table},
    )
    page = next(page for page in pages if page.kind == "feature")

    assert len(block_layout_problems(page.block)) <= MAX_LAYOUT_PROBLEMS
    assert {node.id for node in page.block.nodes} == {
        "routes",
        "workers",
        "logic",
        "models",
        "store-users",
    }
    assert not any(
        edge.src == "routes" and edge.dst == "store-users" for edge in page.block.edges
    )
    assert not any(
        edge.src == "logic" and edge.dst == "routes" for edge in page.block.edges
    )
    drop_note = next(
        note for note in page.tldr.notes if note.text.startswith("Dropped ")
    )
    assert "Dropped 2 lower-volume block edges" in drop_note.text
    assert (
        drop_note.sources[0].path,
        drop_note.sources[0].lines,
    ) == (paths["routes"], (50, 50))
