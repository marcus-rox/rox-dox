# rox-dox — specification

**Status · 2026-10-01 · 7 requirements, 0 failing, 5 unbound.** Accepted by Marcus; replaces SPEC_deprecated.md. `R-1` and `R-3` are retired; `R-2` and `R-4` carry over verbatim.

## Requirement levels

```
R-5   rox-core is browsable as a feature tree, one level per click     page tree
├── R-2    Every page has the fixed design-doc layout                   page renderer
├── R-6    Every source file is covered by a page                       feature map
├── R-9    Every feature page shows why its files belong together       feature map
└── R-7    Clicking a folder opens documentation, never GitHub          file explorer
R-4   No uncited claim appears on any page                              citation check
R-8   One unattended run rebuilds the whole site as a rox-dox PR       scheduled run
```

| Component | Level 1 | Level 2 |
|---|---|---|
| page tree | `R-5` | — |
| page renderer | — | `R-2` |
| feature map | — | `R-6`, `R-9` |
| file explorer | — | `R-7` |
| citation check | `R-4` | — |
| scheduled run | `R-8` | — |

`R-5` can be green while resting on nothing: a tree of feature pages that silently leaves out
half the code still navigates. `R-6` is what makes the tree a complete map of rox-core, and
`R-9` is what lets a reader check that a feature page's files really are one feature.

## Purpose

A researcher without production access needs to understand what rox-core does, what it stores
and how its parts talk. The docs start at one overview page and go one level deeper per click:
the whole system, then its domains, then the features inside each domain, down to pages that
describe one feature end to end. They are self-contained HTML pages, rebuilt on a schedule from
the latest rox-core code.

## Requirements

### R-1 — Module-tree navigation — RETIRED

Replaced by `R-5`: pages follow features, not folders.

### R-2 — Design-doc page layout

*Level 2 · page renderer · serves `R-5`*

Every page SHALL present, in order: a collapsible section with links to related modules and
systems, a TLDR in the recap format (Summary, Key Points, Table, Interesting Notes), a UML
block diagram, a static SVG schema diagram of its SQL and NoSQL data, and UML sequence
diagrams for its happy paths; the root schema SHALL
show one card per domain with key tables, while submodule schemas SHALL show every in-scope
table and column; and each page SHALL show a table of contents of those sections at the top of
the left panel, above the navigation tree.

#### Scenario: complete page
- GIVEN any generated page
- WHEN it is opened in a browser with no network access
- THEN every section above is present in that order, Related is collapsible, the table of contents sits above the navigation tree, and every diagram renders

#### Scenario: nothing to show
- GIVEN a module that owns no data or has no happy path to draw
- WHEN its page opens
- THEN that section is present and says so, rather than being omitted

### R-3 — Notion context panel — RETIRED

Retired by Marcus: Notion pages are no longer looked up or shown.

### R-4 — Every claim is cited

*Level 1 · citation check*

Every diagram element, arrow and TLDR statement SHALL link to its source (a file and line
range at a named commit, or a Notion page), and anything without a valid source SHALL NOT
appear on a page.

#### Scenario: uncited element
- GIVEN a page model with an arrow that has no source
- WHEN the page is built
- THEN the build fails naming that arrow

#### Scenario: stale source
- GIVEN a source pointing at lines that do not exist at the stated commit
- WHEN the page is built
- THEN the build fails naming the source

### R-5 — Feature-tree navigation

*Level 1 · page tree*

The site SHALL have one root page for rox-core, one page per domain and one page per feature,
where each page links to its parent and its children, and the left panel shows the whole
feature tree with the current page highlighted.

#### Scenario: drilling down
- GIVEN the root page
- WHEN the reader clicks a domain, then one of its features, in the left panel
- THEN each page opens in turn, listing its own children and a breadcrumb back to the root

#### Scenario: leaf
- GIVEN a feature with no child features
- WHEN its page opens
- THEN it shows every part of that feature that exists — HTTP routes, business logic, background workers, web screens and tables — on that one page

### R-6 — Every source file is covered

*Level 2 · feature map · serves `R-5`*

Every source file at the documented commit SHALL be listed on at least one feature page, or on
a page of files no feature covers, where source files are backend code, web code, agent skills
and deployment config; and the root page SHALL state that tests and migrations are not covered.

#### Scenario: new file
- GIVEN a source file added to rox-core since the last run
- WHEN the site is rebuilt at a commit that contains it
- THEN the file is listed on a feature page or on the uncovered-files page

#### Scenario: excluded file
- GIVEN a test file or a migration
- WHEN the site is rebuilt
- THEN it is on no page, and the root page says tests and migrations are not covered

### R-7 — Folder clicks open documentation

*Level 2 · file explorer · serves `R-5`*

Clicking any folder in the left panel's file explorer SHALL open a documentation page that
lists every feature page covering files in that folder, and SHALL NOT open GitHub.

#### Scenario: folder split across features
- GIVEN a folder whose files belong to two features
- WHEN the reader clicks it in the file explorer
- THEN a docs page opens linking to both feature pages, and nothing on it links to GitHub

#### Scenario: folder no feature covers
- GIVEN a folder whose files no feature covers
- WHEN the reader clicks it
- THEN a docs page opens pointing to the uncovered-files page

### R-8 — Whole-site regeneration

*Level 1 · scheduled run*

A single unattended run SHALL rebuild the feature tree and every page from one named rox-core
commit and open a rox-dox pull request from a new branch carrying the rebuilt site, and SHALL
open no pull request if any page fails to build.

#### Scenario: one commit everywhere
- GIVEN a run started against the latest rox-core main
- WHEN it finishes
- THEN a new rox-dox pull request carries the site, and every page in it names the same rox-core commit

#### Scenario: one page fails
- GIVEN a run in which one page fails its build
- WHEN the run ends
- THEN no pull request is opened and the failing page is named

### R-9 — Grouping evidence

*Level 2 · feature map · serves `R-5`*

Every feature page SHALL show the tables and calls its files share, each cited, as the reason
those files are one feature.

#### Scenario: cross-layer feature
- GIVEN a feature whose route files and logic files sit in distant folders
- WHEN its page opens
- THEN it shows the tables and calls that join them, each linking to the code

## Not required

- Regenerating only the pages whose code changed — every run rebuilds everything for now.
- A run per rox-core pull request — there are too many; the schedule is enough.
- Notion context on pages — `R-3` retired by Marcus.
- Tests and migrations — not documented; the root page says so (`R-6`).
- One page per folder — folders only point to the feature pages that cover them.

## Clarifications

None.

## Conformance

| Requirement | Component | Test | Status |
|---|---|---|---|
| R-1 | — | — | retired |
| R-2 | page renderer | `tests/conformance/test_r2_layout.py` | ✅ |
| R-3 | — | `tests/conformance/test_r3_context.py` (to be removed with the panel) | retired |
| R-4 | citation check | `tests/conformance/test_r4_citations.py` | ✅ |
| R-5 | — | — | unbound |
| R-6 | — | — | unbound |
| R-7 | — | — | unbound |
| R-8 | — | — | unbound |
| R-9 | — | — | unbound |
