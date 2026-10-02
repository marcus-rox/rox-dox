from rox_dox.components import (
    Endpoint,
    ExternalCall,
    FileFacts,
    TaskConsumer,
    TaskProducer,
    TaskType,
    Worker,
)
from rox_dox.features import FeatureEvidence, FeatureFile
from rox_dox.model import CodeSource, Edge
from rox_dox.projection import _deduplicate_edges, project_component_diagram


def _entry(
    component_id: str,
    label: str,
    kind: str,
    column: str,
    shape: str,
    match: dict,
) -> dict:
    return {
        "id": component_id,
        "label": label,
        "kind": kind,
        "column": column,
        "shape": shape,
        "match": match,
        "source": {"path": f"catalog/{component_id}.py", "lines": [1, 1]},
    }


def _runtime_catalog() -> list[dict]:
    return [
        _entry("web", "web app", "client", "Callers", "component", {"web_files": True}),
        _entry("http_clients", "HTTP clients", "client", "Callers", "component", {}),
        _entry(
            "provider_push",
            "Provider push",
            "external",
            "Callers",
            "external",
            {"implied_by": "WEBHOOK endpoint"},
        ),
        _entry(
            "interaction",
            "INTERACTION (Flask)",
            "service",
            "HTTP services",
            "component",
            {"deploy_targets": ["INTERACTION"]},
        ),
        _entry(
            "webhook",
            "WEBHOOK (Flask)",
            "service",
            "HTTP services",
            "component",
            {"deploy_targets": ["WEBHOOK"]},
        ),
        _entry(
            "temporal",
            "Temporal workflows",
            "queue",
            "Workflows",
            "component",
            {"worker_kinds": ["temporal_workflow", "temporal_activity"]},
        ),
        _entry("sqs", "SQS queues", "queue", "Queues", "queue", {}),
        _entry(
            "data_workers",
            "INTEGRATION workers",
            "service(many)",
            "Background workers",
            "component",
            {
                "deploy_targets": ["INTEGRATION"],
                "queue_type_classes": ["IntegrationQueueType"],
            },
        ),
        _entry("postgres", "PostgreSQL", "store", "Stores", "store", {}),
        _entry(
            "crm",
            "CRM + workspace APIs",
            "external",
            "Provider APIs",
            "external",
            {"external_services": ["Salesforce"]},
        ),
    ]


def _file(path: str, evidence: list[FeatureEvidence] | None = None) -> FeatureFile:
    return FeatureFile(
        path=path,
        primary=True,
        reason="route" if evidence else "tables",
        evidence=evidence or [],
    )


def _projection_fixture():
    web_path = "web/apps/accounts/page.tsx"
    api_path = "backend/src/rox_core/api/accounts.py"
    webhook_path = "backend/src/rox_core/api/webhook.py"
    helper_path = "backend/src/rox_core/services/accounts.py"
    worker_path = "backend/src/rox_core/tasks/accounts.py"
    temporal_path = "backend/src/rox_core/workflows/accounts.py"
    task_types_path = "backend/src/tasks/types.py"
    route_tag = "accounts"
    files = [
        _file(
            web_path,
            [FeatureEvidence(kind="route", path=web_path, line=5, tag=route_tag)],
        ),
        _file(
            api_path,
            [FeatureEvidence(kind="route", path=api_path, line=10, tag=route_tag)],
        ),
        _file(webhook_path),
        _file(helper_path),
        _file(worker_path),
        _file(temporal_path),
        _file("backend/src/unreached.py"),
    ]
    facts = {
        web_path: FileFacts(
            path=web_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[],
        ),
        api_path: FileFacts(
            path=api_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts/list",
                    handler="list_accounts",
                    line=11,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[],
        ),
        webhook_path: FileFacts(
            path=webhook_path,
            api_group="provider",
            endpoints=[
                Endpoint(
                    method="POST",
                    path="/webhook/accounts",
                    handler="receive_accounts",
                    line=12,
                    deploy_target="WEBHOOK",
                )
            ],
            workers=[],
            externals=[],
        ),
        helper_path: FileFacts(
            path=helper_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[
                ExternalCall(service="Salesforce", module="salesforce", line=21)
            ],
            task_producers=[
                TaskProducer(task_type="TASK_A", path=helper_path, line=20)
            ],
            workflow_starts=[22],
        ),
        worker_path: FileFacts(
            path=worker_path,
            api_group=None,
            endpoints=[],
            workers=[Worker(name="SyncExecutor", kind="task_executor", line=4)],
            externals=[],
            task_consumers=[
                TaskConsumer(
                    task_type="TASK_A",
                    executor="SyncExecutor",
                    path=worker_path,
                    line=30,
                ),
                TaskConsumer(
                    task_type="TASK_B",
                    executor="SyncExecutor",
                    path=worker_path,
                    line=31,
                ),
            ],
        ),
        temporal_path: FileFacts(
            path=temporal_path,
            api_group=None,
            endpoints=[],
            workers=[
                Worker(
                    name="AccountsWorkflow",
                    kind="temporal_workflow",
                    line=7,
                )
            ],
            externals=[],
        ),
        task_types_path: FileFacts(
            path=task_types_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[],
            task_types=[
                TaskType(
                    name="TASK_A",
                    queue_type="IntegrationQueueType.DEFAULT",
                    queue_class="IntegrationQueueType",
                    deploy_target="INTEGRATION",
                    path=task_types_path,
                    line=40,
                ),
                TaskType(
                    name="TASK_B",
                    queue_type="IntegrationQueueType.DEFAULT",
                    queue_class="IntegrationQueueType",
                    deploy_target="INTEGRATION",
                    path=task_types_path,
                    line=41,
                ),
            ],
        ),
    }
    imports = {api_path: {helper_path: 19}}
    table_accesses = {helper_path: {"accounts": (23, 24)}}
    projection = project_component_diagram(
        files,
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports=imports,
        table_accesses=table_accesses,
        scope_tables={"accounts"},
        external_callers={},
    )
    return projection, helper_path


def test_component_projection_attributes_helpers_and_cites_runtime_flow() -> None:
    projection, helper_path = _projection_fixture()
    diagram = projection.diagram

    assert {node.id for node in diagram.nodes} == {
        "web",
        "provider_push",
        "interaction",
        "webhook",
        "temporal",
        "sqs",
        "data_workers",
        "postgres",
        "crm",
    }
    assert {(edge.src, edge.dst, edge.label) for edge in diagram.edges} == {
        ("web", "interaction", "REST calls"),
        ("provider_push", "webhook", "provider events"),
        ("interaction", "postgres", "reads + writes"),
        ("interaction", "sqs", "enqueue tasks"),
        ("interaction", "temporal", "start workflow"),
        ("interaction", "crm", "API calls"),
        ("sqs", "data_workers", "long-poll"),
    }
    assert not any(edge.src == "http_clients" for edge in diagram.edges)
    for edge in diagram.edges:
        assert edge.source.lines
    for group in diagram.groups:
        assert group.source.lines
    for node in diagram.nodes:
        assert node.source.lines
        for detail in node.details:
            assert detail.sources
    helper_edges = {
        edge.label: edge for edge in diagram.edges if edge.source.path == helper_path
    }
    assert {
        "reads + writes",
        "enqueue tasks",
        "start workflow",
        "API calls",
    } <= helper_edges.keys()
    details_by_node = {
        node.id: {detail.text for detail in node.details} for node in diagram.nodes
    }
    assert "/accounts: 1 endpoints" in details_by_node["interaction"]
    assert "INTEGRATION · 2 task types" in details_by_node["data_workers"]
    assert "TASK_A" not in " ".join(details_by_node["data_workers"])
    assert "TASK_B" not in " ".join(details_by_node["data_workers"])
    assert "AccountsWorkflow" in details_by_node["temporal"]
    assert "IntegrationQueueType · 2 task types" in details_by_node["sqs"]
    assert "TASK_A" not in " ".join(details_by_node["sqs"])
    assert "TASK_B" not in " ".join(details_by_node["sqs"])
    assert "accounts" in details_by_node["postgres"]
    assert "Salesforce" in details_by_node["crm"]
    assert any("Salesforce" in note.text for note in diagram.notes)
    assert diagram.unreached_files == ["backend/src/unreached.py"]
    assert 3 <= len(diagram.notes) <= 6
    assert all(note.sources for note in diagram.notes)


def test_provider_box_merging_keeps_component_count_within_budget() -> None:
    api_path = "backend/src/api/accounts.py"
    helper_path = "backend/src/services/accounts.py"
    providers = [
        _entry(
            f"provider_{index:02}",
            f"Provider {index:02}",
            "external",
            "Provider APIs",
            "external",
            {"external_services": [f"Service{index:02}"]},
        )
        for index in range(15)
    ]
    catalog = [
        _entry(
            "interaction",
            "INTERACTION (Flask)",
            "service",
            "HTTP services",
            "component",
            {"deploy_targets": ["INTERACTION"]},
        ),
        *providers,
    ]
    facts = {
        api_path: FileFacts(
            path=api_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="list_accounts",
                    line=3,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[],
        ),
        helper_path: FileFacts(
            path=helper_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[
                ExternalCall(
                    service=f"Service{index:02}",
                    module=f"service_{index:02}",
                    line=index + 1,
                )
                for index in range(15)
            ],
        ),
    }
    projection = project_component_diagram(
        [_file(api_path), _file(helper_path)],
        component_catalog=catalog,
        component_facts=facts,
        component_imports={api_path: {helper_path: 4}},
        table_accesses={},
        scope_tables=set(),
        external_callers={},
    )

    assert len(projection.diagram.nodes) <= 15
    assert {node.id for node in projection.diagram.nodes} == {
        "interaction",
        "provider-apis",
    }
    assert len(projection.diagram.edges) == 1
    assert projection.diagram.edges[0].src == "interaction"
    assert projection.diagram.edges[0].dst == "provider-apis"
    assert projection.diagram.edges[0].label == "API calls"


def test_shared_helper_is_owned_by_nearest_entry_component() -> None:
    near_path = "backend/src/rox_core/api/accounts.py"
    far_path = "backend/src/rox_core/api/webhook.py"
    bridge_path = "backend/src/rox_core/services/bridge.py"
    helper_path = "backend/src/rox_core/services/shared.py"
    facts = {
        near_path: FileFacts(
            path=near_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="list_accounts",
                    line=3,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[],
        ),
        far_path: FileFacts(
            path=far_path,
            api_group="webhook",
            endpoints=[
                Endpoint(
                    method="POST",
                    path="/webhook",
                    handler="receive_webhook",
                    line=4,
                    deploy_target="WEBHOOK",
                )
            ],
            workers=[],
            externals=[],
        ),
        bridge_path: FileFacts(
            path=bridge_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[],
        ),
        helper_path: FileFacts(
            path=helper_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[ExternalCall(service="Salesforce", module="salesforce", line=8)],
        ),
    }
    projection = project_component_diagram(
        [_file(path) for path in (near_path, far_path, bridge_path, helper_path)],
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports={
            near_path: {helper_path: 5},
            far_path: {bridge_path: 6},
            bridge_path: {helper_path: 7},
        },
        table_accesses={},
        scope_tables=set(),
        external_callers={},
    )

    provider_edges = [
        edge
        for edge in projection.diagram.edges
        if edge.dst == "crm" and edge.label == "API calls"
    ]
    assert len(provider_edges) == 1
    assert provider_edges[0].src == "interaction"
    assert provider_edges[0].source.path == helper_path


def test_external_caller_seeds_an_unreached_scope_file() -> None:
    target_path = "backend/src/rox_core/api/external_accounts.py"
    caller_path = "backend/src/chat/routes/accounts.py"
    facts = {
        target_path: FileFacts(
            path=target_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[ExternalCall(service="Salesforce", module="salesforce", line=8)],
        ),
        caller_path: FileFacts(
            path=caller_path,
            api_group="chat",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="get_accounts",
                    line=3,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[ExternalCall(service="Twilio", module="twilio", line=9)],
        ),
    }
    projection = project_component_diagram(
        [_file(target_path)],
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports={},
        table_accesses={},
        scope_tables=set(),
        external_callers={caller_path: [target_path]},
    )

    assert {(edge.src, edge.dst, edge.label) for edge in projection.diagram.edges} == {
        ("interaction", "crm", "API calls")
    }
    assert projection.diagram.edges[0].source.path == target_path
    assert projection.diagram.unreached_files == []


def test_backward_edges_become_cited_notes_and_unconnected_box_disappears() -> None:
    worker_path = "backend/src/tasks/pool.py"
    api_path = "backend/src/rox_core/api/accounts.py"
    facts = {
        worker_path: FileFacts(
            path=worker_path,
            api_group=None,
            endpoints=[
                Endpoint(
                    method="POST",
                    path="/tasks",
                    handler="enqueue",
                    line=3,
                    deploy_target="INTEGRATION",
                )
            ],
            workers=[],
            externals=[],
            task_producers=[
                TaskProducer(task_type="TASK_A", path=worker_path, line=20)
            ],
            workflow_starts=[21],
        ),
        api_path: FileFacts(
            path=api_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="list_accounts",
                    line=4,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[ExternalCall(service="Salesforce", module="salesforce", line=5)],
        ),
    }
    projection = project_component_diagram(
        [_file(worker_path), _file(api_path)],
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports={},
        table_accesses={},
        scope_tables=set(),
        external_callers={},
    )

    assert {(edge.src, edge.dst, edge.label) for edge in projection.diagram.edges} == {
        ("http_clients", "interaction", "REST calls"),
        ("interaction", "crm", "API calls"),
    }
    assert "data_workers" not in {node.id for node in projection.diagram.nodes}
    note = next(
        note
        for note in projection.diagram.notes
        if "INTEGRATION workers also" in note.text
    )
    assert 3 <= len(projection.diagram.notes) <= 6
    assert (
        note.text
        == "INTEGRATION workers also enqueue follow-up SQS tasks and start Temporal workflows."
    )
    assert {source.lines for source in note.sources} == {(20, 20), (21, 21)}


def test_http_clients_edge_uses_first_service_endpoint_without_route_evidence() -> None:
    api_path = "backend/src/rox_core/api/accounts.py"
    facts = {
        api_path: FileFacts(
            path=api_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="POST",
                    path="/accounts/new",
                    handler="create_account",
                    line=30,
                    deploy_target="INTERACTION",
                ),
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="list_accounts",
                    line=10,
                    deploy_target="INTERACTION",
                ),
            ],
            workers=[],
            externals=[],
        )
    }
    projection = project_component_diagram(
        [_file(api_path)],
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports={},
        table_accesses={},
        scope_tables=set(),
        external_callers={},
    )

    assert len(projection.diagram.edges) == 1
    edge = projection.diagram.edges[0]
    assert (edge.src, edge.dst, edge.label) == (
        "http_clients",
        "interaction",
        "REST calls",
    )
    assert edge.source.path == api_path
    assert edge.source.lines == (10, 10)
    assert any(
        note.text == "HTTP clients make REST calls to INTERACTION (Flask)."
        for note in projection.diagram.notes
    )


def test_temporal_workflow_details_show_two_names_then_remainder() -> None:
    api_path = "backend/src/rox_core/api/accounts.py"
    workflow_paths = [
        f"backend/src/rox_core/workflows/workflow_{index}.py" for index in range(4)
    ]
    facts = {
        api_path: FileFacts(
            path=api_path,
            api_group="accounts",
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/accounts",
                    handler="list_accounts",
                    line=6,
                    deploy_target="INTERACTION",
                )
            ],
            workers=[],
            externals=[],
            workflow_starts=[8],
        ),
        **{
            path: FileFacts(
                path=path,
                api_group=None,
                endpoints=[],
                workers=[
                    Worker(
                        name=f"Workflow{index}",
                        kind="temporal_workflow",
                        line=index + 1,
                    )
                ],
                externals=[],
            )
            for index, path in enumerate(workflow_paths)
        },
    }
    projection = project_component_diagram(
        [_file(api_path), *(_file(path) for path in workflow_paths)],
        component_catalog=_runtime_catalog(),
        component_facts=facts,
        component_imports={},
        table_accesses={},
        scope_tables=set(),
        external_callers={},
    )

    temporal = next(node for node in projection.diagram.nodes if node.id == "temporal")
    assert [detail.text for detail in temporal.details] == [
        "Workflow0",
        "Workflow1",
        "+2 more",
    ]
    assert temporal.details[-1].sources


def test_edge_deduplication_merges_access_modes_and_uses_first_source() -> None:
    first_source = CodeSource(path="a.py", lines=(4, 4))
    later_source = CodeSource(path="b.py", lines=(2, 2))
    edges = _deduplicate_edges(
        [
            Edge(src="service", dst="postgres", label="writes", source=later_source),
            Edge(src="service", dst="postgres", label="reads", source=first_source),
        ]
    )

    assert len(edges) == 1
    assert edges[0].label == "reads + writes"
    assert edges[0].source == first_source
