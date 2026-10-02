from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rox_dox.components import FileFacts, TaskConsumer, TaskType, Worker, collect_task_facts
from rox_dox.features import FeatureEvidence, FeatureFile
from rox_dox.model import BlockDiagram, Claim, CodeSource, Edge, Group, Node


@dataclass(frozen=True)
class ComponentProjection:
    diagram: BlockDiagram
    tables_by_node: Mapping[str, tuple[str, ...]]
    services_by_node: Mapping[str, tuple[str, ...]]
    kinds_by_node: Mapping[str, str]


def _source(path: str, line: int) -> CodeSource:
    return CodeSource(path=path, lines=(line, line))


def _source_key(source: CodeSource) -> tuple[str, int, int]:
    return source.path, source.lines[0], source.lines[1]


def _first_source(sources: Collection[CodeSource]) -> CodeSource:
    return min(sources, key=_source_key)


def _unique_sources(sources: Iterable[CodeSource]) -> list[CodeSource]:
    unique = {_source_key(source): source for source in sources}
    return [unique[key] for key in sorted(unique)]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _catalog_source(entry: Mapping[str, Any]) -> CodeSource | None:
    source = entry.get("source")
    if not isinstance(source, Mapping):
        return None
    path = source.get("path")
    lines = source.get("lines")
    if isinstance(path, str) and isinstance(lines, list) and len(lines) == 2:
        return CodeSource(path=path, lines=(int(lines[0]), int(lines[1])))
    return None


def _catalog_ids_by_match(
    catalog: Sequence[Mapping[str, Any]],
    match_key: str,
) -> dict[str, str]:
    return {
        str(value): str(entry["id"])
        for entry in catalog
        for value in entry.get("match", {}).get(match_key, [])
    }


def _task_component_id(
    task: TaskType,
    queue_class_components: Mapping[str, str],
    target_components: Mapping[str, str],
) -> str | None:
    if task.queue_class in queue_class_components:
        return queue_class_components[task.queue_class]
    if task.deploy_target is not None:
        return target_components.get(task.deploy_target)
    return None


def _endpoint_component_ids(
    path: str,
    facts: FileFacts,
    catalog_by_id: Mapping[str, Mapping[str, Any]],
    target_components: Mapping[str, str],
) -> set[str]:
    matches = []
    for endpoint in facts.endpoints:
        component_id = (
            target_components.get(endpoint.deploy_target)
            if endpoint.deploy_target is not None
            else None
        )
        if component_id is None:
            component_id = next(
                (
                    str(entry["id"])
                    for entry in catalog_by_id.values()
                    if any(
                        path.startswith(prefix)
                        for prefix in entry.get("match", {}).get("path_prefixes", [])
                    )
                ),
                None,
            )
        if component_id is not None:
            matches.append(component_id)
    return set(matches)


def _entry_component_ids(
    path: str,
    facts: FileFacts,
    catalog_by_id: Mapping[str, Mapping[str, Any]],
    target_components: Mapping[str, str],
    queue_class_components: Mapping[str, str],
    consumers_by_executor: Mapping[str, Collection[TaskConsumer]],
    task_types: Mapping[str, TaskType],
) -> set[str]:
    matches = set()
    for entry in catalog_by_id.values():
        if entry.get("match", {}).get("web_files") and path.startswith("web/"):
            matches.add(str(entry["id"]))
    matches.update(
        _endpoint_component_ids(path, facts, catalog_by_id, target_components)
    )
    for worker in facts.workers:
        for entry in catalog_by_id.values():
            if worker.kind in entry.get("match", {}).get("worker_kinds", []):
                matches.add(str(entry["id"]))
        if worker.kind != "task_executor":
            continue
        for consumer in consumers_by_executor.get(worker.name, []):
            task = task_types.get(consumer.task_type)
            if task is None:
                continue
            component_id = _task_component_id(
                task,
                queue_class_components,
                target_components,
            )
            if component_id is not None:
                matches.add(component_id)
    return matches


def _scope_import_closure(
    start: str,
    scope_paths: set[str],
    imports: Mapping[str, Mapping[str, int]],
) -> set[str]:
    reached = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for target in sorted(set(imports.get(current, {})) & scope_paths):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return reached


def _add_detail(
    details: defaultdict[str, defaultdict[str, list[CodeSource]]],
    node_id: str,
    text: str,
    source: CodeSource,
) -> None:
    details[node_id][text].append(source)


def _detail_claims(
    details: Mapping[str, Collection[CodeSource]],
    limit: int = 3,
) -> list[Claim]:
    items = [
        Claim(
            text=text,
            sources=_unique_sources(sources),
        )
        for text, sources in sorted(details.items())
        if sources
    ]
    if len(items) <= limit:
        return items
    overflow = items[limit:]
    overflow_sources = _unique_sources(
        source for item in overflow for source in item.sources
    )
    return [
        *items[:limit],
        Claim(text=f"+{len(overflow)} more", sources=overflow_sources),
    ]


def _task_target_detail(target: str, task_names: list[str]) -> str:
    prefix = f"{target}: "
    listed_names = task_names[:3]
    while listed_names:
        omitted_count = len(task_names) - len(listed_names)
        suffix = f" +{omitted_count} more" if omitted_count else ""
        text = f"{prefix}{', '.join(listed_names)}{suffix}"
        if len(text) <= 90:
            return text
        listed_names.pop()
    omitted_count = len(task_names) - 1
    suffix = f" +{omitted_count} more" if omitted_count else ""
    available = max(1, 90 - len(prefix) - len(suffix))
    first_name = task_names[0]
    if len(first_name) > available:
        first_name = (
            f"{first_name[: available - 1]}…" if available > 1 else first_name[:1]
        )
    return f"{prefix}{first_name}{suffix}"[:90]


def _deduplicate_edges(edges: Collection[Edge]) -> list[Edge]:
    grouped: defaultdict[tuple[str, str], list[Edge]] = defaultdict(list)
    for edge in edges:
        grouped[(edge.src, edge.dst)].append(edge)
    result = []
    for (src, dst), records in sorted(grouped.items()):
        labels = {edge.label for edge in records}
        if labels <= {"reads", "writes", "reads + writes"}:
            modes = {
                mode
                for label in labels
                for mode in ("reads", "writes")
                if mode in label
            }
            label = (
                "reads + writes"
                if len(modes) == 2
                else next(iter(modes))
            )
        elif all(label.startswith("calls ") for label in labels):
            services = sorted(
                {
                    service.strip()
                    for label in labels
                    for service in label.removeprefix("calls ").split(",")
                }
            )
            label = f"calls {', '.join(services)}"
        else:
            label = next(iter(labels)) if len(labels) == 1 else " / ".join(sorted(labels))
        result.append(
            Edge(
                src=src,
                dst=dst,
                label=label,
                source=_first_source(_unique_sources(edge.source for edge in records)),
            )
        )
    return result


def _merge_node_group(
    nodes: Collection[Node],
    *,
    node_id: str,
    label: str,
    column: str,
    kind: str,
) -> Node:
    detail_sources: defaultdict[str, list[CodeSource]] = defaultdict(list)
    node_sources = []
    for node in nodes:
        node_sources.append(node.source)
        detail_sources[node.label].append(node.source)
        for detail in node.details:
            detail_sources[detail.text].extend(
                source for source in detail.sources if isinstance(source, CodeSource)
            )
    details = _detail_claims(detail_sources)
    return Node(
        id=node_id,
        label=label,
        source=_first_source(node_sources),
        kind=kind,
        group=f"column-{_slug(column)}",
        many=True,
        details=details,
    )


def _fit_node_budget(
    nodes: list[Node],
    edges: list[Edge],
    catalog_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[Node], list[Edge], dict[str, str], dict[str, str]]:
    node_map = {}
    semantic_kinds = {
        node.id: str(catalog_by_id[node.id].get("kind", node.kind))
        for node in nodes
        if node.id in catalog_by_id
    }
    if len(nodes) > 15:
        provider_nodes = [
            node
            for node in nodes
            if catalog_by_id.get(node.id, {}).get("column") == "Provider APIs"
        ]
        if provider_nodes:
            provider_ids = {node.id for node in provider_nodes}
            nodes = [node for node in nodes if node.id not in provider_ids]
            nodes.append(
                _merge_node_group(
                    provider_nodes,
                    node_id="provider-apis",
                    label="Provider APIs",
                    column="Provider APIs",
                    kind="external",
                )
            )
            node_map.update({node_id: "provider-apis" for node_id in provider_ids})
            semantic_kinds["provider-apis"] = "external"
            edges = _deduplicate_edges(
                [
                    Edge(
                        src=node_map.get(edge.src, edge.src),
                        dst=node_map.get(edge.dst, edge.dst),
                        label=edge.label,
                        source=edge.source,
                    )
                    for edge in edges
                ]
            )
    if len(nodes) > 15:
        worker_nodes = [
            node
            for node in nodes
            if catalog_by_id.get(node.id, {}).get("column")
            == "Background workers"
        ]
        if worker_nodes:
            worker_ids = {node.id for node in worker_nodes}
            nodes = [node for node in nodes if node.id not in worker_ids]
            nodes.append(
                _merge_node_group(
                    worker_nodes,
                    node_id="background-workers",
                    label="Background workers",
                    column="Background workers",
                    kind="component",
                )
            )
            node_map.update({node_id: "background-workers" for node_id in worker_ids})
            semantic_kinds["background-workers"] = "service(many)"
            edges = _deduplicate_edges(
                [
                    Edge(
                        src=node_map.get(edge.src, edge.src),
                        dst=node_map.get(edge.dst, edge.dst),
                        label=edge.label,
                        source=edge.source,
                    )
                    for edge in edges
                ]
            )
    if len(nodes) > 15:
        raise ValueError(f"component diagram has {len(nodes)} boxes; maximum is 15")
    return nodes, edges, node_map, semantic_kinds


def _flow_notes(
    nodes: Collection[Node],
    edges: Collection[Edge],
    catalog_by_id: Mapping[str, Mapping[str, Any]],
) -> list[Claim]:
    nodes_by_id = {node.id: node for node in nodes}
    column_indexes: dict[str, int] = {}
    for index, entry in enumerate(catalog_by_id.values()):
        column_indexes.setdefault(
            f"column-{_slug(str(entry.get('column', '')))}",
            index,
        )
    claims = []
    ordered_edges = sorted(
        edges,
        key=lambda edge: (
            column_indexes.get(nodes_by_id[edge.src].group or "", 0),
            edge.src,
            edge.dst,
            edge.label,
        ),
    )
    for edge in ordered_edges:
        source_node = nodes_by_id[edge.src]
        target_label = nodes_by_id[edge.dst].label
        phrases = []
        for label in edge.label.split(" / "):
            if label == "REST calls":
                phrases.append(f"makes REST calls to {target_label}")
            elif label == "provider events":
                phrases.append(f"sends provider events to {target_label}")
            elif label == "enqueue tasks":
                phrases.append(f"enqueues tasks to {target_label}")
            elif label == "long-poll":
                phrases.append(f"long-polls {target_label}")
            elif label == "start workflow":
                phrases.append(f"starts workflows on {target_label}")
            elif label.startswith("calls "):
                phrases.append(f"{label} through {target_label}")
            elif label in {"reads", "writes", "reads + writes"}:
                phrases.append(f"{label} {target_label}")
        if phrases:
            claims.append(
                Claim(
                    text=f"{source_node.label} {', '.join(phrases)}.",
                    sources=[edge.source],
                )
            )
    if len(claims) <= 6:
        return claims
    remaining_edges = ordered_edges[5:]
    remaining_sources = _unique_sources(edge.source for edge in remaining_edges)
    remaining_nodes = sorted({nodes_by_id[edge.src].label for edge in remaining_edges})
    return [
        *claims[:5],
        Claim(
            text=(
                f"Additional flows from {', '.join(remaining_nodes)} "
                f"({len(remaining_edges)} edges)."
            ),
            sources=remaining_sources,
        ),
    ]


def project_component_diagram(
    scope_files: Collection[FeatureFile],
    *,
    component_catalog: Sequence[Mapping[str, Any]],
    component_facts: Mapping[str, FileFacts],
    component_imports: Mapping[str, Mapping[str, int]],
    table_accesses: Mapping[str, Mapping[str, tuple[int | None, int | None]]],
    scope_tables: Collection[str],
    external_callers: Mapping[str, Collection[str]],
) -> ComponentProjection:
    catalog_by_id = {str(entry["id"]): entry for entry in component_catalog}
    target_components = _catalog_ids_by_match(component_catalog, "deploy_targets")
    queue_class_components = _catalog_ids_by_match(
        component_catalog,
        "queue_type_classes",
    )
    external_components = _catalog_ids_by_match(
        component_catalog,
        "external_services",
    )
    task_facts = collect_task_facts(component_facts)
    task_types = {task.name: task for task in task_facts.task_types}
    consumers_by_executor: defaultdict[str, list[TaskConsumer]] = defaultdict(list)
    workers_by_name: defaultdict[str, list[tuple[str, Worker]]] = defaultdict(list)
    for consumer in task_facts.consumers:
        consumers_by_executor[consumer.executor].append(consumer)
    for path, facts in component_facts.items():
        for worker in facts.workers:
            if worker.kind == "task_executor":
                workers_by_name[worker.name].append((path, worker))
    files_by_path = {
        file.path: file for file in sorted(scope_files, key=lambda item: item.path)
    }
    scope_paths = set(files_by_path)
    scope_table_names = set(scope_tables)
    facts_by_path = {
        path: component_facts.get(
            path,
            FileFacts(
                path=path,
                api_group=None,
                endpoints=[],
                workers=[],
                externals=[],
            ),
        )
        for path in scope_paths
    }

    entry_components_by_path = {
        path: _entry_component_ids(
            path,
            facts,
            catalog_by_id,
            target_components,
            queue_class_components,
            consumers_by_executor,
            task_types,
        )
        for path, facts in facts_by_path.items()
    }
    files_by_component: defaultdict[str, set[str]] = defaultdict(set)
    for path, component_ids in entry_components_by_path.items():
        for component_id in component_ids:
            files_by_component[component_id].update(
                _scope_import_closure(path, scope_paths, component_imports)
            )
    for caller_path, targets in sorted(external_callers.items()):
        caller_facts = component_facts.get(caller_path)
        if caller_facts is None:
            continue
        caller_components = _entry_component_ids(
            caller_path,
            caller_facts,
            catalog_by_id,
            target_components,
            queue_class_components,
            consumers_by_executor,
            task_types,
        )
        for target in sorted(set(targets) & scope_paths):
            for component_id in caller_components:
                files_by_component[component_id].update(
                    _scope_import_closure(target, scope_paths, component_imports)
                )
    reached_paths = {
        path for paths in files_by_component.values() for path in paths
    }
    unreached = sorted(scope_paths - reached_paths)

    edge_sources: defaultdict[tuple[str, str, str], list[CodeSource]] = defaultdict(
        list
    )
    component_table_sources: defaultdict[
        tuple[str, str, str], list[CodeSource]
    ] = defaultdict(list)
    component_tables: defaultdict[str, set[str]] = defaultdict(set)
    component_services: defaultdict[str, set[str]] = defaultdict(set)
    provider_services: defaultdict[str, set[str]] = defaultdict(set)
    details: defaultdict[str, defaultdict[str, list[CodeSource]]] = defaultdict(
        lambda: defaultdict(list)
    )
    endpoint_groups: defaultdict[
        tuple[str, str], dict[tuple[str, str, str, str, int], CodeSource]
    ] = defaultdict(dict)
    task_names_by_component: defaultdict[str, set[str]] = defaultdict(set)
    task_sources_by_component: defaultdict[str, defaultdict[str, list[CodeSource]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    queue_task_names: set[str] = set()
    queue_task_sources: defaultdict[str, list[CodeSource]] = defaultdict(list)
    webhook_id = target_components.get("WEBHOOK")
    provider_push_id = "provider_push" if "provider_push" in catalog_by_id else None
    temporal_id = "temporal" if "temporal" in catalog_by_id else None
    sqs_id = "sqs" if "sqs" in catalog_by_id else None
    postgres_id = "postgres" if "postgres" in catalog_by_id else None

    for path, facts in facts_by_path.items():
        for endpoint in facts.endpoints:
            component_id = (
                target_components.get(endpoint.deploy_target)
                if endpoint.deploy_target is not None
                else None
            )
            if component_id is None:
                candidates = _endpoint_component_ids(
                    path,
                    facts,
                    catalog_by_id,
                    target_components,
                )
                component_id = min(candidates) if candidates else None
            if component_id is not None:
                prefix = "/" + endpoint.path.strip("/").split("/", 1)[0]
                if prefix == "/":
                    prefix = "/"
                endpoint_groups[(component_id, prefix)][
                    (path, endpoint.method, endpoint.path, endpoint.handler, endpoint.line)
                ] = _source(path, endpoint.line)
            if (
                provider_push_id is not None
                and webhook_id is not None
                and endpoint.deploy_target == "WEBHOOK"
            ):
                edge_sources[
                    (provider_push_id, webhook_id, "provider events")
                ].append(_source(path, endpoint.line))

    for component_id, paths in files_by_component.items():
        for path in sorted(paths):
            facts = facts_by_path.get(path, component_facts.get(path))
            if facts is None:
                continue
            for external in facts.externals:
                provider_id = external_components.get(external.service)
                if provider_id is None:
                    continue
                source = _source(path, external.line)
                edge_sources[(component_id, provider_id, f"calls {external.service}")].append(
                    source
                )
                component_services[component_id].add(external.service)
                provider_services[provider_id].add(external.service)
            for line in facts.workflow_starts:
                if temporal_id is not None and component_id != temporal_id:
                    edge_sources[(component_id, temporal_id, "start workflow")].append(
                        _source(path, line)
                    )
            if component_id == temporal_id:
                for worker in facts.workers:
                    if worker.kind in {"temporal_workflow", "temporal_activity"}:
                        _add_detail(
                            details,
                            temporal_id,
                            worker.name,
                            _source(path, worker.line),
                        )
            for producer in facts.task_producers:
                if sqs_id is None:
                    continue
                source = _source(producer.path, producer.line)
                edge_sources[(component_id, sqs_id, "enqueue tasks")].append(source)
                queue_task_names.add(producer.task_type)
                queue_task_sources[producer.task_type].append(source)
            for table, (write_line, read_line) in table_accesses.get(path, {}).items():
                if table not in scope_table_names:
                    continue
                if write_line is not None:
                    source = _source(path, write_line)
                    component_table_sources[(component_id, table, "writes")].append(
                        source
                    )
                    component_tables[component_id].add(table)
                if read_line is not None:
                    source = _source(path, read_line)
                    component_table_sources[(component_id, table, "reads")].append(
                        source
                    )
                    component_tables[component_id].add(table)

    scope_worker_paths = {
        path
        for path in scope_paths
        if any(worker.kind == "task_executor" for worker in facts_by_path[path].workers)
    }
    for consumer in task_facts.consumers:
        task = task_types.get(consumer.task_type)
        if task is None:
            continue
        component_id = _task_component_id(
            task,
            queue_class_components,
            target_components,
        )
        if component_id is None or sqs_id is None:
            continue
        worker_records = [
            (path, worker)
            for path, worker in workers_by_name.get(consumer.executor, [])
            if path in scope_worker_paths
        ]
        if not worker_records and consumer.path not in scope_paths:
            continue
        source = _source(consumer.path, consumer.line)
        queue_task_names.add(task.name)
        queue_task_sources[task.name].append(source)
        task_names_by_component[component_id].add(task.name)
        task_sources_by_component[component_id][
            task.deploy_target or task.queue_class or "Unmapped"
        ].extend([_source(task.path, task.line), source])
        edge_sources[(sqs_id, component_id, "long-poll")].append(source)

    if sqs_id is not None:
        sqs_details: defaultdict[str, list[CodeSource]] = defaultdict(list)
        queue_names_by_label: defaultdict[str, set[str]] = defaultdict(set)
        for task_name in sorted(queue_task_names):
            task = task_types.get(task_name)
            label = (
                task.queue_class or task.queue_type
                if task is not None
                else f"Unmapped: {task_name}"
            )
            sources = (
                [_source(task.path, task.line)]
                if task is not None
                else queue_task_sources[task_name]
            )
            sqs_details[label].extend(sources)
            queue_names_by_label[label].add(task_name)
        for label, names in sorted(queue_names_by_label.items()):
            _add_detail(
                details,
                sqs_id,
                f"{label}: {len(names)} task types",
                _first_source(sqs_details[label]),
            )

    component_table_keys = sorted(
        {(component_id, table) for component_id, table, _ in component_table_sources}
    )
    for component_id, table in component_table_keys:
        sources = [
            *component_table_sources.get((component_id, table, "reads"), []),
            *component_table_sources.get((component_id, table, "writes"), []),
        ]
        if postgres_id is not None and sources:
            component_tables[postgres_id].add(table)
            _add_detail(details, postgres_id, table, _first_source(sources))
    for component_id, task_names in task_names_by_component.items():
        for target, _sources in sorted(task_sources_by_component[component_id].items()):
            task_names_for_target = sorted(
                {
                    task.name
                    for task in task_facts.task_types
                    if task.name in task_names
                    and (task.deploy_target or task.queue_class or "Unmapped") == target
                }
            )
            if not task_names_for_target:
                continue
            _add_detail(
                details,
                component_id,
                _task_target_detail(target, task_names_for_target),
                _first_source(task_sources_by_component[component_id][target]),
            )

    for provider_id, services in provider_services.items():
        for service in services:
            _add_detail(
                details,
                provider_id,
                service,
                _first_source(
                    [
                        source
                        for (src, dst, label), sources in edge_sources.items()
                        if dst == provider_id and label == f"calls {service}"
                        for source in sources
                    ]
                ),
            )
    route_evidence: defaultdict[str, dict[str, list[FeatureEvidence]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for file in scope_files:
        for evidence in file.evidence:
            if evidence.kind == "route" and evidence.tag is not None:
                route_evidence[evidence.tag][
                    "web" if evidence.path.startswith("web/") else "backend"
                ].append(evidence)
    web_id = next(
        (
            str(entry["id"])
            for entry in component_catalog
            if entry.get("match", {}).get("web_files")
        ),
        None,
    )
    for groups in route_evidence.values():
        for web in groups.get("web", []):
            for backend in groups.get("backend", []):
                backend_facts = facts_by_path.get(backend.path)
                if backend_facts is None or web_id is None:
                    continue
                for service_id in _endpoint_component_ids(
                    backend.path,
                    backend_facts,
                    catalog_by_id,
                    target_components,
                ):
                    if catalog_by_id.get(service_id, {}).get("kind") != "service":
                        continue
                    edge_sources[(web_id, service_id, "REST calls")].append(
                        _source(web.path, web.line)
                    )

    for (component_id, table), modes in sorted(
        {
            (component_id, table): {
                mode
                for owner, name, mode in component_table_sources
                if owner == component_id and name == table
            }
            for component_id, table, _ in component_table_sources
        }.items()
    ):
        if postgres_id is None or not modes:
            continue
        label = "reads + writes" if len(modes) == 2 else next(iter(modes))
        edge_sources[(component_id, postgres_id, label)].extend(
            source
            for mode in modes
            for source in component_table_sources[(component_id, table, mode)]
        )

    edges = _deduplicate_edges(
        [
            Edge(src=src, dst=dst, label=label, source=_first_source(sources))
            for (src, dst, label), sources in edge_sources.items()
            if sources and src != dst
        ]
    )
    participating = {edge.src for edge in edges} | {edge.dst for edge in edges}

    endpoint_details: defaultdict[str, defaultdict[str, list[CodeSource]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (component_id, prefix), records in endpoint_groups.items():
        endpoint_details[component_id][
            f"{prefix}: {len(records)} endpoints"
        ].extend(records.values())
    for component_id, detail_map in endpoint_details.items():
        for text, sources in detail_map.items():
            details[component_id][text].extend(sources)

    nodes = []
    semantic_kinds = {}
    for node_id in sorted(participating):
        entry = catalog_by_id.get(node_id, {})
        column = str(entry.get("column", ""))
        group_id = f"column-{_slug(column)}"
        node_details = _detail_claims(
            details.get(node_id, {}),
            limit=4 if node_id == postgres_id else 3,
        )
        incident_sources = [
            edge.source for edge in edges if edge.src == node_id or edge.dst == node_id
        ]
        source = _catalog_source(entry) or _first_source(incident_sources)
        nodes.append(
            Node(
                id=node_id,
                label=str(entry.get("label", node_id)),
                source=source,
                kind=str(entry.get("shape", "component")),
                group=group_id,
                many=bool(entry.get("many", False)),
                details=node_details,
            )
        )
        semantic_kinds[node_id] = str(entry.get("kind", "component"))

    nodes, edges, node_map, semantic_kinds = _fit_node_budget(
        nodes,
        edges,
        catalog_by_id,
    )
    table_values: defaultdict[str, set[str]] = defaultdict(set)
    service_values: defaultdict[str, set[str]] = defaultdict(set)
    for node_id, values in component_tables.items():
        table_values[node_map.get(node_id, node_id)].update(values)
    for node_id, values in component_services.items():
        service_values[node_map.get(node_id, node_id)].update(values)
    for node_id, values in provider_services.items():
        service_values[node_map.get(node_id, node_id)].update(values)
    table_map = {
        node_id: tuple(sorted(values)) for node_id, values in table_values.items()
    }
    service_map = {
        node_id: tuple(sorted(values)) for node_id, values in service_values.items()
    }
    column_indexes = {
        f"column-{_slug(column)}": index
        for index, column in enumerate(
            dict.fromkeys(str(entry.get("column", "")) for entry in component_catalog)
        )
    }
    nodes.sort(key=lambda node: (column_indexes.get(node.group or "", 0), node.id))
    edges.sort(key=lambda edge: (edge.src, edge.dst, edge.label))
    active_node_ids = {node.id for node in nodes}
    semantic_kinds = {
        node_id: kind
        for node_id, kind in semantic_kinds.items()
        if node_id in active_node_ids
    }
    notes = _flow_notes(nodes, edges, catalog_by_id)
    groups = []
    for column in dict.fromkeys(str(entry.get("column", "")) for entry in component_catalog):
        members = [node for node in nodes if node.group == f"column-{_slug(column)}"]
        if members:
            groups.append(
                Group(
                    id=f"column-{_slug(column)}",
                    label=column,
                    source=members[0].source,
                )
            )
    diagram = BlockDiagram(
        notes=notes,
        groups=groups,
        nodes=nodes,
        edges=edges,
        unreached_files=unreached,
    )
    return ComponentProjection(
        diagram=diagram,
        tables_by_node=table_map,
        services_by_node=service_map,
        kinds_by_node=semantic_kinds,
    )
