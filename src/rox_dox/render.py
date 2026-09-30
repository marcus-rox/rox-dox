from __future__ import annotations

import html
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from rox_dox.diagrams import (
    block_plantuml,
    emit_diagram_warnings,
    schema_plantuml,
    sequence_plantuml,
    state_plantuml,
)
from rox_dox.links import page_href, source_url
from rox_dox.model import (
    Claim,
    Page,
    Related,
    Sequence,
    Source,
    StateMachine,
    page_sources,
)
from rox_dox.plantuml import DiagramError, render_svg
from rox_dox.schema import Table
from rox_dox.tree import SiteTree


PAGE_CSS = """\
:root {
  color-scheme: light;
  color: #182230;
  background: #f4f6f9;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-synthesis: none;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  line-height: 1.6;
}
.page-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
  grid-template-areas: "nav main aside";
  align-items: start;
  gap: 1rem;
  max-width: 1600px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}
#site-nav, #context {
  position: sticky;
  top: 0;
  max-height: 100vh;
  overflow-y: auto;
  padding: 1rem;
  border: 1px solid #e2e7ee;
  border-radius: 14px;
  background: #fff;
}
#site-nav {
  grid-area: nav;
}
#context {
  grid-area: aside;
}
.page-main {
  grid-area: main;
  min-width: 0;
}
.page-tree, .page-tree ul {
  margin: 0;
  padding-left: 1rem;
  list-style: none;
}
.page-tree {
  padding-left: 0;
}
.page-tree li {
  margin: 0.25rem 0;
}
.page-tree summary {
  cursor: pointer;
}
.page-tree a {
  display: inline-block;
  padding: 0.2rem 0.4rem;
  border-radius: 6px;
  text-decoration: none;
}
.page-tree a.current {
  background: #E8F0FE;
  color: #182230;
  font-weight: 700;
}
.breadcrumbs {
  margin: 0.25rem 0 1rem;
  color: #667085;
}
.breadcrumbs a {
  margin-right: 0.4rem;
}
.page-header {
  margin-bottom: 1.5rem;
  padding: 1.5rem 1.75rem;
  border: 1px solid #e2e7ee;
  border-radius: 14px;
  background: #fff;
}
h1, h2, h3 {
  line-height: 1.25;
}
.page-header h1 {
  margin: 0;
  font-size: clamp(1.8rem, 4vw, 2.5rem);
}
.page-meta {
  margin: 0.5rem 0 0;
  color: #667085;
  overflow-wrap: anywhere;
}
.submodules {
  margin: 0.5rem 0 0;
}
section {
  margin: 1rem 0;
  padding: 1.5rem 1.75rem;
  border: 1px solid #e2e7ee;
  border-radius: 14px;
  background: #fff;
}
section h2 {
  margin: 0 0 1rem;
  font-size: 1.35rem;
}
h3 {
  margin: 1.25rem 0 0.5rem;
  font-size: 1.05rem;
}
p {
  margin: 0.65rem 0;
}
a {
  color: #2458a6;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.15em;
}
a:hover {
  color: #173d78;
}
.toc, .claim-list, .related-list {
  margin: 0.5rem 0;
  padding-left: 1.35rem;
}
.toc li, .claim-list li, .related-list li {
  margin: 0.35rem 0;
}
.citations {
  margin-left: 0.2rem;
  white-space: nowrap;
}
.citations sup {
  margin-right: 0.2rem;
}
.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.6rem 0;
}
th, td {
  padding: 0.65rem 0.75rem;
  border: 1px solid #e2e7ee;
  text-align: left;
  vertical-align: top;
}
th {
  background: #f7f8fa;
  font-weight: 600;
}
.diagram-card {
  margin: 1rem 0 1.5rem;
}
.diagram-card h3 {
  margin-top: 0;
}
.diagram {
  max-width: 100%;
  overflow-x: auto;
  padding: 0.75rem;
  border: 1px solid #e8ecf2;
  border-radius: 10px;
  background: #fff;
}
.diagram svg {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}
.sources {
  margin-top: 0.75rem;
  color: #475467;
}
.sources summary {
  cursor: pointer;
  font-weight: 600;
}
.empty {
  color: #667085;
  font-style: italic;
}
blockquote {
  margin: 0.75rem 0;
  padding-left: 1rem;
  border-left: 3px solid #e2e7ee;
  color: #475467;
}
.related-list li {
  overflow-wrap: anywhere;
}
@media (max-width: 1100px) {
  .page-shell {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "nav"
      "main"
      "aside";
    padding: 1rem 0.75rem 2rem;
  }
  #site-nav, #context {
    position: static;
    max-height: none;
  }
  .page-header, section {
    padding: 1rem;
  }
  th, td {
    padding: 0.5rem;
  }
}"""
SECTION_LINKS = (
    ("tldr", "TLDR"),
    ("block", "Block diagram"),
    ("schema", "Schema"),
    ("sequences", "Sequence diagrams"),
    ("states", "State diagrams"),
    ("related", "Related"),
)
EMPTY_MESSAGE = "Nothing to show for this module."
SVG_NAMESPACE_ATTRIBUTES = (
    ' xmlns="http://www.w3.org/2000/svg"',
    ' xmlns:xlink="http://www.w3.org/1999/xlink"',
)
URL_SCHEME_PATTERN = re.compile(r"https?://", re.IGNORECASE)
ANCHOR_TAG_PATTERN = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
HREF_ATTRIBUTE_PATTERN = re.compile(r"""\bhref\s*=\s*(["']).*?\1""", re.IGNORECASE)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _source_href(source: Source, *, page: Page, repo_url: str) -> str:
    return source_url(source, repo_url=repo_url, commit=page.commit)


def _anchor(url: str, label: str) -> str:
    return f'<a href="{_escape(url)}">{_escape(label)}</a>'


def _citation_links(sources: list[Source], *, page: Page, repo_url: str) -> str:
    references = (
        f"<sup>{_anchor(_source_href(source, page=page, repo_url=repo_url), f'[{number}]')}</sup>"
        for number, source in enumerate(sources, start=1)
    )
    joined = " ".join(references)
    return f'<span class="citations">{joined}</span>' if joined else ""


def _claim_text(claim: Claim, *, page: Page, repo_url: str) -> str:
    return (
        f"{_escape(claim.text)}"
        f"{_citation_links(claim.sources, page=page, repo_url=repo_url)}"
    )


def _claim_list(
    claims: list[Claim],
    *,
    page: Page,
    repo_url: str,
) -> str:
    items = "".join(
        f"<li>{_claim_text(claim, page=page, repo_url=repo_url)}</li>"
        for claim in claims
    )
    return f'<ul class="claim-list">{items}</ul>'


def _table_html(page: Page, *, repo_url: str) -> str:
    table = page.tldr.table
    headings = "".join(
        f'<th scope="col">{_escape(column)}</th>' for column in table.columns
    )
    rows = "".join(
        "<tr>" + "".join(f"<td>{_escape(cell)}</td>" for cell in row) + "</tr>"
        for row in table.rows
    )
    citations = _citation_links(table.sources, page=page, repo_url=repo_url)
    return (
        '<div class="table-scroll"><table>'
        f"<thead><tr>{headings}</tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        f"<p>Sources: {citations}</p>"
    )


def _tldr_html(page: Page, *, repo_url: str) -> str:
    summary = "".join(
        f"<p>{_claim_text(claim, page=page, repo_url=repo_url)}</p>"
        for claim in page.tldr.summary
    )
    key_points = (
        _claim_list(page.tldr.key_points, page=page, repo_url=repo_url)
        if page.tldr.key_points
        else f'<p class="empty">{EMPTY_MESSAGE}</p>'
    )
    notes = (
        _claim_list(page.tldr.notes, page=page, repo_url=repo_url)
        if page.tldr.notes
        else f'<p class="empty">{EMPTY_MESSAGE}</p>'
    )
    return (
        "<h3>Summary</h3>"
        f"{summary}"
        "<h3>Key Points</h3>"
        f"{key_points}"
        "<h3>Table</h3>"
        f"{_table_html(page, repo_url=repo_url)}"
        "<h3>Interesting Notes</h3>"
        f"{notes}"
    )


def _section(section_id: str, title: str, content: str) -> str:
    return (
        f'<section id="{_escape(section_id)}">'
        f"<h2>{_escape(title)}</h2>{content}</section>"
    )


def _table_of_contents() -> str:
    links = "".join(
        f'<li><a href="#{section_id}">{_escape(title)}</a></li>'
        for section_id, title in SECTION_LINKS
    )
    return f'<ul class="toc">{links}</ul>'


def _sources_details(
    elements: Iterable[tuple[str, Source]],
    *,
    page: Page,
    repo_url: str,
) -> str:
    rows = "".join(
        "<tr>"
        f'<th scope="row">{_escape(label)}</th>'
        f"<td>{_anchor(_source_href(source, page=page, repo_url=repo_url), 'Source')}</td>"
        "</tr>"
        for label, source in elements
    )
    return (
        '<details class="sources"><summary>Sources</summary>'
        '<div class="table-scroll"><table><thead><tr>'
        '<th scope="col">Element</th><th scope="col">Citation</th>'
        f"</tr></thead><tbody>{rows}</tbody></table></div></details>"
    )


def _inline_svg(svg: str) -> str:
    for namespace_attribute in SVG_NAMESPACE_ATTRIBUTES:
        svg = svg.replace(namespace_attribute, "")
    return svg.replace("xlink:href=", "href=")


def _offline_html(document: str) -> str:
    parts: list[str] = []
    cursor = 0
    for anchor_match in ANCHOR_TAG_PATTERN.finditer(document):
        parts.append(_encode_url_schemes(document[cursor : anchor_match.start()]))
        anchor_tag = anchor_match.group()
        href_match = HREF_ATTRIBUTE_PATTERN.search(anchor_tag)
        if href_match is None:
            parts.append(_encode_url_schemes(anchor_tag))
        else:
            parts.extend(
                (
                    _encode_url_schemes(anchor_tag[: href_match.start()]),
                    href_match.group(),
                    _encode_url_schemes(anchor_tag[href_match.end() :]),
                )
            )
        cursor = anchor_match.end()
    parts.append(_encode_url_schemes(document[cursor:]))
    return "".join(parts)


def _encode_url_schemes(value: str) -> str:
    return URL_SCHEME_PATTERN.sub(
        lambda match: f"{match.group()[:-3]}&#58;//",
        value,
    )


def _diagram_markup(source: str, *, jar: Path) -> str:
    return f'<div class="diagram">{_inline_svg(render_svg(source, jar))}</div>'


def _diagram_card(
    title: str,
    source: str,
    elements: Iterable[tuple[str, Source]],
    *,
    page: Page,
    repo_url: str,
    jar: Path,
) -> str:
    try:
        diagram_markup = _diagram_markup(source, jar=jar)
    except DiagramError as error:
        raise DiagramError(f"{title}: {error}") from error
    return (
        '<article class="diagram-card">'
        f"<h3>{_escape(title)}</h3>"
        f"{diagram_markup}"
        f"{_sources_details(elements, page=page, repo_url=repo_url)}"
        "</article>"
    )


def _block_section(page: Page, *, repo_url: str, jar: Path) -> str:
    if not page.block.nodes:
        return _section(
            "block", "Block diagram", f'<p class="empty">{EMPTY_MESSAGE}</p>'
        )
    elements = [
        (label, source)
        for label, source in page_sources(page)
        if label.startswith(("block node ", "block edge "))
    ]
    diagram = block_plantuml(page, repo_url=repo_url)
    card = _diagram_card(
        "System overview",
        diagram,
        elements,
        page=page,
        repo_url=repo_url,
        jar=jar,
    )
    return _section("block", "Block diagram", card)


def _schema_sources(
    page: Page,
    tables: Mapping[str, Table],
) -> list[tuple[str, Source]]:
    elements = [
        (f"SQL table {table_name}", tables[table_name].source)
        for table_name in page.data.sql_tables
    ]
    elements.extend(
        (f"NoSQL store {store.name}", store.source) for store in page.data.nosql
    )
    return elements


def _schema_section(
    page: Page,
    *,
    repo_url: str,
    tables: Mapping[str, Table],
    jar: Path,
) -> str:
    if not page.data.sql_tables and not page.data.nosql:
        return _section("schema", "Schema", f'<p class="empty">{EMPTY_MESSAGE}</p>')
    diagram = schema_plantuml(page, repo_url=repo_url, tables=tables)
    card = _diagram_card(
        "Data stores",
        diagram,
        _schema_sources(page, tables),
        page=page,
        repo_url=repo_url,
        jar=jar,
    )
    return _section("schema", "Schema", card)


def _sequence_elements(sequence: Sequence) -> list[tuple[str, Source]]:
    elements = [
        (
            f"sequence '{sequence.title}' participant {participant.id}",
            participant.source,
        )
        for participant in sequence.participants
    ]
    elements.extend(
        (
            f"sequence '{sequence.title}' step {step_number} {step.src}->{step.dst}",
            step.source,
        )
        for step_number, step in enumerate(sequence.steps, start=1)
    )
    return elements


def _sequence_section(page: Page, *, repo_url: str, jar: Path) -> str:
    if not page.sequences:
        return _section(
            "sequences",
            "Sequence diagrams",
            f'<p class="empty">{EMPTY_MESSAGE}</p>',
        )
    cards = "".join(
        _diagram_card(
            sequence.title,
            sequence_plantuml(page, sequence, repo_url=repo_url),
            _sequence_elements(sequence),
            page=page,
            repo_url=repo_url,
            jar=jar,
        )
        for sequence in page.sequences
    )
    return _section("sequences", "Sequence diagrams", cards)


def _state_elements(state_machine: StateMachine) -> list[tuple[str, Source]]:
    elements = [
        (f"state machine '{state_machine.title}' state {state.id}", state.source)
        for state in state_machine.states
    ]
    elements.extend(
        (
            f"state machine '{state_machine.title}' transition "
            f"{transition.src}->{transition.dst}",
            transition.source,
        )
        for transition in state_machine.transitions
    )
    return elements


def _state_section(page: Page, *, repo_url: str, jar: Path) -> str:
    if not page.states:
        return _section(
            "states",
            "State diagrams",
            f'<p class="empty">{EMPTY_MESSAGE}</p>',
        )
    cards = "".join(
        _diagram_card(
            state_machine.title,
            state_plantuml(page, state_machine, repo_url=repo_url),
            _state_elements(state_machine),
            page=page,
            repo_url=repo_url,
            jar=jar,
        )
        for state_machine in page.states
    )
    return _section("states", "State diagrams", cards)


def _related_item(
    related: Related,
    *,
    page: Page,
    repo_url: str,
) -> str:
    target = (
        page_href(page.id, related.page)
        if related.page is not None
        else related.url or ""
    )
    label = _anchor(target, related.label)
    citations = _citation_links([related.source], page=page, repo_url=repo_url)
    return f"<li>{label}{citations}</li>"


def _related_section(page: Page, *, repo_url: str) -> str:
    if not page.related:
        return _section("related", "Related", f'<p class="empty">{EMPTY_MESSAGE}</p>')
    items = "".join(
        _related_item(related, page=page, repo_url=repo_url) for related in page.related
    )
    return _section("related", "Related", f'<ul class="related-list">{items}</ul>')


def _page_link(tree: SiteTree, from_id: str, to_id: str) -> str:
    return _anchor(page_href(from_id, to_id), tree.pages[to_id].title)


def _current_page_link(tree: SiteTree, from_id: str, page_id: str) -> str:
    return (
        f'<a class="current" aria-current="page" '
        f'href="{_escape(page_href(from_id, page_id))}">'
        f"{_escape(tree.pages[page_id].title)}</a>"
    )


def _tree_item(
    tree: SiteTree,
    current_id: str,
    page_id: str,
    ancestors: set[str],
) -> str:
    link = (
        _current_page_link(tree, current_id, page_id)
        if page_id == current_id
        else _page_link(tree, current_id, page_id)
    )
    child_ids = tree.children_of(page_id)
    if not child_ids:
        return f"<li>{link}</li>"

    expanded = page_id == tree.root or page_id in ancestors or page_id == current_id
    open_attribute = " open" if expanded else ""
    items = "".join(
        _tree_item(tree, current_id, child_id, ancestors) for child_id in child_ids
    )
    return (
        f"<li><details{open_attribute}><summary>{link}</summary>"
        f"<ul>{items}</ul></details></li>"
    )


def _site_nav_html(tree: SiteTree, page: Page) -> str:
    ancestors = set(tree.ancestors(page.id))
    root_item = _tree_item(tree, page.id, tree.root, ancestors)
    return (
        '<nav id="site-nav" aria-label="Site navigation">'
        f'<ul class="page-tree">{root_item}</ul></nav>'
    )


def _breadcrumbs_html(tree: SiteTree, page: Page) -> str:
    ancestors = tree.ancestors(page.id)
    links = [_page_link(tree, page.id, ancestor) for ancestor in ancestors]
    links.append(_escape(page.title))
    trail = ' <span aria-hidden="true">›</span> '.join(links)
    return f'<nav class="breadcrumbs" aria-label="Breadcrumbs">{trail}</nav>'


def _submodules_html(tree: SiteTree, page: Page) -> str:
    child_ids = tree.children_of(page.id)
    if not child_ids:
        return ""
    links = ", ".join(_page_link(tree, page.id, child_id) for child_id in child_ids)
    return f'<p class="submodules"><strong>Submodules:</strong> {links}</p>'


def _page_header_html(tree: SiteTree, page: Page) -> str:
    covers = ", ".join(f"<code>{_escape(path)}</code>" for path in page.paths)
    return (
        '<header class="page-header">'
        f"<h1>{_escape(page.title)}</h1>"
        f'<p class="page-meta">Page ID: <code>{_escape(page.id)}</code>'
        f" · verified at <code>{_escape(page.commit[:10])}</code></p>"
        f'<p class="page-meta">Covers: {covers}</p>'
        f"{_submodules_html(tree, page)}"
        "</header>"
    )


def render_page(
    page: Page,
    *,
    tree: SiteTree,
    repo_url: str,
    tables: Mapping[str, Table],
    jar: Path,
) -> str:
    emit_diagram_warnings(page)
    page_header = _page_header_html(tree, page)
    sections = "".join(
        [
            _section("tldr", "TLDR", _tldr_html(page, repo_url=repo_url)),
            _section("contents", "Table of contents", _table_of_contents()),
            _block_section(page, repo_url=repo_url, jar=jar),
            _schema_section(page, repo_url=repo_url, tables=tables, jar=jar),
            _sequence_section(page, repo_url=repo_url, jar=jar),
            _state_section(page, repo_url=repo_url, jar=jar),
            _related_section(page, repo_url=repo_url),
        ]
    )
    document = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_escape(page.title)}</title>"
        f"<style>{PAGE_CSS}</style></head>"
        f'<body><div class="page-shell">{_site_nav_html(tree, page)}'
        f'<main class="page-main">{_breadcrumbs_html(tree, page)}'
        f"{page_header}{sections}</main>"
        '<aside id="context" aria-label="Context"></aside></div></body></html>'
    )
    return _offline_html(document)
