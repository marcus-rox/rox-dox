from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _first_duplicate(values: list[str]) -> str | None:
    counts = Counter(values)
    return next((value for value in values if counts[value] > 1), None)


class CodeSource(Model):
    path: str
    lines: tuple[int, int]


class NotionSource(Model):
    notion: str


Source = CodeSource | NotionSource


class Claim(Model):
    text: str
    sources: list[Source] = Field(min_length=1)


class Node(Model):
    id: str
    label: str
    source: Source
    link: str | None = None
    kind: Literal["component", "store", "external", "queue"] = "component"


class Edge(Model):
    src: str
    dst: str
    label: str
    source: Source

    @model_validator(mode="before")
    @classmethod
    def require_source(cls, values: Any) -> Any:
        if isinstance(values, dict) and "source" not in values:
            src = values.get("src", "<unknown>")
            dst = values.get("dst", "<unknown>")
            raise ValueError(f"block edge {src}->{dst}: missing source")
        return values


class BlockDiagram(Model):
    nodes: list[Node]
    edges: list[Edge]

    @model_validator(mode="after")
    def validate_structure(self) -> BlockDiagram:
        node_ids = [node.id for node in self.nodes]
        declared_nodes = set(node_ids)
        duplicate_id = _first_duplicate(node_ids)
        if duplicate_id is not None:
            raise ValueError(f"block diagram: duplicate node id '{duplicate_id}'")

        for edge in self.edges:
            if edge.src not in declared_nodes:
                raise ValueError(
                    f"block edge {edge.src}->{edge.dst}: unknown node '{edge.src}'"
                )
            if edge.dst not in declared_nodes:
                raise ValueError(
                    f"block edge {edge.src}->{edge.dst}: unknown node '{edge.dst}'"
                )
        return self


class Participant(Model):
    id: str
    label: str
    source: Source


class Step(Model):
    src: str
    dst: str
    message: str
    source: Source


class Sequence(Model):
    title: str
    participants: list[Participant]
    steps: list[Step]

    @model_validator(mode="after")
    def validate_structure(self) -> Sequence:
        participant_ids = [participant.id for participant in self.participants]
        declared_participants = set(participant_ids)
        duplicate_id = _first_duplicate(participant_ids)
        if duplicate_id is not None:
            raise ValueError(
                f"sequence '{self.title}': duplicate participant id '{duplicate_id}'"
            )

        for step_number, step in enumerate(self.steps, start=1):
            if step.src not in declared_participants:
                raise ValueError(
                    f"sequence '{self.title}' step {step_number} "
                    f"{step.src}->{step.dst}: "
                    f"unknown participant '{step.src}'"
                )
            if step.dst not in declared_participants:
                raise ValueError(
                    f"sequence '{self.title}' step {step_number} "
                    f"{step.src}->{step.dst}: "
                    f"unknown participant '{step.dst}'"
                )
        return self


class State(Model):
    id: str
    label: str
    source: Source


class Transition(Model):
    src: str
    dst: str
    event: str
    source: Source


class StateMachine(Model):
    title: str
    entity: str
    states: list[State]
    transitions: list[Transition]

    @model_validator(mode="after")
    def validate_structure(self) -> StateMachine:
        state_ids = [state.id for state in self.states]
        declared_states = set(state_ids)
        duplicate_id = _first_duplicate(state_ids)
        if duplicate_id is not None:
            raise ValueError(
                f"state machine '{self.title}': duplicate state id '{duplicate_id}'"
            )

        for transition in self.transitions:
            if transition.src not in declared_states:
                raise ValueError(
                    f"state machine '{self.title}' transition "
                    f"{transition.src}->{transition.dst}: "
                    f"unknown state '{transition.src}'"
                )
            if transition.dst not in declared_states:
                raise ValueError(
                    f"state machine '{self.title}' transition "
                    f"{transition.src}->{transition.dst}: "
                    f"unknown state '{transition.dst}'"
                )
        return self


class NoSqlStore(Model):
    name: str
    kind: str
    fields: list[str]
    source: Source


class DataModel(Model):
    sql_tables: list[str] = Field(default_factory=list)
    nosql: list[NoSqlStore] = Field(default_factory=list)


class SummaryTable(Model):
    columns: list[str]
    rows: list[list[str]]
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rows(self) -> SummaryTable:
        for row_number, row in enumerate(self.rows, start=1):
            if len(row) != len(self.columns):
                raise ValueError(
                    f"TLDR table row {row_number} has {len(row)} cells; "
                    f"expected {len(self.columns)} columns"
                )
        return self


class Tldr(Model):
    summary: list[Claim]
    key_points: list[Claim]
    table: SummaryTable
    notes: list[Claim]


class Related(Model):
    label: str
    page: str | None = None
    url: str | None = None
    source: Source

    @model_validator(mode="after")
    def validate_target(self) -> Related:
        if (self.page is None) == (self.url is None):
            raise ValueError("related item must specify exactly one of page or url")
        return self


class NotionDoc(Model):
    title: str
    url: str
    last_edited: date
    excerpt: str


class Page(Model):
    id: str
    title: str
    commit: str
    parent: str | None
    paths: list[str] = Field(min_length=1)
    tldr: Tldr
    block: BlockDiagram
    data: DataModel
    sequences: list[Sequence]
    states: list[StateMachine]
    related: list[Related]
    notion: list[NotionDoc]

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, paths: list[str]) -> list[str]:
        for path in paths:
            parsed = PurePosixPath(path)
            if (
                not path
                or path.endswith("/")
                or parsed.is_absolute()
                or ".." in parsed.parts
            ):
                raise ValueError(f"path '{path}' is not repo-relative")
        return paths


def _claim_sources(claims: list[Claim], section: str) -> list[tuple[str, Source]]:
    return [
        (f"TLDR {section}: {claim.text[:60]}", source)
        for claim in claims
        for source in claim.sources
    ]


def page_sources(page: Page) -> list[tuple[str, Source]]:
    sources: list[tuple[str, Source]] = []
    sources.extend(_claim_sources(page.tldr.summary, "summary"))
    sources.extend(_claim_sources(page.tldr.key_points, "key point"))
    sources.extend((("TLDR table", source) for source in page.tldr.table.sources))
    sources.extend(_claim_sources(page.tldr.notes, "note"))
    sources.extend((f"block node {node.id}", node.source) for node in page.block.nodes)
    sources.extend(
        (f"block edge {edge.src}->{edge.dst}", edge.source) for edge in page.block.edges
    )

    for sequence in page.sequences:
        sources.extend(
            (
                f"sequence '{sequence.title}' participant {participant.id}",
                participant.source,
            )
            for participant in sequence.participants
        )
        sources.extend(
            (
                f"sequence '{sequence.title}' step {step_number} "
                f"{step.src}->{step.dst}",
                step.source,
            )
            for step_number, step in enumerate(sequence.steps, start=1)
        )

    for state_machine in page.states:
        sources.extend(
            (
                f"state machine '{state_machine.title}' state {state.id}",
                state.source,
            )
            for state in state_machine.states
        )
        sources.extend(
            (
                f"state machine '{state_machine.title}' transition "
                f"{transition.src}->{transition.dst}",
                transition.source,
            )
            for transition in state_machine.transitions
        )

    sources.extend(
        (f"NoSQL store {store.name}", store.source) for store in page.data.nosql
    )
    sources.extend(
        (f"related '{related.label}'", related.source) for related in page.related
    )
    return sources
