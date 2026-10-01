# rox-dox sprint tasks

**Status:** Approved 2026-09-30.

## Manifest

| # | Task | Satisfies | Parent plan step | Depends on | Priority |
|---|---|---|---|---|---|
| 1 | Define the page model and citation validator | R-4 | Next step 1 | — | High |
| 2 | Render one complete offline design-doc page | R-2, R-4 | Next step 1 | 1 | High |
| 3 | Add recursive navigation and page linking | R-1, R-2 | Next step 1 | 2 | High |
| 4 | Add Notion context to generated pages | R-3 | Next step 1 | 2 | High |
| 5 | Generate the first three real rox-core pages | R-1, R-2, R-3, R-4 | Next step 1 | 3, 4 | High |
| 6 | Define and run the generalized rox-core generation skill | R-1, R-2, R-3, R-4 | Next step 2 | 5 | Medium |

## Requirement coverage

| Requirement | Status now | Tasks | Status if this sprint lands |
|---|---|---|---|
| R-1 | unbound | 3, 5, 6 | ✅ for the generated scope |
| R-2 | unbound | 2, 3, 5, 6 | ✅ |
| R-3 | unbound | 4, 5, 6 | ✅ |
| R-4 | unbound | 1, 2, 5, 6 | ✅ |

## Parallel execution plan

| Wave | Tasks | Blocked by |
|---|---|---|
| 1 | 1 | — |
| 2 | 2 | 1 |
| 3 | 3, 4 | 2 |
| 4 | 5 | 3, 4 |
| 5 | 6 | 5 |

The maximum useful parallelism is two tasks in Wave 3.

---

# Task 1 — Define the page model and citation validator

**Satisfies:** R-4.

## User story

As the documentation generator, I want every page element represented with a source, so that
uncited or stale documentation cannot be rendered.

## Context

The approved design is model-first: a structured page model is validated before a deterministic
renderer produces HTML and UML diagrams.

## Scope

In scope:
- A structured model for TLDR claims, tables, diagram nodes and edges, sequence steps, states,
  transitions, related links, and Notion references.
- Code sources pinned to a commit and line range.
- Notion sources.
- Validation of missing, malformed, and stale sources.

Out of scope:
- HTML rendering.
- Notion searching.
- Automatic authoring of page models.

## Requirements

- Every emitted claim and diagram element has at least one source.
- Code sources identify a file, commit, and valid line range.
- Invalid or stale sources fail the build and identify the affected element.

## Acceptance criteria

- Given a page model with an uncited arrow, when validation runs, then it fails naming that arrow.
- Given a page model with a line range absent at its pinned commit, when validation runs, then it
  fails naming the source.
- Given a valid page model, when validation runs, then it succeeds.
- Errors and edge cases: a missing commit, missing file, invalid line range, undeclared diagram
  endpoint, or invalid Notion source fails explicitly.

## Definition of Done

- All acceptance criteria pass.
- R-4 is green in the SPEC conformance table.
- Code is reviewed and merged.
- Appropriate automated tests pass.
- The change is deployed to the local repository workflow.
- No unresolved critical defects remain.

## Dependencies and constraints

- Sources must be checkable without production database access.
- The model must support every section required by R-2.

## Proof of value

**Discharges:** Plan → Decided — model first, then render, so citation checking is deterministic.

**Claim:** If every acceptance criterion holds, the generator has a checkable source boundary
before rendering.

**Premises:**
1. Uncited elements fail validation — source: acceptance criterion 1.
2. Stale code sources fail validation — source: acceptance criterion 2.
3. Valid models pass validation — source: acceptance criterion 3.

**Argument:**
1. Every rendered element must first be represented in the model.
2. The validator rejects the two failure classes that would make an element unverifiable.
3. Therefore, rendering receives only structurally cited models.

**Attempted counterexample:** A semantically incorrect claim can cite a real line range. That is
not a structural citation failure and must be caught by review of generated pages.

**Falsifier:** A page with a missing or stale source passes validation.

**Verdict:** Proved for structural citation validity; semantic support remains a review concern.

## References

- Design: PLAN.md — Model first, then render.
- Technical specification: SPEC.md — R-4.
- Related issues: Task 2 — Render one complete offline design-doc page.

## Delivery

- Owner: TBD
- Priority: High
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 1 — Generator plus 3 real pages

---

# Task 2 — Render one complete offline design-doc page

**Satisfies:** R-2, R-4.

## User story

As a researcher, I want one generated page to contain the complete design-doc layout offline, so
that I can understand a module without production access or network access.

## Context

Every page has the same ordered sections and uses inline UML diagrams and CSS.

## Scope

In scope:
- Recap TLDR, table of contents, UML block, schema, sequence, and state sections.
- Inline SVG and CSS.
- Empty-section placeholders.
- Source links on emitted content.

Out of scope:
- Recursive page discovery.
- Notion search.
- Whole-tree generation.

## Requirements

- Sections appear in the order specified by R-2.
- The output is self-contained and opens without network access.
- UML diagrams render inline.

## Acceptance criteria

- Given a valid page model, when the renderer runs, then it produces one self-contained HTML page
  with all required sections in order.
- Given a section with no applicable content, when the page opens, then that section remains and
  explains that there is nothing to show.
- Given a generated page with network access disabled, when it opens, then its content and
  diagrams still render.
- Errors and edge cases: invalid diagram syntax or an uncited model fails the build rather than
  emitting partial HTML.

## Definition of Done

- All acceptance criteria pass.
- R-2 is green in the SPEC conformance table.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- The page opens from a local clone in VS Code or Cursor.
- No unresolved critical defects remain.

## Dependencies and constraints

- Depends on Task 1.
- Diagrams are UML.
- The approximately 24-box readability guide applies to block diagrams; sequence and state
  diagrams use an approximately 12-element guide. Schema diagrams are explicitly exempt and
  must show all tables in scope.

## Proof of value

**Discharges:** Plan → Constraints — pages are self-contained HTML with UML diagrams.

**Claim:** If every acceptance criterion holds, one generated page demonstrates the fixed offline
  design-doc contract.

**Premises:**
1. All sections appear in order — source: acceptance criterion 1.
2. Empty sections remain visible — source: acceptance criterion 2.
3. The page renders without network access — source: acceptance criterion 3.

**Argument:**
1. The ordered section check establishes the document shape.
2. The empty-section check establishes stable shape across modules.
3. The offline check establishes the local viewing contract.
4. Therefore, the page satisfies the design-doc rendering contract.

**Attempted counterexample:** A page can pass while a diagram is visually unreadable. The
readability guide requires review of the rendered page before this task is accepted.

**Falsifier:** Any required section is missing, reordered, or dependent on a network resource.

**Verdict:** Conditional on visual review of the rendered diagrams.

## References

- Design: PLAN.md — self-contained HTML, UML, and readability guide.
- Technical specification: SPEC.md — R-2 and R-4.
- Related issues: Task 1 — Define the page model and citation validator; Task 3 — Add recursive navigation and page linking.

## Delivery

- Owner: TBD
- Priority: High
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 1 — Generator plus 3 real pages

---

# Task 3 — Add recursive navigation and page linking

**Satisfies:** R-1, R-2.

## User story

As a researcher, I want to click from rox-core into any folder and back, so that each click gives
me a more detailed view of the system.

## Context

The tree is generalized: nothing in rox-core is off limits, including `web`, `k8s`, and
`.agents/skills`. A page may represent a folder or a regrouping required for readability.

## Scope

In scope:
- Root page, parent links, child links, breadcrumbs, and left navigation.
- Clickable diagram links between pages.
- Coverage of every rox-core folder in the configured documentation scope.

Out of scope:
- Notion retrieval.
- Semantic correctness review of page narratives.

## Requirements

- The navigation tree includes every in-scope folder.
- Every page links to its parent and children where they exist.
- The current page is highlighted.

## Acceptance criteria

- Given the root page, when a reader clicks an in-scope folder, then its page opens and links
  back to the root.
- Given a page with children, when it opens, then the left navigation and page content list all
  children.
- Given a leaf page, when it opens, then it has no child links and still has parent navigation.
- Errors and edge cases: duplicate paths, orphan pages, and links to missing pages fail the build.

## Definition of Done

- All acceptance criteria pass.
- R-1 is green for the generated scope.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- No unresolved critical defects remain.

## Dependencies and constraints

- Depends on Task 2.
- Tree scope includes all rox-core folders.
- A 3,051-folder repository inventory is an input to the coverage strategy; the generator must
  define a readable regrouping where a one-page-per-folder output is not useful.

## Proof of value

**Discharges:** Plan → Objective — start at the rox-core root and click to deeper module pages.

**Claim:** If every acceptance criterion holds, every generated page is reachable through the
navigation tree and links back toward the root.

**Premises:**
1. Every in-scope folder appears in the tree — source: acceptance criterion 1.
2. Parent and child links are emitted — source: acceptance criteria 2 and 3.
3. Missing and orphan links fail — source: acceptance criterion 4.

**Argument:**
1. Coverage makes every target a node in the tree.
2. Parent and child links connect each node to its surrounding levels.
3. Link validation prevents disconnected output.
4. Therefore, the reader can drill down and return.

**Attempted counterexample:** A folder inventory may contain generated or irrelevant directories
that should be regrouped. The acceptance criterion requires the final generated scope to be
explicit and complete, not silently omitted.

**Falsifier:** An in-scope folder cannot be reached from the root or a generated link resolves to
no page.

**Verdict:** Proved given the dependency-based regrouping approved in PLAN.md.

## References

- Design: PLAN.md — module tree and progressively lower abstraction.
- Technical specification: SPEC.md — R-1.
- Related issues: Task 2 — Render one complete offline design-doc page; Task 4 — Add Notion context to generated pages.

## Delivery

- Owner: TBD
- Priority: High
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 1 — Generator plus 3 real pages

---

# Task 4 — Add Notion context to generated pages

**Satisfies:** R-3.

## User story

As a researcher, I want related Notion context beside each page, so that I can understand why
the code exists in addition to what it does.

## Context

Notion is a supplemental source. Slack remains a visible future slot, but is not an active
source for these pages.

## Scope

In scope:
- Right-side Notion panel with each document shown as its linked title.
- Empty-state handling.
- Slack placeholder below the Notion panel.
- Notion citations in page models.

Out of scope:
- Slack search or Slack-derived claims.
- Production usage metrics.

## Requirements

- Every page has the right-side context panel.
- Related Notion entries show each document as its linked title.
- The Slack section is present below Notion.

## Acceptance criteria

- Given related Notion pages, when a page opens, then the panel shows each as its linked title.
- Given no related Notion pages, when a page opens, then the panel remains and shows an empty state.
- Given any page, when the right panel opens, then the Slack section appears below Notion.
- Errors and edge cases: invalid links, missing titles, or malformed dates fail authoring/build
  validation rather than producing misleading context.

## Definition of Done

- All acceptance criteria pass.
- R-3 is green.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- No unresolved critical defects remain.

## Dependencies and constraints

- Depends on Task 2.
- Notion content is gathered during page authoring and stored in the page model.
- Pages remain viewable without network access.

## Proof of value

**Discharges:** Plan → Decided — Notion context is included in v1 and Slack is represented by a
placeholder.

**Claim:** If every acceptance criterion holds, each page provides offline supplemental Notion
context without making Slack an active source.

**Premises:**
1. Related entries show all required fields — source: acceptance criterion 1.
2. Empty pages still show the panel — source: acceptance criterion 2.
3. Slack appears below Notion — source: acceptance criterion 3.

**Argument:**
1. The panel has a stable shape whether or not matches exist.
2. Each displayed Notion fact has the fields needed to inspect its provenance.
3. The Slack placeholder preserves the intended layout without unsupported content.
4. Therefore, the context-panel contract is met.

**Attempted counterexample:** A Notion page can change after authoring. The page remains a
snapshot; regeneration is responsible for refreshing it.

**Falsifier:** A generated page omits a required Notion field or requires network access to open.

**Verdict:** Proved for the generated snapshot.

## References

- Design: PLAN.md — model-first rendering and Notion context.
- Technical specification: SPEC.md — R-3.
- Related issues: Task 2 — Render one complete offline design-doc page; Task 5 — Generate the first three real rox-core pages.

## Delivery

- Owner: TBD
- Priority: High
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 1 — Generator plus 3 real pages

---

# Task 5 — Generate the first three real rox-core pages

**Satisfies:** R-1, R-2, R-3, R-4.

## User story

As a researcher, I want to review a real root-to-leaf path, so that I can decide whether the
documentation format is useful before generating the whole repository.

## Context

The first vertical slice is rox-core root → chat → one leaf module.

## Scope

In scope:
- Three real page models.
- Root, chat, and one leaf page.
- All required diagrams and panels.
- Local offline review.

Out of scope:
- The complete rox-core tree.
- Automated generation skill.

## Requirements

- The three pages are linked as a drill-down path.
- Each page uses the fixed layout and citation checks.
- The pages are understandable from the code and available Notion context.

## Acceptance criteria

- Given a local clone, when the root page opens, then the reader can click through chat to the
  leaf and back.
- Given the three generated pages, when the conformance checks run, then all four requirements
  pass for this slice.
- Given a page review, when the diagrams and TLDR are compared with the source, then no
  contradiction is found.
- Errors and edge cases: any missing page, broken link, stale citation, or contradiction blocks
  the slice from being accepted.

## Definition of Done

- All acceptance criteria pass.
- R-1 through R-4 are green for the slice.
- Code and generated pages are reviewed and merged.
- Appropriate automated and manual tests pass.
- Pages open locally in VS Code or Cursor.
- No unresolved critical defects remain.

## Dependencies and constraints

- Depends on Tasks 3 and 4.
- Schema diagrams show all tables in scope, even when there are 37 or more.
- Block diagrams follow an approximate 24-box readability guide; sequence and state diagrams
  follow an approximate 12-element guide. Schema diagrams show every table in scope.

## Proof of value

**Discharges:** Plan → Next step 1 — generator plus three real pages.

**Claim:** If every acceptance criterion holds, the project has a reviewable end-to-end slice
before whole-tree generation.

**Premises:**
1. The three pages form a linked path — source: acceptance criterion 1.
2. All requirements pass for the slice — source: acceptance criterion 2.
3. Human review finds no contradiction — source: acceptance criterion 3.

**Argument:**
1. The path demonstrates navigation.
2. Conformance demonstrates the renderer and validator integration.
3. Review demonstrates usefulness against real code.
4. Therefore, the first slice supplies evidence for whole-tree generation.

**Attempted counterexample:** A three-page slice may not expose problems in unusual folders such
as k8s or skills. Those are deferred to Task 6's whole-tree coverage.

**Falsifier:** Marcus rejects the pages as unreadable or a cited claim contradicts rox-core.

**Verdict:** Proved for the slice; not evidence of whole-tree correctness.

## References

- Design: PLAN.md — Next step 1.
- Technical specification: SPEC.md — R-1 through R-4.
- Related issues: Task 3 — Add recursive navigation and page linking; Task 4 — Add Notion context to generated pages.

## Delivery

- Owner: TBD
- Priority: High
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 1 — Generator plus 3 real pages

---

# Task 6 — Define and run the generalized rox-core generation skill

**Satisfies:** R-1, R-2, R-3, R-4.

## User story

As a Devin operator, I want one reusable generation skill that accepts a repository and module
scope, so that the same documentation process works across every rox-core folder.

## Context

The approved plan's second step is a `generate-rox-docs` skill. It must handle the complete
rox-core tree, including web, k8s, and `.agents/skills`.

## Scope

In scope:
- Skill instructions for discovering folders and source material.
- Page-model authoring and citation validation.
- Notion lookup and page rendering.
- Whole-tree coverage and merge-safe output ownership.

Out of scope:
- Slack search.
- Production usage analysis.
- Requiring a hosted documentation site.

## Requirements

- The skill can generate pages for any permitted rox-core folder.
- Generated output passes the same navigation, layout, Notion, and citation checks.
- The skill has a deterministic ownership rule so parallel work does not overwrite another
  module's subtree.

## Acceptance criteria

- Given any in-scope folder, when the skill runs, then it produces or updates that folder's page
  and the links needed to reach it.
- Given parallel module generation, when outputs are combined, then no two workers own the same
  page path.
- Given generated output, when the conformance suite runs, then R-1 through R-4 pass for the
  generated scope.
- Errors and edge cases: unsupported file types, missing source history, failed Notion lookup,
  and page ownership collisions fail with an actionable error.

## Definition of Done

- All acceptance criteria pass.
- R-1 through R-4 are green for the generated scope.
- The skill is reviewed and merged.
- Appropriate automated and manual tests pass.
- No unresolved critical defects remain.

## Dependencies and constraints

- Depends on Task 5.
- The skill lives in rox-dox under `.agents/skills/`.
- Every folder is eligible; the final grouping policy must preserve navigability for the
  repository's approximately 3,051 folders.

## Proof of value

**Discharges:** Plan → Next step 2 — whole rox-core tree via the `generate-rox-docs` skill.

**Claim:** If every acceptance criterion holds, the approved generation process can be reused
across the complete rox-core folder tree without losing citations or navigation.

**Premises:**
1. Any in-scope folder can be generated — source: acceptance criterion 1.
2. Parallel output ownership is disjoint — source: acceptance criterion 2.
3. Generated output passes all requirements — source: acceptance criterion 3.

**Argument:**
1. Folder coverage establishes generality.
2. Ownership establishes safe parallel execution.
3. Conformance establishes that reuse preserves the page contract.
4. Therefore, the skill operationalizes whole-tree generation.

**Attempted counterexample:** A generated page can be structurally valid but semantically wrong.
The source citation requirement and spot checks reduce this risk but do not prove semantic
correctness for every narrative sentence.

**Falsifier:** A supported folder cannot be generated, or whole-tree output contains an orphan,
uncited, stale, or contradictory page.

**Verdict:** Proved given the approved dependency-based regrouping and skill location.

## References

- Design: PLAN.md — Next step 2 and decided model-first architecture.
- Technical specification: SPEC.md — R-1 through R-4.
- Related issues: Task 5 — Generate the first three real rox-core pages.

## Delivery

- Owner: TBD
- Priority: Medium
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 2 — Whole rox-core tree via `generate-rox-docs`
