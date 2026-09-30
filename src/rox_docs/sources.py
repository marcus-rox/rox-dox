"""Checks that every cited code range exists at the cited commit (SPEC R-4)."""

import subprocess
from pathlib import Path

from rox_docs.model import CodeSource, NotionSource, Page, Source, page_sources

NOTION_HOSTS = (
    "https://www.notion.so/",
    "https://notion.so/",
    "https://app.notion.com/",
)


def line_count_at(repo: Path, commit: str, path: str) -> int | None:
    """Lines in `path` at `commit`, or None if the file does not exist there."""
    shown = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        capture_output=True,
        check=False,
    )
    if shown.returncode != 0:
        return None
    return shown.stdout.count(b"\n") + (0 if shown.stdout.endswith(b"\n") else 1)


def source_problem(source: Source, line_count: int | None) -> str | None:
    if isinstance(source, NotionSource):
        return (
            None
            if source.notion.startswith(NOTION_HOSTS)
            else f"not a Notion URL: {source.notion}"
        )
    start, end = source.lines
    if line_count is None:
        return f"{source.path} does not exist"
    if not 1 <= start <= end <= line_count:
        return f"{source.path} lines {start}-{end} outside 1-{line_count}"
    return None


def page_problems(page: Page, repo: Path) -> list[str]:
    counts: dict[str, int | None] = {}
    problems = []
    for element, source in page_sources(page):
        if isinstance(source, CodeSource) and source.path not in counts:
            counts[source.path] = line_count_at(repo, page.commit, source.path)
        count = counts.get(source.path) if isinstance(source, CodeSource) else None
        problem = source_problem(source, count)
        if problem:
            problems.append(f"{page.id}: {element}: {problem} at {page.commit[:10]}")
    return problems


def source_url(source: Source, repo_url: str, commit: str) -> str:
    if isinstance(source, NotionSource):
        return source.notion
    start, end = source.lines
    return f"{repo_url}/blob/{commit}/{source.path}#L{start}-L{end}"


def source_label(source: Source) -> str:
    if isinstance(source, NotionSource):
        return "Notion"
    return f"{source.path}:{source.lines[0]}-{source.lines[1]}"
