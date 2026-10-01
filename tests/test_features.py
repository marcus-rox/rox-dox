from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rox_dox.features import (
    FeatureMap,
    _domain_scope,
    _parse_graph,
    _snapshot,
    build_feature_map,
)
from rox_dox.schema import extract_tables


def _commit_sources(tmp_path: Path, sources: dict[str, str]) -> tuple[Path, str]:
    repo = tmp_path / "feature-source"
    repo.mkdir()
    for relative_path, source in sources.items():
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    subprocess.run(
        ["git", "init", str(repo)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "add", *sources],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add feature fixture"],
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


def _base_sources(*, foreign_key: bool = False) -> dict[str, str]:
    sequence_column = (
        '    sequence_id = Column(Integer, ForeignKey("sequence.id"))\n'
        if foreign_key
        else ""
    )
    return {
        "backend/src/rox_core/sequence.py": (
            "from sqlalchemy import Column, Integer\n"
            "\n"
            "class Sequence:\n"
            '    __tablename__ = "sequence"\n'
            "    id = Column(Integer, primary_key=True)\n"
        ),
        "backend/src/rox_core/campaign.py": (
            "from sqlalchemy import Column, Integer, ForeignKey\n"
            "\n"
            "class Campaign:\n"
            '    __tablename__ = "campaign"\n'
            "    id = Column(Integer, primary_key=True)\n"
            f"{sequence_column}"
        ),
        "backend/src/rox_core/sequence_service.py": (
            "from .sequence import Sequence\n"
            "from .shared import shared\n"
            "\n"
            "def run() -> Sequence:\n"
            "    return shared()\n"
        ),
        "backend/src/rox_core/campaign_service.py": (
            "from .campaign import Campaign\n"
            "\n"
            "def run() -> Campaign:\n"
            "    return Campaign()\n"
        ),
        "backend/src/rox_core/shared.py": 'def shared() -> str:\n    return "shared"\n',
        "backend/src/rox_core/split.py": (
            "from .sequence_service import run as sequence_run\n"
            "from .campaign_service import run as campaign_run\n"
        ),
        "backend/src/rox_core/seq_routes.py": (
            "from flask_restx import Namespace as FlaskRestxNamespace\n"
            "from .sequence_service import run\n"
            '\nns = FlaskRestxNamespace(name="sequences")\n'
        ),
        "backend/src/rox_core/broken.py": "def broken(:\n",
        "backend/src/tests/ignored.py": "from .sequence import Sequence\n",
        "backend/src/rox_core/test_helper.py": "from .sequence import Sequence\n",
        "web/apps/web/src/page.tsx": (
            'import useSequences from "#/app/hooks/react-query/generated/'
            'sequences/sequences";\n'
        ),
        "web/apps/web/src/unmapped.tsx": (
            'import useMissing from "#/app/hooks/react-query/generated/'
            'missing/missing";\n'
        ),
        ".github/workflows/map.yml": "module: rox_core.sequence_service\n",
        ".agents/skills/sequence/SKILL.md": (
            "See backend/src/rox_core/sequence_service.py.\n"
        ),
    }


def _build(
    tmp_path: Path,
    *,
    foreign_key: bool = False,
    tables: list[str] | None = None,
) -> FeatureMap:
    repo, commit = _commit_sources(
        tmp_path,
        _base_sources(foreign_key=foreign_key),
    )
    return build_feature_map(
        repo,
        commit,
        {"seq": tables or ["campaign", "sequence"]},
        "seq",
    )


def _feature_by_table(feature_map: FeatureMap, table: str):
    return next(feature for feature in feature_map.features if table in feature.tables)


def _dump(feature_map: FeatureMap) -> str:
    return (
        json.dumps(
            feature_map.model_dump(exclude_none=True),
            indent=1,
        )
        + "\n"
    )


def test_domain_scope_clustering_and_call_propagation(tmp_path: Path) -> None:
    feature_map = _build(tmp_path)

    assert feature_map.counts.domain_files == 7
    assert feature_map.counts.unparseable == 1
    assert {frozenset(feature.tables) for feature in feature_map.features} == {
        frozenset({"campaign"}),
        frozenset({"sequence"}),
    }
    sequence = _feature_by_table(feature_map, "sequence")
    campaign = _feature_by_table(feature_map, "campaign")
    assert "backend/src/rox_core/sequence_service.py" in {
        file.path for file in sequence.files
    }
    assert "backend/src/rox_core/campaign_service.py" in {
        file.path for file in campaign.files
    }
    assert "backend/src/rox_core/shared.py" in {file.path for file in sequence.files}
    assert "backend/src/rox_core/split.py" in {file.path for file in campaign.files}


def test_domain_scope_split_vote_stays_unassigned(tmp_path: Path) -> None:
    repo, commit = _commit_sources(tmp_path, _base_sources())
    snapshot = _snapshot(repo, commit)
    tables = extract_tables(repo, commit)
    graph, _ = _parse_graph(snapshot, tables, {"campaign", "sequence"})

    domains, _ = _domain_scope(
        graph,
        {"seq": ["sequence"], "other": ["campaign"]},
    )

    assert "backend/src/rox_core/split.py" not in domains


def test_foreign_key_link_merges_clusters_at_default_threshold(
    tmp_path: Path,
) -> None:
    feature_map = _build(tmp_path, foreign_key=True)

    assert len(feature_map.features) == 1
    assert set(feature_map.features[0].tables) == {"campaign", "sequence"}
    assert any(link.signal == "fk" for link in feature_map.features[0].table_links)


def test_evidence_check_reports_partnerless_file(tmp_path: Path) -> None:
    sources = _base_sources()
    sources["backend/src/rox_core/orphan.py"] = (
        "from sqlalchemy import Column, Integer\n"
        "\n"
        "class Orphan:\n"
        '    __tablename__ = "orphan"\n'
        "    id = Column(Integer, primary_key=True)\n"
    )
    repo, commit = _commit_sources(tmp_path, sources)
    feature_map = build_feature_map(
        repo,
        commit,
        {"seq": ["campaign", "orphan", "sequence"]},
        "seq",
    )

    assert {item.path: item.reason for item in feature_map.uncovered}[
        "backend/src/rox_core/orphan.py"
    ] == ("no shared table or call in its feature")


def test_excluded_paths_never_appear(tmp_path: Path) -> None:
    feature_map = _build(tmp_path)

    paths = {
        file.path for feature in feature_map.features for file in feature.files
    } | {file.path for file in feature_map.uncovered}
    assert "backend/src/tests/ignored.py" not in paths
    assert "backend/src/rox_core/test_helper.py" not in paths


def test_web_routes_and_unmapped_tags(tmp_path: Path) -> None:
    feature_map = _build(tmp_path)
    sequence = _feature_by_table(feature_map, "sequence")
    sequence_paths = {file.path for file in sequence.files}

    assert "web/apps/web/src/page.tsx" in sequence_paths
    assert "missing" in feature_map.unmapped_tags
    assert feature_map.counts.web == 1


def test_deployment_and_skill_references_join_their_feature(
    tmp_path: Path,
) -> None:
    feature_map = _build(tmp_path)
    sequence = _feature_by_table(feature_map, "sequence")
    sequence_paths = {file.path for file in sequence.files}

    assert ".github/workflows/map.yml" in sequence_paths
    assert ".agents/skills/sequence/SKILL.md" in sequence_paths
    assert feature_map.counts.deployment == 1
    assert feature_map.counts.skills == 1


def test_every_evidence_line_exists_at_the_commit(tmp_path: Path) -> None:
    repo, commit = _commit_sources(tmp_path, _base_sources())
    feature_map = build_feature_map(
        repo,
        commit,
        {"seq": ["campaign", "sequence"]},
        "seq",
    )

    for feature in feature_map.features:
        for file in feature.files:
            for evidence in file.evidence:
                source = subprocess.run(
                    ["git", "-C", str(repo), "show", f"{commit}:{evidence.path}"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.splitlines()
                assert 1 <= evidence.line <= len(source)


def test_feature_map_is_deterministic(tmp_path: Path) -> None:
    repo, commit = _commit_sources(tmp_path, _base_sources())
    first = build_feature_map(
        repo,
        commit,
        {"seq": ["campaign", "sequence"]},
        "seq",
    )
    second = build_feature_map(
        repo,
        commit,
        {"seq": ["campaign", "sequence"]},
        "seq",
    )

    assert _dump(first) == _dump(second)
