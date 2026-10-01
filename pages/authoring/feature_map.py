import argparse
import json
from pathlib import Path

import rox_core_domains
from rox_dox.features import build_feature_map
from rox_dox.schema import extract_tables

DEFAULT_REPO = Path("/home/ubuntu/repos/rox-core")
DEFAULT_COMMIT = "315a00b5b4ecbd6970b537c3e20b1d827ae3b845"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a commit-pinned rox-core feature map."
    )
    parser.add_argument("--domain", default="seq")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--commit", default=DEFAULT_COMMIT)
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()

    tables = extract_tables(args.repo.resolve(), args.commit)
    domain_tables = rox_core_domains.assign(sorted(tables))
    if args.domain not in domain_tables:
        raise SystemExit(f"unknown domain: {args.domain}")
    feature_map = build_feature_map(
        args.repo.resolve(),
        args.commit,
        domain_tables,
        args.domain,
        threshold=args.threshold,
    )
    output_path = Path("features") / f"{args.domain}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            feature_map.model_dump(exclude_none=True),
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
