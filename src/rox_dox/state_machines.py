"""Turn the deterministic states report into cited state diagrams for a page."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import PurePosixPath

from rox_dox.model import CodeSource, State, StateMachine, Transition
from rox_dox.states import StateEnum, StatesReport


def _source(path: str, line: int) -> CodeSource:
    return CodeSource(path=path, lines=(line, line))


def _is_lifecycle(state_enum: StateEnum) -> bool:
    """An enum is a lifecycle when something persists or assigns its members."""
    return bool(state_enum.columns or state_enum.sets or state_enum.transitions)


def _belongs_to(
    state_enum: StateEnum,
    paths: Collection[str],
    tables: Collection[str],
) -> bool:
    owned_paths = set(paths)
    if state_enum.path in owned_paths:
        return True
    if any(column.table in tables for column in state_enum.columns):
        return True
    if any(state_set.path in owned_paths for state_set in state_enum.sets):
        return True
    return any(transition.path in owned_paths for transition in state_enum.transitions)


def _entity(state_enum: StateEnum) -> str:
    columns = sorted(
        {f"{column.table}.{column.column}" for column in state_enum.columns}
    )
    return ", ".join(columns) if columns else state_enum.enum


def _state_machine(state_enum: StateEnum) -> StateMachine:
    members = {member.name for member in state_enum.members}
    return StateMachine(
        title=f"{state_enum.enum} lifecycle",
        entity=_entity(state_enum),
        states=[
            State(
                id=member.name,
                label=member.name,
                source=_source(state_enum.path, member.line),
            )
            for member in state_enum.members
        ],
        transitions=[
            Transition(
                src=transition.from_member,
                dst=transition.to_member,
                event=f"{PurePosixPath(transition.path).name}:{transition.line}",
                source=_source(transition.path, transition.line),
            )
            for transition in state_enum.transitions
            if transition.from_member in members and transition.to_member in members
        ],
    )


def page_state_machines(
    report: StatesReport | None,
    *,
    paths: Collection[str],
    tables: Collection[str],
) -> list[StateMachine]:
    """Lifecycle enums defined, assigned or persisted inside a page's files/tables."""
    if report is None:
        return []
    return [
        _state_machine(state_enum)
        for state_enum in report.enums
        if _is_lifecycle(state_enum) and _belongs_to(state_enum, paths, tables)
    ]
