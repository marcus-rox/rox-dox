from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from rox_dox.block_svg import block_layout_problems
from rox_dox.components import Endpoint, ExternalCall, FileFacts, Worker
from rox_dox.features import (
    Feature,
    FeatureEvidence,
    FeatureFile,
    FeatureMap,
    TableLink,
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
GENERIC_SEGMENTS = {
    "backend",
    "src",
    "tasks",
    "task",
    "executors",
    "executor",
    "workers",
    "worker",
    "temporal",
    "activities",
    "activity",
    "workflows",
    "workflow",
    "jobs",
    "job",
    "cron",
}


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
    return _humanize(feature.id)


@dataclass(frozen=True)
class _FeatureBlock:
    diagram: BlockDiagram
    tables_by_node: Mapping[str, tuple[str, ...]]
    services_by_node: Mapping[str, tuple[str, ...]]
    callers: tuple[_Caller, ...]
    library_rows: tuple[_LibraryRow, ...]


@dataclass(frozen=True)
class _Caller:
    path: str
    targets: tuple[str, ...]
    import_sources: tuple[CodeSource, ...]
    owner_name: str | None
    owner_page: str | None


@dataclass(frozen=True)
class _LibraryRow:
    label: str
    tables: tuple[str, ...]
    services: tuple[str, ...]
    sources: tuple[CodeSource, ...]


def _component_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "component"


def _feature_facts(
    feature: Feature,
    components: Mapping[str, FileFacts],
) -> dict[str, FileFacts]:
    return {
        file.path: components.get(
            file.path,
            FileFacts(
                path=file.path,
                api_group=None,
                endpoints=[],
                workers=[],
                externals=[],
            ),
        )
        for file in feature.files
    }


def _feature_callers(
    feature: Feature,
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    primary_features: Mapping[str, tuple[str, str]],
) -> tuple[_Caller, ...]:
    member_paths = {file.path for file in feature.files}
    callers = []
    for path, imports in sorted(component_imports.items()):
        if path in member_paths:
            continue
        facts = component_facts.get(path)
        if facts is None or not (facts.endpoints or facts.workers):
            continue
        targets = tuple(sorted(set(imports) & member_paths))
        if not targets:
            continue
        owner = primary_features.get(path)
        callers.append(
            _Caller(
                path=path,
                targets=targets,
                import_sources=tuple(
                    _source(path, imports[target]) for target in targets
                ),
                owner_name=owner[0] if owner else None,
                owner_page=owner[1] if owner else None,
            )
        )
    return tuple(callers)


def _runtime_records(
    facts: Mapping[str, FileFacts],
) -> tuple[
    list[tuple[str, Endpoint]],
    list[tuple[str, Worker]],
    list[tuple[str, ExternalCall]],
]:
    endpoints = sorted(
        (
            (path, endpoint)
            for path, file_facts in facts.items()
            for endpoint in file_facts.endpoints
        ),
        key=lambda item: (
            item[1].path,
            item[1].method,
            item[0],
            item[1].handler,
            item[1].line,
        ),
    )
    workers = sorted(
        (
            (path, worker)
            for path, file_facts in facts.items()
            for worker in file_facts.workers
        ),
        key=lambda item: (item[1].kind, item[1].name, item[0], item[1].line),
    )
    externals = sorted(
        (
            (path, external)
            for path, file_facts in facts.items()
            for external in file_facts.externals
        ),
        key=lambda item: (
            item[1].service,
            item[1].module,
            item[0],
            item[1].line,
        ),
    )
    return endpoints, workers, externals


def _worker_label(
    directory: str,
    records: list[tuple[str, Worker]],
    family: str,
) -> str:
    label_family = "workers" if family == "task_executor" else "workflows"
    for segment in reversed(PurePosixPath(directory).parts):
        parts = [
            part
            for part in segment.lower().replace("-", "_").split("_")
            if part and part not in GENERIC_SEGMENTS
        ]
        if parts:
            return f"{_humanize('_'.join(parts))} {label_family}"
    first_name = min(records, key=lambda item: (item[1].name, item[0], item[1].line))[
        1
    ].name
    base_name = re.sub(r"(TaskExecutor|Executor|Workflow|Activity)$", "", first_name)
    label = _humanize(base_name or first_name)
    more = len(records) - 1
    if more:
        label = f"{label} + {more} more"
    return f"{label} {label_family}"


def _caller_detail(callers: list[_Caller]) -> Claim:
    origins = sorted({caller.owner_name or "outside any feature" for caller in callers})
    text = f"Calls into this feature from {', '.join(origins)}"
    sources = _unique_sources(
        [source for caller in callers for source in caller.import_sources]
    )
    return Claim(
        text=_bounded_detail_text(text),
        sources=sources,
    )


def _caller_records(
    callers: Collection[_Caller],
    component_facts: Mapping[str, FileFacts],
) -> tuple[list[tuple[str, Endpoint]], list[tuple[str, Worker]]]:
    facts = {caller.path: component_facts[caller.path] for caller in callers}
    endpoints, workers, _ = _runtime_records(facts)
    return endpoints, workers


def _caller_groups(
    endpoints: list[tuple[str, Endpoint]],
    workers: list[tuple[str, Worker]],
    component_facts: Mapping[str, FileFacts],
) -> list[str]:
    groups = {
        _humanize(component_facts[path].api_group or PurePosixPath(path).stem)
        for path, _ in endpoints
    }
    worker_groups: defaultdict[tuple[str, str], list[tuple[str, Worker]]] = defaultdict(
        list
    )
    for path, worker in workers:
        family = "task_executor" if worker.kind == "task_executor" else "temporal"
        worker_groups[(PurePosixPath(path).parent.as_posix(), family)].append(
            (path, worker)
        )
    groups.update(
        _worker_label(directory, records, family)
        for (directory, family), records in sorted(worker_groups.items())
    )
    return sorted(groups)


def _bounded_details(
    records: list[tuple[str, CodeSource]],
    noun: str,
) -> list[Claim]:
    details = [
        Claim(text=_bounded_detail_text(text), sources=[source])
        for text, source in records[:5]
    ]
    if len(records) > 5:
        details.append(
            Claim(
                text=f"+{len(records) - 5} more {noun}",
                sources=[records[5][1]],
            )
        )
    return details


def _bounded_detail_text(text: str) -> str:
    if len(text) <= 90:
        return text
    prefix, separator, value = text.partition(" ")
    if separator and len(prefix) < 87:
        room = 90 - len(prefix) - 2
        left = (room + 1) // 2
        right = room - left
        tail = value[-right:] if right else ""
        return f"{prefix} {value[:left]}…{tail}"
    return f"{text[:89]}…"


def _web_directory_detail(directory: str, file_count: int) -> str:
    suffix = f" — {file_count} files"
    max_path_length = 90 - len(suffix)
    parts = PurePosixPath(directory).parts
    retained = list(parts)
    while len("/".join(retained)) > max_path_length - 2 and len(retained) > 1:
        retained.pop(0)
    summary = "/".join(retained)
    if len(retained) < len(parts):
        summary = f"…/{summary}"
    if len(summary) > max_path_length:
        summary = f"…{summary[-(max_path_length - 1) :]}"
    return f"{summary}{suffix}"


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


def _feature_tldr(
    feature: Feature,
    tables: Mapping[str, Table],
    component_facts: Mapping[str, FileFacts],
    block: _FeatureBlock,
) -> Tldr:
    table_sources = _table_sources(feature, tables)
    files = feature.files
    facts = _feature_facts(feature, component_facts)
    endpoints, workers, externals = _runtime_records(facts)
    other_feature_callers = [
        caller for caller in block.callers if caller.owner_name is not None
    ]
    caller_endpoints, caller_workers = _caller_records(
        other_feature_callers,
        component_facts,
    )
    caller_endpoints = list(
        {
            (path, endpoint.method, endpoint.path, endpoint.handler, endpoint.line): (
                path,
                endpoint,
            )
            for path, endpoint in caller_endpoints
        }.values()
    )
    caller_workers = list(
        {
            (path, worker.kind, worker.name, worker.line): (path, worker)
            for path, worker in caller_workers
        }.values()
    )
    summary = []
    endpoints_by_group: defaultdict[str, list[tuple[str, Endpoint]]] = defaultdict(list)
    for path, endpoint in endpoints:
        group = facts[path].api_group or PurePosixPath(path).stem
        endpoints_by_group[group].append((path, endpoint))
    if endpoints:
        endpoint_sources = [
            _source(path, endpoint.line)
            for group in sorted(endpoints_by_group)
            for path, endpoint in [
                min(
                    endpoints_by_group[group],
                    key=lambda item: (
                        item[1].path,
                        item[1].method,
                        item[0],
                        item[1].line,
                    ),
                )
            ]
        ]
        summary.append(
            Claim(
                text=(
                    f"Owns {len(endpoints)} HTTP endpoints in "
                    f"{len(endpoints_by_group)} API groups: "
                    f"{', '.join(_humanize(group) for group in sorted(endpoints_by_group))}."
                ),
                sources=_unique_sources(endpoint_sources),
            )
        )
    if caller_endpoints or caller_workers:
        caller_sources = [
            *[_source(path, endpoint.line) for path, endpoint in caller_endpoints],
            *[_source(path, worker.line) for path, worker in caller_workers],
            *[
                source
                for caller in other_feature_callers
                for source in caller.import_sources
            ],
        ]
        summary.append(
            Claim(
                text=(
                    f"Reached from {len(caller_endpoints)} HTTP endpoints and "
                    f"{len(caller_workers)} workers in other features: "
                    f"{', '.join(_caller_groups(caller_endpoints, caller_workers, component_facts))}."
                ),
                sources=_unique_sources(caller_sources),
            )
        )
    if workers:
        named_workers = sorted(
            workers,
            key=lambda item: (item[1].name, item[0], item[1].line),
        )
        worker_names = [worker.name for _, worker in named_workers[:5]]
        more = len(named_workers) - len(worker_names)
        summary.append(
            Claim(
                text=(
                    f"Runs {len(workers)} background workers and workflows: "
                    f"{', '.join(worker_names)}"
                    f"{f' and {more} more' if more else ''}."
                ),
                sources=_unique_sources(
                    [_source(path, worker.line) for path, worker in named_workers[:5]]
                ),
            )
        )
    services = sorted({external.service for _, external in externals})
    if services:
        summary.append(
            Claim(
                text=f"Calls outside services: {', '.join(services)}.",
                sources=_unique_sources(
                    [_source(path, external.line) for path, external in externals]
                ),
            )
        )
    if feature.tables:
        summary.append(
            Claim(
                text=f"Stores data in: {', '.join(feature.tables)}.",
                sources=table_sources,
            )
        )
    if not endpoints and not workers:
        summary.append(
            Claim(
                text=(
                    "No HTTP endpoints or background workers; its code is library "
                    "code used by other features."
                ),
                sources=[
                    _file_evidence_source(
                        min(files, key=lambda file: file.path),
                        table_sources[0],
                    )
                    if files
                    else table_sources[0]
                ],
            )
        )
    key_points = []
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
    rows = []
    row_sources = list(table_sources)
    kind_by_group = {
        "group-web-app": "Web app",
        "group-http-api": "HTTP API",
        "group-background-workers": "Background workers / workflows",
        "group-library-code": "Library code",
        "group-database": "Database",
        "group-external-services": "External service",
    }
    for node in block.diagram.nodes:
        tables_used = block.tables_by_node.get(node.id, ())
        outside_services = block.services_by_node.get(node.id, ())
        if node.kind == "store" and not tables_used:
            tables_used = (node.label,)
        if node.kind == "external" and not outside_services:
            outside_services = (node.label,)
        rows.append(
            [
                node.label,
                kind_by_group.get(node.group or "", node.kind),
                ", ".join(tables_used) or "—",
                ", ".join(outside_services) or "—",
            ]
        )
        row_sources.extend(
            [
                node.source,
                *(source for detail in node.details for source in detail.sources),
            ]
        )
        row_sources.extend(
            edge.source
            for edge in block.diagram.edges
            if edge.src == node.id or edge.dst == node.id
        )
    for library in block.library_rows:
        rows.append(
            [
                library.label,
                "Library code",
                ", ".join(library.tables) or "—",
                ", ".join(library.services) or "—",
            ]
        )
        row_sources.extend(library.sources)
    return Tldr(
        summary=summary,
        key_points=key_points,
        table=SummaryTable(
            columns=["Component", "Kind", "Tables used", "Outside services"],
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


def _feature_block(
    feature: Feature,
    tables: Mapping[str, Table],
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    primary_features: Mapping[str, tuple[str, str]],
) -> _FeatureBlock:
    fallback = tables[feature.id].source
    feature_file_by_path = {file.path: file for file in feature.files}
    facts = _feature_facts(feature, component_facts)
    callers = _feature_callers(
        feature,
        component_facts,
        component_imports,
        primary_features,
    )
    nodes = []
    component_files: dict[str, set[str]] = {}
    component_roles: dict[str, str] = {}
    entry_files: dict[str, set[str]] = {}
    entry_starts: dict[str, set[str]] = {}
    api_files: dict[str, set[str]] = {}
    used_ids: set[str] = set()

    def node_id(prefix: str, value: str) -> str:
        base = f"{prefix}-{_component_slug(value)}"
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    web_files = sorted(path for path in feature_file_by_path if path.startswith("web/"))
    if web_files:
        directories: defaultdict[str, list[FeatureFile]] = defaultdict(list)
        for path in web_files:
            directories[PurePosixPath(path).parent.as_posix()].append(
                feature_file_by_path[path]
            )
        directory_records = [
            (
                _web_directory_detail(directory, len(directory_files)),
                _directory_detail_source(directory_files, fallback),
            )
            for directory, directory_files in sorted(
                directories.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ]
        web_id = node_id("web", "app")
        web_node = Node(
            id=web_id,
            label="Web app",
            source=_file_evidence_source(
                feature_file_by_path[web_files[0]],
                fallback,
            ),
            group="group-web-app",
            details=_bounded_details(directory_records, "directories"),
        )
        nodes.append(web_node)
        component_files[web_id] = set(web_files)
        component_roles[web_id] = "web"

    api_records: defaultdict[str, list[tuple[str, Endpoint]]] = defaultdict(list)
    api_member_paths: defaultdict[str, set[str]] = defaultdict(set)
    api_callers: defaultdict[str, list[_Caller]] = defaultdict(list)
    for path, file_facts in facts.items():
        if not file_facts.endpoints:
            continue
        group = file_facts.api_group or PurePosixPath(path).stem
        api_records[group].extend((path, endpoint) for endpoint in file_facts.endpoints)
        api_member_paths[group].add(path)
    for caller in callers:
        caller_facts = component_facts[caller.path]
        if not caller_facts.endpoints:
            continue
        group = caller_facts.api_group or PurePosixPath(caller.path).stem
        api_records[group].extend(
            (caller.path, endpoint) for endpoint in caller_facts.endpoints
        )
        api_callers[group].append(caller)
    api_nodes: dict[str, str] = {}
    for api_group in sorted(api_records):
        records = sorted(
            api_records[api_group],
            key=lambda item: (
                item[1].path,
                item[1].method,
                item[0],
                item[1].line,
            ),
        )
        details = _bounded_details(
            [
                (
                    f"{endpoint.method} {endpoint.path}",
                    _source(path, endpoint.line),
                )
                for path, endpoint in records
            ],
            "endpoints",
        )
        group_callers = api_callers[api_group]
        if group_callers:
            details.append(_caller_detail(group_callers))
        component_id = node_id("api", api_group)
        api_paths = api_member_paths[api_group]
        api_nodes[api_group] = component_id
        api_files[component_id] = api_paths | {caller.path for caller in group_callers}
        entry_files[component_id] = api_paths
        entry_starts[component_id] = api_paths | {
            target for caller in group_callers for target in caller.targets
        }
        caller_only = not api_paths
        caller_link = next(
            (
                caller.owner_page
                for caller in sorted(group_callers, key=lambda item: item.path)
                if caller.owner_page is not None
            ),
            None,
        )
        nodes.append(
            Node(
                id=component_id,
                label=f"{_humanize(api_group)} API",
                source=details[0].sources[0],
                link=caller_link if caller_only else None,
                group="group-http-api",
                details=details,
            )
        )
        component_files[component_id] = set(api_paths)
        component_roles[component_id] = "entry"

    worker_records: defaultdict[tuple[str, str], list[tuple[str, Worker]]] = (
        defaultdict(list)
    )
    worker_member_paths: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    worker_callers: defaultdict[tuple[str, str], list[_Caller]] = defaultdict(list)
    for path, file_facts in facts.items():
        directory = PurePosixPath(path).parent.as_posix()
        for worker in file_facts.workers:
            family = "task_executor" if worker.kind == "task_executor" else "temporal"
            worker_records[(directory, family)].append((path, worker))
            worker_member_paths[(directory, family)].add(path)
    for caller in callers:
        caller_facts = component_facts[caller.path]
        directory = PurePosixPath(caller.path).parent.as_posix()
        for worker in caller_facts.workers:
            family = "task_executor" if worker.kind == "task_executor" else "temporal"
            key = (directory, family)
            worker_records[key].append((caller.path, worker))
            worker_callers[key].append(caller)
    for (directory, family), records in sorted(worker_records.items()):
        records.sort(key=lambda item: (item[1].name, item[0], item[1].line))
        group_name = "group-background-workers"
        component_id = node_id(family, directory)
        component_files_for_node = worker_member_paths[(directory, family)]
        details = _bounded_details(
            [(worker.name, _source(path, worker.line)) for path, worker in records],
            "workers" if family == "task_executor" else "workflows",
        )
        group_callers = worker_callers[(directory, family)]
        if group_callers:
            details.append(_caller_detail(group_callers))
        caller_only = not component_files_for_node
        caller_link = next(
            (
                caller.owner_page
                for caller in sorted(group_callers, key=lambda item: item.path)
                if caller.owner_page is not None
            ),
            None,
        )
        nodes.append(
            Node(
                id=component_id,
                label=_worker_label(directory, records, family),
                source=details[0].sources[0],
                link=caller_link if caller_only else None,
                group=group_name,
                details=details,
            )
        )
        component_files[component_id] = set(component_files_for_node)
        component_roles[component_id] = "entry"
        entry_files[component_id] = component_files_for_node
        entry_starts[component_id] = set(component_files_for_node) | {
            target for caller in group_callers for target in caller.targets
        }

    entry_ids_by_path: defaultdict[str, set[str]] = defaultdict(set)
    for component_id, paths in entry_files.items():
        for path in paths:
            entry_ids_by_path[path].add(component_id)

    call_edges: defaultdict[str, set[str]] = defaultdict(set)
    feature_paths = set(feature_file_by_path)
    for file in feature.files:
        for evidence in file.evidence:
            if (
                evidence.kind == "call"
                and evidence.to is not None
                and evidence.path in feature_paths
                and evidence.to in feature_paths
            ):
                call_edges[evidence.path].add(evidence.to)
    reached_by_entry: dict[str, set[str]] = {}
    for component_id, own_files in entry_starts.items():
        reached = set(own_files)
        pending = sorted(own_files)
        cursor = 0
        while cursor < len(pending):
            current = pending[cursor]
            cursor += 1
            owners = entry_ids_by_path.get(current, set())
            if owners and component_id not in owners:
                continue
            for target in sorted(call_edges[current]):
                owners = entry_ids_by_path.get(target, set())
                if owners and component_id not in owners:
                    continue
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        reached_by_entry[component_id] = reached
    reached_from_entries = (
        set().union(*reached_by_entry.values()) if reached_by_entry else set()
    )

    library_rows = []
    library_files: defaultdict[str, list[FeatureFile]] = defaultdict(list)
    for path in sorted(feature_paths - reached_from_entries):
        if path.startswith("backend/"):
            library_files[PurePosixPath(path).parent.as_posix()].append(
                feature_file_by_path[path]
            )
    for directory, files in sorted(
        library_files.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        paths = {file.path for file in files}
        table_evidence = [
            evidence
            for file in files
            for evidence in file.evidence
            if evidence.kind == "table" and evidence.table is not None
        ]
        external_records = [
            (path, external)
            for path in sorted(paths)
            for external in facts[path].externals
        ]
        if not table_evidence and not external_records:
            continue
        sources = [_source(evidence.path, evidence.line) for evidence in table_evidence]
        sources.extend(
            _source(path, external.line) for path, external in external_records
        )
        source = min(sources, key=lambda item: (item.path, item.lines[0]))
        library_row = _LibraryRow(
            label=f"{_humanize(PurePosixPath(directory).name)} (library)",
            tables=tuple(
                sorted(
                    {
                        evidence.table
                        for file in files
                        for evidence in file.evidence
                        if evidence.kind == "table" and evidence.table in feature.tables
                    }
                )
            ),
            services=tuple(
                sorted({external.service for _, external in external_records})
            ),
            sources=tuple(_unique_sources(sources)),
        )
        if entry_files:
            library_rows.append(library_row)
            continue
        component_id = node_id("library", directory)
        nodes.append(
            Node(
                id=component_id,
                label=library_row.label,
                source=source,
                group="group-library-code",
            )
        )
        component_files[component_id] = paths
        component_roles[component_id] = "library"

    data_component_files = {
        component_id: (
            reached_by_entry[component_id]
            if component_roles[component_id] == "entry"
            else component_files[component_id]
        )
        for component_id in component_files
        if component_roles[component_id] in {"entry", "library"}
    }
    table_sources_by_component: defaultdict[tuple[str, str], list[CodeSource]] = (
        defaultdict(list)
    )
    service_sources_by_component: defaultdict[tuple[str, str], list[CodeSource]] = (
        defaultdict(list)
    )
    for component_id, paths in data_component_files.items():
        for path in sorted(paths):
            file = feature_file_by_path[path]
            for evidence in file.evidence:
                if (
                    evidence.kind == "table"
                    and evidence.table in feature.tables
                    and evidence.table is not None
                ):
                    table_sources_by_component[(component_id, evidence.table)].append(
                        _source(evidence.path, evidence.line)
                    )
            for external in facts[path].externals:
                service_sources_by_component[(component_id, external.service)].append(
                    _source(path, external.line)
                )
    table_uses_by_node = {
        component_id: tuple(
            sorted(
                table
                for owner, table in table_sources_by_component
                if owner == component_id
            )
        )
        for component_id in data_component_files
    }
    service_uses_by_node = {
        component_id: tuple(
            sorted(
                service
                for owner, service in service_sources_by_component
                if owner == component_id
            )
        )
        for component_id in data_component_files
    }

    table_store_ids: dict[str, str] = {}
    store_tables_by_node: dict[str, tuple[str, ...]] = {}
    if len(table_sources_by_component) <= 12:
        for table_name in feature.tables:
            store_id = node_id("store", table_name)
            table_store_ids[table_name] = store_id
            store_tables_by_node[store_id] = (table_name,)
            nodes.append(
                Node(
                    id=store_id,
                    label=table_name,
                    source=tables[table_name].source,
                    kind="store",
                    group="group-database",
                )
            )
    else:
        store_id = "database"
        table_store_ids = {table_name: store_id for table_name in feature.tables}
        store_tables_by_node[store_id] = tuple(feature.tables)
        table_records = [
            (table_name, tables[table_name].source) for table_name in feature.tables
        ]
        nodes.append(
            Node(
                id=store_id,
                label=f"Database ({len(feature.tables)} tables)",
                source=tables[feature.tables[0]].source,
                kind="store",
                group="group-database",
                details=_bounded_details(table_records, "tables"),
            )
        )

    edges = []
    if web_files:
        route_pairs: defaultdict[str, dict[str, list[FeatureEvidence]]] = defaultdict(
            lambda: {"web": [], "backend": []}
        )
        for file in feature.files:
            for evidence in file.evidence:
                if evidence.kind != "route" or evidence.tag is None:
                    continue
                if evidence.path.startswith("web/"):
                    route_pairs[evidence.tag]["web"].append(evidence)
                elif evidence.path.startswith("backend/"):
                    route_pairs[evidence.tag]["backend"].append(evidence)
        web_id = next(
            node.id
            for node in nodes
            if node.label == "Web app" and node.group == "group-web-app"
        )
        for api_group, component_id in sorted(api_nodes.items()):
            paired_sources = [
                _source(web_evidence.path, web_evidence.line)
                for pairs in route_pairs.values()
                for web_evidence in pairs["web"]
                if web_evidence.path in web_files
                for backend_evidence in pairs["backend"]
                if backend_evidence.path in api_files[component_id]
            ]
            if paired_sources:
                edges.append(
                    Edge(
                        src=web_id,
                        dst=component_id,
                        label="HTTP",
                        source=min(
                            paired_sources,
                            key=lambda source: (source.path, source.lines[0]),
                        ),
                    )
                )

    if len(table_sources_by_component) <= 12:
        for (component_id, table_name), sources in sorted(
            table_sources_by_component.items()
        ):
            edges.append(
                Edge(
                    src=component_id,
                    dst=table_store_ids[table_name],
                    label="reads/writes",
                    source=min(
                        sources, key=lambda source: (source.path, source.lines[0])
                    ),
                )
            )
    else:
        for component_id, table_names in sorted(table_uses_by_node.items()):
            used_tables = [table for table in table_names if table in feature.tables]
            if not used_tables:
                continue
            sources = [
                source
                for table_name in used_tables
                for source in table_sources_by_component[(component_id, table_name)]
            ]
            edges.append(
                Edge(
                    src=component_id,
                    dst="database",
                    label="reads/writes",
                    source=min(
                        sources, key=lambda source: (source.path, source.lines[0])
                    ),
                )
            )

    all_services = sorted({service for _, service in service_sources_by_component})
    for service in all_services:
        service_id = node_id("external", service)
        sources = [
            source
            for (component_id, used_service), component_sources in (
                service_sources_by_component.items()
            )
            if used_service == service
            for source in component_sources
        ]
        source = min(sources, key=lambda item: (item.path, item.lines[0]))
        nodes.append(
            Node(
                id=service_id,
                label=service,
                source=source,
                kind="external",
                group="group-external-services",
            )
        )
        service_uses_by_node[service_id] = (service,)
        for component_id, used_service in sorted(service_sources_by_component):
            if used_service != service:
                continue
            component_sources = service_sources_by_component[
                (component_id, used_service)
            ]
            edges.append(
                Edge(
                    src=component_id,
                    dst=service_id,
                    label=f"calls {service}",
                    source=min(
                        component_sources,
                        key=lambda item: (item.path, item.lines[0]),
                    ),
                )
            )

    groups = []
    if web_files:
        web_node = next(node for node in nodes if node.group == "group-web-app")
        groups.append(
            Group(
                id="group-web-app",
                label="Web app",
                source=web_node.source,
            )
        )
    entry_group_specs = (
        ("group-http-api", "HTTP API"),
        ("group-background-workers", "Background workers"),
        ("group-library-code", "Library code"),
    )
    if any(
        node.group in {group_id for group_id, _ in entry_group_specs} for node in nodes
    ):
        entry_source = next(
            node.source
            for node in nodes
            if node.group in {group_id for group_id, _ in entry_group_specs}
        )
        groups.append(
            Group(
                id="column-entry-points",
                label="Entry points",
                source=entry_source,
            )
        )
        for group_id, label in entry_group_specs:
            members = [node for node in nodes if node.group == group_id]
            if members:
                groups.append(
                    Group(
                        id=group_id,
                        label=label,
                        source=members[0].source,
                        parent="column-entry-points",
                    )
                )
    data_group_specs = (
        ("group-database", "Database"),
        ("group-external-services", "External services"),
    )
    if any(
        node.group in {group_id for group_id, _ in data_group_specs} for node in nodes
    ):
        data_source = next(
            node.source
            for node in nodes
            if node.group in {group_id for group_id, _ in data_group_specs}
        )
        groups.append(
            Group(
                id="column-data-services",
                label="Data & services",
                source=data_source,
            )
        )
        for group_id, label in data_group_specs:
            members = [node for node in nodes if node.group == group_id]
            if members:
                groups.append(
                    Group(
                        id=group_id,
                        label=label,
                        source=members[0].source,
                        parent="column-data-services",
                    )
                )

    diagram = BlockDiagram(groups=groups, nodes=nodes, edges=edges)
    problems = block_layout_problems(diagram)
    if problems:
        raise ValueError(f"feature '{feature.id}' block layout problems: {problems}")
    table_uses_by_node = {
        **table_uses_by_node,
        **store_tables_by_node,
    }
    return _FeatureBlock(
        diagram=diagram,
        tables_by_node=table_uses_by_node,
        services_by_node=service_uses_by_node,
        callers=callers,
        library_rows=tuple(library_rows),
    )


_RELATION_PRIORITY = {
    "fk": 0,
    "primaryjoin": 1,
    "comparison": 2,
    "id_column": 3,
    "commented_fk": 4,
}
_RELATION_LABELS = {
    "fk": ("model ForeignKey", "symbolic"),
    "primaryjoin": ("ORM join", "symbolic"),
    "comparison": ("query join", "symbolic"),
    "id_column": ("ID column name", "symbolic"),
    "commented_fk": ("commented-out FK", "symbolic"),
}


def _table_relations(links: Collection[TableLink]) -> list[Relation]:
    strongest: dict[tuple[str, str], TableLink] = {}
    for link in links:
        if link.signal == "same_file" or link.signal.endswith(":ambiguous"):
            continue
        pair = tuple(sorted((link.a, link.b)))
        current = strongest.get(pair)
        candidate_key = (
            _RELATION_PRIORITY.get(link.signal, 5),
            link.path,
            link.line,
            link.signal,
        )
        current_key = (
            (
                _RELATION_PRIORITY.get(current.signal, 5),
                current.path,
                current.line,
                current.signal,
            )
            if current is not None
            else None
        )
        if current is None or candidate_key < current_key:
            strongest[pair] = link
    relations = []
    for (src, dst), link in sorted(strongest.items()):
        label, kind = _RELATION_LABELS.get(
            link.signal,
            (link.signal, "symbolic"),
        )
        relations.append(
            Relation(
                src=src,
                dst=dst,
                label=label,
                kind=kind,
                source=_source(link.path, link.line),
            )
        )
    return relations


def _feature_relations(feature: Feature) -> list[Relation]:
    return _table_relations(feature.table_links)


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
    component_facts: Mapping[str, FileFacts],
    block: _FeatureBlock,
) -> Tldr:
    result = _feature_tldr(feature, tables, component_facts, block)
    result.notes = _feature_shared_notes(feature, feature_map, names, tables)
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
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    primary_features: Mapping[str, tuple[str, str]],
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
    block = _feature_block(
        feature,
        tables,
        component_facts,
        component_imports,
        primary_features,
    )
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
            component_facts,
            block,
        ),
        block=block.diagram,
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
    component_facts: Mapping[str, FileFacts],
) -> tuple[BlockDiagram, list[BlockFigure]]:
    nodes = []
    edges = []
    for feature in feature_map.features:
        facts = _feature_facts(feature, component_facts)
        endpoints, workers, externals = _runtime_records(facts)
        endpoints_by_group: defaultdict[str, list[tuple[str, Endpoint]]] = defaultdict(
            list
        )
        for path, endpoint in endpoints:
            group = facts[path].api_group or PurePosixPath(path).stem
            endpoints_by_group[group].append((path, endpoint))
        services = sorted({external.service for _, external in externals})
        web_paths = sorted(path for path in facts if path.startswith("web/"))
        page_id = f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}"
        feature_source = (
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
        endpoint_sources = [
            _source(path, endpoint.line)
            for group in sorted(endpoints_by_group)
            for path, endpoint in [
                min(
                    endpoints_by_group[group],
                    key=lambda item: (
                        item[1].path,
                        item[1].method,
                        item[0],
                        item[1].line,
                    ),
                )
            ]
        ]
        details = []
        if endpoints:
            details.append(
                Claim(
                    text=f"{len(endpoints)} HTTP endpoints",
                    sources=_unique_sources(endpoint_sources),
                )
            )
        if workers:
            details.append(
                Claim(
                    text=f"{len(workers)} workers / workflows",
                    sources=_unique_sources(
                        [_source(path, worker.line) for path, worker in workers]
                    ),
                )
            )
        if web_paths:
            details.append(
                Claim(
                    text=f"{len(web_paths)} web screens",
                    sources=_unique_sources(
                        [
                            _file_evidence_source(
                                next(
                                    file for file in feature.files if file.path == path
                                ),
                                tables[feature.id].source,
                            )
                            for path in web_paths
                        ]
                    ),
                )
            )
        if services:
            details.append(
                Claim(
                    text=f"Calls {', '.join(services)}",
                    sources=_unique_sources(
                        [_source(path, external.line) for path, external in externals]
                    ),
                )
            )
        feature_node_id = f"feature-{feature.id}"
        nodes.append(
            Node(
                id=feature_node_id,
                label=_feature_name(feature, names),
                source=feature_source,
                link=page_id,
                group="group-features",
                details=details,
            )
        )
        table_records = [
            (table_name, tables[table_name].source) for table_name in feature.tables
        ]
        store_id = f"store-feature-{_component_slug(feature.id)}"
        nodes.append(
            Node(
                id=store_id,
                label=f"{_feature_name(feature, names)} tables",
                source=tables[feature.tables[0]].source,
                kind="store",
                group="group-database",
                details=_bounded_details(table_records, "tables"),
            )
        )
        edges.append(
            Edge(
                src=feature_node_id,
                dst=store_id,
                label="owns",
                source=tables[feature.tables[0]].source,
            )
        )

    feature_external_sources: defaultdict[tuple[str, str], list[CodeSource]] = (
        defaultdict(list)
    )
    service_sources: defaultdict[str, list[CodeSource]] = defaultdict(list)
    for feature in feature_map.features:
        facts = _feature_facts(feature, component_facts)
        for path, external in _runtime_records(facts)[2]:
            source = _source(path, external.line)
            feature_external_sources[(feature.id, external.service)].append(source)
            service_sources[external.service].append(source)
    service_node_ids = {}
    for service in sorted(service_sources):
        service_id = f"external-service-{_component_slug(service)}"
        service_node_ids[service] = service_id
        sources = service_sources[service]
        nodes.append(
            Node(
                id=service_id,
                label=service,
                source=min(sources, key=lambda source: (source.path, source.lines[0])),
                kind="external",
                group="group-external-services",
            )
        )
    feature_node_ids = {
        feature.id: f"feature-{feature.id}" for feature in feature_map.features
    }
    for (feature_id, service), sources in sorted(feature_external_sources.items()):
        edges.append(
            Edge(
                src=feature_node_ids[feature_id],
                dst=service_node_ids[service],
                label="calls",
                source=min(sources, key=lambda source: (source.path, source.lines[0])),
            )
        )

    groups = []
    feature_nodes = [node for node in nodes if node.group == "group-features"]
    if feature_nodes:
        groups.append(
            Group(
                id="group-features",
                label="Features",
                source=feature_nodes[0].source,
            )
        )
    data_nodes = [
        node
        for node in nodes
        if node.group in {"group-database", "group-external-services"}
    ]
    if data_nodes:
        groups.append(
            Group(
                id="column-data-services",
                label="Data & services",
                source=data_nodes[0].source,
            )
        )
        store_nodes = [node for node in data_nodes if node.group == "group-database"]
        if store_nodes:
            groups.append(
                Group(
                    id="group-database",
                    label="Database",
                    source=store_nodes[0].source,
                    parent="column-data-services",
                )
            )
        external_nodes = [
            node for node in data_nodes if node.group == "group-external-services"
        ]
        if external_nodes:
            groups.append(
                Group(
                    id="group-external-services",
                    label="External services",
                    source=external_nodes[0].source,
                    parent="column-data-services",
                )
            )
    block = BlockDiagram(groups=groups, nodes=nodes, edges=edges)
    problems = block_layout_problems(block)
    if problems:
        raise ValueError(
            f"domain '{feature_map.domain}' block layout problems: {problems}"
        )
    return block, []


def _domain_tldr(
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    primary_features: Mapping[str, tuple[str, str]],
    domain_titles: Mapping[str, str],
    table_domains: Mapping[str, str],
) -> Tldr:
    table_names = sorted(
        {table for feature in feature_map.features for table in feature.tables}
    )
    table_sources = _unique_sources([tables[name].source for name in table_names])
    endpoint_records = {}
    worker_records = {}
    web_sources = {}
    external_records = {}
    feature_metrics = {}
    reached_metrics = {}
    reached_sources = []
    for feature in feature_map.features:
        facts = _feature_facts(feature, component_facts)
        endpoints, workers, externals = _runtime_records(facts)
        feature_metrics[feature.id] = (endpoints, workers, externals)
        callers = _feature_callers(
            feature,
            component_facts,
            component_imports,
            primary_features,
        )
        caller_endpoints, caller_workers = _caller_records(callers, component_facts)
        unique_caller_endpoints = {
            (path, endpoint.method, endpoint.path, endpoint.handler, endpoint.line)
            for path, endpoint in caller_endpoints
        }
        unique_caller_workers = {
            (path, worker.kind, worker.name, worker.line)
            for path, worker in caller_workers
        }
        reached_metrics[feature.id] = len(unique_caller_endpoints) + len(
            unique_caller_workers
        )
        for path, endpoint in caller_endpoints:
            reached_sources.append(_source(path, endpoint.line))
        for path, worker in caller_workers:
            reached_sources.append(_source(path, worker.line))
        for caller in callers:
            reached_sources.extend(caller.import_sources)
        for path, endpoint in endpoints:
            endpoint_records[
                (path, endpoint.method, endpoint.path, endpoint.handler, endpoint.line)
            ] = _source(path, endpoint.line)
        for path, worker in workers:
            worker_records[(path, worker.kind, worker.name, worker.line)] = _source(
                path, worker.line
            )
        for path in facts:
            if path.startswith("web/"):
                web_sources[path] = _file_evidence_source(
                    next(file for file in feature.files if file.path == path),
                    tables[feature.id].source,
                )
        for path, external in externals:
            external_records[
                (path, external.service, external.module, external.line)
            ] = _source(path, external.line)
    runtime_sources = _unique_sources(
        [
            *endpoint_records.values(),
            *worker_records.values(),
            *web_sources.values(),
            *external_records.values(),
            *table_sources,
        ]
    )
    summary = [
        Claim(
            text=(
                f"{len(feature_map.features)} features with "
                f"{len(endpoint_records)} HTTP endpoints, "
                f"{len(worker_records)} workers and workflows, "
                f"{len(web_sources)} web screens."
            ),
            sources=runtime_sources,
        )
    ]
    all_services = sorted({service for _, service, _, _ in external_records})
    if all_services:
        summary.append(
            Claim(
                text=f"Outside services: {', '.join(all_services)}.",
                sources=_unique_sources(list(external_records.values())),
            )
        )
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
    row_sources = list(reached_sources)
    for row_number, feature in enumerate(feature_map.features):
        endpoints, workers, externals = feature_metrics[feature.id]
        services = sorted({external.service for _, external in externals})
        rows.append(
            [
                _feature_name(feature, names),
                str(len(endpoints)),
                str(len(workers)),
                str(reached_metrics[feature.id]),
                str(len(feature.tables)),
                ", ".join(services) or "—",
            ]
        )
        links.append(
            SummaryTableLink(
                row=row_number,
                column=0,
                page=f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}",
            )
        )
        row_sources.extend(_source(path, endpoint.line) for path, endpoint in endpoints)
        row_sources.extend(_source(path, worker.line) for path, worker in workers)
        row_sources.extend(_source(path, external.line) for path, external in externals)
        row_sources.extend(tables[table_name].source for table_name in feature.tables)
        if not feature.files:
            row_sources.append(tables[feature.id].source)
    notes = [
        Claim(
            text=f"{len(feature_map.uncovered)} in-scope files are uncovered.",
            sources=table_sources,
        )
    ]
    primary_owner = {
        file.path: feature.id
        for feature in feature_map.features
        for file in feature.files
        if file.primary
    }
    imports: defaultdict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for source_feature, target_feature, line, path, _target in _domain_calls(
        feature_map,
        primary_owner,
    ):
        imports[(source_feature, target_feature)].append((path, line))
    import_notes = sorted(
        imports.items(),
        key=lambda item: (
            -len(item[1]),
            _feature_name(
                next(
                    feature
                    for feature in feature_map.features
                    if feature.id == item[0][0]
                ),
                names,
            ),
            _feature_name(
                next(
                    feature
                    for feature in feature_map.features
                    if feature.id == item[0][1]
                ),
                names,
            ),
        ),
    )
    feature_by_id = {feature.id: feature for feature in feature_map.features}
    notes.extend(
        Claim(
            text=(
                f"{_feature_name(feature_by_id[source_feature], names)} imports "
                f"code from {_feature_name(feature_by_id[target_feature], names)} "
                f"({len(sources)} imports)."
            ),
            sources=[_source(*min(sources))],
        )
        for (source_feature, target_feature), sources in import_notes
    )
    external_rows = []
    external_links = []
    external_sources = []
    for link in feature_map.external_links:
        a_domain = table_domains.get(link.a)
        b_domain = table_domains.get(link.b)
        if (
            a_domain is None
            or b_domain is None
            or a_domain == b_domain
            or feature_map.domain not in {a_domain, b_domain}
        ):
            continue
        own_table, other_table = (
            (link.a, link.b)
            if a_domain == feature_map.domain
            else (link.b, link.a)
        )
        other_domain = b_domain if a_domain == feature_map.domain else a_domain
        external_rows.append(
            [
                own_table,
                other_table,
                domain_titles.get(other_domain, _humanize(other_domain)),
                _RELATION_LABELS.get(link.signal, (link.signal, "symbolic"))[0],
            ]
        )
        external_links.append(
            SummaryTableLink(
                row=len(external_rows) - 1,
                column=2,
                page=f"domain-{other_domain}",
            )
        )
        external_sources.append(_source(link.path, link.line))
    additional_tables = (
        [
            SummaryTable(
                title="Links to other domains",
                columns=["This table", "Other table", "Other domain", "Signal"],
                rows=external_rows,
                links=external_links,
                sources=_unique_sources(external_sources),
            )
        ]
        if external_rows
        else None
    )
    return Tldr(
        summary=summary,
        key_points=key_points,
        table=SummaryTable(
            columns=[
                "Feature",
                "Endpoints",
                "Workers",
                "Reached from",
                "Tables",
                "Outside services",
            ],
            rows=rows,
            links=links,
            sources=_unique_sources([*row_sources, *table_sources]),
        ),
        notes=notes,
        additional_tables=additional_tables,
    )


def _domain_data(
    feature_map: FeatureMap,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
) -> DataModel:
    relations = _table_relations(feature_map.cross_links)
    feature_by_table = {
        table: feature.id
        for feature in feature_map.features
        for table in feature.tables
    }
    relation_tables: defaultdict[str, set[str]] = defaultdict(set)
    for relation in relations:
        for table in (relation.src, relation.dst):
            feature_id = feature_by_table.get(table)
            if feature_id is not None:
                relation_tables[feature_id].add(table)
    domains = []
    for feature in feature_map.features:
        users: Counter[str] = Counter()
        for file in feature.files:
            for evidence in file.evidence:
                if evidence.kind == "table" and evidence.table is not None:
                    users[evidence.table] += 1
        key_tables = set(
            sorted(feature.tables, key=lambda table: (-users[table], table))[:3]
        )
        key_tables.update(relation_tables[feature.id])
        domains.append(
            SchemaDomain(
                id=feature.id,
                title=_feature_name(feature, names),
                tables=feature.tables,
                key_tables=sorted(
                    key_tables,
                    key=lambda table: (-users[table], table),
                ),
                page=f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}",
            )
        )
    return DataModel(domains=domains, relations=relations)


def _domain_page(
    feature_map: FeatureMap,
    *,
    root_id: str,
    domain_title: str,
    names: Mapping[str, str],
    tables: Mapping[str, Table],
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    primary_features: Mapping[str, tuple[str, str]],
    domain_titles: Mapping[str, str],
    table_domains: Mapping[str, str],
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
    block, figures = _domain_block(feature_map, names, tables, component_facts)
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
        tldr=_domain_tldr(
            feature_map,
            names,
            tables,
            component_facts,
            component_imports,
            primary_features,
            domain_titles,
            table_domains,
        ),
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
    component_facts: Mapping[str, FileFacts] | None = None,
    component_imports: Mapping[str, Mapping[str, int]] | None = None,
    primary_features: Mapping[str, tuple[str, str]] | None = None,
    domain_titles: Mapping[str, str] | None = None,
    table_domains: Mapping[str, str] | None = None,
) -> list[Page]:
    runtime_facts = component_facts or {}
    runtime_imports = component_imports or {}
    primary_feature_owners = primary_features or {}
    pages = [
        _domain_page(
            feature_map,
            root_id=root_id,
            domain_title=domain_title,
            names=names,
            tables=tables,
            component_facts=runtime_facts,
            component_imports=runtime_imports,
            primary_features=primary_feature_owners,
            domain_titles=domain_titles or {},
            table_domains=table_domains or {},
        )
    ]
    pages.extend(
        _feature_page(
            feature,
            feature_map,
            domain_title=domain_title,
            names=names,
            tables=tables,
            component_facts=runtime_facts,
            component_imports=runtime_imports,
            primary_features=primary_feature_owners,
        )
        for feature in feature_map.features
    )
    return pages
