from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rox_dox.components import (
    FileFacts,
    TaskConsumer,
    TaskType,
    Worker,
    collect_task_facts,
)
from rox_dox.features import FeatureEvidence, FeatureFile
from rox_dox.model import BlockDiagram, Claim, CodeSource, Edge, Group, Node

MAX_FLOW_NOTES = 6
TEMPORAL_WORKFLOW_DETAIL_LIMIT = 2


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


def _reachable_component_candidates(
    seeds: Collection[tuple[str, str, str, int]],
    scope_paths: set[str],
    imports: Mapping[str, Mapping[str, int]],
) -> dict[str, set[tuple[int, str, str]]]:
    reached_by_entry: dict[tuple[str, str], int] = {}
    candidates: defaultdict[str, set[tuple[int, str, str]]] = defaultdict(set)
    pending = deque(sorted(seeds))
    while pending:
        current, entry_path, component_id, distance = pending.popleft()
        key = current, entry_path
        if reached_by_entry.get(key, distance + 1) <= distance:
            continue
        reached_by_entry[key] = distance
        candidates[current].add((distance, component_id, entry_path))
        for target in sorted(set(imports.get(current, {})) & scope_paths):
            pending.append((target, entry_path, component_id, distance + 1))
    return candidates


def _nearest_component_owners(
    candidates: Mapping[str, Collection[tuple[int, str, str]]],
    catalog_order: Mapping[str, int],
) -> dict[str, str]:
    owners = {}
    for path, records in candidates.items():
        nearest_distance = min(distance for distance, _, _ in records)
        entry_counts: defaultdict[str, set[str]] = defaultdict(set)
        for distance, component_id, entry_path in records:
            if distance == nearest_distance:
                entry_counts[component_id].add(entry_path)
        owners[path] = min(
            entry_counts,
            key=lambda component_id: (
                -len(entry_counts[component_id]),
                catalog_order.get(component_id, len(catalog_order)),
                component_id,
            ),
        )
    return owners


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
            label = "reads + writes" if len(modes) == 2 else next(iter(modes))
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
            label = (
                next(iter(labels)) if len(labels) == 1 else " / ".join(sorted(labels))
            )
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
            if catalog_by_id.get(node.id, {}).get("column") == "Background workers"
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
    services_by_node: Mapping[str, Collection[str]],
    backward_edges: Collection[Edge] = (),
) -> list[Claim]:
    nodes_by_id = {node.id: node for node in nodes}
    column_indexes: dict[str, int] = {}
    for entry in catalog_by_id.values():
        group = f"column-{_slug(str(entry.get('column', '')))}"
        column_indexes.setdefault(group, len(column_indexes))
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
    backward_by_component: defaultdict[str, list[Edge]] = defaultdict(list)
    for edge in backward_edges:
        backward_by_component[edge.src].append(edge)
    backward_claims = []
    for component_id, component_edges in sorted(
        backward_by_component.items(),
        key=lambda item: (
            column_indexes.get(
                f"column-{_slug(str(catalog_by_id.get(item[0], {}).get('column', '')))}",
                0,
            ),
            item[0],
        ),
    ):
        component = catalog_by_id.get(component_id, {})
        source_node = nodes_by_id.get(component_id)
        source_label = (
            source_node.label
            if source_node is not None
            else str(component.get("label", component_id))
        )
        if component.get("kind") == "service(many)" and not source_label.endswith(
            "workers"
        ):
            source_label = f"{source_label} workers"
        phrases = []
        for edge in sorted(component_edges, key=lambda item: (item.dst, item.label)):
            target = catalog_by_id.get(edge.dst, {})
            target_node = nodes_by_id.get(edge.dst)
            target_label = (
                target_node.label
                if target_node is not None
                else str(target.get("label", edge.dst))
            )
            if edge.label == "enqueue tasks":
                phrases.append("enqueue follow-up SQS tasks")
            elif edge.label == "start workflow":
                phrases.append("start Temporal workflows")
            elif edge.label == "REST calls":
                phrases.append(f"make REST calls to {target_label}")
            elif edge.label == "API calls":
                phrases.append(f"make API calls to {target_label}")
            elif edge.label == "provider events":
                phrases.append(f"send provider events to {target_label}")
            elif edge.label == "long-poll":
                phrases.append(f"long-poll {target_label}")
            elif edge.label == "reads":
                phrases.append(f"read {target_label}")
            elif edge.label == "writes":
                phrases.append(f"write {target_label}")
            elif edge.label == "reads + writes":
                phrases.append(f"read and write {target_label}")
            else:
                phrases.append(f"{edge.label} {target_label}")
        backward_claims.append(
            Claim(
                text=f"{source_label} also {' and '.join(dict.fromkeys(phrases))}.",
                sources=_unique_sources(edge.source for edge in component_edges),
            )
        )
    for edge in ordered_edges:
        source_node = nodes_by_id[edge.src]
        target_label = nodes_by_id[edge.dst].label
        phrases = []
        for label in edge.label.split(" / "):
            if label == "REST calls":
                verb = "make" if edge.src == "http_clients" else "makes"
                phrases.append(f"{verb} REST calls to {target_label}")
            elif label == "provider events":
                phrases.append(f"sends provider events to {target_label}")
            elif label == "enqueue tasks":
                phrases.append(f"enqueues tasks to {target_label}")
            elif label == "long-poll":
                phrases.append(f"long-polls {target_label}")
            elif label == "start workflow":
                phrases.append(f"starts workflows on {target_label}")
            elif label == "API calls":
                services = sorted(services_by_node.get(edge.dst, ()))
                service_text = f" ({', '.join(services)})" if services else ""
                phrases.append(f"makes API calls to {target_label}{service_text}")
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
    claims = [*backward_claims, *claims]
    if len(claims) <= MAX_FLOW_NOTES:
        return claims
    trailing_claims = claims[MAX_FLOW_NOTES - 1 :]
    return [
        *claims[: MAX_FLOW_NOTES - 1],
        Claim(
            text=(
                "Additional flows include: "
                f"{'; '.join(claim.text.rstrip('.') for claim in trailing_claims)}."
            ),
            sources=_unique_sources(
                source for claim in trailing_claims for source in claim.sources
            ),
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

    catalog_order = {
        str(entry["id"]): index for index, entry in enumerate(component_catalog)
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
    entry_components = {
        path: min(
            component_ids,
            key=lambda component_id: (
                catalog_order.get(component_id, len(catalog_order)),
                component_id,
            ),
        )
        for path, component_ids in entry_components_by_path.items()
        if component_ids
    }
    owner_candidates = _reachable_component_candidates(
        [
            (path, path, component_id, 0)
            for path, component_id in entry_components.items()
        ],
        scope_paths,
        component_imports,
    )
    external_seeds = []
    for caller_path, targets in sorted(external_callers.items()):
        if caller_path in scope_paths:
            continue
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
        seedable_components = [
            component_id
            for component_id in caller_components
            if catalog_by_id.get(component_id, {}).get("kind")
            in {"service", "service(many)"}
        ]
        if not seedable_components:
            continue
        component_id = min(
            seedable_components,
            key=lambda candidate: (
                catalog_order.get(candidate, len(catalog_order)),
                candidate,
            ),
        )
        for target in sorted(set(targets) & scope_paths):
            if target not in owner_candidates:
                external_seeds.append((target, caller_path, component_id, 1))
    external_candidates = _reachable_component_candidates(
        external_seeds,
        scope_paths,
        component_imports,
    )
    for path, records in external_candidates.items():
        owner_candidates.setdefault(path, set()).update(records)
    owners_by_path = _nearest_component_owners(owner_candidates, catalog_order)
    unreached = sorted(scope_paths - owners_by_path.keys())

    edge_sources: defaultdict[tuple[str, str, str], list[CodeSource]] = defaultdict(
        list
    )
    component_table_sources: defaultdict[tuple[str, str, str], list[CodeSource]] = (
        defaultdict(list)
    )
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
    queue_task_names: set[str] = set()
    queue_task_sources: defaultdict[str, list[CodeSource]] = defaultdict(list)
    service_endpoint_sources: defaultdict[str, list[CodeSource]] = defaultdict(list)
    webhook_id = target_components.get("WEBHOOK")
    http_clients_id = "http_clients" if "http_clients" in catalog_by_id else None
    provider_push_id = "provider_push" if "provider_push" in catalog_by_id else None
    temporal_id = "temporal" if "temporal" in catalog_by_id else None
    sqs_id = "sqs" if "sqs" in catalog_by_id else None
    postgres_id = "postgres" if "postgres" in catalog_by_id else None

    for path, facts in facts_by_path.items():
        owner_id = owners_by_path.get(path)
        for endpoint in facts.endpoints:
            if owner_id is not None:
                prefix = "/" + endpoint.path.strip("/").split("/", 1)[0]
                if prefix == "/":
                    prefix = "/"
                endpoint_groups[(owner_id, prefix)][
                    (
                        path,
                        endpoint.method,
                        endpoint.path,
                        endpoint.handler,
                        endpoint.line,
                    )
                ] = _source(path, endpoint.line)
                if catalog_by_id.get(owner_id, {}).get("kind") == "service":
                    service_endpoint_sources[owner_id].append(
                        _source(path, endpoint.line)
                    )
            if (
                provider_push_id is not None
                and webhook_id is not None
                and endpoint.deploy_target == "WEBHOOK"
            ):
                edge_sources[(provider_push_id, webhook_id, "provider events")].append(
                    _source(path, endpoint.line)
                )

        if owner_id is None:
            continue
        for external in facts.externals:
            provider_id = external_components.get(external.service)
            if provider_id is None:
                continue
            source = _source(path, external.line)
            edge_sources[(owner_id, provider_id, "API calls")].append(source)
            component_services[owner_id].add(external.service)
            provider_services[provider_id].add(external.service)
        for line in facts.workflow_starts:
            if temporal_id is not None and owner_id != temporal_id:
                edge_sources[(owner_id, temporal_id, "start workflow")].append(
                    _source(path, line)
                )
        if owner_id == temporal_id:
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
            edge_sources[(owner_id, sqs_id, "enqueue tasks")].append(source)
            queue_task_names.add(producer.task_type)
            queue_task_sources[producer.task_type].append(source)
        for table, (write_line, read_line) in table_accesses.get(path, {}).items():
            if table not in scope_table_names:
                continue
            if write_line is not None:
                source = _source(path, write_line)
                component_table_sources[(owner_id, table, "writes")].append(source)
                component_tables[owner_id].add(table)
            if read_line is not None:
                source = _source(path, read_line)
                component_table_sources[(owner_id, table, "reads")].append(source)
                component_tables[owner_id].add(table)

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
        edge_sources[(sqs_id, component_id, "long-poll")].append(source)

    if sqs_id is not None:
        sqs_details: defaultdict[str, list[CodeSource]] = defaultdict(list)
        queue_names_by_label: defaultdict[str, set[str]] = defaultdict(set)
        for task_name in sorted(queue_task_names):
            task = task_types.get(task_name)
            label = task.queue_class if task is not None else None
            label = label or "Unmapped"
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
                f"{label} · {len(names)} task types",
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
        tasks_by_target: defaultdict[str, dict[str, TaskType]] = defaultdict(dict)
        for task in task_facts.task_types:
            if task.name not in task_names:
                continue
            target = task.deploy_target or task.queue_class or "Unmapped"
            tasks_by_target[target][task.name] = task
        for target, tasks_by_name in sorted(tasks_by_target.items()):
            target_tasks = sorted(
                tasks_by_name.values(),
                key=lambda task: (task.path, task.line, task.name),
            )
            if not target_tasks:
                continue
            first_task = target_tasks[0]
            _add_detail(
                details,
                component_id,
                f"{target} · {len(tasks_by_name)} task types",
                _source(first_task.path, first_task.line),
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
                        if dst == provider_id and label == "API calls"
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
    route_service_ids = set()
    for groups in route_evidence.values():
        for web in groups.get("web", []):
            for backend in groups.get("backend", []):
                web_component_id = owners_by_path.get(web.path)
                service_id = owners_by_path.get(backend.path)
                if web_component_id is None or service_id is None:
                    continue
                if (
                    catalog_by_id.get(web_component_id, {}).get("kind") != "client"
                    or catalog_by_id.get(service_id, {}).get("kind") != "service"
                ):
                    continue
                route_service_ids.add(service_id)
                edge_sources[(web_component_id, service_id, "REST calls")].append(
                    _source(web.path, web.line)
                )
    if http_clients_id is not None:
        for service_id, sources in sorted(service_endpoint_sources.items()):
            if service_id == webhook_id or service_id in route_service_ids:
                continue
            edge_sources[(http_clients_id, service_id, "REST calls")].append(
                _first_source(sources)
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
    column_order = {}
    for entry in component_catalog:
        column = str(entry.get("column", ""))
        column_order.setdefault(column, len(column_order))
    backward_edges = []
    figure_edges = []
    for edge in edges:
        source_column = str(catalog_by_id.get(edge.src, {}).get("column", ""))
        target_column = str(catalog_by_id.get(edge.dst, {}).get("column", ""))
        if column_order.get(target_column, 0) < column_order.get(source_column, 0):
            backward_edges.append(edge)
        else:
            figure_edges.append(edge)
    edges = figure_edges
    participating = {edge.src for edge in edges} | {edge.dst for edge in edges}

    endpoint_details: defaultdict[str, defaultdict[str, list[CodeSource]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for (component_id, prefix), records in endpoint_groups.items():
        endpoint_details[component_id][f"{prefix}: {len(records)} endpoints"].extend(
            records.values()
        )
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
            limit=(
                TEMPORAL_WORKFLOW_DETAIL_LIMIT
                if node_id == temporal_id
                else 4
                if node_id == postgres_id
                else 3
            ),
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
    notes = _flow_notes(
        nodes,
        edges,
        catalog_by_id,
        service_map,
        backward_edges,
    )
    groups = []
    for column in dict.fromkeys(
        str(entry.get("column", "")) for entry in component_catalog
    ):
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
