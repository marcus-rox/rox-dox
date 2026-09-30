# rox-docs — linked HTML design docs for rox-core, one module deeper per click

**Status · 2026-09-30 · planned.** Feasibility gate passed (PlantUML renders all four UML types with clickable links, no Graphviz).

## The objective

Marcus can start at the rox-core root page and, by clicking, reach any module's block, schema,
sequence and state diagrams with every element cited (SPEC R-1 to R-4).

## Constraints

- Diagrams are UML, with a soft limit of about 12 boxes per diagram. More than that is unreadable, and the CIAO study found generated diagrams to be the weakest output.
- Facts come from code, and the narrative comes from the model. An uncited element fails the build. DeepWiki-style made-up architecture is the failure this prevents.
- Pages are self-contained HTML (inline SVG and CSS) and open from a local clone.

## Next steps

1. **Generator plus 3 real pages** (root → chat → one leaf). The generator is the page-model JSON, the renderer, the SQLAlchemy schema extractor and the citation check. *Falsifier:* Marcus says the pages don't read like the EvalKit doc, or the citation check can't reject a bad source. *Cost:* this session.
2. **Whole rox-core tree** via the `generate-rox-docs` skill, run as one child session per top-level module. *Falsifier:* spot-checked pages contradict the code. *Cost:* about 1 session, mostly parallel child sessions.

## Decided

- **Model first, then render.** Devin writes a JSON page model (nodes, edges, messages, transitions, each with a source), and a deterministic renderer turns it into PlantUML and HTML. This keeps layout stable between runs and makes R-4 checkable.
- **Schema diagrams come from parsing the SQLAlchemy models in code.** NoSQL stores (Redis, Mongo, OpenSearch, S3) are modelled by Devin, with sources.
- **The page tree follows rox-core's module folders.** Folders that are too large or too small are regrouped by dependencies, as in CodeWiki.
- **PlantUML with Smetana layout**, which is pure Java and needs no Graphviz.
- **TLDR uses the `recap` format.**

## Open

- How the site is viewed: open it from a local clone, or GitHub Pages. Marcus decides.
