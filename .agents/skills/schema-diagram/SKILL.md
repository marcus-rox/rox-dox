---
name: schema-diagram
description: Author and verify source-cited schema diagrams and implicit relationships. Use when creating or revising a schema diagram, assigning tables to domains, or investigating relationships.
---

# schema-diagram

## Root domains and submodule tables

Schema diagrams have two levels:

- The root/umbrella page is a **domain view**: one card per domain, with a small set of key
  tables. Every non-test SQL table belongs to exactly one domain. Keep the ordered assignment
  rules in `pages/authoring/rox_core_domains.py`; fail authoring when a table is unassigned.
  Choose 4–7 key tables per domain, including every endpoint of a relation drawn on the root.
- A submodule page is a **table view**: show every table the folder defines or reads/writes,
  with every extracted column and type. Put intra-domain relations on these pages.

At the root, draw only cross-domain SQL relations and NoSQL/blob relations. Summarize the
common `rox_org_id` and `rox_user_id` tenant FKs in a cited note rather than drawing those
edges. Declared SQL foreign keys between tables on a table-view page are drawn automatically.
The AST extractor includes mapped columns inherited transitively from base classes in the same
file; subclass declarations override inherited columns with the same name.

Use `data.relations` for relationships that need to be authored. `kind` is one of:

- `enforced`: the source SQL column's declared FK must equal the destination `table.column`.
- `symbolic`: no matching database constraint, including commented-out FKs and query joins.
- `blob`: a blob-pointer relationship.

Relation endpoints are `table.column` for SQL, or a NoSQL store name optionally followed by
`::field`; NoSQL field text is free-form. Domain-view SQL endpoints must be key tables, and
same-domain SQL relations belong on the domain's submodule page.

The static inline SVG legend defines the visual language: amber/bold PKs, blue FK-like
columns, solid blue enforced edges, dashed grey symbolic edges, dotted amber blob edges, and
grey shared boilerplate columns. Edge dots mark the referenced (one) side; arrows mark the
many side. In a domain view, each card is a domain, rows are key tables, and relation-used keys
are listed on the right. A table guide below the diagram links every table in each domain.

`data.columns` optionally defines the left-to-right card layout using domain IDs, SQL table
names, or NoSQL store names. Items in each list retain their authored order; omitted items are
placed in a trailing column. Without an explicit layout, the renderer balances items across
`ceil(sqrt(n))` columns while preserving authored order within placements.

## Implicit relations

rox-core mostly does **not** declare foreign keys: many are commented out
(`# ForeignKey("task_run.run_id")`) or omitted on purpose ("no foreign key to avoid locking the
organization row"). The extractor only sees declared `ForeignKey(...)`, so supported implicit
relationships must be found and recorded in `data.relations`. Check each in-scope relationship
against the evidence hierarchy below; do not invent edges. A page with no authored relations can
be correct when no in-scope relationship is supported.

For each relevant pair of tables, look for evidence, strongest first. On a root domain view,
consider cross-domain SQL and NoSQL/blob relations only; keep same-domain SQL relations for the
submodule table view.

1. **Declared FK** — `ForeignKey("t.c")` in the column. Drawn automatically.
2. **ORM join** — `relationship(..., primaryjoin="foreign(A.x) == B.y")`.
3. **Query join or filter** — `.join(B, A.x == B.y)`, `.filter(A.x == B.y)`,
   `A.x.in_(select(B.y))`.
4. **Write site** — a row built with a value taken from another table:
   `TaskRunLog(run_id=task_run_id)`, `root_task_run_id = parent.root_task_run_id`.
5. **Lookup by id** — a function receives `x_id` and resolves it on one column:
   `Conversation.find_by_public_id(public_id=conversation_id)` proves `conversation_id`
   everywhere in that flow is `conversation.public_id`.
6. **NoSQL key** — a key builder or partition key embedding a SQL id:
   `f"chat:conversation:{conversation_id}:stream:{stream_id}"`, a DynamoDB partition key
   `conversation_id`. Pair it with (5) to name the SQL column.
7. **Hints only** — commented-out `ForeignKey`, `<table>_id` naming, a column comment
   ("stores a reference to the parent task run id"). A hint alone may be cited only when it is
   the column's own documented meaning; otherwise find (2)–(6).

`rox-dox relations --repo <rox-core> --commit <sha> --tables a,b,c` lists commit-pinned
candidates from signals 2, 3 and 7 with file and line. When an ORM class name maps to multiple
tables, the finder resolves imports from the scanned file; unresolved possibilities are emitted
with a `:ambiguous` signal suffix. Confirm each candidate by reading the cited lines; the tool
proposes, the author decides.

Record each confirmed relationship as:

```json
{"src": "task_run_log.run_id", "dst": "task_run.run_id",
 "label": "written at queue time", "kind": "symbolic",
 "source": {"path": "...", "lines": [344, 351]}}
```

- `src`/`dst` are `table.column` for SQL; for a NoSQL store use the store `name`, optionally
  `name::field`.
- Cite the strongest evidence found; the `label` says what kind it is
  (`ORM primaryjoin`, `written at queue time`, `lookup by public_id`, `key embeds id`).
- On table-view pages, draw a relation only when both ends are in scope; declared FKs are drawn
  automatically. At the root, draw only cross-domain SQL and NoSQL/blob relations. Summarize
  the common tenant FKs in the root note rather than drawing them.
- Self-references (`parent_task_run_id → run_id`) are relations too.

## Checks before reporting

- Every authored domain member and table-view SQL table exists at the pinned commit.
- Each key table and relation endpoint is on the page and source-cited.
