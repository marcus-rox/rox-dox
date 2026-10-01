from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from rox_dox.model import Page
from rox_dox.plantuml import DiagramError
from rox_dox.relations import RelationCandidate, find_relation_candidates
from rox_dox.render import render_page
from rox_dox.repo_tree import list_entries
from rox_dox.schema import Table, extract_tables
from rox_dox.sources import page_problems
from rox_dox.tree import build_tree, tree_problems


def _parse_tables(value: str) -> tuple[str, ...]:
    tables = tuple(table.strip() for table in value.split(","))
    if not tables or any(not table for table in tables):
        raise argparse.ArgumentTypeError(
            "tables must be a comma-separated list of table names"
        )
    return tables


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rox-dox")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("pages_dir", type=Path)
    check.add_argument("--repo", type=Path, required=True)

    build = commands.add_parser("build")
    build.add_argument("pages_dir", type=Path)
    build.add_argument("--repo", type=Path, required=True)
    build.add_argument("--repo-url", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument(
        "--plantuml-jar",
        type=Path,
        default=Path("tools/plantuml.jar"),
    )

    relations = commands.add_parser("relations")
    relations.add_argument("--repo", type=Path, required=True)
    relations.add_argument("--commit", required=True)
    relations.add_argument("--tables", type=_parse_tables, required=True)
    return parser


def _load_pages(pages_dir: Path) -> list[tuple[Path, Page | None, str | None]]:
    pages = []
    for page_file in sorted(pages_dir.rglob("*.json")):
        try:
            page_data = json.loads(page_file.read_text(encoding="utf-8"))
            page = Page.model_validate(page_data)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            pages.append((page_file, None, str(error)))
        else:
            pages.append((page_file, page, None))
    return pages


def _check_pages(pages_dir: Path, repo: Path) -> int:
    pages = _load_pages(pages_dir)
    problems_found = False
    valid_pages = []
    for page_file, page, load_error in pages:
        if load_error is not None:
            print(f"{page_file}: {load_error}")
            problems_found = True
            continue
        if page is None:
            continue
        valid_pages.append(page)

        for problem in page_problems(page, repo):
            print(f"{page_file}: {problem}")
            problems_found = True

    for problem in tree_problems(valid_pages):
        print(f"{pages_dir}: {problem}")
        problems_found = True

    if problems_found:
        return 1
    print(f"{len(pages)} pages OK")
    return 0


def _page_output_path(out_dir: Path, page: Page) -> Path | None:
    output_root = out_dir.resolve()
    output_path = (out_dir / f"{page.id}.html").resolve()
    if output_root not in output_path.parents:
        return None
    return output_path


def _build_pages(args: argparse.Namespace) -> int:
    problems: list[tuple[Path, str]] = []
    pages_to_render: list[tuple[Path, Page, dict[str, Table], Path]] = []
    output_paths: dict[Path, Path] = {}
    table_cache: dict[tuple[Path, str], dict[str, Table]] = {}
    table_errors: dict[tuple[Path, str], str] = {}
    valid_pages = []

    for page_file, page, load_error in _load_pages(args.pages_dir):
        if load_error is not None:
            problems.append((page_file, load_error))
            continue
        if page is None:
            continue
        valid_pages.append(page)

        citation_problems = page_problems(page, args.repo)
        problems.extend((page_file, problem) for problem in citation_problems)
        commit_missing = f"commit '{page.commit}' not found in repository"
        tables: dict[str, Table] = {}
        cache_key = (args.repo, page.commit)
        if page.data.sql_tables and commit_missing not in citation_problems:
            if cache_key not in table_cache and cache_key not in table_errors:
                try:
                    table_cache[cache_key] = extract_tables(args.repo, page.commit)
                except RuntimeError as error:
                    table_errors[cache_key] = str(error)
            if cache_key in table_errors:
                problems.append((page_file, table_errors[cache_key]))
            else:
                tables = table_cache[cache_key]
                for table_name in dict.fromkeys(page.data.sql_tables):
                    if table_name not in tables:
                        problems.append(
                            (
                                page_file,
                                f"SQL table '{table_name}' not found at "
                                f"commit {page.commit[:10]}",
                            )
                        )
                    elif tables[table_name].duplicate_paths:
                        duplicate_paths = ", ".join(tables[table_name].duplicate_paths)
                        print(
                            f"warning: {page_file}: SQL table '{table_name}' also "
                            f"declared in {duplicate_paths}; using "
                            f"{tables[table_name].source.path}",
                            file=sys.stderr,
                        )

        output_path = _page_output_path(args.out, page)
        if output_path is None:
            problems.append(
                (
                    page_file,
                    f"page id '{page.id}' would write outside output directory",
                )
            )
        elif output_path in output_paths:
            problems.append(
                (
                    page_file,
                    f"output path '{output_path}' is already used by "
                    f"{output_paths[output_path]}",
                )
            )
        else:
            output_paths[output_path] = page_file
            pages_to_render.append((page_file, page, tables, output_path))

    problems.extend((args.pages_dir, problem) for problem in tree_problems(valid_pages))

    if problems:
        for page_file, problem in problems:
            print(f"{page_file}: {problem}")
        return 1

    tree = build_tree(valid_pages)
    entries = {
        page.id: [
            entry
            for path in page.paths
            for entry in list_entries(args.repo, page.commit, path)
        ]
        for page in valid_pages
    }
    rendered_pages: list[tuple[Path, str]] = []
    render_problems: list[tuple[Path, str]] = []
    for page_file, page, tables, output_path in pages_to_render:
        try:
            rendered = render_page(
                page,
                tree=tree,
                repo_url=args.repo_url,
                tables=tables,
                jar=args.plantuml_jar,
                entries=entries,
            )
        except DiagramError as error:
            render_problems.append((page_file, str(error)))
        else:
            rendered_pages.append((output_path, rendered))

    if render_problems:
        for page_file, problem in render_problems:
            print(f"{page_file}: {problem}")
        return 1

    for output_path, document in rendered_pages:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    print(f"{len(rendered_pages)} pages written to {args.out}")
    return 0


def _print_relation_candidates(
    repo: Path,
    commit: str,
    tables: Sequence[str],
) -> int:
    try:
        candidates: list[RelationCandidate] = find_relation_candidates(
            repo,
            commit,
            tables,
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    for candidate in candidates:
        print(candidate.to_tsv())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "relations":
        return _print_relation_candidates(args.repo, args.commit, args.tables)
    pages_dir: Path = args.pages_dir
    if not pages_dir.is_dir():
        print(f"{pages_dir}: pages directory not found")
        return 1

    if args.command == "check":
        return _check_pages(pages_dir, args.repo)
    return _build_pages(args)


if __name__ == "__main__":
    raise SystemExit(main())
