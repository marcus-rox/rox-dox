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

Use `--open-pr` only after a successful rebuild to publish changed `pages/` and
`features/` JSON artifacts as a pull request.

## View the site locally

From the repository root, ensure `tools/plantuml.jar` exists; fetch it with
`./scripts/fetch_plantuml.sh` if needed. Then build the offline site:

```sh
uv run rox-dox build pages \
  --repo /path/to/rox-core \
  --repo-url https://github.com/Rox-AI/rox-core \
  --out site
```

The root page is `site/rox-core.html` (there is no top-level `site/index.html`):

```sh
xdg-open site/rox-core.html
```
