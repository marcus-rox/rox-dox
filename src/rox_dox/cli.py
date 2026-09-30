from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from rox_dox.model import Page
from rox_dox.sources import page_problems


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rox-dox")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("pages_dir", type=Path)
    check.add_argument("--repo", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pages_dir: Path = args.pages_dir
    if not pages_dir.is_dir():
        print(f"{pages_dir}: pages directory not found")
        return 1

    page_files = sorted(pages_dir.rglob("*.json"))
    problems_found = False
    for page_file in page_files:
        try:
            page_data = json.loads(page_file.read_text(encoding="utf-8"))
            page = Page.model_validate(page_data)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            print(f"{page_file}: {error}")
            problems_found = True
            continue

        for problem in page_problems(page, args.repo):
            print(f"{page_file}: {problem}")
            problems_found = True

    if problems_found:
        return 1
    print(f"{len(page_files)} pages OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
