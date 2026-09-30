uv sync
uv run pytest
uv run ruff check src tests
uv run rox-dox check pages --repo /path/to/repo
./scripts/fetch_plantuml.sh
uv run rox-dox build pages --repo /path/to/repo --repo-url https://github.com/Rox-AI/rox-core --out site