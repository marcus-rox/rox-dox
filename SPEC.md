# rox-docs — specification

**Status · 2026-09-30 · 4 requirements, 4 unbound (nothing built yet).**

## Requirement levels

```
R-1   rox-core is browsable top-down, one module deeper per click   page tree
├── R-2    Every page has the fixed design-doc layout                 page renderer
└── R-3    Every page shows the Notion context for its module         context panel
R-4   No uncited claim appears on any page                            citation check
```

| Component | Level 1 | Level 2 |
|---|---|---|
| page tree | `R-1` | — |
| page renderer | — | `R-2` |
| context panel | — | `R-3` |
| citation check | `R-4` | — |

`R-1` is only useful if each page it links to is readable at its level; `R-2` is what makes a
click into a module worth making, so `R-1` green with `R-2` red is a tree of empty pages.

## Purpose

A researcher without production access needs to understand what rox-core does, what it
stores and how its parts talk, starting from one overview page and clicking into modules and
submodules for progressively more detail. The docs are self-contained HTML pages in the
Rox-AI/rox-docs repository, regenerated when someone runs the generator.

## Requirements

### R-1 — Module-tree navigation

*Level 1 · page tree*

The site SHALL have one root page for rox-core and one page per module and submodule, where
each page links to its parent and its children, and a navigation panel on the left shows the
whole tree with the current page highlighted.

#### Scenario: drilling down
- GIVEN the root page
- WHEN the reader clicks a module in the navigation panel or in the block diagram
- THEN that module's page opens, with its own submodules listed as children and a breadcrumb back to the root

#### Scenario: leaf
- GIVEN a module small enough to describe on one page
- WHEN its page opens
- THEN it has no children and describes its classes, functions and the data they read and write

### R-2 — Design-doc page layout

*Level 2 · page renderer · serves `R-1`*

Every page SHALL present, in order: a TLDR in the recap format (Summary, Key Points, Table,
Interesting Notes), a table of contents, a UML block diagram, a UML schema diagram of the SQL
and NoSQL data the module owns, UML sequence diagrams for its happy paths, UML state diagrams
for its stateful entities, and links to related modules and systems.

#### Scenario: complete page
- GIVEN any generated page
- WHEN it is opened in a browser with no network access
- THEN every section above is present in that order and every diagram renders

#### Scenario: nothing to show
- GIVEN a module that owns no data or has no stateful entity
- WHEN its page opens
- THEN that section is present and says so, rather than being omitted

### R-3 — Notion context panel

*Level 2 · context panel · serves `R-1`*

Every page SHALL show, in a panel on the right, the Notion pages related to its module, each
with its title, link, last-edited date and a short excerpt, above a Slack section marked as
not yet available.

#### Scenario: related docs exist
- GIVEN a module discussed in Notion
- WHEN its page opens
- THEN the right panel lists those Notion pages with excerpts and working links

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

## Clarifications

None.

## Conformance

| Requirement | Component | Test | Status |
|---|---|---|---|
| R-1 | page tree | `tests/conformance/test_r1_navigation.py` | green |
| R-2 | page renderer | `tests/conformance/test_r2_layout.py` | green |
| R-3 | context panel | `tests/conformance/test_r3_context.py` | green |
| R-4 | citation check | `tests/conformance/test_r4_citations.py` | green |
