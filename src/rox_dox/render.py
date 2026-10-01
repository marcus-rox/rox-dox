from __future__ import annotations

import html
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote

from rox_dox.block_svg import block_svg
from rox_dox.diagrams import (
    emit_diagram_warnings,
    schema_plantuml,
    sequence_plantuml,
    state_plantuml,
)
from rox_dox.links import page_href, source_url
from rox_dox.model import (
    Claim,
    NotionDoc,
    Page,
    Related,
    Sequence as SequenceDiagram,
    Source,
    StateMachine,
    page_sources,
)
from rox_dox.plantuml import DiagramError, render_svg
from rox_dox.repo_tree import RepoEntry
from rox_dox.schema import Table
from rox_dox.tree import SiteTree


NO_ENTRIES: Mapping[str, Sequence[RepoEntry]] = MappingProxyType({})


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
.panel-toggle {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
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
#toggle-left:checked ~ .page-shell {
  grid-template-columns: 0 minmax(0, 1fr) 320px;
}
#toggle-right:checked ~ .page-shell {
  grid-template-columns: 280px minmax(0, 1fr) 0;
}
#toggle-left:checked ~ #toggle-right:checked ~ .page-shell {
  grid-template-columns: 0 minmax(0, 1fr) 0;
}
#toggle-left:checked ~ .page-shell #sidebar,
#toggle-right:checked ~ .page-shell #context {
  display: none;
}
.panel-controls {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.panel-toggle-button {
  display: inline-flex;
  padding: 0.3rem 0.65rem;
  border: 1px solid #d0d5dd;
  border-radius: 999px;
  background: #fff;
  color: #344054;
  line-height: 1.35;
  cursor: pointer;
}
.panel-toggle-button .collapsed {
  display: none;
}
#toggle-left:checked ~ .page-shell .panel-toggle-left .expanded,
#toggle-right:checked ~ .page-shell .panel-toggle-right .expanded {
  display: none;
}
#toggle-left:checked ~ .page-shell .panel-toggle-left .collapsed,
#toggle-right:checked ~ .page-shell .panel-toggle-right .collapsed {
  display: inline;
}
#toggle-left:focus-visible ~ .page-shell .panel-toggle-left,
#toggle-right:focus-visible ~ .page-shell .panel-toggle-right {
  outline: 2px solid #3b6fd8;
  outline-offset: 2px;
}
#sidebar {
  grid-area: nav;
  position: sticky;
  top: 0;
  max-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
#toc, #site-nav, #context {
  padding: 1rem;
  border: 1px solid #e2e7ee;
  border-radius: 14px;
  background: #fff;
}
#toc {
  flex: 0 0 auto;
}
#site-nav {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
#context {
  grid-area: aside;
  position: sticky;
  top: 0;
  max-height: 100vh;
  overflow-y: auto;
}
#toc > h2, #site-nav > h2, #context > h2 {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
}
#context > h2:not(:first-child) {
  margin-top: 1.25rem;
}
.notion-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.notion-doc {
  padding: 0.45rem 0;
  border-top: 1px solid #eef1f5;
  font-size: 0.92rem;
  line-height: 1.35;
}
.notion-doc:first-child {
  border-top: 0;
  padding-top: 0;
}
.notion-doc a {
  color: #182230;
  text-decoration: none;
}
.notion-doc a:hover {
  color: #145bc4;
  text-decoration: underline;
}
.page-main {
  grid-area: main;
  min-width: 0;
}
#site-nav > h2 {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #667085;
}
.page-tree, .page-tree ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.page-tree {
  font: 13px/1.2 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
.page-tree ul {
  margin-left: 11px;
  padding-left: 6px;
  border-left: 1px solid #e6e9ef;
}
.page-tree summary {
  list-style: none;
  cursor: pointer;
}
.page-tree summary::-webkit-details-marker {
  display: none;
}
.page-tree .row {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 6px 0 2px;
  border-radius: 4px;
  color: #26323f;
  text-decoration: none;
  white-space: nowrap;
}
.page-tree .row span {
  overflow: hidden;
  text-overflow: ellipsis;
}
.page-tree .row:hover {
  background: #f0f3f7;
}
.page-tree .row.current {
  background: #e3ecfb;
  color: #0f3f8c;
  font-weight: 600;
}
.page-tree .row.pending, .page-tree .row.file {
  color: #7a8594;
}
.page-tree .chevron, .page-tree .chevron-spacer {
  flex: 0 0 14px;
  width: 14px;
  height: 14px;
  color: #7a8594;
  transition: transform 0.1s;
}
.page-tree details[open] > summary .chevron {
  transform: rotate(90deg);
}
.page-tree .icon {
  flex: 0 0 15px;
  width: 15px;
  height: 15px;
  color: #8a94a6;
}
.page-tree .row.page .icon {
  color: #145bc4;
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
.figure-bar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}
.figure-bar .collapse, .zoom-figure:target .figure-bar .expand {
  display: none;
}
.zoom-figure:target .figure-bar .collapse {
  display: inline;
}
.zoom-figure:target {
  position: fixed;
  inset: 0;
  z-index: 10;
  margin: 0;
  padding: 1rem 1.5rem;
  overflow: auto;
  background: #fff;
}
.zoom-figure:target .diagram {
  border: 0;
}
.block-scroll svg {
  max-width: none !important;
  margin: 0 !important;
}
.block-svg a:hover text {
  text-decoration: underline;
}
.block-svg .edge-label {
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 4px;
  stroke-linejoin: round;
}
.diagram svg {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}
.diagram-scroll svg {
  max-width: none;
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
#related summary {
  cursor: pointer;
  list-style: none;
}
#related summary::-webkit-details-marker {
  display: none;
}
#related summary h2 {
  display: inline-block;
  margin: 0;
}
#related details[open] summary {
  margin-bottom: 0.75rem;
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
  #toggle-left:checked ~ .page-shell,
  #toggle-right:checked ~ .page-shell,
  #toggle-left:checked ~ #toggle-right:checked ~ .page-shell {
    grid-template-columns: minmax(0, 1fr);
  }
  #sidebar, #context {
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
    ("related", "Related"),
    ("tldr", "TLDR"),
    ("block", "Block diagram"),
    ("schema", "Schema"),
    ("sequences", "Sequence diagrams"),
    ("states", "State diagrams"),
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
    return (
        '<nav id="toc" aria-label="On this page">'
        "<h2>On this page</h2>"
        f'<ul class="toc">{links}</ul></nav>'
    )


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
    return (
        f'<div class="diagram diagram-scroll">'
        f"{_inline_svg(render_svg(source, jar))}</div>"
    )


def _diagram_card(
    title: str,
    source: str,
    elements: Iterable[tuple[str, Source]],
    *,
    diagram_id: str,
    section_id: str,
    page: Page,
    repo_url: str,
    jar: Path,
) -> str:
    try:
        diagram_markup = _diagram_markup(source, jar=jar)
    except DiagramError as error:
        raise DiagramError(f"{title}: {error}") from error
    return (
        f'<article class="diagram-card zoom-figure" id="{_escape(diagram_id)}">'
        '<div class="figure-bar">'
        f"<h3>{_escape(title)}</h3>"
        f'<a class="expand" href="#{_escape(diagram_id)}">Expand full screen</a>'
        f'<a class="collapse" href="#{_escape(section_id)}">Close</a></div>'
        f"{diagram_markup}"
        f"{_sources_details(elements, page=page, repo_url=repo_url)}"
        "</article>"
    )


def _block_section(page: Page, *, repo_url: str) -> str:
    if not page.block.nodes:
        return _section(
            "block", "Block diagram", f'<p class="empty">{EMPTY_MESSAGE}</p>'
        )
    elements = [
        (label, source)
        for label, source in page_sources(page)
        if label.startswith(("block group ", "block node ", "block edge "))
    ]
    card = (
        '<article class="diagram-card zoom-figure" id="block-figure">'
        '<div class="figure-bar"><h3>System overview</h3>'
        '<a class="expand" href="#block-figure">Expand full screen</a>'
        '<a class="collapse" href="#block">Close</a></div>'
        f'<div class="diagram block-scroll">{block_svg(page, repo_url=repo_url)}</div>'
        f"{_sources_details(elements, page=page, repo_url=repo_url)}"
        "</article>"
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
    elements.extend(
        (f"relation {relation.src} -> {relation.dst}", relation.source)
        for relation in page.data.relations
    )
    return elements


def _schema_section(
    page: Page,
    *,
    repo_url: str,
    tables: Mapping[str, Table],
    jar: Path,
) -> str:
    if not page.data.sql_tables and not page.data.nosql and not page.data.relations:
        return _section("schema", "Schema", f'<p class="empty">{EMPTY_MESSAGE}</p>')
    diagram = schema_plantuml(page, repo_url=repo_url, tables=tables)
    card = _diagram_card(
        "Data stores",
        diagram,
        _schema_sources(page, tables),
        diagram_id="fig-schema",
        section_id="schema",
        page=page,
        repo_url=repo_url,
        jar=jar,
    )
    return _section("schema", "Schema", card)


def _sequence_elements(sequence: SequenceDiagram) -> list[tuple[str, Source]]:
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
            diagram_id=f"fig-sequences-{number}",
            section_id="sequences",
            page=page,
            repo_url=repo_url,
            jar=jar,
        )
        for number, sequence in enumerate(page.sequences, start=1)
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
            diagram_id=f"fig-states-{number}",
            section_id="states",
            page=page,
            repo_url=repo_url,
            jar=jar,
        )
        for number, state_machine in enumerate(page.states, start=1)
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
        content = f'<p class="empty">{EMPTY_MESSAGE}</p>'
    else:
        items = "".join(
            _related_item(related, page=page, repo_url=repo_url)
            for related in page.related
        )
        content = f'<ul class="related-list">{items}</ul>'
    return (
        '<section id="related"><details open>'
        "<summary><h2>Related</h2></summary>"
        f"{content}</details></section>"
    )


def _page_link(tree: SiteTree, from_id: str, to_id: str) -> str:
    return _anchor(page_href(from_id, to_id), tree.pages[to_id].title)


def _current_page_link(tree: SiteTree, from_id: str, page_id: str) -> str:
    return (
        f'<a class="current" aria-current="page" '
        f'href="{_escape(page_href(from_id, page_id))}">'
        f"{_escape(tree.pages[page_id].title)}</a>"
    )


CHEVRON_ICON = (
    '<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true">'
    '<path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'
)
FOLDER_ICON = (
    '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 3.5h4.5l1.5 '
    '1.5h7v8h-13z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>'
)
FILE_ICON = (
    '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 1.5h6l3 3v10h-9z'
    'M9.5 1.5v3h3" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>'
)
SPACER_ICON = '<span class="chevron-spacer" aria-hidden="true"></span>'


def _entry_href(entry: RepoEntry, *, page: Page, repo_url: str) -> str:
    kind = "tree" if entry.is_dir else "blob"
    return f"{repo_url.rstrip('/')}/{kind}/{page.commit}/{quote(entry.path, safe='/')}"


def _explorer_row(
    icon: str, label: str, href: str, css_class: str, title: str = ""
) -> str:
    title_attribute = f' title="{_escape(title)}"' if title else ""
    current = ' aria-current="page"' if "current" in css_class else ""
    return (
        f'<a class="row {css_class}" href="{_escape(href)}"{title_attribute}{current}>'
        f"{icon}<span>{_escape(label)}</span></a>"
    )


def _sort_key(item: tuple[bool, str, str]) -> tuple[int, str]:
    is_dir, label, _markup = item
    return (0 if is_dir else 1, label.lower())


def _tree_item(
    tree: SiteTree,
    current: Page,
    page_id: str,
    *,
    expanded_ids: set[str],
    entries: Mapping[str, Sequence[RepoEntry]],
    repo_url: str,
) -> str:
    page = tree.pages[page_id]
    css_class = "page current" if page_id == current.id else "page"
    row = _explorer_row(
        CHEVRON_ICON + FOLDER_ICON,
        page.title,
        page_href(current.id, page_id),
        css_class,
    )
    child_ids = tree.children_of(page_id)
    documented_paths = {
        path for child_id in child_ids for path in tree.pages[child_id].paths
    }
    items: list[tuple[bool, str, str]] = [
        (
            True,
            tree.pages[child_id].title,
            _tree_item(
                tree,
                current,
                child_id,
                expanded_ids=expanded_ids,
                entries=entries,
                repo_url=repo_url,
            ),
        )
        for child_id in child_ids
    ]
    for entry in entries.get(page_id, []):
        if entry.path in documented_paths:
            continue
        href = _entry_href(entry, page=current, repo_url=repo_url)
        if entry.is_dir:
            markup = _explorer_row(
                SPACER_ICON + FOLDER_ICON,
                entry.name,
                href,
                "folder pending",
                "No page yet",
            )
        else:
            markup = _explorer_row(SPACER_ICON + FILE_ICON, entry.name, href, "file")
        items.append((entry.is_dir, entry.name, f"<li>{markup}</li>"))
    if not items:
        return f"<li>{row}</li>"
    open_attribute = " open" if page_id in expanded_ids else ""
    children = "".join(
        markup for _is_dir, _label, markup in sorted(items, key=_sort_key)
    )
    return (
        f"<li><details{open_attribute}><summary>{row}</summary>"
        f"<ul>{children}</ul></details></li>"
    )


def _site_nav_html(
    tree: SiteTree,
    page: Page,
    *,
    entries: Mapping[str, Sequence[RepoEntry]],
    repo_url: str,
) -> str:
    expanded_ids = {tree.root, page.id, *tree.ancestors(page.id)}
    root_item = _tree_item(
        tree,
        page,
        tree.root,
        expanded_ids=expanded_ids,
        entries=entries,
        repo_url=repo_url,
    )
    return (
        '<nav id="site-nav" aria-label="Site navigation">'
        "<h2>Explorer</h2>"
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


def _notion_doc_html(document: NotionDoc) -> str:
    return f'<li class="notion-doc">{_anchor(document.url, document.title)}</li>'


def _context_panel_html(page: Page) -> str:
    notion_content = "".join(_notion_doc_html(document) for document in page.notion)
    if notion_content:
        notion_content = f'<ul class="notion-list">{notion_content}</ul>'
    else:
        notion_content = '<p class="empty">No related Notion pages.</p>'
    return (
        '<aside id="context" aria-label="Context">'
        f"<h2>Notion</h2>{notion_content}"
        '<h2>Slack</h2><p class="empty">Not yet available.</p></aside>'
    )


def render_page(
    page: Page,
    *,
    tree: SiteTree,
    repo_url: str,
    tables: Mapping[str, Table],
    jar: Path,
    entries: Mapping[str, Sequence[RepoEntry]] = NO_ENTRIES,
) -> str:
    emit_diagram_warnings(page)
    page_header = _page_header_html(tree, page)
    sections = "".join(
        [
            _related_section(page, repo_url=repo_url),
            _section("tldr", "TLDR", _tldr_html(page, repo_url=repo_url)),
            _block_section(page, repo_url=repo_url),
            _schema_section(page, repo_url=repo_url, tables=tables, jar=jar),
            _sequence_section(page, repo_url=repo_url, jar=jar),
            _state_section(page, repo_url=repo_url, jar=jar),
        ]
    )
    document = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_escape(page.title)}</title>"
        f"<style>{PAGE_CSS}</style></head>"
        f'<body><input class="panel-toggle" id="toggle-left" type="checkbox">'
        f'<input class="panel-toggle" id="toggle-right" type="checkbox">'
        f'<div class="page-shell"><div id="sidebar">'
        f"{_table_of_contents()}"
        f"{_site_nav_html(tree, page, entries=entries, repo_url=repo_url)}</div>"
        f'<main class="page-main"><div class="panel-controls">'
        '<label class="panel-toggle-button panel-toggle-left" for="toggle-left">'
        '<span class="expanded">◀ Panel</span><span class="collapsed">▶ Panel</span></label>'
        '<label class="panel-toggle-button panel-toggle-right" for="toggle-right">'
        '<span class="expanded">Panel ▶</span><span class="collapsed">Panel ◀</span></label>'
        f"</div>{_breadcrumbs_html(tree, page)}"
        f"{page_header}{sections}</main>"
        f"{_context_panel_html(page)}</div></body></html>"
    )
    return _offline_html(document)
