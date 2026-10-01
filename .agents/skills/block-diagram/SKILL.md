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

Columns read left to right, and every arrow goes from one column to the next. No backward, same-column or column-skipping arrows: reorder the columns, nest groups inside one column, or split the figure. `rox-dox build` warns on violations; fix every warning.

When one box talks to every box in a group, draw one arrow to the group, not one per box.

Every queue or stream has at least one producer arrow in and one consumer arrow out. Arrows follow the data (producer → queue → consumer), even when the consumer polls.

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
