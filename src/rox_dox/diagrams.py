from __future__ import annotations

import sys
from collections.abc import Mapping
from urllib.parse import quote

from rox_dox.links import page_href, source_url
from rox_dox.model import Group, Node, Page, Sequence, Source, StateMachine
from rox_dox.plantuml import DiagramError
from rox_dox.schema import Table


MAX_DIAGRAM_ELEMENTS = 12
LINK_TOOLTIP = "Open cited source"
SKINPARAMS = """skinparam backgroundColor transparent
skinparam defaultFontName Helvetica
skinparam defaultFontSize 13
skinparam roundCorner 14
skinparam shadowing false
skinparam ArrowColor #333333
skinparam rectangleBackgroundColor #E8F0FE
skinparam rectangleBorderColor #3B6FD8
skinparam databaseBackgroundColor #FFF4E5
skinparam databaseBorderColor #E08A1E
skinparam cloudBackgroundColor #F3E8FD
skinparam cloudBorderColor #8B4FD1
skinparam queueBackgroundColor #E7F6EC
skinparam queueBorderColor #2F9E5B
skinparam participantBackgroundColor #E8F0FE
skinparam participantBorderColor #3B6FD8
skinparam sequenceLifeLineBorderColor #9AA4B2
skinparam stateBackgroundColor #E8F0FE
skinparam stateBorderColor #3B6FD8
skinparam classBackgroundColor #E8F0FE
skinparam classHeaderBackgroundColor #E8F0FE
skinparam classBorderColor #3B6FD8"""
NODE_SHAPES = {
    "component": "rectangle",
    "store": "database",
    "external": "cloud",
    "queue": "queue",
}
PLANTUML_URL_SAFE_CHARACTERS = "/:#?&=+%"


def _escape_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _quoted_label(value: str) -> str:
    return f'"{_escape_label(value)}"'


def _plantuml_url(url: str) -> str:
    return quote(url, safe=PLANTUML_URL_SAFE_CHARACTERS)


def _linked_label(url: str, label: str) -> str:
    escaped_label = _escape_label(label).replace("[", "~[").replace("]", "~]")
    return f"[[{_plantuml_url(url)}{{{LINK_TOOLTIP}}} {escaped_label}]]"


def _diagram_header(*, smetana: bool) -> list[str]:
    lines = ["@startuml"]
    if smetana:
        lines.append("!pragma layout smetana")
    lines.extend(SKINPARAMS.splitlines())
    return lines


def _element_url(page: Page, repo_url: str, source: Source) -> str:
    return source_url(source, repo_url=repo_url, commit=page.commit)


def _node_plantuml(
    node: Node,
    *,
    alias: str,
    page: Page,
    repo_url: str,
    indentation: str,
) -> list[str]:
    label = node.label
    if node.details:
        detail_lines = [f"<size:11>{detail.text}</size>" for detail in node.details]
        label = f"**{label}**\n" + "\n".join(detail_lines)
    target = (
        page_href(page.id, node.link)
        if node.link is not None
        else _element_url(page, repo_url, node.source)
    )
    return [
        f"{indentation}{NODE_SHAPES[node.kind]} {_quoted_label(label)} as {alias}",
        f"{indentation}url of {alias} is [[{_plantuml_url(target)}]]",
    ]


def _group_plantuml(
    group: Group,
    *,
    group_aliases: Mapping[str, str],
    child_groups: Mapping[str, list[Group]],
    group_nodes: Mapping[str, list[Node]],
    node_aliases: Mapping[str, str],
    page: Page,
    repo_url: str,
    indentation: str,
) -> list[str]:
    alias = group_aliases[group.id]
    child_indentation = f"{indentation}  "
    lines = [
        f"{indentation}rectangle {_quoted_label(group.label)} as {alias} #F7F9FC {{"
    ]
    for child_group in child_groups[group.id]:
        lines.extend(
            _group_plantuml(
                child_group,
                group_aliases=group_aliases,
                child_groups=child_groups,
                group_nodes=group_nodes,
                node_aliases=node_aliases,
                page=page,
                repo_url=repo_url,
                indentation=child_indentation,
            )
        )
    for node in group_nodes[group.id]:
        lines.extend(
            _node_plantuml(
                node,
                alias=node_aliases[node.id],
                page=page,
                repo_url=repo_url,
                indentation=child_indentation,
            )
        )
    lines.append(f"{indentation}}}")
    url = _element_url(page, repo_url, group.source)
    lines.append(f"{indentation}url of {alias} is [[{_plantuml_url(url)}]]")
    return lines


def _aliases(ids: list[str], prefix: str) -> dict[str, str]:
    return {element_id: f"{prefix}_{index}" for index, element_id in enumerate(ids)}


def block_plantuml(page: Page, *, repo_url: str) -> str:
    node_aliases = _aliases([node.id for node in page.block.nodes], "node")
    group_aliases = _aliases([group.id for group in page.block.groups], "group")
    lines = _diagram_header(smetana=True)
    if page.block.direction == "left-right":
        lines.append("left to right direction")

    child_groups: dict[str, list[Group]] = {group.id: [] for group in page.block.groups}
    group_nodes: dict[str, list[Node]] = {group.id: [] for group in page.block.groups}
    for group in page.block.groups:
        if group.parent is not None:
            child_groups[group.parent].append(group)
    for node in page.block.nodes:
        if node.group is not None:
            group_nodes[node.group].append(node)

    for group in page.block.groups:
        if group.parent is None:
            lines.extend(
                _group_plantuml(
                    group,
                    group_aliases=group_aliases,
                    child_groups=child_groups,
                    group_nodes=group_nodes,
                    node_aliases=node_aliases,
                    page=page,
                    repo_url=repo_url,
                    indentation="",
                )
            )
    for node in page.block.nodes:
        if node.group is None:
            lines.extend(
                _node_plantuml(
                    node,
                    alias=node_aliases[node.id],
                    page=page,
                    repo_url=repo_url,
                    indentation="",
                )
            )

    for edge in page.block.edges:
        url = _element_url(page, repo_url, edge.source)
        lines.append(
            f"{node_aliases[edge.src]} --> {node_aliases[edge.dst]} : "
            f"{_linked_label(url, edge.label)}"
        )
    lines.append("@enduml")
    return "\n".join(lines)


def schema_plantuml(
    page: Page,
    *,
    repo_url: str,
    tables: Mapping[str, Table],
) -> str:
    sql_aliases = _aliases(page.data.sql_tables, "sql")
    for table_name in page.data.sql_tables:
        if table_name not in tables:
            raise DiagramError(
                f"SQL table '{table_name}' is missing for page '{page.id}'"
            )

    nosql_aliases = _aliases(
        [store.name for store in page.data.nosql],
        "nosql",
    )
    lines = _diagram_header(smetana=True)
    lines.extend(["hide circle", "hide empty methods"])
    for table_name in page.data.sql_tables:
        table = tables[table_name]
        alias = sql_aliases[table_name]
        lines.append(f"class {_quoted_label(table.name)} as {alias} {{")
        for column in table.columns:
            markers = []
            if column.primary_key:
                markers.append("<<PK>>")
            if column.foreign_key is not None:
                markers.append("<<FK>>")
            suffix = f" {' '.join(markers)}" if markers else ""
            lines.append(
                f"  {_escape_label(column.name)}: {_escape_label(column.type)}{suffix}"
            )
        lines.append("}")
        url = _element_url(page, repo_url, table.source)
        lines.append(f"url of {alias} is [[{_plantuml_url(url)}]]")

    for store in page.data.nosql:
        alias = nosql_aliases[store.name]
        kind = _escape_label(store.kind).replace(">", "\\>")
        lines.append(f"class {_quoted_label(store.name)} as {alias} <<{kind}>> {{")
        lines.extend(f"  {_escape_label(field)}" for field in store.fields)
        lines.append("}")
        url = _element_url(page, repo_url, store.source)
        lines.append(f"url of {alias} is [[{_plantuml_url(url)}]]")

    for table_name in page.data.sql_tables:
        table = tables[table_name]
        for column in table.columns:
            if column.foreign_key is None:
                continue
            referenced_name = column.foreign_key.rsplit(".", 1)[0]
            if referenced_name not in sql_aliases:
                referenced_name = referenced_name.rsplit(".", 1)[-1]
            if referenced_name not in sql_aliases:
                continue
            url = _element_url(page, repo_url, table.source)
            lines.append(
                f"{sql_aliases[table_name]} --> {sql_aliases[referenced_name]} : "
                f"{_linked_label(url, column.name)}"
            )
    lines.append("@enduml")
    return "\n".join(lines)


def sequence_plantuml(
    page: Page,
    sequence: Sequence,
    *,
    repo_url: str,
) -> str:
    participant_aliases = _aliases(
        [participant.id for participant in sequence.participants],
        "participant",
    )
    lines = _diagram_header(smetana=False)
    lines.extend(
        [
            f"title {_quoted_label(sequence.title)}",
            "autonumber",
        ]
    )
    for participant in sequence.participants:
        alias = participant_aliases[participant.id]
        lines.append(f"participant {_quoted_label(participant.label)} as {alias}")
        url = _element_url(page, repo_url, participant.source)
        lines.append(f"url of {alias} is [[{_plantuml_url(url)}]]")
    for step in sequence.steps:
        url = _element_url(page, repo_url, step.source)
        lines.append(
            f"{participant_aliases[step.src]} -> {participant_aliases[step.dst]} : "
            f"{_linked_label(url, step.message)}"
        )
    lines.append("@enduml")
    return "\n".join(lines)


def state_plantuml(
    page: Page,
    state_machine: StateMachine,
    *,
    repo_url: str,
) -> str:
    state_aliases = _aliases([state.id for state in state_machine.states], "state")
    lines = _diagram_header(smetana=True)
    lines.append(f"title {_quoted_label(state_machine.title)}")
    for state in state_machine.states:
        alias = state_aliases[state.id]
        lines.append(f"state {_quoted_label(state.label)} as {alias}")
        url = _element_url(page, repo_url, state.source)
        lines.append(f"url of {alias} is [[{_plantuml_url(url)}]]")

    if state_machine.states:
        first_state = state_machine.states[0]
        url = _element_url(page, repo_url, first_state.source)
        lines.append(
            f"[*] --> {state_aliases[first_state.id]} : {_linked_label(url, 'start')}"
        )
    for transition in state_machine.transitions:
        url = _element_url(page, repo_url, transition.source)
        lines.append(
            f"{state_aliases[transition.src]} --> {state_aliases[transition.dst]} : "
            f"{_linked_label(url, transition.event)}"
        )
    lines.append("@enduml")
    return "\n".join(lines)


def diagram_size_warnings(page: Page) -> list[str]:
    warnings = []
    if len(page.block.nodes) > MAX_DIAGRAM_ELEMENTS:
        warnings.append(
            f"warning: page '{page.id}' block diagram has {len(page.block.nodes)} nodes "
            f"(guide: {MAX_DIAGRAM_ELEMENTS})"
        )
    warnings.extend(
        f"warning: page '{page.id}' sequence '{sequence.title}' has "
        f"{len(sequence.participants)} participants (guide: {MAX_DIAGRAM_ELEMENTS})"
        for sequence in page.sequences
        if len(sequence.participants) > MAX_DIAGRAM_ELEMENTS
    )
    warnings.extend(
        f"warning: page '{page.id}' state machine '{state_machine.title}' has "
        f"{len(state_machine.states)} states (guide: {MAX_DIAGRAM_ELEMENTS})"
        for state_machine in page.states
        if len(state_machine.states) > MAX_DIAGRAM_ELEMENTS
    )
    return warnings


def emit_diagram_warnings(page: Page) -> None:
    for warning in diagram_size_warnings(page):
        print(warning, file=sys.stderr)
