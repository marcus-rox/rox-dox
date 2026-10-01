import argparse
import json
from pathlib import Path

import rox_core_domains
from rox_dox.components import extract_file_facts
from rox_dox.feature_pages import feature_pages
from rox_dox.features import FeatureMap
from rox_dox.schema import extract_tables

DEFAULT_REPO = Path("/home/ubuntu/repos/rox-core")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cited domain and feature pages from feature maps."
    )
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
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

    root_page = json.loads((pages_dir / "rox-core.json").read_text(encoding="utf-8"))
    names = json.loads(
        (project_root / "features" / "names.json").read_text(encoding="utf-8")
    )
    domain_titles = {
        domain_id: title for domain_id, title, *_ in rox_core_domains.DOMAINS
    }
    tables_by_commit = {}
    components_by_commit = {}
    generated = []
    for feature_map in feature_maps:
        if feature_map.commit not in tables_by_commit:
            tables_by_commit[feature_map.commit] = extract_tables(
                repo, feature_map.commit
            )
            source_paths = sorted(
                {
                    file.path
                    for candidate in feature_maps
                    if candidate.commit == feature_map.commit
                    for feature in candidate.features
                    for file in feature.files
                }
            )
            components_by_commit[feature_map.commit] = extract_file_facts(
                repo,
                feature_map.commit,
                source_paths,
            )
        generated.extend(
            feature_pages(
                feature_map,
                root_id=root_page["id"],
                domain_title=domain_titles[feature_map.domain],
                names=names.get(feature_map.domain, {}),
                tables=tables_by_commit[feature_map.commit],
                component_facts=components_by_commit[feature_map.commit],
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
            if old_path not in expected_paths:
                old_path.unlink()


if __name__ == "__main__":
    main()
