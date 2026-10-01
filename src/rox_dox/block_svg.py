"""Column-layout SVG renderer for block diagrams.

Top-level groups become columns, read left to right. Nested groups become
labelled sections inside their column. Edges leave a card on its right side
and enter the target on its left side, routed orthogonally through the gutters
between columns; edges that skip columns or point backwards travel along a
shared channel below the columns.
"""

from __future__ import annotations

import html
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass, field

from rox_dox.links import page_href, source_url
from rox_dox.model import Edge, Group, Node, Page, Source


FONT_FAMILY = "Helvetica, Arial, sans-serif"
TEXT_COLOR = "#23334a"
MUTED_COLOR = "#5b6878"
ARROW_COLOR = "#40536a"
SECTION_FILL = "#fafbfd"
SECTION_STROKE = "#d5dce6"
KIND_STYLES = {
    "component": ("#f5f8fe", "#145bc4", ""),
    "store": ("#fff8ef", "#c9781a", "STORE"),
    "queue": ("#f1faf4", "#2f8f57", "QUEUE"),
    "external": ("#fbf5ff", "#7d4cc0", "EXTERNAL"),
}
UNGROUPED_COLUMN_LABEL = "Other"

CARD_WIDTH = 300
CARD_PADDING = 14
TITLE_LINE_HEIGHT = 20
DETAIL_LINE_HEIGHT = 17
DETAIL_FONT_SIZE = 11.5
DETAIL_CHARS_PER_LINE = 44
TITLE_CHARS_PER_LINE = 34
CHANNEL_ARROW_COLOR = "#8593a6"
CARD_GAP = 16
SECTION_INSET = 12
SECTION_HEADER_HEIGHT = 28
SECTION_GAP = 18
COLUMN_HEADER_HEIGHT = 46
TOP_MARGIN = 16
OUTER_MARGIN = 24
LANE_MARGIN = 14
LANE_STEP = 10
LABEL_CHAR_WIDTH = 6.1
LABEL_PADDING = 10
MIN_GUTTER_WIDTH = 90
CHANNEL_OFFSET = 34
CHANNEL_STEP = 14
LEGEND_HEIGHT = 40


@dataclass
class _Card:
    node: Node
    x: float
    y: float
    height: float
    outgoing: list[Edge] = field(default_factory=list)
    incoming: list[Edge] = field(default_factory=list)


@dataclass
class _Section:
    group: Group
    x: float
    y: float
    width: float
    height: float


@dataclass
class _Column:
    label: str
    source: Source | None
    width: float
    sections: list[_Section] = field(default_factory=list)
    cards: list[_Card] = field(default_factory=list)
    height: float = 0.0
    x: float = 0.0


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _wrap(text: str, width: int = DETAIL_CHARS_PER_LINE) -> list[str]:
    return textwrap.wrap(text, width) or [text]


def _title_lines(node: Node) -> list[str]:
    suffix = "  ›" if node.link is not None else ""
    return _wrap(node.label + suffix, TITLE_CHARS_PER_LINE)


def _card_height(node: Node) -> float:
    detail_lines = sum(len(_wrap(detail.text)) for detail in node.details)
    gaps = max(len(node.details) - 1, 0) * 3
    title_height = len(_title_lines(node)) * TITLE_LINE_HEIGHT
    return (
        2 * CARD_PADDING
        + title_height
        + detail_lines * DETAIL_LINE_HEIGHT
        + gaps
        + (6 if node.details else 0)
    )


def _group_depth(group_id: str, children: Mapping[str, list[Group]]) -> int:
    child_depths = [_group_depth(child.id, children) for child in children[group_id]]
    return 1 + max(child_depths, default=0)


def _place_group_contents(
    column: _Column,
    group_id: str,
    *,
    x: float,
    y: float,
    width: float,
    children: Mapping[str, list[Group]],
    members: Mapping[str | None, list[Node]],
) -> float:
    for node in members[group_id]:
        height = _card_height(node)
        column.cards.append(
            _Card(node=node, x=x + (width - CARD_WIDTH) / 2, y=y, height=height)
        )
        y += height + CARD_GAP
    for child in children[group_id]:
        top = y
        bottom = _place_group_contents(
            column,
            child.id,
            x=x + SECTION_INSET,
            y=y + SECTION_HEADER_HEIGHT,
            width=width - 2 * SECTION_INSET,
            children=children,
            members=members,
        )
        section_height = bottom - top - CARD_GAP + SECTION_INSET
        column.sections.append(
            _Section(group=child, x=x, y=top, width=width, height=section_height)
        )
        y = top + section_height + SECTION_GAP
    return y


def _columns(page: Page) -> list[_Column]:
    block = page.block
    children: dict[str, list[Group]] = {group.id: [] for group in block.groups}
    members: dict[str | None, list[Node]] = {group.id: [] for group in block.groups}
    members[None] = []
    for group in block.groups:
        if group.parent is not None:
            children[group.parent].append(group)
    for node in block.nodes:
        members[node.group].append(node)

    columns = []
    top = TOP_MARGIN + COLUMN_HEADER_HEIGHT
    for group in block.groups:
        if group.parent is not None:
            continue
        nested_depth = _group_depth(group.id, children) - 1
        width = CARD_WIDTH + 2 * SECTION_INSET * nested_depth
        column = _Column(label=group.label, source=group.source, width=width)
        bottom = _place_group_contents(
            column,
            group.id,
            x=0,
            y=top,
            width=width,
            children=children,
            members=members,
        )
        column.height = bottom - top
        columns.append(column)
    if members[None]:
        column = _Column(label=UNGROUPED_COLUMN_LABEL, source=None, width=CARD_WIDTH)
        y = top
        for node in members[None]:
            height = _card_height(node)
            column.cards.append(_Card(node=node, x=0, y=y, height=height))
            y += height + CARD_GAP
        column.height = y - top
        columns.append(column)
    return columns


def _shift_column(column: _Column, dx: float) -> None:
    column.x = dx
    for card in column.cards:
        card.x += dx
    for section in column.sections:
        section.x += dx


def _label_width(label: str) -> float:
    return len(label) * LABEL_CHAR_WIDTH + LABEL_PADDING


@dataclass(frozen=True)
class _Route:
    edge: Edge
    points: list[tuple[float, float]]
    label_x: float
    label_y: float
    via_channel: bool


def _port_y(card: _Card, index: int, count: int) -> float:
    return card.y + card.height * (index + 1) / (count + 1)


def _layout(
    page: Page,
) -> tuple[list[_Column], dict[str, _Card], list[_Route], float, float]:
    columns = _columns(page)
    cards = {card.node.id: card for column in columns for card in column.cards}
    column_of = {
        card.node.id: index
        for index, column in enumerate(columns)
        for card in column.cards
    }
    edges = page.block.edges
    for edge in edges:
        cards[edge.src].outgoing.append(edge)
        cards[edge.dst].incoming.append(edge)

    gutter_count = len(columns) + 1
    lanes: list[list[Edge]] = [[] for _ in range(gutter_count)]
    entry_labels: list[float] = [0.0] * gutter_count
    channel_edges = []
    for edge in edges:
        exit_gutter = column_of[edge.src] + 1
        entry_gutter = column_of[edge.dst]
        lanes[exit_gutter].append(edge)
        if exit_gutter != entry_gutter:
            lanes[entry_gutter].append(edge)
            channel_edges.append(edge)
        entry_labels[entry_gutter] = max(
            entry_labels[entry_gutter], _label_width(edge.label)
        )

    gutter_widths = []
    for index in range(gutter_count):
        lane_space = LANE_MARGIN + len(lanes[index]) * LANE_STEP if lanes[index] else 0
        width = lane_space + entry_labels[index]
        is_margin = index in (0, gutter_count - 1)
        if width == 0:
            gutter_widths.append(OUTER_MARGIN if is_margin else MIN_GUTTER_WIDTH)
        else:
            gutter_widths.append(max(width + LABEL_PADDING, MIN_GUTTER_WIDTH))

    x = gutter_widths[0]
    gutter_lefts = [0.0]
    for index, column in enumerate(columns):
        _shift_column(column, x)
        x += column.width
        gutter_lefts.append(x)
        x += gutter_widths[index + 1]
    width = x

    columns_bottom = max(
        (TOP_MARGIN + COLUMN_HEADER_HEIGHT + column.height for column in columns),
        default=0,
    )
    channel_top = columns_bottom + CHANNEL_OFFSET

    exit_y: dict[int, float] = {}
    entry_y: dict[int, float] = {}
    for card in cards.values():
        outgoing = sorted(card.outgoing, key=lambda edge: cards[edge.dst].y)
        for index, edge in enumerate(outgoing):
            exit_y[id(edge)] = _port_y(card, index, len(outgoing))
        incoming = sorted(card.incoming, key=lambda edge: cards[edge.src].y)
        for index, edge in enumerate(incoming):
            entry_y[id(edge)] = _port_y(card, index, len(incoming))

    lane_x: dict[tuple[int, int], float] = {}
    for gutter, gutter_edges in enumerate(lanes):
        ordered = sorted(gutter_edges, key=lambda edge: exit_y[id(edge)])
        for index, edge in enumerate(ordered):
            lane_x[(gutter, id(edge))] = (
                gutter_lefts[gutter] + LANE_MARGIN + index * LANE_STEP
            )

    channel_y = {
        id(edge): channel_top + index * CHANNEL_STEP
        for index, edge in enumerate(channel_edges)
    }

    routes = []
    for edge in edges:
        source_card = cards[edge.src]
        target_card = cards[edge.dst]
        exit_gutter = column_of[edge.src] + 1
        entry_gutter = column_of[edge.dst]
        start = (source_card.x + CARD_WIDTH, exit_y[id(edge)])
        end = (target_card.x, entry_y[id(edge)])
        first_lane = lane_x[(exit_gutter, id(edge))]
        if exit_gutter == entry_gutter:
            points = [start, (first_lane, start[1]), (first_lane, end[1]), end]
        else:
            last_lane = lane_x[(entry_gutter, id(edge))]
            bus = channel_y[id(edge)]
            points = [
                start,
                (first_lane, start[1]),
                (first_lane, bus),
                (last_lane, bus),
                (last_lane, end[1]),
                end,
            ]
        routes.append(
            _Route(
                edge=edge,
                points=points,
                label_x=end[0] - 8,
                label_y=end[1] - 5,
                via_channel=len(points) > 4,
            )
        )

    channel_bottom = channel_top + max(len(channel_edges) - 1, 0) * CHANNEL_STEP
    height = (
        (channel_bottom if channel_edges else columns_bottom)
        + CHANNEL_OFFSET
        + LEGEND_HEIGHT
    )
    return columns, cards, routes, width, height


def _link(href: str, content: str) -> str:
    return f'<a href="{_escape(href)}" target="_top">{content}</a>'


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    weight: int = 400,
    color: str = TEXT_COLOR,
    anchor: str = "start",
    extra: str = "",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT_FAMILY}" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{extra}>'
        f"{_escape(value)}</text>"
    )


def _card_svg(card: _Card, *, page: Page, repo_url: str) -> str:
    node = card.node
    fill, stroke, tag = KIND_STYLES[node.kind]
    parts = [
        f'<rect x="{card.x:.1f}" y="{card.y:.1f}" width="{CARD_WIDTH}" '
        f'height="{card.height:.1f}" rx="8" fill="{fill}" stroke="{stroke}" '
        'stroke-width="1.5"/>'
    ]
    title_y = card.y + CARD_PADDING + 13
    left = card.x + CARD_PADDING
    if node.link is not None:
        title_href = page_href(page.id, node.link)
        title_color = stroke
    else:
        title_href = source_url(node.source, repo_url=repo_url, commit=page.commit)
        title_color = TEXT_COLOR
    title_lines = _title_lines(node)
    title = "".join(
        _text(
            left,
            title_y + index * TITLE_LINE_HEIGHT,
            line,
            size=13.5,
            weight=700,
            color=title_color,
        )
        for index, line in enumerate(title_lines)
    )
    title_y += (len(title_lines) - 1) * TITLE_LINE_HEIGHT
    parts.append(f'<g class="card-title">{_link(title_href, title)}</g>')
    if tag:
        parts.append(
            _text(
                card.x + CARD_WIDTH - CARD_PADDING,
                card.y + CARD_PADDING + 2,
                tag,
                size=8.5,
                weight=700,
                color=stroke,
                anchor="end",
                extra=' letter-spacing="0.08em"',
            )
        )
    y = title_y + 6
    for detail in node.details:
        lines = _wrap(detail.text)
        texts = []
        for line_index, line in enumerate(lines):
            y += DETAIL_LINE_HEIGHT
            prefix = "•  " if line_index == 0 else "    "
            texts.append(_text(left, y, prefix + line, size=DETAIL_FONT_SIZE))
        href = source_url(detail.sources[0], repo_url=repo_url, commit=page.commit)
        parts.append(f'<g class="card-detail">{_link(href, "".join(texts))}</g>')
        y += 3
    return "".join(parts)


def _section_svg(section: _Section, *, page: Page, repo_url: str) -> str:
    href = source_url(section.group.source, repo_url=repo_url, commit=page.commit)
    label = _text(
        section.x + 12,
        section.y + 18,
        section.group.label,
        size=10.5,
        weight=700,
        color=MUTED_COLOR,
        extra=' letter-spacing="0.06em"',
    )
    return (
        f'<rect x="{section.x:.1f}" y="{section.y:.1f}" width="{section.width:.1f}" '
        f'height="{section.height:.1f}" rx="8" fill="{SECTION_FILL}" '
        f'stroke="{SECTION_STROKE}" stroke-dasharray="4 3"/>'
        f'<g class="section-label">{_link(href, label)}</g>'
    )


def _column_header_svg(
    index: int, column: _Column, *, page: Page, repo_url: str
) -> str:
    label = _text(
        column.x + column.width / 2,
        TOP_MARGIN + 18,
        f"{index} · {column.label}",
        size=13,
        weight=700,
        anchor="middle",
        extra=' letter-spacing="0.03em"',
    )
    if column.source is None:
        return label
    href = source_url(column.source, repo_url=repo_url, commit=page.commit)
    return f'<g class="column-label">{_link(href, label)}</g>'


def _route_path_svg(route: _Route) -> str:
    path = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(route.points)
    )
    color, marker = (
        (CHANNEL_ARROW_COLOR, "block-arrow-channel")
        if route.via_channel
        else (ARROW_COLOR, "block-arrow")
    )
    return (
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.4" '
        f'stroke-linejoin="round" marker-end="url(#{marker})"/>'
    )


def _route_label_svg(route: _Route, *, page: Page, repo_url: str) -> str:
    href = source_url(route.edge.source, repo_url=repo_url, commit=page.commit)
    label = _text(
        route.label_x,
        route.label_y,
        route.edge.label,
        size=11,
        color=MUTED_COLOR,
        anchor="end",
        extra=' class="edge-label"',
    )
    return f'<g class="edge-link">{_link(href, label)}</g>'


def _legend_svg(height: float) -> str:
    y = height - LEGEND_HEIGHT / 2
    x = OUTER_MARGIN
    parts = []
    for kind, (fill, stroke, _tag) in KIND_STYLES.items():
        parts.append(
            f'<rect x="{x}" y="{y - 7:.1f}" width="14" height="14" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        parts.append(_text(x + 20, y + 4, kind, size=11, color=MUTED_COLOR))
        x += 110
    parts.append(
        _text(
            x + 10,
            y + 4,
            "Click a box, line or arrow label to open its source.",
            size=11,
            color=MUTED_COLOR,
        )
    )
    return "".join(parts)


def block_svg(page: Page, *, repo_url: str) -> str:
    columns, cards, routes, width, height = _layout(page)
    body = []
    for column in columns:
        for section in sorted(column.sections, key=lambda section: section.y):
            body.append(_section_svg(section, page=page, repo_url=repo_url))
    for index, column in enumerate(columns, start=1):
        body.append(_column_header_svg(index, column, page=page, repo_url=repo_url))
    body.extend(_route_path_svg(route) for route in routes)
    for card in cards.values():
        body.append(_card_svg(card, page=page, repo_url=repo_url))
    body.extend(
        _route_label_svg(route, page=page, repo_url=repo_url) for route in routes
    )
    body.append(_legend_svg(height))
    return (
        f'<svg class="block-svg" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        'role="img">'
        '<defs><marker id="block-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0 0 L10 5 L0 10Z" fill="{ARROW_COLOR}"/></marker>'
        '<marker id="block-arrow-channel" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0 0 L10 5 L0 10Z" fill="{CHANNEL_ARROW_COLOR}"/></marker></defs>'
        f"{''.join(body)}</svg>"
    )
