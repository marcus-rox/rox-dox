from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

from rox_dox.cli import main

REPO_URL = "https://github.com/Rox-AI/rox-core"


def test_three_page_navigation_and_relative_links_resolve(
    tmp_path: Path,
    git_repo: tuple[Path, str],
    site_pages: list[dict[str, object]],
    plantuml_jar: Path,
) -> None:
    repo, _ = git_repo
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
            REPO_URL,
            "--out",
            str(output_dir),
            "--plantuml-jar",
            str(plantuml_jar),
        ]
    )

    assert exit_code == 0
    root_file = output_dir / "rox-core.html"
    child_file = output_dir / "rox-core" / "pkg.html"
    leaf_file = output_dir / "rox-core" / "pkg" / "sub.html"
    root = root_file.read_text(encoding="utf-8")
    child = child_file.read_text(encoding="utf-8")
    leaf = leaf_file.read_text(encoding="utf-8")

    for document in (root, child, leaf):
        assert document.count('aria-current="page"') == 1
    assert _breadcrumb_text(root) == "rox-core"
    assert _breadcrumb_text(leaf) == "rox-core › pkg › sub"

    root_hrefs = re.findall(r'<a\b[^>]*href="([^"]+)"', root)
    assert "rox-core.html" in root_hrefs
    assert "rox-core/pkg.html" in root_hrefs
    assert "rox-core/pkg/sub.html" in root_hrefs
    assert '<details open><summary><a class="row page current"' in root
    child_site_nav = re.search(
        r'<nav id="site-nav" aria-label="Site navigation">.*?</nav>',
        child,
        re.DOTALL,
    )
    leaf_site_nav = re.search(
        r'<nav id="site-nav" aria-label="Site navigation">.*?</nav>',
        leaf,
        re.DOTALL,
    )
    assert child_site_nav is not None
    assert leaf_site_nav is not None
    assert len(re.findall(r"<details open>", child_site_nav.group())) == 2
    assert len(re.findall(r"<details open>", leaf_site_nav.group())) == 3
    assert "Covers: <code>.</code>" in root
    assert "Covers: <code>pkg</code>" in child
    assert "Covers: <code>pkg/sub</code>" in leaf
    assert "Submodules:" in child
    assert '<a href="pkg/sub.html">sub</a>' in child
    assert '<a href="../rox-core.html">rox-core</a>' in child
    assert "Submodules:" not in leaf
    assert '<a href="../../rox-core.html">rox-core</a>' in leaf
    assert '<a href="../pkg.html">pkg</a>' in leaf
    assert '<details open><summary><a class="row page current"' in leaf

    for html_file, document in (
        (root_file, root),
        (child_file, child),
        (leaf_file, leaf),
    ):
        for href in re.findall(r'<a\b[^>]*href="([^"]+)"', document):
            parsed = urlsplit(unescape(href))
            if parsed.scheme or not parsed.path:
                continue
            target = (html_file.parent / unquote(parsed.path)).resolve()
            assert target.is_file(), f"{html_file}: relative href {href}"


def _breadcrumb_text(document: str) -> str:
    breadcrumb = re.search(r'<nav class="breadcrumbs".*?</nav>', document, re.DOTALL)
    assert breadcrumb is not None
    return unescape(re.sub(r"<[^>]+>", "", breadcrumb.group(0)))
