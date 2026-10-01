---
name: daily-rebuild
description: Rebuild every rox-dox page at the latest rox-core main and open one rox-dox PR from a new branch, or open none and name every failing page. Use when a scheduled run starts, when the user says "rebuild the site", "regenerate the docs", or "run the daily rebuild", and when a rebuild failed and needs repair.
---

# Daily rebuild

One run pins one rox-core commit, regenerates every page from it, builds the site, and either
opens one PR or opens none. Never publish a page whose citations fail.

## Setup

1. rox-dox checkout: clone `https://github.com/marcus-rox/rox-dox.git` with
   `GIT_ASKPASS` reading `MARCUS_ROX_DOX_GITHUB_TOKEN` (never print it, never put it in a URL),
   check out `main`, run `uv sync`.
2. rox-core checkout: any clone of `Rox-AI/rox-core` with an `origin` remote. The run reads it
   only through git objects, so its working tree may be dirty or on any branch.
3. PlantUML jar: `scripts/fetch_plantuml.sh` if `tools/plantuml.jar` is missing.

## Run

```bash
uv run rox-dox rebuild --repo <rox-core> --out <site dir> --open-pr
```

The command fetches rox-core `origin/main`, writes its SHA to `pages/authoring/COMMIT`, runs
every authoring step, builds the site, checks that every page names that SHA, and writes
`rebuild-report.json` into the site directory.

- Exit 0 with a PR URL: done. Report the URL.
- Exit 0 with "no changes": done. Report that no PR was needed.
- Exit 1: go to Repair.

## Repair

Generated pages (domains, features, folders, uncovered) have no hand-written content. A failure
in them is a generator bug: do not edit the generated JSON. Report it and stop.

The root page (`pages/authoring/rox_core.py`) is hand-authored. Its typical failure is a cited
line that moved or vanished (`needle not found`), or a new table no domain claims. For each one:

1. Read the cited file at the new commit with `git show <sha>:<path>`.
2. If the same fact still holds at a new line, update the needle so it matches that line.
3. If the fact changed, rewrite the claim, box or arrow from the new code, following
   `generate-rox-docs` and the matching diagram skill. Every new claim needs a citation at the
   new commit.
4. If the fact is gone, delete the claim and anything that depended on it.
5. A new table: add it to the domain whose existing tables it shares files and foreign keys
   with, in `rox_core_domains`; if none clearly fits, stop and report it.

Re-run the command. Stop after three failing runs and report every failing page with its
message; open no PR. Never weaken a check, skip a step, or pin an older commit to get a pass.

## Report

End with: the rox-core SHA, the PR URL or "no PR", the failing pages if any, each repair made to
the root script with the citation it now uses, and the run time.
