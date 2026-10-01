import argparse
import json
from pathlib import Path

import rox_core_domains
from rox_dox.components import extract_file_facts
from rox_dox.feature_pages import feature_pages
from rox_dox.features import FeatureMap, _cached_parse_graph, _snapshot
from rox_dox.schema import extract_tables

DEFAULT_REPO = Path("/home/ubuntu/repos/rox-core")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cited domain and feature pages from feature maps."
    )
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--domain", default="all")
    args = parser.parse_args()
    repo = args.repo.resolve()

    project_root = Path(__file__).resolve().parents[2]
    pages_dir = project_root / "pages"
    feature_maps = []
    for map_file in sorted((project_root / "features").glob("*.json")):
        if map_file.stem == "names":
            continue
        feature_maps.append(
            FeatureMap.model_validate(json.loads(map_file.read_text(encoding="utf-8")))
        )
    if args.domain != "all" and not any(
        feature_map.domain == args.domain for feature_map in feature_maps
    ):
        raise SystemExit(f"unknown domain: {args.domain}")
    selected_maps = [
        feature_map
        for feature_map in feature_maps
        if args.domain == "all" or feature_map.domain == args.domain
    ]

    root_page = json.loads((pages_dir / "rox-core.json").read_text(encoding="utf-8"))
    names = json.loads(
        (project_root / "features" / "names.json").read_text(encoding="utf-8")
    )
    domain_titles = {
        domain_id: title for domain_id, title, *_ in rox_core_domains.DOMAINS
    }
    tables_by_commit = {}
    components_by_commit = {}
    imports_by_commit = {}
    table_accesses_by_commit = {}
    generated = []
    for feature_map in selected_maps:
        if feature_map.commit not in tables_by_commit:
            tables_by_commit[feature_map.commit] = extract_tables(
                repo, feature_map.commit
            )
            snapshot = _snapshot(repo, feature_map.commit)
            graph, _ = _cached_parse_graph(
                repo,
                feature_map.commit,
                snapshot,
                tables_by_commit[feature_map.commit],
                set(tables_by_commit[feature_map.commit]),
            )
            source_paths = sorted(graph)
            components_by_commit[feature_map.commit] = extract_file_facts(
                repo,
                feature_map.commit,
                source_paths,
            )
            imports_by_commit[feature_map.commit] = {
                path: {
                    imported: graph_file.import_lines[imported]
                    for imported in graph_file.imports
                }
                for path, graph_file in sorted(graph.items())
            }
            table_accesses_by_commit[feature_map.commit] = {
                path: graph_file.table_accesses
                for path, graph_file in sorted(graph.items())
            }

    primary_features = {}
    table_domains = {
        table: feature_map.domain
        for feature_map in feature_maps
        for table in feature_map.tables
    }
    for candidate in feature_maps:
        for feature in candidate.features:
            display_name = names.get(candidate.domain, {}).get(feature.id)
            if display_name is None:
                display_name = " ".join(
                    part.capitalize()
                    for part in feature.id.replace("-", "_").split("_")
                )
            page_id = f"feature-{candidate.domain}-{feature.id.replace('_', '-')}"
            for file in feature.files:
                if file.primary and (
                    file.path not in primary_features
                    or page_id < primary_features[file.path][1]
                ):
                    primary_features[file.path] = (display_name, page_id)

    for feature_map in selected_maps:
        generated.extend(
            feature_pages(
                feature_map,
                root_id=root_page["id"],
                domain_title=domain_titles[feature_map.domain],
                names=names.get(feature_map.domain, {}),
                tables=tables_by_commit[feature_map.commit],
                component_facts=components_by_commit[feature_map.commit],
                component_imports=imports_by_commit[feature_map.commit],
                table_accesses=table_accesses_by_commit[feature_map.commit],
                primary_features=primary_features,
                domain_titles=domain_titles,
                table_domains=table_domains,
            )
        )

    output_dirs = {
        "domain": pages_dir / "domains",
        "feature": pages_dir / "features",
    }
    expected = {directory: set() for directory in output_dirs.values()}
    for page in generated:
        directory = output_dirs[page.kind]
        output_path = directory / (
            f"{page.id.removeprefix('domain-')}.json"
            if page.kind == "domain"
            else f"{page.id}.json"
        )
        expected[directory].add(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                page.model_dump(exclude_none=True),
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
    for directory, expected_paths in expected.items():
        for old_path in directory.glob("*.json"):
            belongs_to_selected_domain = (
                directory == output_dirs["domain"] and old_path.stem == args.domain
            ) or (
                directory == output_dirs["feature"]
                and old_path.stem.startswith(f"feature-{args.domain}-")
            )
            if old_path not in expected_paths and (
                args.domain == "all" or belongs_to_selected_domain
            ):
                old_path.unlink()


if __name__ == "__main__":
    main()
