"""The page model: what Devin writes per page, and what the renderer draws from."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RECAP_BULLET_LIMIT = 5


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CodeSource(_Strict):
    path: str
    lines: tuple[int, int]


class NotionSource(_Strict):
    notion: str


Source = CodeSource | NotionSource


class Claim(_Strict):
    text: str
    sources: list[Source] = Field(min_length=1)


class Node(_Strict):
    id: str
    label: str
    kind: Literal[
        "component", "database", "queue", "actor", "cloud", "interface", "node"
    ]
    page: str | None = None
    source: Source


class Edge(_Strict):
    src: str = Field(alias="from")
    dst: str = Field(alias="to")
    label: str
    source: Source


class BlockDiagram(_Strict):
    nodes: list[Node] = Field(min_length=1)
    edges: list[Edge]

    @model_validator(mode="after")
    def _edges_join_nodes(self) -> "BlockDiagram":
        _check_endpoints(
            {n.id for n in self.nodes},
            [(e.src, e.dst) for e in self.edges],
            "block edge",
        )
        return self


class Participant(_Strict):
    id: str
    label: str
    kind: Literal[
        "participant",
        "actor",
        "database",
        "queue",
        "boundary",
        "control",
        "entity",
        "collections",
    ]
    source: Source


class Step(_Strict):
    src: str = Field(alias="from")
    dst: str = Field(alias="to")
    label: str
    reply: bool = False
    source: Source


class Sequence(_Strict):
    title: str
    summary: str
    participants: list[Participant] = Field(min_length=2)
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def _steps_join_participants(self) -> "Sequence":
        _check_endpoints(
            {p.id for p in self.participants},
            [(s.src, s.dst) for s in self.steps],
            f"step in '{self.title}'",
        )
        return self


class State(_Strict):
    id: str
    label: str
    source: Source


class Transition(_Strict):
    src: str = Field(alias="from")
    dst: str = Field(alias="to")
    label: str
    source: Source


class StateMachine(_Strict):
    title: str
    entity: str
    states: list[State] = Field(min_length=2)
    initial: str
    final: list[str] = []
    transitions: list[Transition] = Field(min_length=1)

    @model_validator(mode="after")
    def _transitions_join_states(self) -> "StateMachine":
        ids = {s.id for s in self.states}
        _check_endpoints(
            ids,
            [(t.src, t.dst) for t in self.transitions],
            f"transition in '{self.title}'",
        )
        _check_endpoints(
            ids,
            [(self.initial, s) for s in self.final],
            f"initial/final of '{self.title}'",
        )
        return self


class NoSqlStore(_Strict):
    name: str
    kind: Literal[
        "redis",
        "mongo",
        "dynamo",
        "kv",
        "s3",
        "opensearch",
        "snowflake",
        "databricks",
        "sqs",
        "other",
    ]
    fields: list[str]
    source: Source


class DataModel(_Strict):
    tables: list[str] = []
    stores: list[NoSqlStore] = []


class SummaryTable(_Strict):
    columns: list[str] = Field(min_length=2)
    rows: list[list[str]] = Field(min_length=1)
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def _rows_match_columns(self) -> "SummaryTable":
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"row {row} has {len(row)} cells, expected {len(self.columns)}"
                )
        return self


class Tldr(_Strict):
    summary: list[Claim] = Field(min_length=1, max_length=RECAP_BULLET_LIMIT)
    key_points: list[Claim] = Field(max_length=RECAP_BULLET_LIMIT)
    table: SummaryTable
    notes: list[Claim] = Field(max_length=RECAP_BULLET_LIMIT)


class Related(_Strict):
    label: str
    reason: str
    page: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _has_one_target(self) -> "Related":
        if (self.page is None) == (self.url is None):
            raise ValueError(
                f"related '{self.label}' needs exactly one of page/url, got page={self.page} url={self.url}"
            )
        return self


class NotionDoc(_Strict):
    title: str
    url: str
    last_edited: str
    excerpt: str


class Page(_Strict):
    id: str
    title: str
    parent: str | None
    covers: list[str] = Field(min_length=1)
    commit: str = Field(min_length=7)
    tldr: Tldr
    block: BlockDiagram
    data: DataModel
    sequences: list[Sequence]
    states: list[StateMachine]
    related: list[Related]
    notion: list[NotionDoc]


def _check_endpoints(known: set[str], pairs: list[tuple[str, str]], what: str) -> None:
    for a, b in pairs:
        for end in (a, b):
            if end not in known:
                raise ValueError(
                    f"{what} {a}->{b} names unknown id '{end}'; known: {sorted(known)}"
                )


def page_sources(page: Page) -> list[tuple[str, Source]]:
    """Every (element description, source) pair on a page, for the citation check and source lists."""
    pairs: list[tuple[str, Source]] = []
    tldr = page.tldr
    for claim in [*tldr.summary, *tldr.key_points, *tldr.notes]:
        pairs += [(f"TLDR: {claim.text[:60]}", s) for s in claim.sources]
    pairs += [("TLDR table", s) for s in tldr.table.sources]
    pairs += [(f"block node {n.id}", n.source) for n in page.block.nodes]
    pairs += [(f"block edge {e.src}->{e.dst}", e.source) for e in page.block.edges]
    pairs += [(f"store {s.name}", s.source) for s in page.data.stores]
    for seq in page.sequences:
        pairs += [
            (f"'{seq.title}' participant {p.id}", p.source) for p in seq.participants
        ]
        pairs += [(f"'{seq.title}' step {s.src}->{s.dst}", s.source) for s in seq.steps]
    for sm in page.states:
        pairs += [(f"'{sm.title}' state {s.id}", s.source) for s in sm.states]
        pairs += [
            (f"'{sm.title}' transition {t.src}->{t.dst}", t.source)
            for t in sm.transitions
        ]
    return pairs
