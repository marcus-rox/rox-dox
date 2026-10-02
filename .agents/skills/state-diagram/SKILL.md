---
name: state-diagram
description: Author source-cited state diagrams from persisted or enumerated state machines. Use when creating or revising a state diagram for a documented entity.
---

# state-diagram

Only model entities with a persisted or enumerated state. Derive states and transitions from
the code's enums and transition tables, not from reading the happy path.

## Source of truth

Run `uv run rox-dox states --repo <rox-core> --commit <sha> [--prefix backend/src/...] --json`
to get every state enum with its members, SQL columns, assignment sites, and transitions.
Draw only enums with at least one column or transition, and cite member and transition
lines (`path:line`) straight from the tool output. Your judgement is reserved for what the
tool cannot answer: which entity the diagram is for, whether string-typed status columns
assigned via `X.MEMBER.value` belong in it, and how to name states.
