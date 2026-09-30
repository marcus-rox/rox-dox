"""Page model + rendered SVGs -> one self-contained HTML page (SPEC R-1, R-2, R-3)."""

from dataclasses import dataclass
from html import escape

from rox_docs.model import Claim, Page, Source
from rox_docs.schema import Table
from rox_docs.sources import source_label, source_url


@dataclass(frozen=True)
class Site:
    pages: dict[str, Page]
    repo_url: str
    schema_commit: str
    generated_on: str


@dataclass(frozen=True)
class PageSvgs:
    block: str
    schema: str | None
    sequences: list[str]
    states: list[str]


CSS = """
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Helvetica, Arial, sans-serif; background: #fafafa; color: #222; margin: 0;
       display: grid; grid-template-columns: 260px minmax(0, 1fr) 320px; min-height: 100vh; }
a { color: #1f4e9c; }
nav.tree, aside.context { position: sticky; top: 0; height: 100vh; overflow-y: auto; padding: 18px 16px;
                          font-size: 13px; background: #fff; }
nav.tree { border-right: 1px solid #ddd; }
aside.context { border-left: 1px solid #ddd; }
nav.tree .site { font-weight: 700; font-size: 14px; margin-bottom: 12px; display: block; color: #222; text-decoration: none; }
nav.tree ul { list-style: none; padding-left: 14px; margin: 2px 0; }
nav.tree > ul { padding-left: 0; }
nav.tree li { margin: 3px 0; }
nav.tree a { text-decoration: none; color: #333; }
nav.tree a.here { font-weight: 700; color: #000; background: #eef2fa; border-radius: 4px; padding: 1px 5px; }
main { padding: 24px 36px 80px; counter-reset: sec; max-width: 1280px; }
.crumbs { font-size: 12px; color: #777; margin-bottom: 6px; }
h1 { font-size: 22px; margin: 0 0 6px; }
.meta { font-size: 12px; color: #777; margin-bottom: 18px; }
h2 { font-size: 16px; margin: 34px 0 8px; counter-increment: sec; counter-reset: sub; }
h2::before { content: counter(sec) ".\\00a0"; color: #999; }
h3 { font-size: 14px; margin: 22px 0 6px; counter-increment: sub; }
h3::before { content: counter(sec) "." counter(sub, lower-alpha) "\\00a0"; color: #999; }
.lede { font-size: 13px; color: #555; margin: 0 0 8px; }
.none { font-size: 13px; color: #777; font-style: italic; }
svg { background: #fff; border: 1px solid #ddd; border-radius: 8px; display: block; max-width: 100%; height: auto; }
.tldr { background: #fff; border: 1px solid #ddd; border-left: 3px solid #1f4e9c; border-radius: 6px; padding: 12px 20px 14px; font-size: 13.5px; line-height: 1.55; }
.tldr .h { font-weight: 700; margin: 10px 0 2px; }
.tldr .h:first-child { margin-top: 0; }
.tldr ul { margin: 2px 0 4px; padding-left: 20px; }
.toc { margin: 18px 0 8px; padding: 12px 20px; border: 1px solid #ddd; border-left: 3px solid #333; border-radius: 6px; background: #fff; }
.toc .h { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #888; margin-bottom: 6px; }
.toc ol { margin: 0; padding-left: 20px; font-size: 13.5px; }
.toc ol ol { list-style: lower-alpha; font-size: 13px; }
.toc a { color: #222; text-decoration: none; font-weight: 600; }
table.grid { border-collapse: collapse; font-size: 13px; margin: 8px 0; }
table.grid th, table.grid td { border: 1px solid #ddd; padding: 5px 9px; text-align: left; vertical-align: top; }
table.grid th { background: #f0f0f0; }
details { font-size: 12.5px; margin: 6px 0 0; color: #555; }
details summary { cursor: pointer; }
sup a { text-decoration: none; font-size: 10px; }
.children { font-size: 13.5px; }
.card { border: 1px solid #e3e3e3; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
.card .t { font-weight: 600; }
.card .d { color: #888; font-size: 11.5px; margin: 2px 0 4px; }
.card .x { color: #444; line-height: 1.45; }
.panel-h { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #888; margin: 4px 0 6px; }
.later { color: #888; font-style: italic; border: 1px dashed #ccc; border-radius: 6px; padding: 8px 10px; }
"""


def page_html(
    page: Page,
    svgs: PageSvgs,
    schema_tables: list[Table],
    touched: list[Table],
    site: Site,
) -> str:
    refs = _Refs(site.repo_url, page.commit)
    body = "\n".join(
        [
            _crumbs(page, site.pages),
            f"<h1>{escape(page.title)}</h1>",
            _meta(page, site),
            _tldr(page, refs),
            _toc(page),
            _block(page, svgs.block, site.pages, refs),
            _data(page, svgs.schema, schema_tables, touched, site, refs),
            _sequences(page, svgs.sequences, refs),
            _states(page, svgs.states, refs),
            _related(page, site.pages),
            _references(refs),
        ]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(page.title)} · rox-docs</title>
<style>{CSS}</style></head>
<body>
{_tree(page.id, site.pages)}
<main>
{body}
</main>
{_context(page)}
</body></html>
"""


class _Refs:
    """Numbers every cited source on a page in first-use order, for superscripts and the reference list."""

    def __init__(self, repo_url: str, commit: str) -> None:
        self.repo_url = repo_url
        self.commit = commit
        self.urls: list[tuple[str, str]] = []

    def cite(self, sources: list[Source]) -> str:
        marks = []
        for s in sources:
            entry = (source_url(s, self.repo_url, self.commit), source_label(s))
            if entry not in self.urls:
                self.urls.append(entry)
            n = self.urls.index(entry) + 1
            marks.append(
                f'<a href="{escape(entry[0])}" title="{escape(entry[1])}">[{n}]</a>'
            )
        return f"<sup>{''.join(marks)}</sup>"

    def url(self, source: Source) -> str:
        return source_url(source, self.repo_url, self.commit)


def _ancestors(page_id: str, pages: dict[str, Page]) -> list[Page]:
    chain = []
    parent = pages[page_id].parent
    while parent is not None:
        chain.insert(0, pages[parent])
        parent = pages[parent].parent
    return chain


def children_of(page_id: str, pages: dict[str, Page]) -> list[Page]:
    return sorted(
        (p for p in pages.values() if p.parent == page_id), key=lambda p: p.title
    )


def _crumbs(page: Page, pages: dict[str, Page]) -> str:
    links = [
        f'<a href="{p.id}.html">{escape(p.title)}</a>'
        for p in _ancestors(page.id, pages)
    ]
    return f'<div class="crumbs">{" › ".join([*links, escape(page.title)])}</div>'


def _meta(page: Page, site: Site) -> str:
    covers = ", ".join(
        f'<a href="{site.repo_url}/tree/{page.commit}/{escape(c)}"><code>{escape(c)}</code></a>'
        for c in page.covers
    )
    commit = f'<a href="{site.repo_url}/commit/{page.commit}"><code>{page.commit[:10]}</code></a>'
    return f'<div class="meta">Covers {covers} · verified at {commit} · generated {escape(site.generated_on)}</div>'


def _claims(claims: list[Claim], refs: _Refs) -> str:
    if not claims:
        return "<p>None</p>"
    return (
        "<ul>"
        + "".join(f"<li>{escape(c.text)}{refs.cite(c.sources)}</li>" for c in claims)
        + "</ul>"
    )


def _tldr(page: Page, refs: _Refs) -> str:
    t = page.tldr
    lead, *bullets = t.summary
    head = "".join(f"<th>{escape(c)}</th>" for c in t.table.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in t.table.rows
    )
    return f"""<div class="tldr" id="tldr">
<div class="h">Summary:</div><p>{escape(lead.text)}{refs.cite(lead.sources)}</p>{_claims(bullets, refs) if bullets else ""}
<div class="h">Key Points:</div>{_claims(t.key_points, refs)}
<div class="h">Table:</div><table class="grid"><tr>{head}</tr>{rows}</table>{refs.cite(t.table.sources)}
<div class="h">Interesting Notes:</div>{_claims(t.notes, refs)}
</div>"""


def _toc(page: Page) -> str:
    seqs = "".join(
        f'<li><a href="#seq-{i}">{escape(s.title)}</a></li>'
        for i, s in enumerate(page.sequences)
    )
    states = "".join(
        f'<li><a href="#state-{i}">{escape(s.title)}</a></li>'
        for i, s in enumerate(page.states)
    )
    return f"""<div class="toc"><div class="h">Contents</div><ol>
<li><a href="#block">Block diagram</a></li>
<li><a href="#data">Data model</a></li>
<li><a href="#sequences">Sequence diagrams</a>{f"<ol>{seqs}</ol>" if seqs else ""}</li>
<li><a href="#states">State diagrams</a>{f"<ol>{states}</ol>" if states else ""}</li>
<li><a href="#related">Related systems</a></li>
<li><a href="#references">References</a></li>
</ol></div>"""


def _source_rows(pairs: list[tuple[str, Source]], refs: _Refs) -> str:
    rows = "".join(
        f'<tr><td>{escape(what)}</td><td><a href="{escape(refs.url(s))}">{escape(source_label(s))}</a></td></tr>'
        for what, s in pairs
    )
    return f'<details><summary>Sources ({len(pairs)})</summary><table class="grid"><tr><th>Element</th><th>Source</th></tr>{rows}</table></details>'


def _block(page: Page, svg: str, pages: dict[str, Page], refs: _Refs) -> str:
    kids = children_of(page.id, pages)
    kid_list = (
        "<p class='children'>Submodules: "
        + ", ".join(f'<a href="{k.id}.html">{escape(k.title)}</a>' for k in kids)
        + "</p>"
        if kids
        else "<p class='none'>Leaf module: no submodule pages.</p>"
    )
    pairs = [(f"{n.label}", n.source) for n in page.block.nodes] + [
        (f"{e.src} → {e.dst}: {e.label}", e.source) for e in page.block.edges
    ]
    return f"""<h2 id="block">Block diagram</h2>
<p class="lede">UML component diagram. Boxes with a submodule page link to it; every other box links to its code.</p>
{svg}{kid_list}{_source_rows(pairs, refs)}"""


def _data(
    page: Page,
    svg: str | None,
    shown: list[Table],
    touched: list[Table],
    site: Site,
    refs: _Refs,
) -> str:
    diagram = (
        svg
        if svg
        else "<p class='none'>This module declares no curated tables or stores.</p>"
    )
    rows = "".join(
        f'<tr><td><a href="{site.repo_url}/blob/{site.schema_commit}/{t.path}#L{t.line}-L{t.end_line}"><code>{escape(t.name)}</code></a></td>'
        f"<td>{escape(t.class_name)}</td><td>{len(t.columns)}</td><td><code>{escape(t.path)}</code></td></tr>"
        for t in touched
    )
    table = (
        f'<details><summary>All {len(touched)} SQL tables this module declares or imports</summary><table class="grid">'
        f"<tr><th>Table</th><th>Model</th><th>Columns</th><th>Declared in</th></tr>{rows}</table></details>"
        if touched
        else "<p class='none'>This module declares or imports no SQL tables.</p>"
    )
    stores = [(s.name, s.source) for s in page.data.stores]
    return f"""<h2 id="data">Data model</h2>
<p class="lede">UML class diagram. Postgres tables and columns are parsed from the SQLAlchemy models at <code>{site.schema_commit[:10]}</code>; NoSQL stores are cited individually.</p>
{diagram}{table}{_source_rows(stores, refs) if stores else ""}"""


def _sequences(page: Page, svgs: list[str], refs: _Refs) -> str:
    if not page.sequences:
        return '<h2 id="sequences">Sequence diagrams</h2><p class="none">No happy path at this level; see submodules.</p>'
    parts = ['<h2 id="sequences">Sequence diagrams</h2>']
    for i, (seq, svg) in enumerate(zip(page.sequences, svgs, strict=True)):
        pairs = [(p.label, p.source) for p in seq.participants] + [
            (f"{n}. {s.label}", s.source) for n, s in enumerate(seq.steps, 1)
        ]
        parts.append(
            f'<h3 id="seq-{i}">{escape(seq.title)}</h3><p class="lede">{escape(seq.summary)}</p>{svg}{_source_rows(pairs, refs)}'
        )
    return "\n".join(parts)


def _states(page: Page, svgs: list[str], refs: _Refs) -> str:
    if not page.states:
        return '<h2 id="states">State diagrams</h2><p class="none">No stateful entity at this level.</p>'
    parts = ['<h2 id="states">State diagrams</h2>']
    for i, (sm, svg) in enumerate(zip(page.states, svgs, strict=True)):
        pairs = [(s.label, s.source) for s in sm.states] + [
            (f"{t.src} → {t.dst}: {t.label}", t.source) for t in sm.transitions
        ]
        parts.append(
            f'<h3 id="state-{i}">{escape(sm.title)}</h3><p class="lede">Lifecycle of <code>{escape(sm.entity)}</code>.</p>{svg}{_source_rows(pairs, refs)}'
        )
    return "\n".join(parts)


def _related(page: Page, pages: dict[str, Page]) -> str:
    if not page.related:
        return '<h2 id="related">Related systems</h2><p class="none">None</p>'
    items = []
    for r in page.related:
        href = f"{r.page}.html" if r.page else r.url
        title = pages[r.page].title if r.page else r.label
        items.append(
            f'<li><a href="{escape(href or "")}">{escape(title)}</a>: {escape(r.reason)}</li>'
        )
    return f'<h2 id="related">Related systems</h2><ul>{"".join(items)}</ul>'


def _references(refs: _Refs) -> str:
    items = "".join(
        f'<li><a href="{escape(u)}">{escape(label)}</a></li>' for u, label in refs.urls
    )
    return (
        f'<h2 id="references">References</h2><ol style="font-size:12.5px">{items}</ol>'
    )


def _tree(current: str, pages: dict[str, Page]) -> str:
    root = next(p for p in pages.values() if p.parent is None)
    return f'<nav class="tree"><a class="site" href="index.html">rox-docs</a><ul>{_tree_item(root, current, pages)}</ul></nav>'


def _tree_item(page: Page, current: str, pages: dict[str, Page]) -> str:
    here = ' class="here"' if page.id == current else ""
    kids = children_of(page.id, pages)
    sub = (
        f"<ul>{''.join(_tree_item(k, current, pages) for k in kids)}</ul>"
        if kids
        else ""
    )
    return f'<li><a{here} href="{page.id}.html">{escape(page.title)}</a>{sub}</li>'


def _context(page: Page) -> str:
    cards = (
        "".join(
            f'<div class="card"><div class="t"><a href="{escape(d.url)}">{escape(d.title)}</a></div>'
            f'<div class="d">Edited {escape(d.last_edited)}</div><div class="x">{escape(d.excerpt)}</div></div>'
            for d in page.notion
        )
        or "<p class='none'>No related Notion pages found.</p>"
    )
    return f"""<aside class="context">
<div class="panel-h">Notion</div>{cards}
<div class="panel-h" style="margin-top:18px">Slack</div><div class="later">Slack context arrives in v2.</div>
</aside>"""
