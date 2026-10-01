---
name: block-diagram
description: Author and verify source-cited block diagrams for rox-core. Use when creating or revising a block figure, reviewing a diagram inherited from rox-core documentation, or checking its layout.
---

# block-diagram

## Reuse diagrams only after verifying them

1. Find diagrams at the pinned commit with
   `git grep -l -E '```mermaid|┌|@startuml' <sha> -- '*.md'`.
2. Check every box, name and arrow against code; use `outline` for module structure and
   `call-tree` for flows.
3. Drop claims that cannot be verified from rox-core (for example, autoscaling thresholds)
   and correct stale names.
4. Reuse a diagram as a figure with a cited “Based on <doc>, corrected: …” note.
5. Each root/folder Block section has one overview (Figure 1) plus focused per-flow figures,
   selected with `minimal-cover` and numbered sequentially.

## Layout and visual language

Columns read left to right. Every arrow must point to a column strictly to its right; forward skips are allowed. `rox-dox build` warns on backward and same-column edges and fails when a figure has more than 5 layout problems. Above that, reorder columns, nest groups, use group endpoints, or split the figure.

When one box talks to every box in a group, draw one arrow to the group, not one per box.

Queues and streams show producer → queue → consumer whenever both sides are in scope. A domain-scoped flow may include a queue with only one in-domain side. Arrows follow the data even when the consumer polls.

## Generated domain and feature pages
- Feature columns are Web app → Entry points → Task queues → Queue workers → Data & services; empty columns are omitted.
- Entry points group HTTP APIs, non-queue background workers, and task-producing library code not reached by another entry.
- Reach follows in-feature call evidence and stops before files owned by another entry.
- Caller and queue-worker reach starts only at imported member files, never at the caller's other code.
- Queue edges follow producers → queue → consumers, with queue details cited at task-type definitions.
- Entry and worker store edges use the extracted reads, writes, reads & writes, or uses evidence.
- Domain flows show in-domain producer and consumer features around queues, including queues with one in-domain side.

A box that stands for many runtime instances (one per queue type, per user, per executor class) is drawn stacked (`many: true`), and its citation must show the plurality.

Shapes: rectangles for components, upright cylinders for stores, chevrons for queues and streams, dashed boxes for outside services, dashed outlines for groups.

Block diagrams use white component rectangles with 1.5px `#1f2937` strokes, centered bold
titles, dividers and bulleted details; stores are `#eff6ff` vertical cylinders with `#1e40af`
strokes, and queues/streams are `#f0fdf4` chevrons with `#166534` strokes. Third parties use
white dashed `#6b7280` boxes with an `«external»` stereotype; groups are transparent dashed
`#9ca3af` UML boundaries. Use `component` for services, clients and workers, `store` for
databases and caches, `queue` for queues and streams, and `external` for third parties. Keep
cited edge labels on white rounded backgrounds, use solid `#374151` arrows for ordinary routes
and dashed `4 3` arrows for long-channel routes, and include the shape legend.

## Generated domain and feature pages

Feature diagrams flow left to right from Web app through HTTP APIs, background workers and
eligible library code to Database and External services.
Domain diagrams flow from linked Features to their per-feature tables and shared external services.
Entry reach starts at each API or worker and follows internal `call` evidence within that feature.
Reach stops before files owned by a different entry; unreachable backend library directories are
shown only when they use a table or an outside service.
Web-to-API arrows require paired web-route and backend endpoint-path evidence; all diagram
components, details and edges retain source citations.
