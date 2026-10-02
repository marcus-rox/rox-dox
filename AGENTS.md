# rox-dox

Always-on pointers to repository skills. Load a skill when its trigger fires.

- Before writing, editing or refactoring code, invoke `coding-standards`.
- When work spans more than one checkpoint, invoke `checkpoint-commits`.
- Building something whose requirements are known? `build` is the default development style.
- A list of requirements or hypotheses too long to read? `minimal-cover`.
- Finishing a task: `consistency` before declaring a change done, `tldr` for the handoff.
- `call-tree`: `.agents/skills/call-tree/SKILL.md`
- `daily-rebuild`: `.agents/skills/daily-rebuild/SKILL.md`
- `outline`: `.agents/skills/outline/SKILL.md`
- `rox-dox outline PATH ... [--repo R --commit C] [--json]`: per-file top-level classes, functions and UPPER_CASE constants with line and first docstring line.
- `block-diagram`: `.agents/skills/block-diagram/SKILL.md`
- `sequence-diagram`: `.agents/skills/sequence-diagram/SKILL.md`
- `schema-diagram`: `.agents/skills/schema-diagram/SKILL.md`
- `state-diagram`: `.agents/skills/state-diagram/SKILL.md`
- `rox-dox lint-diagrams pages [--page <id> ...] [--json]`: block and schema diagram rules; exit 1 on errors.
- `rox-dox states --repo R --commit C [--prefix P ...] [--json]`: state enums with their members, columns, sets and transitions (source of truth for state diagrams).
- `pages/authoring/rox_core.py` regenerates the root page JSON at `pages/rox-core.json`.
