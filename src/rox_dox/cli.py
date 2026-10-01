from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from rox_dox.block_svg import MAX_LAYOUT_PROBLEMS, block_layout_problems
from rox_dox.features import (
    FeatureMap,
    is_excluded_path,
    is_feature_path,
)
from rox_dox.model import Page
from rox_dox.plantuml import DiagramError
from rox_dox.relations import RelationCandidate, find_relation_candidates
from rox_dox.render import render_folder_page, render_page, render_uncovered_page
from rox_dox.repo_tree import list_entries, list_tree_paths
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
    build.add_argument("--features", type=Path, default=Path("features"))
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
    table_cache: dict[tuple[Path, str], dict[str, Table]] = {}
    for page_file, page, load_error in pages:
        if load_error is not None:
            print(f"{page_file}: {load_error}")
            problems_found = True
            continue
        if page is None:
            continue
        valid_pages.append(page)

        tables: dict[str, Table] = {}
        if page.data.sql_tables or page.data.domains:
            cache_key = (repo, page.commit)
            if cache_key not in table_cache:
                try:
                    table_cache[cache_key] = extract_tables(repo, page.commit)
                except RuntimeError as error:
                    print(f"{page_file}: {error}")
                    problems_found = True
            tables = table_cache.get(cache_key, {})
            requested_tables = [
                *page.data.sql_tables,
                *(table for domain in page.data.domains for table in domain.tables),
            ]
            for table_name in dict.fromkeys(requested_tables):
                if table_name not in tables:
                    print(
                        f"{page_file}: SQL table '{table_name}' not found at "
                        f"commit {page.commit[:10]}"
                    )
                    problems_found = True

        for problem in page_problems(page, repo, tables=tables):
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


def _load_feature_maps(features_dir: Path) -> tuple[list[FeatureMap], list[str]]:
    maps = []
    problems = []
    if not features_dir.is_dir():
        return maps, problems
    for map_file in sorted(features_dir.glob("*.json")):
        if map_file.stem == "names":
            continue
        try:
            feature_map = FeatureMap.model_validate(
                json.loads(map_file.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            problems.append(f"{map_file}: {error}")
        else:
            maps.append(feature_map)
    return maps, problems


def _folder_output_relative(folder: str) -> Path:
    return Path("folders/index.html" if folder == "." else f"folders/{folder}.html")


def _subtree(path: str, folder: str) -> bool:
    return folder == "." or path == folder or path.startswith(f"{folder}/")


def _tree_directories(paths: Sequence[str]) -> list[str]:
    directories = {"."}
    for path in paths:
        parts = PurePosixPath(path).parts
        for depth in range(1, len(parts)):
            directories.add("/".join(parts[:depth]))
    return sorted(directories)


def _child_directories(folder: str, directories: Sequence[str]) -> list[str]:
    children = []
    for directory in directories:
        if directory == ".":
            continue
        parent = str(PurePosixPath(directory).parent)
        if parent == ".":
            parent = "."
        if parent == folder:
            children.append(directory)
    return children


def _build_folder_pages(
    *,
    args: argparse.Namespace,
    tree,
    root_page: Page,
    entries: Mapping[str, Sequence],
    feature_maps: Sequence[FeatureMap],
    all_paths: Sequence[str],
) -> tuple[list[tuple[Path, str]], int] | list[str]:
    directories = _tree_directories(all_paths)
    in_scope = {path for path in all_paths if is_feature_path(path)}
    placed = {
        feature_file.path
        for feature_map in feature_maps
        for feature in feature_map.features
        for feature_file in feature.files
    }
    globally_uncovered = sorted(in_scope - placed)
    per_map_reasons: dict[str, list[tuple[str, str]]] = {}
    map_reports = []
    for feature_map in sorted(feature_maps, key=lambda item: item.domain):
        current_report = sorted(
            (item.path, item.reason) for item in feature_map.uncovered
        )
        map_reports.append((feature_map.domain, current_report))
        for path, reason in current_report:
            per_map_reasons.setdefault(path, []).append((feature_map.domain, reason))

    output_root = args.out.resolve()
    rendered: list[tuple[Path, str]] = []
    for folder in directories:
        subtree_paths = [path for path in all_paths if _subtree(path, folder)]
        uncovered_count = sum(
            1 for path in globally_uncovered if _subtree(path, folder)
        )
        feature_rows = []
        for feature_map in feature_maps:
            domain_id = f"domain-{feature_map.domain}"
            domain_page = tree.pages.get(domain_id)
            if domain_page is None:
                continue
            for feature in feature_map.features:
                feature_id = (
                    f"feature-{feature_map.domain}-{feature.id.replace('_', '-')}"
                )
                feature_page = tree.pages.get(feature_id)
                if feature_page is None:
                    continue
                files = [
                    item
                    for item in feature.files
                    if _subtree(item.path, folder) and item.path in in_scope
                ]
                if not files:
                    continue
                primary = sum(item.primary for item in files)
                feature_rows.append(
                    (
                        feature_page.title,
                        feature_id,
                        domain_page.title,
                        domain_id,
                        len({item.path for item in files}),
                        primary,
                        len(files) - primary,
                    )
                )
        tests_only = bool(subtree_paths) and all(
            is_excluded_path(path) for path in subtree_paths
        )
        child_folders = [
            (str(PurePosixPath(child).name), child)
            for child in _child_directories(folder, directories)
        ]
        document = render_folder_page(
            folder_path=folder,
            tree=tree,
            root_page=root_page,
            entries=entries,
            repo_url=args.repo_url,
            feature_rows=sorted(feature_rows),
            uncovered_count=uncovered_count,
            child_folders=child_folders,
            tests_only=tests_only,
        )
        output_path = (args.out / _folder_output_relative(folder)).resolve()
        if output_root not in output_path.parents:
            return [f"folder path '{folder}' would write outside output directory"]
        rendered.append((output_path, document))

    uncovered = {path: per_map_reasons.get(path, []) for path in globally_uncovered}
    uncovered_document = render_uncovered_page(
        tree=tree,
        root_page=root_page,
        entries=entries,
        repo_url=args.repo_url,
        uncovered=uncovered,
        map_reports=map_reports,
    )
    uncovered_path = (args.out / "uncovered.html").resolve()
    if output_root not in uncovered_path.parents:
        return ["uncovered inventory would write outside output directory"]
    rendered.append((uncovered_path, uncovered_document))
    return rendered, len(globally_uncovered)


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

        tables: dict[str, Table] = {}
        cache_key = (args.repo, page.commit)
        if page.data.sql_tables or page.data.domains:
            if cache_key not in table_cache and cache_key not in table_errors:
                try:
                    table_cache[cache_key] = extract_tables(args.repo, page.commit)
                except RuntimeError as error:
                    table_errors[cache_key] = str(error)
            if cache_key in table_errors:
                problems.append((page_file, table_errors[cache_key]))
            else:
                tables = table_cache[cache_key]
                requested_tables = [
                    *page.data.sql_tables,
                    *(table for domain in page.data.domains for table in domain.tables),
                ]
                for table_name in dict.fromkeys(requested_tables):
                    if table_name not in tables:
                        table_kind = "SQL table"
                        if any(
                            table_name in domain.tables for domain in page.data.domains
                        ):
                            table_kind = "schema domain table"
                        problems.append(
                            (
                                page_file,
                                f"{table_kind} '{table_name}' not found at "
                                f"commit {page.commit[:10]}",
                            )
                        )
                    elif (
                        table_name in page.data.sql_tables
                        and tables[table_name].duplicate_paths
                    ):
                        duplicate_paths = ", ".join(tables[table_name].duplicate_paths)
                        print(
                            f"warning: {page_file}: SQL table '{table_name}' also "
                            f"declared in {duplicate_paths}; using "
                            f"{tables[table_name].source.path}",
                            file=sys.stderr,
                        )

        citation_problems = page_problems(page, args.repo, tables=tables)
        problems.extend((page_file, problem) for problem in citation_problems)
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

    layout_limit_exceeded = False
    for page in valid_pages:
        diagrams = [
            ("overview", page.block),
            *((figure.id, figure.block) for figure in page.block_figures),
        ]
        for figure_id, diagram in diagrams:
            layout_problems = block_layout_problems(diagram)
            for problem in layout_problems:
                print(f"warning: {page.id} {figure_id}: {problem}")
            if len(layout_problems) > MAX_LAYOUT_PROBLEMS:
                print(
                    f"error: {page.id} {figure_id}: {len(layout_problems)} layout "
                    f"problems (max {MAX_LAYOUT_PROBLEMS})"
                )
                layout_limit_exceeded = True

    if layout_limit_exceeded:
        return 1

    tree = build_tree(valid_pages)
    root_page = tree.pages[tree.root]
    entries = {
        root_page.id: list_entries(args.repo, root_page.commit, "."),
    }
    feature_maps, map_problems = _load_feature_maps(args.features)
    if map_problems:
        for problem in map_problems:
            print(problem)
        return 1
    feature_maps = [
        feature_map
        for feature_map in feature_maps
        if feature_map.commit == root_page.commit
    ]
    all_paths = list_tree_paths(args.repo, root_page.commit)
    folder_result = _build_folder_pages(
        args=args,
        tree=tree,
        root_page=root_page,
        entries=entries,
        feature_maps=feature_maps,
        all_paths=all_paths,
    )
    if isinstance(folder_result, list):
        for problem in folder_result:
            print(problem)
        return 1
    extra_pages, uncovered_count = folder_result
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

    all_rendered = [*rendered_pages, *extra_pages]
    seen_output_paths: set[Path] = set()
    for output_path, _document in all_rendered:
        if output_path in seen_output_paths:
            print(f"output path '{output_path}' is already used")
            return 1
        seen_output_paths.add(output_path)
    for output_path, document in all_rendered:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")
    print(
        f"{len(all_rendered)} pages written to {args.out}; "
        f"{uncovered_count} in-scope files uncovered"
    )
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
