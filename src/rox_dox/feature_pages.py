from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from itertools import product
from pathlib import PurePosixPath
from typing import Literal

from rox_dox.block_svg import MAX_LAYOUT_PROBLEMS, block_layout_problems
from rox_dox.features import (
    Feature,
    FeatureEvidence,
    FeatureFile,
    FeatureMap,
    _is_deployment_path,
)
from rox_dox.model import (
    BlockDiagram,
    BlockFigure,
    Claim,
    CodeSource,
    DataModel,
    Edge,
    Group,
    MembershipGroup,
    MembershipRow,
    Node,
    Page,
    Related,
    Relation,
    SchemaDomain,
    SummaryTable,
    SummaryTableLink,
    Tldr,
)
from rox_dox.schema import Table

Layer = Literal["web", "routes", "workers", "models", "logic", "skills", "deploy"]

LAYER_ORDER: tuple[Layer, ...] = (
    "web",
    "routes",
    "workers",
    "logic",
    "models",
    "skills",
    "deploy",
)
LAYER_LABELS: dict[Layer, str] = {
    "web": "Web screens",
    "routes": "HTTP routes",
    "workers": "Background workers",
    "models": "Models",
    "logic": "Business logic",
    "skills": "Agent skills",
    "deploy": "Deployment",
}
ROUTE_FILENAMES = {"routes.py", "router.py", "views.py", "endpoints.py"}
WORKER_SEGMENTS = {"tasks", "temporal", "workers", "executors", "cron", "jobs"}
MAX_NODE_DETAIL_LENGTH = 90


def layer_of(path: str) -> Layer:
    parts = PurePosixPath(path).parts
    filename = PurePosixPath(path).name
    if path.startswith("web/"):
        return "web"
    if path.startswith(".agents/skills/"):
        return "skills"
    if _is_deployment_path(path):
        return "deploy"
    if {"routes", "router"} & set(parts) or filename in ROUTE_FILENAMES:
        return "routes"
    if WORKER_SEGMENTS & set(parts):
        return "workers"
    if "models" in parts or filename == "models.py":
        return "models"
    return "logic"


def _humanize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("-", "_").split("_"))


def _feature_name(feature: Feature, names: Mapping[str, str]) -> str:
    name = names.get(feature.id)
    if name is not None:
        return name
    fallback = _humanize(feature.id)
    if len(feature.tables) > 1:
        return f"{fallback} (+{len(feature.tables)} tables)"
    return fallback


def _source(path: str, line: int) -> CodeSource:
    return CodeSource(path=path, lines=(line, line))


def _unique_sources(sources: list[CodeSource]) -> list[CodeSource]:
    found: dict[tuple[str, int, int], CodeSource] = {}
    for source in sources:
        found.setdefault((source.path, *source.lines), source)
    return list(found.values())


def _table_sources(feature: Feature, tables: Mapping[str, Table]) -> list[CodeSource]:
    return _unique_sources([tables[name].source for name in feature.tables])


def _file_sources(file: FeatureFile, fallback: CodeSource) -> list[CodeSource]:
    return _unique_sources(
        [
            _source(evidence.path, evidence.line)
            for evidence in sorted(
                file.evidence,
                key=lambda item: (item.path, item.line, item.kind),
            )
        ]
    ) or [fallback]


def _evidence_text(evidence: FeatureEvidence) -> str:
    if evidence.kind == "table":
        return f"uses {evidence.table}"
    if evidence.kind == "call":
        return f"imports {evidence.to}"
    if evidence.kind == "route":
        return f"route tag {evidence.tag}"
    if evidence.kind == "reference":
        return f"references {evidence.target}"
    return evidence.kind


def _file_evidence_source(file: FeatureFile, fallback: CodeSource) -> CodeSource:
    evidence = sorted(
        (item for item in file.evidence if item.path == file.path),
        key=lambda item: (item.path, item.line, item.kind),
    )
    if evidence:
        item = evidence[0]
        return _source(item.path, item.line)
    if file.evidence:
        item = min(file.evidence, key=lambda evidence: (evidence.path, evidence.line))
        return _source(item.path, item.line)
    return fallback


def _layer_counts(files: list[FeatureFile]) -> Counter[Layer]:
    return Counter(layer_of(file.path) for file in files)


def _top_directories(
    files: list[FeatureFile], layer: Layer
) -> list[tuple[str, list[FeatureFile]]]:
    by_directory: defaultdict[str, list[FeatureFile]] = defaultdict(list)
    for file in files:
        if layer_of(file.path) == layer:
            directory = PurePosixPath(file.path).parent.as_posix()
            by_directory[directory].append(file)
    return sorted(by_directory.items(), key=lambda item: (-len(item[1]), item[0]))[:3]


def _directory_detail_source(
    files: list[FeatureFile], fallback: CodeSource
) -> CodeSource:
    file = min(files, key=lambda item: item.path)
    return _file_evidence_source(file, fallback)


def _directory_detail(directory: str, count: int) -> str:
    suffix = f" — {count} files"
    if len(directory) + len(suffix) <= MAX_NODE_DETAIL_LENGTH:
        return directory + suffix
    components = directory.split("/")
    while len(components) > 1:
        components.pop(0)
        shortened = "…/" + "/".join(components)
        if len(shortened) + len(suffix) <= MAX_NODE_DETAIL_LENGTH:
            return shortened + suffix
    return components[0][: MAX_NODE_DETAIL_LENGTH - len(suffix) - 1] + "…" + suffix


def _feature_tldr(
    feature: Feature,
    tables: Mapping[str, Table],
) -> Tldr:
    table_sources = _table_sources(feature, tables)
    files = feature.files
    summary = [
        Claim(
            text="Stores: " + ", ".join(feature.tables) + ".",
            sources=table_sources,
        )
    ]
    key_points = []
    rows = []
    row_sources = list(table_sources)
    if not files:
        summary.append(
            Claim(
                text="No in-scope code uses its tables.",
                sources=table_sources,
            )
        )
    else:
        counts = _layer_counts(files)
        count_text = ", ".join(
            f"{LAYER_LABELS[layer]}: {counts[layer]}"
            for layer in LAYER_ORDER
            if counts[layer]
        )
        count_sources = [
            _file_evidence_source(
                min(
                    (file for file in files if layer_of(file.path) == layer),
                    key=lambda file: file.path,
                ),
                table_sources[0],
            )
            for layer in LAYER_ORDER
            if counts[layer]
        ]
        summary.append(
            Claim(
                text=f"Files by layer: {count_text}.",
                sources=_unique_sources(count_sources),
            )
        )
        for layer in LAYER_ORDER:
            layer_files = [file for file in files if layer_of(file.path) == layer]
            if not layer_files:
                continue
            directories = _top_directories(files, layer)
            directory_list = ", ".join(
                f"{directory} ({len(directory_files)})"
                for directory, directory_files in directories
            )
            key_points.append(
                Claim(
                    text=f"{LAYER_LABELS[layer]}: {directory_list}.",
                    sources=_unique_sources(
                        [
                            _directory_detail_source(directory_files, table_sources[0])
                            for _, directory_files in directories
                        ]
                    ),
                )
            )
            rows.append(
                [
                    LAYER_LABELS[layer],
                    str(sum(file.primary for file in layer_files)),
                    str(sum(not file.primary for file in layer_files)),
                    directory_list,
                ]
            )
            row_sources.append(
                _file_evidence_source(
                    min(layer_files, key=lambda file: file.path),
                    table_sources[0],
                )
            )
    return Tldr(
        summary=summary,
        key_points=key_points,
        table=SummaryTable(
            columns=["Layer", "Primary", "Shared", "Top directories"],
            rows=rows,
            sources=_unique_sources(row_sources),
        ),
        notes=[],
    )


def _relationship_source(
    feature: Feature,
    other: Feature,
    shared_paths: set[str],
    fallback: CodeSource,
) -> CodeSource:
    evidence = [
        item
        for candidate in (feature, other)
        for file in candidate.files
        if file.path in shared_paths
        for item in file.evidence
    ]
    if not evidence:
        return fallback
    item = min(evidence, key=lambda item: (item.path, item.line))
    return _source(item.path, item.line)


def _table_usage(
    feature: Feature,
) -> dict[str, dict[str, list[tuple[str, FeatureEvidence]]]]:
    usage: defaultdict[str, defaultdict[str, list[tuple[str, FeatureEvidence]]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    seen: set[tuple[str, str, str, int]] = set()
    for file in feature.files:
        layer = layer_of(file.path)
        for evidence in file.evidence:
            if evidence.kind != "table" or evidence.table is None:
                continue
            key = (file.path, evidence.table, evidence.path, evidence.line)
            if key in seen:
                continue
            seen.add(key)
            usage[layer][evidence.table].append((file.path, evidence))
    return {layer: dict(by_table) for layer, by_table in usage.items()}


def _call_edges(feature: Feature) -> list[tuple[str, str, str, int]]:
    files = {file.path for file in feature.files}
    calls = {
        (evidence.path, evidence.to, evidence.line)
        for file in feature.files
        for evidence in file.evidence
        if evidence.kind == "call"
        and evidence.to is not None
        and evidence.path in files
        and evidence.to in files
    }
    return sorted(
        (
            layer_of(path),
            layer_of(target),
            path,
            line,
        )
        for path, target, line in calls
        if layer_of(path) != layer_of(target)
    )


def _feature_block(
    feature: Feature,
    tables: Mapping[str, Table],
) -> tuple[BlockDiagram, list[Edge]]:
    fallback = tables[feature.id].source
    nodes = []
    files_by_layer = {
        layer: [file for file in feature.files if layer_of(file.path) == layer]
        for layer in LAYER_ORDER
    }
    for layer in LAYER_ORDER:
        files = files_by_layer[layer]
        if not files:
            continue
        directory_counts = Counter(
            PurePosixPath(file.path).parent.as_posix() for file in files
        )
        details = []
        for directory, count in sorted(
            directory_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:6]:
            directory_files = [
                file
                for file in files
                if PurePosixPath(file.path).parent.as_posix() == directory
            ]
            details.append(
                Claim(
                    text=_directory_detail(directory, count),
                    sources=[_directory_detail_source(directory_files, fallback)],
                )
            )
        nodes.append(
            Node(
                id=layer,
                label=LAYER_LABELS[layer],
                source=_file_evidence_source(
                    min(files, key=lambda file: file.path),
                    fallback,
                ),
                kind="component",
                details=details,
            )
        )

    store_nodes: dict[str, str] = {}
    if len(feature.tables) <= 6:
        for table_name in feature.tables:
            node_id = f"store-{table_name}"
            store_nodes[table_name] = node_id
            nodes.append(
                Node(
                    id=node_id,
                    label=table_name,
                    source=tables[table_name].source,
                    kind="store",
                )
            )
    else:
        node_id = "store-tables"
        store_nodes = {table_name: node_id for table_name in feature.tables}
        nodes.append(
            Node(
                id=node_id,
                label=f"Tables ({len(feature.tables)})",
                source=tables[feature.id].source,
                kind="store",
                details=[
                    Claim(
                        text=f"{table_name} — {len(tables[table_name].columns)} columns",
                        sources=[tables[table_name].source],
                    )
                    for table_name in feature.tables[:6]
                ],
            )
        )

    calls_by_layers: defaultdict[tuple[str, str], list[tuple[str, int]]] = defaultdict(
        list
    )
    for source_layer, target_layer, path, line in _call_edges(feature):
        calls_by_layers[(source_layer, target_layer)].append((path, line))
    edges = [
        Edge(
            src=source_layer,
            dst=target_layer,
            label=f"imports ({len(evidence)})",
            source=_source(*min(evidence)),
        )
        for (source_layer, target_layer), evidence in sorted(calls_by_layers.items())
    ]

    usage = _table_usage(feature)
    for layer in LAYER_ORDER:
        for table_name in feature.tables:
            evidence = usage.get(layer, {}).get(table_name, [])
            if not evidence:
                continue
            edge_source = min(
                (item for _, item in evidence),
                key=lambda item: (item.path, item.line),
            )
            edges.append(
                Edge(
                    src=layer,
                    dst=store_nodes[table_name],
                    label=f"uses ({len({path for path, _ in evidence})})",
                    source=_source(edge_source.path, edge_source.line),
                )
            )
    layer_nodes = [node for node in nodes if node.kind == "component"]
    store_nodes_in_order = [node for node in nodes if node.kind == "store"]
    best_diagram = None
    best_score = None
    for cuts in product((False, True), repeat=max(0, len(layer_nodes) - 1)):
        groups = []
        assigned_groups: dict[str, str] = {}
        start = 0
        for index, is_cut in enumerate((*cuts, True)):
            if not is_cut:
                continue
            section = layer_nodes[start : index + 1]
            if not section:
                start = index + 1
                continue
            group_id = f"group-layer-{section[0].id}"
            groups.append(
                Group(
                    id=group_id,
                    label=" / ".join(node.label for node in section),
                    source=section[0].source,
                )
            )
            assigned_groups.update({node.id: group_id for node in section})
            start = index + 1
        if store_nodes_in_order:
            groups.append(
                Group(
                    id="group-stores",
                    label="Stores",
                    source=store_nodes_in_order[0].source,
                )
            )
            assigned_groups.update(
                {node.id: "group-stores" for node in store_nodes_in_order}
            )
        grouped_nodes = [
            node.model_copy(update={"group": assigned_groups[node.id]})
            for node in nodes
        ]
        candidate = BlockDiagram(groups=groups, nodes=grouped_nodes, edges=edges)
        problems = block_layout_problems(candidate)
        score = (len(problems), -len(groups), tuple(group.label for group in groups))
        if best_score is None or score < best_score:
            best_diagram = candidate
            best_score = score
    if best_diagram is None:
        raise ValueError(f"feature '{feature.id}' block has no layout")
    selected_edges = list(best_diagram.edges)
    dropped_edges = []
    for edge in sorted(best_diagram.edges, key=_feature_edge_drop_key):
        if (
            len(
                block_layout_problems(
                    BlockDiagram(
                        groups=best_diagram.groups,
                        nodes=best_diagram.nodes,
                        edges=selected_edges,
                    )
                )
            )
            <= MAX_LAYOUT_PROBLEMS
        ):
            break
        selected_edges.remove(edge)
        dropped_edges.append(edge)
    return (
        BlockDiagram(
            groups=best_diagram.groups,
            nodes=best_diagram.nodes,
            edges=selected_edges,
        ),
        dropped_edges,
    )


def _feature_edge_drop_key(edge: Edge) -> tuple[int, int, str, str]:
    count = int(edge.label.rsplit("(", 1)[1][:-1])
    kind_priority = 0 if edge.label.startswith("uses ") else 1
    return count, kind_priority, edge.src, edge.dst


def _feature_relations(feature: Feature) -> list[Relation]:
    return [
        Relation(
            src=link.a,
            dst=link.b,
            label=link.signal,
            kind="enforced" if link.signal == "fk" else "symbolic",
            source=_source(link.path, link.line),
        )
        for link in feature.table_links
    ]


def _feature_shared_notes(
    feature: Feature,
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> list[Claim]:
    paths = {file.path for file in feature.files}
    notes = []
    for other in feature_map.features:
        if other.id == feature.id:
            continue
        shared = paths & {file.path for file in other.files}
        if not shared:
            continue
        notes.append(
            Claim(
                text=f"Shares {len(shared)} files with {_feature_name(other, names)}.",
                sources=[
                    _relationship_source(
                        feature,
                        other,
                        shared,
                        tables[feature.id].source,
                    )
                ],
            )
        )
    if not notes:
        notes.append(
            Claim(
                text="Shares no files with other features.",
                sources=[tables[feature.id].source],
            )
        )
    return notes


def _feature_tldr_for_map(
    feature: Feature,
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
    dropped_edges: list[Edge],
) -> Tldr:
    result = _feature_tldr(feature, tables)
    result.notes = _feature_shared_notes(feature, feature_map, names, tables)
    if dropped_edges:
        result.notes.append(
            Claim(
                text=(
                    f"Dropped {len(dropped_edges)} lower-volume block edges to "
                    "satisfy the layout limit; their evidence remains in the "
                    '"Why these files are one feature" table.'
                ),
                sources=[dropped_edges[0].source],
            )
        )
    return result


def _feature_membership(
    feature: Feature,
    tables: Mapping[str, Table],
) -> list[MembershipGroup]:
    fallback = tables[feature.id].source
    groups = []
    for layer in LAYER_ORDER:
        files = sorted(
            (file for file in feature.files if layer_of(file.path) == layer),
            key=lambda file: (not file.primary, file.path),
        )
        if not files:
            continue
        rows = []
        for file in files:
            evidence = sorted(
                file.evidence,
                key=lambda item: (
                    item.kind,
                    item.path,
                    item.line,
                    item.to or "",
                    item.table or "",
                    item.tag or "",
                    item.target or "",
                ),
            )
            evidence_text = "; ".join(
                dict.fromkeys(_evidence_text(item) for item in evidence)
            )
            rows.append(
                MembershipRow(
                    path=file.path,
                    primary=file.primary,
                    evidence=evidence_text or "feature-map placement",
                    sources=_file_sources(file, fallback),
                )
            )
        groups.append(MembershipGroup(layer=LAYER_LABELS[layer], rows=rows))
    return groups


def _feature_page(
    feature: Feature,
    feature_map: FeatureMap,
    *,
    domain_title: str,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> Page:
    title = _feature_name(feature, names)
    domain_id = f"domain-{feature_map.domain}"
    page_id = f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}"
    paths = sorted(file.path for file in feature.files if file.primary)
    if not paths:
        paths = [tables[feature.id].source.path]
    parent_source = tables[feature.id].source
    shared_ids = {
        candidate.id
        for candidate in feature_map.features
        if candidate.id != feature.id
        and {file.path for file in candidate.files}
        & {file.path for file in feature.files}
    }
    related = [
        Related(
            label=domain_title,
            page=domain_id,
            source=parent_source,
        )
    ]
    for other in feature_map.features:
        if other.id not in shared_ids:
            continue
        related.append(
            Related(
                label=_feature_name(other, names),
                page=f"feature-{feature_map.domain}-{other.id.replace('_', '-')}",
                source=_relationship_source(
                    feature,
                    other,
                    {file.path for file in feature.files}
                    & {file.path for file in other.files},
                    parent_source,
                ),
            )
        )
    block, dropped_edges = _feature_block(feature, tables)
    return Page(
        id=page_id,
        title=title,
        kind="feature",
        commit=feature_map.commit,
        parent=domain_id,
        paths=paths,
        membership=_feature_membership(feature, tables),
        tldr=_feature_tldr_for_map(
            feature,
            feature_map,
            names,
            tables,
            dropped_edges,
        ),
        block=block,
        data=DataModel(
            sql_tables=feature.tables,
            relations=_feature_relations(feature),
        ),
        sequences=[],
        states=[],
        related=related,
    )


def _domain_calls(
    feature_map: FeatureMap,
    primary_owner: Mapping[str, str],
) -> list[tuple[str, str, int, str, str]]:
    calls: set[tuple[str, str, int, str, str]] = set()
    for feature in feature_map.features:
        for file in feature.files:
            for evidence in file.evidence:
                if evidence.kind != "call" or evidence.to is None:
                    continue
                source_feature = primary_owner.get(evidence.path)
                target_feature = primary_owner.get(evidence.to)
                if (
                    source_feature is None
                    or target_feature is None
                    or source_feature == target_feature
                ):
                    continue
                calls.add(
                    (
                        source_feature,
                        target_feature,
                        evidence.line,
                        evidence.path,
                        evidence.to,
                    )
                )
    return sorted(calls, key=lambda item: (item[3], item[2], item[4]))


def _domain_block(
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> tuple[BlockDiagram, list[BlockFigure]]:
    primary_owner = {
        file.path: feature.id
        for feature in feature_map.features
        for file in feature.files
        if file.primary
    }
    feature_nodes = []
    for feature in feature_map.features:
        page_id = f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}"
        source = (
            _file_evidence_source(
                min(
                    (file for file in feature.files if file.primary),
                    key=lambda file: file.path,
                ),
                tables[feature.id].source,
            )
            if any(file.primary for file in feature.files)
            else tables[feature.id].source
        )
        feature_nodes.append(
            Node(
                id=f"feature-{feature.id}",
                label=_feature_name(feature, names),
                source=source,
                link=page_id,
            )
        )
    edge_votes: defaultdict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for source_feature, target_feature, line, path, _target in _domain_calls(
        feature_map,
        primary_owner,
    ):
        edge_votes[(source_feature, target_feature)].append((path, line))
    edges = [
        Edge(
            src=f"feature-{source_feature}",
            dst=f"feature-{target_feature}",
            label=f"imports ({len(sources)})",
            source=_source(*min(sources)),
        )
        for (source_feature, target_feature), sources in edge_votes.items()
    ]
    edges.sort(key=lambda edge: (-int(edge.label[9:-1]), edge.src, edge.dst))
    selected = edges[:]
    while (
        selected
        and len(
            block_layout_problems(BlockDiagram(nodes=feature_nodes, edges=selected))
        )
        > MAX_LAYOUT_PROBLEMS
    ):
        selected.pop()
    dropped = len(edges) - len(selected)
    block = BlockDiagram(nodes=feature_nodes, edges=selected)
    figures = []
    if dropped:
        first_source = min(
            (edge.source for edge in edges[len(selected) :]),
            key=lambda source: (source.path, source.lines[0]),
        )
        figures.append(
            BlockFigure(
                id="inter-feature-imports",
                title="Inter-feature imports",
                notes=[
                    Claim(
                        text=f"{dropped} lower-volume inter-feature import edges were omitted to satisfy the block layout limit.",
                        sources=[first_source],
                    )
                ],
                block=block,
            )
        )
    return block, figures


def _domain_tldr(
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> Tldr:
    table_names = sorted(
        {table for feature in feature_map.features for table in feature.tables}
    )
    table_sources = _unique_sources([tables[name].source for name in table_names])
    primary_paths = {
        file.path
        for feature in feature_map.features
        for file in feature.files
        if file.primary
    }
    evidence_sources = [
        _file_evidence_source(
            min(
                (file for file in feature.files if file.primary),
                key=lambda file: file.path,
            ),
            tables[feature.id].source,
        )
        if any(file.primary for file in feature.files)
        else tables[feature.id].source
        for feature in feature_map.features
    ]
    summary = [
        Claim(
            text=(
                f"{len(feature_map.features)} features, {len(table_names)} tables, "
                f"{len(primary_paths)} primary files."
            ),
            sources=_unique_sources([*table_sources, *evidence_sources]),
        )
    ]
    largest = sorted(
        feature_map.features,
        key=lambda feature: (-len(feature.files), feature.id),
    )[:3]
    key_points = [
        Claim(
            text=(f"{_feature_name(feature, names)}: {len(feature.files)} files."),
            sources=[
                _file_evidence_source(
                    min(
                        (file for file in feature.files if file.primary),
                        key=lambda file: file.path,
                    ),
                    tables[feature.id].source,
                )
                if any(file.primary for file in feature.files)
                else tables[feature.id].source
            ],
        )
        for feature in largest
    ]
    rows = []
    links = []
    row_sources = []
    for row_number, feature in enumerate(feature_map.features):
        feature_files = feature.files
        backend = sum(file.path.startswith("backend/src/") for file in feature_files)
        web = sum(file.path.startswith("web/") for file in feature_files)
        other = len(feature_files) - backend - web
        rows.append(
            [
                _feature_name(feature, names),
                str(len(feature.tables)),
                str(backend),
                str(web),
                str(other),
            ]
        )
        links.append(
            SummaryTableLink(
                row=row_number,
                column=0,
                page=f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}",
            )
        )
        row_sources.extend(
            source
            for file in feature_files
            for source in _file_sources(file, tables[feature.id].source)
        )
        if not feature_files:
            row_sources.append(tables[feature.id].source)
    notes = [
        Claim(
            text=f"{len(feature_map.uncovered)} in-scope files are uncovered.",
            sources=table_sources,
        )
    ]
    return Tldr(
        summary=summary,
        key_points=key_points,
        table=SummaryTable(
            columns=["Feature", "Tables", "Backend", "Web", "Other"],
            rows=rows,
            links=links,
            sources=_unique_sources([*row_sources, *table_sources]),
        ),
        notes=notes,
    )


def _domain_data(
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> DataModel:
    domains = []
    for feature in feature_map.features:
        users: Counter[str] = Counter()
        for file in feature.files:
            for evidence in file.evidence:
                if evidence.kind == "table" and evidence.table is not None:
                    users[evidence.table] += 1
        key_tables = sorted(
            feature.tables,
            key=lambda table: (-users[table], table),
        )[:3]
        domains.append(
            SchemaDomain(
                id=feature.id,
                title=_feature_name(feature, names),
                tables=feature.tables,
                key_tables=key_tables,
                page=f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}",
            )
        )
    return DataModel(domains=domains)


def _domain_page(
    feature_map: FeatureMap,
    *,
    root_id: str,
    domain_title: str,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> Page:
    domain_page_id = f"domain-{feature_map.domain}"
    primary_paths = sorted(
        {
            file.path
            for feature in feature_map.features
            for file in feature.files
            if file.primary
        }
    )
    if not primary_paths:
        primary_paths = [tables[feature_map.features[0].id].source.path]
    block, figures = _domain_block(feature_map, names, tables)
    table_sources = _unique_sources(
        [tables[name].source for name in feature_map.tables]
    )
    root_source = table_sources[0]
    return Page(
        id=domain_page_id,
        title=domain_title,
        kind="domain",
        commit=feature_map.commit,
        parent=root_id,
        paths=primary_paths,
        tldr=_domain_tldr(feature_map, names, tables),
        block=block,
        block_figures=figures,
        data=_domain_data(feature_map, names, tables),
        sequences=[],
        states=[],
        related=[
            Related(
                label="rox-core",
                page=root_id,
                source=root_source,
            )
        ],
    )


def feature_pages(
    feature_map: FeatureMap,
    *,
    root_id: str,
    domain_title: str,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> list[Page]:
    pages = [
        _domain_page(
            feature_map,
            root_id=root_id,
            domain_title=domain_title,
            names=names,
            tables=tables,
        )
    ]
    pages.extend(
        _feature_page(
            feature,
            feature_map,
            domain_title=domain_title,
            names=names,
            tables=tables,
        )
        for feature in feature_map.features
    )
    return pages
