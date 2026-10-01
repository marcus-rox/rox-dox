---
name: block-diagram
description: Author and verify source-cited block diagrams for rox-core in system-design-interview style — a few fundamental runtime components, data flowing left to right. Use when creating or revising a block figure on any root, domain or feature page, reviewing a diagram inherited from rox-core documentation, or checking its layout.
---

# block-diagram

A block diagram answers one question: **what are the running parts, and how does the data
move between them?** It is the "high-level design" a system-design interview asks for, not
an inventory of the code. Extracted facts (endpoints, executors, task types, queues, tables)
are evidence for the boxes and arrows; they are never themselves the boxes.

## 1. Write the flow before drawing anything

Write 3–6 numbered steps in plain words, input to output, for the page's subject:

> 1. A user connects Google in the web app. 2. INTERACTION saves the integration and starts
> the initial-sync workflow. 3. The workflow enqueues calendar extraction. 4. Integration
> workers pull events from Google and write `calendar_event`.

Every step must be citable at the pinned commit. The diagram is these steps drawn left to
right; each arrow carries its step's verb ("connect", "start sync", "enqueue", "write").
If a step cannot be cited, drop it; do not draw it.

## 2. Pick the fundamental components

A box is a **runtime component**: something that is deployed, runs, stores or is called.

| Kind | rox-core examples | Shape |
|---|---|---|
| Client / caller | web app, iOS app, a provider pushing webhooks | rectangle (`component`) or dashed (`external`) |
| Service | INTERACTION, CHAT, PUBLIC_API, WEBHOOK, MCP (deploy targets) | rectangle |
| Async channel | SQS queues, Temporal, Redis stream | chevron (`queue`) |
| Worker pool | INTEGRATION workers, AGENT workers, a Temporal worker | stacked rectangle (`many: true`) |
| Store | Postgres, Redis, S3, KV | cylinder (`store`) |
| Outside system | Google APIs, Microsoft Graph, Slack, Twilio, LLM providers | dashed box (`external`) |

Never a box: a file, module, class, API namespace, task type, executor, table, or a single
queue name. Those go in the bullets inside the box they belong to (at most 4 bullets), or in
a table under the figure.

**Same components at every level.** Domain and feature pages reuse the root page's
components and names (INTERACTION, WEBHOOK, SQS, worker pools, Postgres, providers) and show
only the part the subject uses. Zooming in adds bullets and figures, not new kinds of boxes.

**Merge by role.** All queues the subject uses are one SQS box; all its tables are one
Postgres box listing the main tables; all providers it calls are one box unless the flow
treats them differently. Split a box only when the two halves take different arrows.

## 3. Budget

- 5–12 boxes per figure; hard limit 15. Over budget means the abstraction is wrong: merge
  by role, or move a sub-flow into its own figure.
- At most ~1.5 arrows per box. One arrow per step, not one per call site.
- One overview figure (Figure 1) per page, then at most 3 focused figures, one per flow,
  each obeying the same budget.

## 4. Layout

- Columns read left to right in flow order: callers → services → async channels → workers
  → stores → outside systems. Leave a column out when the subject has none.
- Every arrow points right. A step that goes "back" (a worker calling a service) is drawn
  as a separate figure, or the target is placed further right.
- An outside system that both pushes in and is called out appears twice: once on the left
  as the caller ("Google push"), once on the right as the API ("Google APIs").
- A dotted group marks the system boundary when there are callers or outside systems.
- `rox-dox build` warns on every non-adjacent arrow and fails when a figure has more than 5
  layout problems.

## 5. Check before shipping

- Read the rendered figure at 100% zoom: can a newcomer retell the numbered flow from it
  alone? If not, redo it, whatever the validator says.
- Count boxes and arrows against the budget.
- Every box, bullet and arrow has a citation at the pinned commit.

## Reusing diagrams from rox-core docs

Find them with `git grep -l -E '```mermaid|┌|@startuml' <sha> -- '*.md'`, check every box
and arrow against code (`outline`, `call-tree`), drop what cannot be verified, and cite the
figure as "Based on <doc>, corrected: …".

## Visual language

Block diagrams use white component rectangles with 1.5px `#1f2937` strokes, centered bold
titles, dividers and bulleted details; stores are `#eff6ff` vertical cylinders with `#1e40af`
strokes, and queues/streams are `#f0fdf4` chevrons with `#166534` strokes. Third parties use
white dashed `#6b7280` boxes with an `«external»` stereotype; groups are transparent dashed
`#9ca3af` UML boundaries. Keep cited edge labels on white rounded backgrounds, use solid
`#374151` arrows for ordinary routes and dashed `4 3` arrows for long-channel routes, and
include the shape legend.
