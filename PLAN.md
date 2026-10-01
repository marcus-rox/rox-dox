# rox-dox — a feature tree of cited design docs for rox-core, regenerated on a schedule

**Status · 2026-10-01 · implementing cited runtime projections.** The approved c43 Activity diagrams define the visual style; `/home/ubuntu/scratch/projection_spec.md` defines the catalog and projection.

## The objective

Marcus can open the rox-core root, click a domain, then a feature, and see that feature end to
end: its routes, logic, background workers, web UI and the tables it reads and writes, with
every box, arrow and sentence cited to rox-core code. One scheduled run rebuilds the whole site
from the latest `main` (SPEC `R-2`, `R-4` to `R-9`; tasks in TASKS.md).

![Figure 1 — the feature tree](docs/feature-tree.svg)

![Figure 2 — one scheduled regeneration run](docs/regeneration-run.svg)

## Constraints

1. **Every element is cited at one pinned commit; an uncited or stale element fails the build.**
   Prevents made-up architecture, the DeepWiki failure the project exists to avoid.
2. **Diagrams already in rox-core's docs are hypotheses until checked against code.** None of
   the seven architecture-doc diagrams was correct as written, and two could not be checked.
3. **Pages are grouped by what the code does, not by folder.** rox-core is split by layer, so a
   folder tree splits one feature across distant pages (`chat/routes/org_chart_v2` vs
   `rox_core/api/org_chart_v2`).
4. **A block figure with more than five layout problems fails the build.** Arrows routed through
   the bottom bundle were unreadable.
5. **Pages are self-contained HTML** that open offline from a local clone.
6. **Queue mapping never guesses.** Only `ClassName.MEMBER` values mapped by `QUEUE_CONFIGS` get a deploy target; unknown values remain unmapped.

## Previous steps

| Step | Outcome | What it established |
|---|---|---|
| Root page: overview, domain schema, four checked flow figures | ✅ | Page format, renderers, citation check and diagram skills work · PRs 8–11 |
| Root → chat → leaf as folder pages (old step 1, rest) | ❌ | Removed unrun — superseded by the feature tree |
| Whole repo as a folder tree (old step 2) | ❌ | Removed unrun — folders split features across layers |
| Overlap between sibling folders in `chat` and `chat/routes` | ✅ | Siblings barely overlap; one feature spans distant folders · this session |
| Prior work and brainstorm on parent → child generation | ✅ | Adopted an explicit page tree and full rebuilds; rejected writing parents from children · this session |
| Feature maps, runtime facts, and cached generation | ✅ | Pinned-source feature and runtime extraction support generated pages · Tasks 82–112 |
| Hand-authored Activity figures and forward-skip corridors | ✅ | Approved left-to-right reference style and readable routing · `c43ca202` |
| Generated-page merge checkpoint | ✅ | Retained c43 diagram behavior and the compatible feature-tree work · `ce903d8` |

## Next steps

1. **Reusable component catalog and source facts.** Generate the catalog from root citations, then extract deploy targets, routes, queue mappings, and workflow starts. *Falsifier:* a fact test disagrees with pinned source or an unknown queue expression is mapped. *Cost:* about half a session.
2. **Feature and domain runtime projections.** Attribute in-scope files to catalog entries, produce cited edges and flow notes, and report unreachable files. *Falsifier:* synthetic projections violate the spec or any diagram element lacks source evidence. *Cost:* about one session.
3. **Regenerate Activity and Seq, build, inspect, and deliver.** Regenerate only those domains, capture the requested figures, run the full checks, then checkpoint and push. *Falsifier:* generated figures fail validation or do not match the hand-authored style. *Cost:* about half a session.

## Decided

- **Feature tree, not folder tree.** Level 1 is whatever schema domains the root shows at the run's
  commit (ten today), so the count follows rox-core; the root page stays as it is.
- **One algorithm at every level:** take the page's code, group it by overlap, make each group a
  child page, and repeat on each child until it is a leaf.
- **Overlap decides the number of children; there is no cap.**
- **Page content and diagrams use the existing skills unchanged** (generate-rox-docs,
  block-, schema-, sequence- and state-diagram).
- **Left panel:** table of contents, then the feature tree, then the file Explorer. Clicking a
  folder opens a docs page listing the feature pages that cover its files, never GitHub.
- **Every run rebuilds every page from scratch** at the latest `main` and opens a rox-dox PR
  from a new branch; no change detection yet.
- **Documented files are backend, web, agent skills and deployment config.** Tests and
  migrations are not documented, and the root page says so.
- **Accuracy and readability come before run cost.**
- **No Notion on pages** (SPEC `R-3` retired).
- **Superseded documents are renamed `*_deprecated.md`**, not deleted.
- **Generated diagrams follow the c43 Activity style.** Catalog kinds stay semantic; rendering uses the existing component/store/external/queue shapes.
- **Queue deploy targets come only from default `queue_type`.** Dynamic-routing fields are ignored; unknown expressions are reported, not inferred.
- **Projection attribution starts at runtime entries and follows in-scope imports.** Unreached files are reported rather than assigned by guesswork.
- **The diagram box budget is 15.** Merge provider boxes first and worker-pool boxes second only when needed.

## Out of scope

- Regenerating only changed pages — every run rebuilds everything for now.
- Running on every rox-core PR — there are too many; the schedule is enough.
- Notion context and the right-hand panel — `R-3` retired by Marcus.
- Pages per folder — folders only list the feature pages that cover them.
- Regenerating domains other than Activity and Seq during this task.
- Changes to `/home/ubuntu/rox-docs-t8` or `/home/ubuntu/rox-docs-main`.

## Open

- **Where code that touches no table goes** (shims, the agent framework, the LLM client).
  Step 1 shows how much there is; a "Platform" domain at level 1 is the likely answer.
- **The exact overlap measure and when two groups count as one feature.** Tuned in step 1
  against Marcus's review of the groups.
- **When a feature is a leaf.** Decided on the first features in step 2.
- **How web (TypeScript) code joins a feature.** Matching the API routes it calls to backend
  routes; checked in step 1.
- **Code used by many features** (shared models, utilities). Shown on every feature that uses
  it; whether it also gets its own page is decided in step 1.
