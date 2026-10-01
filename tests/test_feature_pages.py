import json
from pathlib import Path

import pytest

from rox_dox.block_svg import block_layout_problems
from rox_dox.components import Endpoint, ExternalCall, FileFacts, Worker
from rox_dox.feature_pages import (
    _domain_block,
    _domain_data,
    _table_relations,
    feature_pages,
    layer_of,
)
from rox_dox.features import (
    Feature,
    FeatureCounts,
    FeatureEvidence,
    FeatureFile,
    FeatureMap,
    TableLink,
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


def test_generated_feature_pages_pass_block_layout() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    page_files = sorted((repository_root / "pages" / "features").glob("*.json"))
    assert page_files

    for page_file in page_files:
        page = Page.model_validate(json.loads(page_file.read_text(encoding="utf-8")))
        problems = block_layout_problems(page.block)
        assert not problems, f"{page_file}: {problems}"


def _runtime_feature_fixture(
    api_table_count: int = 2,
    endpoint_count: int = 2,
    worker_count: int = 1,
    web_directory: str = "web/apps/integrations/src",
    long_endpoint_path: str | None = None,
    worker_path: str = "backend/src/workers/integration/sync.py",
    worker_name: str = "SyncWorker",
) -> tuple[FeatureMap, dict[str, Table], dict[str, FileFacts]]:
    web_path = f"{web_directory}/IntegrationPage.tsx"
    api_path = "backend/src/api/integrations/endpoints.py"
    api_helper_path = "backend/src/services/api_helper.py"
    worker_helper_path = "backend/src/services/worker_helper.py"
    library_path = "backend/src/services/library.py"
    unused_path = "backend/src/helpers/unneeded.py"
    api_tables = [f"api_table_{index:02}" for index in range(api_table_count)]
    all_tables = [
        *api_tables,
        "api_helper_table",
        "worker_table",
        "library_table",
    ]
    web_evidence = [
        FeatureEvidence(kind="route", tag="integrations", path=web_path, line=4),
        FeatureEvidence(kind="route", tag="integrations", path=api_path, line=8),
    ]
    api_evidence = [
        FeatureEvidence(
            kind="call",
            path=api_path,
            line=15,
            to=api_helper_path,
        ),
        FeatureEvidence(
            kind="call",
            path=api_path,
            line=16,
            to=worker_path,
        ),
        *[
            FeatureEvidence(
                kind="table",
                path=api_path,
                line=20 + index,
                table=table_name,
            )
            for index, table_name in enumerate(api_tables)
        ],
    ]
    files = [
        FeatureFile(
            path=web_path,
            primary=True,
            reason="route",
            evidence=web_evidence,
        ),
        FeatureFile(
            path=api_path,
            primary=True,
            reason="tables",
            evidence=api_evidence,
        ),
        FeatureFile(
            path=api_helper_path,
            primary=True,
            reason="tables",
            evidence=[
                FeatureEvidence(
                    kind="table",
                    path=api_helper_path,
                    line=2,
                    table="api_helper_table",
                )
            ],
        ),
        FeatureFile(
            path=worker_path,
            primary=True,
            reason="tables",
            evidence=[
                FeatureEvidence(
                    kind="call",
                    path=worker_path,
                    line=12,
                    to=worker_helper_path,
                ),
                FeatureEvidence(
                    kind="table",
                    path=worker_path,
                    line=13,
                    table="worker_table",
                ),
            ],
        ),
        FeatureFile(
            path=worker_helper_path,
            primary=True,
            reason="calls",
            evidence=[
                FeatureEvidence(
                    kind="table",
                    path=worker_helper_path,
                    line=2,
                    table="worker_table",
                )
            ],
        ),
        FeatureFile(
            path=library_path,
            primary=True,
            reason="tables",
            evidence=[
                FeatureEvidence(
                    kind="table",
                    path=library_path,
                    line=2,
                    table="library_table",
                )
            ],
        ),
        FeatureFile(
            path=unused_path,
            primary=True,
            reason="calls",
            evidence=[],
        ),
    ]
    feature = Feature(id="integration", tables=all_tables, files=files, table_links=[])
    feature_map = FeatureMap(
        commit="a" * 40,
        domain="activity",
        threshold=0.25,
        tables=all_tables,
        features=[feature],
        uncovered=[],
        unmapped_tags=[],
        counts=FeatureCounts(
            domain_files=len(files),
            primary_placed=len(files),
            shared=0,
            uncovered=0,
            web=1,
            deployment=0,
            skills=0,
            unparseable=0,
        ),
    )
    tables = {
        table_name: Table(
            name=table_name,
            class_name=table_name.title().replace("_", ""),
            columns=[Column(name="id", type="Integer", primary_key=True)],
            source=CodeSource(
                path=f"backend/src/models/{table_name}.py",
                lines=(1, 1),
            ),
        )
        for table_name in all_tables
    }
    tables["integration"] = tables[api_tables[0]]
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
            api_group="integrations",
            endpoints=[
                Endpoint(
                    method="GET",
                    path=(
                        long_endpoint_path
                        if index == 0 and long_endpoint_path is not None
                        else (
                            "/integrations/health"
                            if index == 0
                            else f"/integrations/events/{index}"
                        )
                    ),
                    handler="IntegrationEndpoint",
                    line=10 + index,
                )
                for index in range(endpoint_count)
            ],
            workers=[],
            externals=[],
        ),
        api_helper_path: FileFacts(
            path=api_helper_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[ExternalCall(service="Slack", module="slack_sdk", line=4)],
        ),
        worker_path: FileFacts(
            path=worker_path,
            api_group=None,
            endpoints=[],
            workers=[
                Worker(
                    name=(
                        f"{worker_name}{index}"
                        if worker_count > 1 and not worker_name.endswith("TaskExecutor")
                        else (
                            worker_name
                            if index == 0 or worker_count == 1
                            else f"ZOther{index}TaskExecutor"
                        )
                    ),
                    kind="task_executor",
                    line=5 + index,
                )
                for index in range(worker_count)
            ],
            externals=[],
        ),
        worker_helper_path: FileFacts(
            path=worker_helper_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[
                ExternalCall(
                    service="Google APIs",
                    module="google.oauth2",
                    line=3,
                )
            ],
        ),
        library_path: FileFacts(
            path=library_path,
            api_group=None,
            endpoints=[],
            workers=[],
            externals=[ExternalCall(service="Stripe", module="stripe", line=5)],
        ),
    }
    return feature_map, tables, facts


def _feature_page_from_runtime_fixture(
    api_table_count: int = 2,
    endpoint_count: int = 2,
    worker_count: int = 1,
    web_directory: str = "web/apps/integrations/src",
    long_endpoint_path: str | None = None,
    worker_path: str = "backend/src/workers/integration/sync.py",
    worker_name: str = "SyncWorker",
    component_imports: dict[str, dict[str, int]] | None = None,
    primary_features: dict[str, tuple[str, str]] | None = None,
) -> Page:
    feature_map, tables, facts = _runtime_feature_fixture(
        api_table_count,
        endpoint_count,
        worker_count,
        web_directory,
        long_endpoint_path,
        worker_path,
        worker_name,
    )
    pages = feature_pages(
        feature_map,
        root_id="rox-core",
        domain_title="Activity",
        names={"integration": "Integration connections & sync"},
        tables=tables,
        component_facts=facts,
        component_imports=component_imports,
        primary_features=primary_features,
    )
    return next(page for page in pages if page.kind == "feature")


def test_feature_block_models_runtime_components_and_web_api_route() -> None:
    page = _feature_page_from_runtime_fixture()
    nodes = {node.id: node for node in page.block.nodes}
    api_node = next(node for node in nodes.values() if node.label == "Integrations API")
    worker_node = next(
        node for node in nodes.values() if node.label == "Integration workers"
    )
    web_node = next(node for node in nodes.values() if node.label == "Web app")
    external_nodes = {
        node.label: node for node in nodes.values() if node.kind == "external"
    }

    assert block_layout_problems(page.block) == []
    assert [group.label for group in page.block.groups if group.parent is None] == [
        "Web app",
        "Entry points",
        "Data & services",
    ]
    assert any(
        edge.src == web_node.id and edge.dst == api_node.id and edge.label == "HTTP"
        for edge in page.block.edges
    )
    assert any(
        edge.src == api_node.id
        and edge.dst == external_nodes["Slack"].id
        and edge.label == "calls Slack"
        for edge in page.block.edges
    )
    assert any(
        edge.src == worker_node.id and edge.dst == external_nodes["Google APIs"].id
        for edge in page.block.edges
    )
    assert not any("(library)" in node.label for node in page.block.nodes)
    assert not any(node.label == "Stripe" for node in external_nodes.values())
    assert page.tldr.table.columns == [
        "Component",
        "Kind",
        "Tables used",
        "Outside services",
    ]
    assert any(row[0] == "Services (library)" for row in page.tldr.table.rows)
    assert page.tldr.summary[0].text == (
        "Owns 2 HTTP endpoints in 1 API groups: Integrations."
    )
    assert page.tldr.summary[1].text == (
        "Runs 1 background workers and workflows: SyncWorker."
    )
    assert [group.layer for group in page.membership] == [
        "Web screens",
        "HTTP routes",
        "Background workers",
        "Business logic",
    ]
    assert all(row.sources for group in page.membership for row in group.rows)
    assert not any(node.label == "Helpers (library)" for node in page.block.nodes)


def test_callers_join_entries_link_to_their_feature_and_cite_the_import() -> None:
    feature_map, tables, facts = _runtime_feature_fixture(
        endpoint_count=0,
        worker_count=0,
    )
    caller_path = "backend/src/tasks/executors/endpoints.py"
    member_path = "backend/src/services/api_helper.py"
    decoy_path = "backend/src/other/decoy.py"
    facts[caller_path] = FileFacts(
        path=caller_path,
        api_group="integrations",
        endpoints=[
            Endpoint(
                method="GET",
                path="/integrations/callback",
                handler="CallbackEndpoint",
                line=20,
            )
        ],
        workers=[
            Worker(
                name="SyncTaskExecutor",
                kind="task_executor",
                line=24,
            )
        ],
        externals=[
            ExternalCall(service="Salesforce", module="simple_salesforce", line=25)
        ],
    )
    facts[decoy_path] = FileFacts(
        path=decoy_path,
        api_group=None,
        endpoints=[],
        workers=[],
        externals=[ExternalCall(service="Twilio", module="twilio", line=2)],
    )
    caller_import_line = 30
    caller_owner = ("CRM integrations", "feature-crm-integrations")
    imports = {
        caller_path: {
            member_path: caller_import_line,
            decoy_path: 31,
        }
    }
    owners = {caller_path: caller_owner}
    pages = feature_pages(
        feature_map,
        root_id="rox-core",
        domain_title="Activity",
        names={"integration": "Integration connections & sync"},
        tables=tables,
        component_facts=facts,
        component_imports=imports,
        primary_features=owners,
    )
    page = next(page for page in pages if page.kind == "feature")
    nodes = {node.label: node for node in page.block.nodes}
    api_node = nodes["Integrations API"]
    worker_node = nodes["Sync workers"]
    api_call = next(
        detail for detail in api_node.details if detail.text.startswith("Calls into")
    )
    worker_call = next(
        detail for detail in worker_node.details if detail.text.startswith("Calls into")
    )

    assert api_node.link == caller_owner[1]
    assert worker_node.link == caller_owner[1]
    assert not any("(library)" in node.label for node in page.block.nodes)
    assert api_call.text == "Calls into this feature from CRM integrations"
    assert api_call.sources[0].path == caller_path
    assert api_call.sources[0].lines == (caller_import_line, caller_import_line)
    assert worker_call.sources[0].lines == (caller_import_line, caller_import_line)
    reached = next(
        claim for claim in page.tldr.summary if claim.text.startswith("Reached from")
    )
    assert reached.text == (
        "Reached from 1 HTTP endpoints and 1 workers in other features: "
        "Integrations, Sync workers."
    )
    assert block_layout_problems(page.block) == []

    external_labels = {
        node.label for node in page.block.nodes if node.kind == "external"
    }
    assert external_labels == {"Slack"}
    slack = nodes["Slack"]
    slack_edge = next(
        edge
        for edge in page.block.edges
        if edge.src == api_node.id and edge.dst == slack.id
    )
    assert slack_edge.source.path == member_path
    assert slack_edge.source.lines == (4, 4)
    helper_store = nodes["api_helper_table"]
    table_edge = next(
        edge
        for edge in page.block.edges
        if edge.src == api_node.id and edge.dst == helper_store.id
    )
    assert table_edge.source.path == member_path
    assert table_edge.source.lines == (2, 2)
    assert not any(
        edge.dst == nodes["worker_table"].id
        and edge.src in {api_node.id, worker_node.id}
        for edge in page.block.edges
    )
    domain_page = pages[0]
    assert "Reached from" in domain_page.tldr.table.columns
    assert domain_page.tldr.table.rows[0][1:4] == ["0", "0", "2"]
    assert any(
        source.path == caller_path
        and source.lines == (caller_import_line, caller_import_line)
        for source in domain_page.tldr.table.sources
    )


@pytest.mark.parametrize(
    ("worker_path", "worker_name", "worker_count", "expected"),
    [
        (
            "backend/src/tasks/executors/sync.py",
            "SyncTaskExecutor",
            2,
            "Sync + 1 more workers",
        ),
        (
            "backend/src/rox_core/slack_integration/workers/sync.py",
            "SyncTaskExecutor",
            1,
            "Slack Integration workers",
        ),
    ],
)
def test_worker_labels_use_specific_directories_or_generic_fallback(
    worker_path: str,
    worker_name: str,
    worker_count: int,
    expected: str,
) -> None:
    page = _feature_page_from_runtime_fixture(
        worker_path=worker_path,
        worker_name=worker_name,
        worker_count=worker_count,
    )
    worker_node = next(
        node for node in page.block.nodes if node.group == "group-background-workers"
    )
    table_row = next(
        row
        for row in page.tldr.table.rows
        if row[1] == "Background workers / workflows"
    )

    assert worker_node.label == expected
    assert table_row[0] == expected


def test_library_nodes_appear_only_without_entry_nodes() -> None:
    without_entries = _feature_page_from_runtime_fixture(
        endpoint_count=0,
        worker_count=0,
    )
    with_entries = _feature_page_from_runtime_fixture()

    assert any("(library)" in node.label for node in without_entries.block.nodes)
    assert not any("(library)" in node.label for node in with_entries.block.nodes)
    assert block_layout_problems(without_entries.block) == []
    assert block_layout_problems(with_entries.block) == []


def test_api_and_worker_details_show_five_then_a_cited_more_row() -> None:
    page = _feature_page_from_runtime_fixture(endpoint_count=8, worker_count=7)
    api_node = next(
        node for node in page.block.nodes if node.label == "Integrations API"
    )
    worker_node = next(
        node for node in page.block.nodes if node.label == "Integration workers"
    )

    assert [detail.text for detail in api_node.details] == [
        "GET /integrations/events/1",
        "GET /integrations/events/2",
        "GET /integrations/events/3",
        "GET /integrations/events/4",
        "GET /integrations/events/5",
        "+3 more endpoints",
    ]
    assert api_node.details[-1].sources[0].lines == (16, 16)
    assert [detail.text for detail in worker_node.details] == [
        "SyncWorker0",
        "SyncWorker1",
        "SyncWorker2",
        "SyncWorker3",
        "SyncWorker4",
        "+2 more workers",
    ]
    assert worker_node.details[-1].sources[0].lines == (10, 10)


def test_web_directory_details_fit_the_block_claim_limit() -> None:
    web_directory = "web/" + "/".join(f"screen-{index}" for index in range(20))
    page = _feature_page_from_runtime_fixture(web_directory=web_directory)
    web_node = next(node for node in page.block.nodes if node.label == "Web app")

    assert len(web_node.details[0].text) <= 90
    assert web_node.details[0].text.startswith("…/")
    assert web_node.details[0].sources


def test_long_endpoint_details_keep_their_method_and_citation() -> None:
    long_endpoint_path = "/integrations/" + "/".join(
        f"segment-{index}" for index in range(12)
    )
    page = _feature_page_from_runtime_fixture(
        long_endpoint_path=long_endpoint_path,
    )
    api_node = next(
        node for node in page.block.nodes if node.label == "Integrations API"
    )
    detail = next(
        detail for detail in api_node.details if detail.sources[0].lines == (10, 10)
    )

    assert len(detail.text) <= 90
    assert detail.text.startswith("GET /integrations/")
    assert "…" in detail.text


def test_feature_block_aggregates_store_over_twelve_component_table_edges() -> None:
    page = _feature_page_from_runtime_fixture(api_table_count=13)
    database = next(
        node for node in page.block.nodes if node.label.startswith("Database (")
    )

    assert database.label == "Database (16 tables)"
    assert [detail.text for detail in database.details] == [
        "api_table_00",
        "api_table_01",
        "api_table_02",
        "api_table_03",
        "api_table_04",
        "+11 more tables",
    ]
    assert block_layout_problems(page.block) == []


def test_feature_entry_reach_does_not_enter_another_entry_files() -> None:
    page = _feature_page_from_runtime_fixture()
    nodes = {node.id: node for node in page.block.nodes}
    api_node = next(node for node in nodes.values() if node.label == "Integrations API")
    worker_node = next(
        node for node in nodes.values() if node.label == "Integration workers"
    )
    worker_table = next(node for node in nodes.values() if node.label == "worker_table")
    google = next(node for node in nodes.values() if node.label == "Google APIs")

    assert not any(
        edge.src == api_node.id and edge.dst == worker_table.id
        for edge in page.block.edges
    )
    assert not any(
        edge.src == api_node.id and edge.dst == google.id for edge in page.block.edges
    )
    assert any(
        edge.src == worker_node.id and edge.dst == google.id
        for edge in page.block.edges
    )


def test_domain_block_flows_features_to_stores_without_feature_edges() -> None:
    feature_map, tables, facts = _runtime_feature_fixture()

    block, figures = _domain_block(feature_map, {}, tables, facts)

    assert block_layout_problems(block) == []
    assert figures == []
    feature_ids = {node.id for node in block.nodes if node.id.startswith("feature-")}
    assert not any(
        edge.src in feature_ids and edge.dst in feature_ids for edge in block.edges
    )
    assert any(edge.label == "owns" for edge in block.edges)
    assert all(
        edge.src in feature_ids
        or edge.dst.startswith("external-service-")
        or edge.dst.startswith("store-feature-")
        for edge in block.edges
    )
    assert {node.label for node in block.nodes if node.kind == "external"} == {
        "Google APIs",
        "Slack",
        "Stripe",
    }
    assert all(
        detail.sources
        for node in block.nodes
        if node.id in feature_ids
        for detail in node.details
    )


def test_empty_feature_and_domain_use_key_table_definition_path() -> None:
    source = CodeSource(path="backend/src/models/user.py", lines=(12, 12))
    table = Table(
        name="users",
        class_name="User",
        columns=[Column(name="id", type="Integer", primary_key=True)],
        source=source,
    )
    feature_map = FeatureMap(
        commit="a" * 40,
        domain="test",
        threshold=0.25,
        tables=["users"],
        features=[Feature(id="users", tables=["users"], files=[], table_links=[])],
        uncovered=[],
        unmapped_tags=[],
        counts=FeatureCounts(
            domain_files=0,
            primary_placed=0,
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
        names={},
        tables={"users": table},
    )

    assert pages[0].paths == [source.path]
    assert pages[1].paths == [source.path]
    assert "No HTTP endpoints or background workers" in pages[1].tldr.summary[-1].text


def test_table_relations_keep_the_strongest_signal_per_unordered_pair() -> None:
    links = [
        TableLink(
            a="sessions",
            b="users",
            signal="commented_fk",
            path="backend/src/models/session.py",
            line=10,
        ),
        TableLink(
            a="users",
            b="sessions",
            signal="comparison",
            path="backend/src/services/users.py",
            line=20,
        ),
        TableLink(
            a="sessions",
            b="users",
            signal="primaryjoin",
            path="backend/src/models/session.py",
            line=30,
        ),
        TableLink(
            a="sessions",
            b="users",
            signal="fk",
            path="backend/src/models/session.py",
            line=40,
        ),
        TableLink(
            a="sessions",
            b="users",
            signal="same_file",
            path="backend/src/models/session.py",
            line=50,
        ),
        TableLink(
            a="sessions",
            b="users",
            signal="comparison:ambiguous",
            path="backend/src/services/users.py",
            line=60,
        ),
    ]

    relations = _table_relations(links)

    assert len(relations) == 1
    assert (
        relations[0].src,
        relations[0].dst,
        relations[0].label,
        relations[0].kind,
        relations[0].source.path,
        relations[0].source.lines,
    ) == (
        "sessions",
        "users",
        "declared FK",
        "enforced",
        "backend/src/models/session.py",
        (40, 40),
    )


def test_domain_schema_key_tables_include_cross_feature_relation_endpoints() -> None:
    table_names = ["a", "b", "c", "d", "z"]
    tables = {
        name: Table(
            name=name,
            class_name=name.capitalize(),
            columns=[Column(name="id", type="Integer", primary_key=True)],
            source=CodeSource(
                path=f"backend/src/models/{name}.py",
                lines=(1, 1),
            ),
        )
        for name in table_names
    }
    feature_map = FeatureMap(
        commit="a" * 40,
        domain="test",
        threshold=0.25,
        tables=table_names,
        features=[
            Feature(id="a", tables=["a", "b", "c", "d"], files=[], table_links=[]),
            Feature(id="z", tables=["z"], files=[], table_links=[]),
        ],
        cross_links=[
            TableLink(
                a="d",
                b="z",
                signal="primaryjoin",
                path="backend/src/models/d.py",
                line=8,
            )
        ],
        uncovered=[],
        unmapped_tags=[],
        counts=FeatureCounts(
            domain_files=0,
            primary_placed=0,
            shared=0,
            uncovered=0,
            web=0,
            deployment=0,
            skills=0,
            unparseable=0,
        ),
    )

    data = _domain_data(feature_map, {}, tables)

    assert [domain.key_tables for domain in data.domains] == [
        ["a", "b", "c", "d"],
        ["z"],
    ]
    assert [
        (relation.src, relation.dst, relation.label) for relation in data.relations
    ] == [("d", "z", "ORM join")]
