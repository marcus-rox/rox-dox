"""Validates every page model, checks every citation, and writes the HTML site."""

import argparse
import datetime
import functools
import json
import subprocess
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from rox_docs.model import Page
from rox_docs.puml import (
    block_puml,
    render_svgs,
    schema_puml,
    sequence_puml,
    state_puml,
)
from rox_docs.render import PageSvgs, Site, page_html
from rox_docs.schema import Table, extract_tables, tables_touched
from rox_docs.sources import page_problems, source_url


def load_pages(pages_dir: Path) -> tuple[dict[str, Page], list[str]]:
    pages, problems = {}, []
    for file in sorted(pages_dir.glob("*.json")):
        try:
            page = Page.model_validate(json.loads(file.read_text()))
        except ValidationError as err:
            problems.append(f"{file.name}: {err}")
            continue
        if page.id != file.stem:
            problems.append(f"{file.name}: id '{page.id}' does not match file name")
        pages[page.id] = page
    return pages, problems


def structure_problems(pages: dict[str, Page]) -> list[str]:
    problems = []
    roots = [p.id for p in pages.values() if p.parent is None]
    if len(roots) != 1:
        problems.append(f"expected exactly one root page, got {roots}")
    for p in pages.values():
        if p.parent is not None and p.parent not in pages:
            problems.append(f"{p.id}: parent '{p.parent}' has no page")
        links = [n.page for n in p.block.nodes if n.page] + [
            r.page for r in p.related if r.page
        ]
        problems += [
            f"{p.id}: links to missing page '{t}'" for t in links if t not in pages
        ]
    return problems


def diagram_warnings(page: Page, max_boxes: int) -> list[str]:
    counts = {
        "block": len(page.block.nodes),
        "data": len(page.data.tables) + len(page.data.stores),
    }
    counts |= {f"sequence '{s.title}'": len(s.participants) for s in page.sequences}
    counts |= {f"state '{s.title}'": len(s.states) for s in page.states}
    return [
        f"{page.id}: {name} has {n} boxes (soft limit {max_boxes})"
        for name, n in counts.items()
        if n > max_boxes
    ]


def build(config_path: Path, generated_on: str) -> list[str]:
    """Returns problems; writes the site only when there are none."""
    cfg = yaml.safe_load(config_path.read_text())
    base = config_path.parent
    rox_core = (base / cfg["rox_core_path"]).resolve()
    pages, problems = load_pages(base / cfg["pages_dir"])
    problems += structure_problems(pages)
    for page in pages.values():
        problems += page_problems(page, rox_core)
    tables = extract_tables(rox_core, cfg["src_dir"])
    by_name = {t.name: t for t in tables}
    for page in pages.values():
        problems += [
            f"{page.id}: data table '{n}' not declared in {cfg['src_dir']}"
            for n in page.data.tables
            if n not in by_name
        ]
    if problems:
        return problems
    for page in pages.values():
        for warning in diagram_warnings(page, cfg["max_boxes_per_diagram"]):
            print("warning:", warning)

    schema_commit = subprocess.run(
        ["git", "-C", str(rox_core), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    site = Site(pages, cfg["repo_url"], schema_commit, generated_on)
    diagrams: dict[str, str] = {}
    for page in pages.values():
        diagrams |= _page_diagrams(
            page,
            [by_name[n] for n in page.data.tables],
            site,
            cfg["max_columns_per_table"],
        )
    svgs = render_svgs(diagrams, base / cfg["plantuml_jar"])

    out = base / cfg["site_dir"]
    out.mkdir(exist_ok=True)
    for page in pages.values():
        page_svgs = PageSvgs(
            block=svgs[f"{page.id}__block"],
            schema=svgs.get(f"{page.id}__schema"),
            sequences=[svgs[f"{page.id}__seq{i}"] for i in range(len(page.sequences))],
            states=[svgs[f"{page.id}__state{i}"] for i in range(len(page.states))],
        )
        html = page_html(
            page,
            page_svgs,
            [by_name[n] for n in page.data.tables],
            tables_touched(rox_core, page.covers, tables),
            site,
        )
        (out / f"{page.id}.html").write_text(html)
        if page.parent is None:
            (out / "index.html").write_text(html)
    print(f"wrote {len(pages)} pages and {len(diagrams)} diagrams to {out}")
    return []


def _page_diagrams(
    page: Page, shown: list[Table], site: Site, max_columns: int
) -> dict[str, str]:
    code = functools.partial(source_url, repo_url=site.repo_url, commit=page.commit)
    block_links = {
        n.id: f"{n.page}.html" if n.page else code(n.source) for n in page.block.nodes
    }
    data_links = {
        t.name: f"{site.repo_url}/blob/{site.schema_commit}/{t.path}#L{t.line}-L{t.end_line}"
        for t in shown
    }
    data_links |= {s.name: code(s.source) for s in page.data.stores}
    diagrams = {f"{page.id}__block": block_puml(page.block, block_links)}
    if shown or page.data.stores:
        diagrams[f"{page.id}__schema"] = schema_puml(
            shown, page.data, max_columns, data_links
        )
    for i, seq in enumerate(page.sequences):
        diagrams[f"{page.id}__seq{i}"] = sequence_puml(
            seq, {p.id: code(p.source) for p in seq.participants}
        )
    for i, sm in enumerate(page.states):
        diagrams[f"{page.id}__state{i}"] = state_puml(
            sm, {s.id: code(s.source) for s in sm.states}
        )
    return diagrams


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    problems = build(
        args.config.resolve(),
        datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(f"{len(problems)} problem(s); site not written")


if __name__ == "__main__":
    main()
