from __future__ import annotations

import json
import re
from pathlib import Path

from rox_dox.cli import main


def _context_fragment(document: str) -> str:
    match = re.search(r'<aside id="context".*?</aside>', document, re.DOTALL)
    assert match is not None
    return match.group(0)


def test_notion_context_and_slack_placeholder_render_on_every_page(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    site_pages: list[dict[str, object]],
    plantuml_jar: Path,
) -> None:
    repo, _ = git_repo
    site_pages[0]["notion"][0]["excerpt"] = "Reference material for <API> & clients."
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    output_dir = tmp_path / "site"
    filenames = ("root.json", "child.json", "leaf.json")
    for filename, payload in zip(filenames, site_pages, strict=True):
        (pages_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(
        [
            "build",
            str(pages_dir),
            "--repo",
            str(repo),
            "--repo-url",
            "https://github.com/Rox-AI/rox-core",
            "--out",
            str(output_dir),
            "--plantuml-jar",
            str(plantuml_jar),
        ]
    )

    assert exit_code == 0
    root = (output_dir / "rox-core.html").read_text(encoding="utf-8")
    child = (output_dir / "rox-core" / "pkg.html").read_text(encoding="utf-8")
    leaf = (output_dir / "rox-core" / "pkg" / "sub.html").read_text(encoding="utf-8")
    notion_panel = _context_fragment(root)
    assert "<h2>Notion</h2>" in notion_panel
    assert (
        '<h3><a href="https://www.notion.so/rox/API-guide-123">API guide</a></h3>'
        in notion_panel
    )
    assert 'Last edited <time datetime="2026-06-10">2026-06-10</time>' in notion_panel
    assert (
        "<blockquote>Reference material for &lt;API&gt; &amp; clients.</blockquote>"
        in notion_panel
    )

    for document in (root, child, leaf):
        context = _context_fragment(document)
        assert context.index("<h2>Notion</h2>") < context.index("<h2>Slack</h2>")
        assert '<p class="empty">Not yet available.</p>' in context
    assert '<p class="empty">No related Notion pages.</p>' in _context_fragment(leaf)


def test_check_rejects_invalid_notion_doc_url(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    page_data: dict[str, object],
    capsys,
) -> None:
    repo, _ = git_repo
    page_data["notion"] = [
        {
            "title": "Bad doc",
            "url": "https://example.com/x",
            "last_edited": "2026-06-10",
            "excerpt": "Reference material.",
        }
    ]
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "root.json").write_text(json.dumps(page_data), encoding="utf-8")

    exit_code = main(["check", str(pages_dir), "--repo", str(repo)])

    assert exit_code == 1
    assert "notion 'Bad doc':" in capsys.readouterr().out
