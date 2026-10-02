uv sync
uv run pytest
uv run ruff check src tests
uv run rox-dox check pages --repo /path/to/repo
./scripts/fetch_plantuml.sh
uv run rox-dox build pages --repo /path/to/repo --repo-url https://github.com/Rox-AI/rox-core --out site

## Daily rebuild

From the repository root, regenerate the pinned pages and feature maps and build
the offline site from the latest `origin/main` commit in rox-core:

```sh
uv run rox-dox rebuild --repo /path/to/rox-core
```

The command prints the temporary output directory and report path. To choose a
fixed directory or source commit, then open the generated root page locally:

```sh
uv run rox-dox rebuild \
  --repo /path/to/rox-core \
  --commit "$(git -C /path/to/rox-core rev-parse HEAD)" \
  --out site
xdg-open site/rox-core.html
```

Use `--open-pr --merge` after a successful rebuild to publish changed `pages/` and
`features/` JSON artifacts and merge the pull request into `main`. Use `--open-pr` without
`--merge` only when the pull request should remain open for review.

## View the site locally

Prerequisites: Java, `uv`, and a local rox-core clone with read access. From the rox-dox
checkout, run:

```sh
scripts/serve_local.sh --rox-core /path/to/rox-core
```

The script builds into `site/` and serves `http://localhost:8000/rox-core.html`. Pages on
rox-dox `main` are updated daily by the Devin automation, so rerun the script to pick up the
latest pages. You can also open `file://<rox-dox-checkout>/site/rox-core.html` without a
server.
