# rox-dox sprint tasks — feature tree

**Status:** Draft 2026-10-01, awaiting Marcus. Decomposes PLAN.md next steps 1–3 against SPEC.md.
The folder-tree tasks are in TASKS_deprecated.md.

## Manifest

| # | Task | Satisfies | Parent plan step | Depends on | Priority |
|---|---|---|---|---|---|
| 1 | Sequences & outreach code is grouped into features, with evidence | R-6, R-9 | Next step 1 | — | High |
| 2 | The left panel navigates a root → domain → feature tree | R-5 | Next step 2 | — | High |
| 3 | Every folder in the Explorer opens a docs page | R-7, R-6 | Next step 2 | 1, 2 | High |
| 4 | The Notion panel is removed from every page | R-3 (retired) | Decided: no Notion on pages | — | Medium |
| 5 | Sequences & outreach has a domain page and a page per feature | R-5, R-9, R-2, R-4 | Next step 2 | 1, 2, 3, 4 | High |
| 6 | Every remaining domain has a feature map and pages | R-5, R-6, R-9, R-2, R-4 | Next step 3 | 5 | Medium |
| 7 | One unattended daily run rebuilds the site as a rox-dox PR | R-8 | Next step 3 | 5 | Medium |

Priority is inferred from each plan step's position; the plan gives none explicitly.

| Req | Status now | Tasks | Status if the sprint lands |
|---|---|---|---|
| R-2 | ✅ | 5, 6 | ✅ — holds on the new pages |
| R-3 | retired | 4 | retired, with its panel and test gone |
| R-4 | ✅ | 5, 6 | ✅ — holds on the new pages |
| R-5 | unbound | 2, 5, 6 | ✅ |
| R-6 | unbound | 1, 3, 6 | ✅ |
| R-7 | unbound | 3 | ✅ |
| R-8 | unbound | 7 | ✅ |
| R-9 | unbound | 1, 5, 6 | ✅ |

## Parallel execution plan

| Wave | Tasks | Blocked by |
|---|---|---|
| 1 | 1, 2, 4 | — |
| 2 | 3 | Tasks 1, 2 |
| 3 | 5 | Wave 2 and Task 4 |
| 4 | 6, 7 | Task 5 |

Maximum useful parallelism is 3 (Wave 1). Task 5 is the bottleneck: it is the first time
feature grouping, navigation and folder pages meet on real content.

---

# Task 1 — Sequences & outreach code is grouped into features, with evidence

**Satisfies:** R-6, R-9.

## User story

As Marcus, a researcher without production access, I want the Sequences & outreach domain's
code split into features with the reason each file belongs to its feature, so that I can
check the grouping before any page is written about it.

## Context

rox-core is split by layer, so one feature's routes, logic, workers and screens sit in
distant folders (PLAN.md, Constraint 3). Sibling-folder overlap was near zero, so grouping
has to follow shared tables and calls across the whole repo (PLAN.md, Decided). This task
produces the grouping for one domain, which plan step 1 asks Marcus to review.

## Scope

In scope:
- A command that, at a pinned rox-core commit, assigns backend, web, agent-skill and
  deployment-config files to features of one domain by shared tables and calls.
- A feature map file in rox-dox: per feature, its files, the tables they read and write, and
  the calls between them, each cited.
- The list of in-domain files no feature covers.
- Excluding tests and migrations.

Out of scope:
- Writing any page (Task 5).
- The other domains (Task 6).
- Choosing a fixed child count: overlap decides (PLAN.md, Decided).
- Deciding when a feature is a leaf (PLAN.md, Open; Task 5).

## Requirements

- The command reads rox-core only through `git show` at the pinned commit.
- A file is in the domain when it reads or writes one of the domain's tables, or is called by
  a file that does.
- Each feature lists its files, and every file in it shares at least one cited table or call
  with another file of that feature.
- Web files join a feature through the backend routes they call.
- Every in-domain file is on a feature or on the uncovered list.
- Rerunning at the same commit gives a byte-identical feature map.

## Acceptance criteria

- Given the pinned commit, when the command runs for Sequences & outreach, then it writes a
  feature map where each feature lists files, tables and calls, each with a source.
- Given that map, when any file is checked, then it shares a cited table or call with another
  file of its feature.
- Given the web code, when the map is built, then web files that call a domain route appear
  on that route's feature.
- Given the domain's files, when the map is built, then every one is on a feature or on the
  uncovered list, and no test or migration appears anywhere.
- Given two runs at the same commit, when their outputs are compared, then they are
  byte-identical.
- Given the map, when Marcus reviews it, then he accepts the features and the uncovered list,
  or the grouping is revised.
- Errors and edge cases: a shared model or utility called by several features is listed on
  each of them, not dropped (PLAN.md, Open); a file that touches no table and is called by
  nothing in the domain stays out of the domain rather than being forced into a feature.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean) — for this task, the
  feature-map half of R-6 and R-9; their page halves land in Tasks 3 and 5.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the feature map is committed in rox-dox.
- No unresolved critical defects remain.

## Dependencies and constraints

- Blocking open question (PLAN.md, Open): the exact overlap measure and when two groups are
  one feature. This task tunes it against Marcus's review; it is not settled in advance.
- Open (PLAN.md): how web code joins a feature; this task tests "through the routes it calls".
- Open (PLAN.md): where code that touches no table goes; this task reports how much there is.
- Assumption carried from the Proof of value: Marcus's review covers whether the uncovered
  list is small enough, since the plan gives no number.
- Depends on: none (Wave 1). Unblocks Tasks 3 and 5.

## Proof of value

**Discharges:** Plan → Next step 1 — falsifier "Marcus judges the groups are not features, or
much of the domain's code can't be placed."

**Claim:** If every acceptance criterion of this task holds, then neither half of the falsifier
fires.

**Premises:**
1. Marcus reviews the feature map and accepts the features — source: this task's Acceptance
   criteria.
2. Every in-domain file is on a feature or on the uncovered list — source: this task's
   Acceptance criteria.
3. Marcus's acceptance covers the size of the uncovered list — source: Assumption
   (unverified); the plan gives no threshold for "much".

**Argument:**
1. From Premise 1, Marcus has not judged the groups to be non-features.
2. From Premise 2, every file the domain could fail to place is visible on the uncovered list.
3. From Premise 3, Marcus has judged that list not to be "much" of the domain.
4. Therefore neither half of the falsifier fires.

**Attempted counterexample:** Marcus accepts the feature list but never looks at the uncovered
list, which holds most of the domain. Premises 1 and 2 hold and the second half of the
falsifier fires — this is why Premise 3 is needed.

**Falsifier:** A later page (Task 5) shows a feature whose files share nothing real, despite
each sharing a cited table or call — the evidence rule would then be too weak.

**Verdict:** Conditional on Marcus's review covering the uncovered list (Premise 3), echoed in
Dependencies and constraints.

## References

- Design: PLAN.md — Constraint 3, Decided, Open; Figure 2
- Technical specification: SPEC.md — R-6, R-9
- Related issues: Task 3 — Every folder in the Explorer opens a docs page; Task 5 — Sequences
  & outreach has a domain page and a page per feature

## Delivery

- Owner: TBD
- Priority: High (inferred)
- Estimate: about half a session (PLAN.md, Next step 1)
- Sprint: TBD
- Parent epic: Next step 1 — Feature map for one domain

---

# Task 2 — The left panel navigates a root → domain → feature tree

**Satisfies:** R-5.

## User story

As Marcus, I want the left panel to show the root, the domains and their features as one tree,
with breadcrumbs and child lists on every page, so that I can drill from the whole system to
one feature in a few clicks.

## Context

Today the left panel's tree mirrors rox-core folders (PLAN_deprecated.md). The feature tree
replaces it: level 1 is the schema domains the root shows, however many there are, below them the features (PLAN.md, Decided,
Figure 1). A feature page covers files from several distant folders.

## Scope

In scope:
- Page models that cover several disjoint source paths and say whether they are the root, a
  domain or a feature.
- The left panel's tree built from page parents, below the table of contents.
- Breadcrumbs and a children list on every page.
- Stub domain and feature pages in tests to prove navigation.

Out of scope:
- Clicking folders in the Explorer (Task 3).
- Writing real domain or feature content (Task 5).
- Grouping code into features (Task 1).

## Requirements

- A page model can list any number of disjoint source paths.
- Each page is marked root, domain or feature, and a domain's parent is the root.
- The left panel shows the full root → domain → feature tree with the current page
  highlighted, below the table of contents.
- Every page has a breadcrumb back to the root and lists its children.
- The existing root page builds unchanged apart from its new children.
- Conformance tests for R-5 are drafted for Marcus to accept.

## Acceptance criteria

- Given a root, one domain and two features whose paths are in distant folders, when the site
  is built, then all four pages build and each feature lists both of its paths.
- Given those pages, when any page opens, then the left panel shows the whole tree below the
  table of contents with that page highlighted.
- Given a feature page, when it opens, then its breadcrumb reads root → domain → feature and
  its children are listed.
- Given a domain whose parent is not the root, when the site is built, then the build fails
  naming that domain.
- Given the current root page model, when it is rebuilt, then it is unchanged apart from
  listing its children.
- Given the drafted `test_r5_*` conformance tests, when Marcus accepts them, then they are
  committed and pass.
- Errors and edge cases: a feature listed under two domains fails the build naming the
  feature, because every page appears once in the tree.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean) — for this task, the
  "drilling down" scenario of R-5; the "leaf" scenario lands in Task 5.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the site builds locally from the pinned commit.
- No unresolved critical defects remain.

## Dependencies and constraints

- Pages stay self-contained HTML that open offline (PLAN.md, Constraint 5).
- Depends on: none (Wave 1). Unblocks Tasks 3 and 5.

## Proof of value

**Discharges:** Plan → Decided — "Left panel: table of contents, then the feature tree" and
Objective — "open the rox-core root, click a domain, then a feature".

**Claim:** If every acceptance criterion of this task holds, then a reader can go from the root
to any feature by clicking through the left panel's feature tree.

**Premises:**
1. The left panel shows the whole root → domain → feature tree on every page, below the table
   of contents — source: this task's Acceptance criteria.
2. Every domain's parent is the root, and every page appears once — source: this task's
   Acceptance criteria.
3. Feature pages can cover several distant paths — source: this task's Acceptance criteria.

**Argument:**
1. From Premise 2, every feature is reachable from the root through exactly one domain.
2. From Premise 1, each step of that path is a visible, clickable row on every page.
3. From Premise 3, a cross-layer feature is one page rather than several folder pages.
4. Therefore the reader reaches any feature from the root by clicking.

**Attempted counterexample:** A feature whose parent is another feature, three levels down.
Premise 1 shows the whole tree, so it is still visible and reachable; no case found where the
criteria hold and a feature is unreachable.

**Falsifier:** With all of the real domains' pages (Task 6), the tree is too long to scan in the
left panel.

**Verdict:** Proved.

## References

- Design: PLAN.md — Decided, Figure 1
- Technical specification: SPEC.md — R-5
- Related issues: Task 3 — Every folder in the Explorer opens a docs page; Task 5 — Sequences
  & outreach has a domain page and a page per feature

## Delivery

- Owner: TBD
- Priority: High (inferred)
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 2 — Pages for that domain

---

# Task 3 — Every folder in the Explorer opens a docs page

**Satisfies:** R-7, R-6.

## User story

As Marcus, I want every folder I click in the Explorer to open a docs page listing the
features that use its files, so that I never get dropped onto GitHub when I want to know what
a folder is for.

## Context

Today a folder without its own page links out to GitHub (PLAN_deprecated.md). Under the
feature tree no folder gets its own page; a folder's files can belong to several features
(PLAN.md, Decided).

## Scope

In scope:
- A generated docs page per rox-core folder, listing every feature page that covers files in
  it.
- An uncovered-files page listing files no feature covers.
- A line on the root page saying tests and migrations are not documented.

Out of scope:
- Writing feature content (Task 5).
- File-level links: clicking a file may still show its source.
- Pages per folder with their own diagrams (PLAN.md, Out of scope).

## Requirements

- Every folder in the Explorer links to its folder docs page, never to GitHub.
- A folder docs page lists every feature page covering files in that folder.
- A folder with uncovered files links to the uncovered-files page.
- The uncovered-files page lists every in-scope file on no feature page.
- The root page states that tests and migrations are not covered.
- Conformance tests for R-6 and R-7 are drafted for Marcus to accept.

## Acceptance criteria

- Given a folder whose files belong to two features, when the reader clicks it, then a docs
  page opens linking to both features, with no GitHub link on it.
- Given a folder whose files no feature covers, when the reader clicks it, then its docs page
  points to the uncovered-files page.
- Given a feature map with an uncovered file, when the site is built, then that file is on the
  uncovered-files page.
- Given the root page, when it opens, then it says tests and migrations are not covered.
- Given the built site, when every Explorer folder link is checked, then none points to GitHub.
- Given the drafted `test_r6_*` and `test_r7_*` conformance tests, when Marcus accepts them,
  then they are committed and pass.
- Errors and edge cases: a folder that holds only tests or migrations opens a docs page saying
  it is not documented, rather than a broken link.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean) — for R-6, on the
  Sequences & outreach domain; full coverage lands in Task 6.
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the site builds locally from the pinned commit.
- No unresolved critical defects remain.

## Dependencies and constraints

- Needs Task 1's feature map for file → feature assignment and the uncovered list.
- Needs Task 2's multi-path feature pages and tree.
- Depends on: Tasks 1, 2 (Wave 2). Unblocks Task 5.

## Proof of value

**Discharges:** Plan → Decided — "Clicking a folder opens a docs page listing the feature pages
that cover its files, never GitHub."

**Claim:** If every acceptance criterion of this task holds, then clicking any Explorer folder
opens docs listing the features that cover it, and never GitHub.

**Premises:**
1. No Explorer folder link points to GitHub — source: this task's Acceptance criteria.
2. A folder's docs page links to every feature covering its files — source: this task's
   Acceptance criteria.
3. A folder with no covered files points to the uncovered-files page or says it is not
   documented — source: this task's Acceptance criteria.

**Argument:**
1. Every folder either has covered files, or has none.
2. With covered files, Premise 2 gives a page listing their features.
3. With none, Premise 3 gives a docs page instead of a dead end.
4. From Premise 1, neither case opens GitHub.
5. Therefore the claim holds for every folder.

**Attempted counterexample:** A folder added since the feature map was built. It appears in the
Explorer but not in the map. Premise 3 still applies, since none of its files is covered, so
it opens a docs page; no case found where the criteria hold and the claim fails.

**Falsifier:** Marcus clicks a folder and the listed features don't explain it, for example
because one feature owns 1 of its 40 files and the rest are uncovered.

**Verdict:** Proved.

## References

- Design: PLAN.md — Decided, Out of scope
- Technical specification: SPEC.md — R-6, R-7
- Related issues: Task 1 — Sequences & outreach code is grouped into features, with evidence;
  Task 2 — The left panel navigates a root → domain → feature tree

## Delivery

- Owner: TBD
- Priority: High (inferred)
- Estimate: TBD
- Sprint: TBD
- Parent epic: Next step 2 — Pages for that domain

---

# Task 4 — The Notion panel is removed from every page

**Satisfies:** R-3 (retired by Marcus; this task removes the code and test behind it).

## User story

As Marcus, I want the Notion and Slack panel gone from every page, so that pages carry only
code-cited content and nobody keeps hand-picking Notion links.

## Context

Automatic Notion lookup was dropped and `R-3` retired (PLAN.md, Decided; SPEC.md). The
right-hand context panel, the page model's Notion field, the root's five hand-picked Notion
titles and the R-3 conformance test still exist.

## Scope

In scope:
- Removing the right-hand panel from the page layout.
- Removing Notion entries from the page model and the root page's authoring script.
- Removing `tests/conformance/test_r3_context.py`, as `R-3` is retired.
- Removing Notion steps from the generate-rox-docs skill.

Out of scope:
- Notion as a citation source under `R-4`, which stays verbatim.
- Any other page section.

## Requirements

- No page has a right-hand Notion or Slack panel.
- Page models have no Notion field, and a model that still has one fails validation.
- The root page regenerates without its Notion entries and is otherwise unchanged.
- The R-3 conformance test is gone; the rest of the conformance suite is unchanged.
- generate-rox-docs no longer mentions Notion context.

## Acceptance criteria

- Given any built page, when it opens, then there is no Notion or Slack panel.
- Given a page model with a Notion field, when it is checked, then validation fails naming the
  field.
- Given the root authoring script, when it regenerates, then the JSON differs from the
  current one only by the removed Notion entries.
- Given the conformance suite, when it is diffed against `main`, then the only change is the
  deleted R-3 test.
- Given the generate-rox-docs skill, when it is searched for "Notion", then nothing is found.
- Errors and edge cases: a citation whose source is a Notion page still renders and passes
  `R-4`, because only the panel is retired.

## Definition of Done

- All acceptance criteria pass.
- The conformance table shows `R-3` retired with no test, and the rest of the conformance
  suite is unchanged (`git diff --exit-code` over it is clean apart from the deleted R-3
  test).
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the site builds locally from the pinned commit.
- No unresolved critical defects remain.

## Dependencies and constraints

- Deleting the R-3 conformance test is allowed only because Marcus retired `R-3`.
- Depends on: none (Wave 1). Unblocks Task 5.

## Proof of value

**Discharges:** Plan → Decided — "No Notion on pages (SPEC `R-3` retired)."

**Claim:** If every acceptance criterion of this task holds, then no page shows Notion content.

**Premises:**
1. No built page has a Notion or Slack panel — source: this task's Acceptance criteria.
2. A page model with a Notion field fails validation — source: this task's Acceptance
   criteria.
3. generate-rox-docs no longer asks for Notion context — source: this task's Acceptance
   criteria.

**Argument:**
1. From Premise 1, current pages show none.
2. From Premise 2, no future page model can carry Notion entries.
3. From Premise 3, the procedure no longer produces them.
4. Therefore no page shows Notion content.

**Attempted counterexample:** A TLDR claim cited to a Notion page. It shows a Notion link as a
citation, not as context, which `R-4` still allows and the plan doesn't forbid. No case found
where the criteria hold and a Notion context panel appears.

**Falsifier:** Marcus wants Notion citations gone too; the plan's decision would then need
widening.

**Verdict:** Proved.

## References

- Design: PLAN.md — Decided, Out of scope
- Technical specification: SPEC.md — R-3 (retired), R-4
- Related issues: Task 5 — Sequences & outreach has a domain page and a page per feature

## Delivery

- Owner: TBD
- Priority: Medium (inferred: a decision, not a next step)
- Estimate: TBD
- Sprint: TBD
- Parent epic: Decided — No Notion on pages

---

# Task 5 — Sequences & outreach has a domain page and a page per feature

**Satisfies:** R-5, R-9, R-2, R-4.

## User story

As Marcus, I want a Sequences & outreach domain page and one page per feature that shows the
feature end to end, so that I can see what each feature stores and how it runs without reading
the code.

## Context

This is the first time the existing page and diagram skills run below the root (PLAN.md,
Decided: skills unchanged). Its falsifier is whether Marcus can tell from a feature page what
it stores and how it runs (PLAN.md, Next step 2).

## Scope

In scope:
- One domain page and one page per feature from Task 1's accepted map, authored with
  generate-rox-docs and the four diagram skills.
- A "why these files are one feature" section on each feature page, built from the feature
  map's cited tables and calls.
- Deciding with Marcus when a feature is a leaf.
- Linking the domain from the root's left panel.

Out of scope:
- Changing the diagram skills (PLAN.md, Decided).
- Other domains (Task 6).
- Notion context (Task 4).

## Requirements

- Each page has every R-2 section in order, and an empty section says so.
- Every claim, box, arrow, step, transition and relationship is cited at the pinned commit.
- Each leaf feature page shows every part of its feature that exists: HTTP routes, business
  logic, background workers, web screens and tables.
- Each feature page shows the cited tables and calls its files share.
- Diagrams taken from rox-core docs are checked against code first (PLAN.md, Constraint 2).
- No block figure has more than five layout problems (PLAN.md, Constraint 4).
- Each page is regenerated by its own authoring script, byte for byte.
- Conformance tests for R-9 and R-5's leaf scenario are drafted for Marcus to accept.

## Acceptance criteria

- Given each new page, when it opens offline, then every R-2 section is present in order and
  every diagram renders.
- Given each new page, when it is built, then the citation check passes with no uncited or
  stale element.
- Given a leaf feature page, when it opens, then its routes, logic, workers, screens and tables
  appear on it, or the page says which of them the feature has none of.
- Given a feature page, when it opens, then a section shows the shared tables and calls, each
  linked to code.
- Given each block figure, when it is built, then it reports at most five layout problems.
- Given each authoring script, when it is rerun, then its page JSON is byte-identical.
- Given the pages, when Marcus reads a feature page, then he can say what it stores and how it
  runs, and spot checks against the code find no contradiction.
- Given the drafted `test_r9_*` and R-5 leaf tests, when Marcus accepts them, then they are
  committed and pass.
- Errors and edge cases: a feature with no background worker or no web screen shows that
  section present and saying so, rather than omitting it.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean).
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the site builds locally from the pinned commit.
- No unresolved critical defects remain.

## Dependencies and constraints

- Blocking open question (PLAN.md, Open): when a feature is a leaf; decided with Marcus here.
- Needs Task 1's accepted feature map, Task 2's tree, Task 3's folder pages and Task 4's
  layout without the Notion panel.
- Depends on: Tasks 1, 2, 3, 4 (Wave 3). Unblocks Tasks 6 and 7.

## Proof of value

**Discharges:** Plan → Next step 2 — falsifier "Marcus can't tell from a feature page what it
stores and how it runs, or a spot check contradicts the code."

**Claim:** If every acceptance criterion of this task holds, then neither half of the falsifier
fires.

**Premises:**
1. Marcus reads a feature page and can say what it stores and how it runs — source: this
   task's Acceptance criteria.
2. Spot checks against the code find no contradiction — source: this task's Acceptance
   criteria.
3. Every element is cited and the citation check passes — source: this task's Acceptance
   criteria.

**Argument:**
1. From Premise 1, the first half of the falsifier does not fire.
2. From Premise 2, the second half does not fire on the spot-checked elements.
3. From Premise 3, every element not spot-checked still points at real code at the pinned
   commit.
4. Therefore neither half of the falsifier fires.

**Attempted counterexample:** A cited arrow whose line exists but says something else, on a page
Marcus didn't spot-check. Premise 3 holds, since the line exists, and the second half of the
falsifier fires. The citation check catches missing lines, not misread ones. Spot checks
bound this risk without removing it; not exhaustively searched.

**Falsifier:** A later reader finds a cited claim that its cited line doesn't support.

**Verdict:** Conditional on spot checks being representative of the pages; the risk is echoed
here: spot checks sample, they don't prove every element.

## References

- Design: PLAN.md — Next step 2, Constraints 2 and 4, Decided
- Technical specification: SPEC.md — R-2, R-4, R-5, R-9
- Related issues: Task 1; Task 2; Task 3; Task 4; Task 6 — Every remaining domain has a
  feature map and pages; Task 7 — One unattended daily run rebuilds the site as a rox-dox PR

## Delivery

- Owner: TBD
- Priority: High (inferred)
- Estimate: about 1 session (PLAN.md, Next step 2, which this task completes with Tasks 2–3)
- Sprint: TBD
- Parent epic: Next step 2 — Pages for that domain

---

# Task 6 — Every remaining domain has a feature map and pages

**Satisfies:** R-5, R-6, R-9, R-2, R-4.

## User story

As Marcus, I want every domain grouped into features and documented the way Sequences &
outreach is, so that I can find any part of rox-core from the root.

## Context

Task 5 proves the procedure on one domain. This task applies it to every other domain the root shows,
however many there are (PLAN.md, Next step 3), and decides where code that touches no table goes.

## Scope

In scope:
- Feature maps (Task 1's command) for every other domain, each reviewed by Marcus.
- Domain and feature pages for each, authored as in Task 5.
- A home for code that touches no table, if Task 1 shows there is enough of it.

Out of scope:
- The scheduled run (Task 7).
- New diagram rules (PLAN.md, Decided).

## Requirements

- The set of domain pages is read from the root's domain grouping at the documented commit,
  never from a fixed list or count.
- Every domain has an accepted feature map and pages meeting Task 5's requirements.
- Every in-scope rox-core file is on a feature page or on the uncovered-files page.
- Code that touches no table has a decided home, reviewed by Marcus.

## Acceptance criteria

- Given each remaining domain, when its feature map is reviewed, then Marcus accepts it.
- Given a root grouping with one domain added or removed, when the site is rebuilt, then
  there is exactly one domain page per domain the root shows.
- Given each new page, when it is built, then it meets every acceptance criterion of Task 5.
- Given the whole site, when every in-scope file is checked, then each one is on a feature
  page or on the uncovered-files page.
- Given code that touches no table, when the site is built, then it sits where Marcus decided,
  or on the uncovered-files page.
- Errors and edge cases: a file claimed by features in two domains appears on both, and the
  build does not count it twice toward coverage.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean).
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, and the site builds locally from the pinned commit.
- No unresolved critical defects remain.

## Dependencies and constraints

- Blocking open question (PLAN.md, Open): where code that touches no table goes.
- Open (PLAN.md): whether shared code gets its own page.
- Assumption carried from the Proof of value: Marcus's spot checks are representative, as in
  Task 5.
- Likely an epic of its own: one task per domain if it is split further.
- Depends on: Task 5 (Wave 4).

## Proof of value

**Discharges:** Plan → Objective — "open the rox-core root, click a domain, then a feature, and
see that feature end to end".

**Claim:** If every acceptance criterion of this task holds, then every domain's features are
reachable from the root and documented end to end.

**Premises:**
1. Every domain has pages meeting Task 5's acceptance criteria — source: this task's
   Acceptance criteria.
2. Every in-scope file is on a feature page or on the uncovered-files page — source: this
   task's Acceptance criteria.
3. Task 5's proof is Conditional on representative spot checks — source: Proof of Task 5.

**Argument:**
1. From Premise 1 and Task 2, every domain's features are in the tree under the root.
2. From Premise 2, no in-scope file is missing from the site.
3. From Premise 3, the end-to-end accuracy of each page is as strong as Task 5's.
4. Therefore the objective holds for every domain, at Task 5's strength.

**Attempted counterexample:** A large share of rox-core lands on the uncovered-files page.
Premise 2 holds, but the objective fails for that code. Marcus's review of each feature map and
the decided home for table-less code are what catch this.

**Falsifier:** The uncovered-files page grows large across runs as rox-core adds code.

**Verdict:** Conditional on representative spot checks (inherited from Task 5), echoed in
Dependencies and constraints.

## References

- Design: PLAN.md — Next step 3, Open
- Technical specification: SPEC.md — R-2, R-4, R-5, R-6, R-9
- Related issues: Task 1; Task 5; Task 7 — One unattended daily run rebuilds the site as a
  rox-dox PR

## Delivery

- Owner: TBD
- Priority: Medium (inferred)
- Estimate: TBD (PLAN.md gives 1–2 sessions for Next step 3 as a whole)
- Sprint: TBD
- Parent epic: Next step 3 — Every domain plus the scheduled run

---

# Task 7 — One unattended daily run rebuilds the site as a rox-dox PR

**Satisfies:** R-8.

## User story

As a daily scheduled Devin run, I want one command and one written procedure that rebuild the
feature maps and every page at the latest rox-core `main` and open a rox-dox PR from a new
branch, so that Marcus gets up-to-date docs without asking.

## Context

Every run rebuilds everything from scratch; there is no change detection (PLAN.md, Decided,
Figure 2). Marcus asked for the output as a PR from a new branch (SPEC.md, R-8).

## Scope

In scope:
- One command that rebuilds the feature maps, runs every page's authoring step, and builds the
  site at one named rox-core commit.
- A skill that tells the scheduled run how to rewrite pages whose cited code changed, using
  generate-rox-docs.
- A schedule that runs it daily at 00:00 UTC and opens a rox-dox PR from a new branch.
- No PR when any page fails, with the failing pages named.

Out of scope:
- Regenerating only changed pages (PLAN.md, Out of scope).
- Running per rox-core PR (PLAN.md, Out of scope).
- Merging the PR, which stays Marcus's.

## Requirements

- A run pins one rox-core commit, the latest `main` at its start, and every page names it.
- A successful run opens one rox-dox PR from a new branch carrying the rebuilt site.
- A run with any failing page opens no PR and reports every failing page.
- The schedule runs daily at 00:00 UTC with no human step before the PR.
- Conformance tests for R-8 are drafted for Marcus to accept.

## Acceptance criteria

- Given the latest rox-core `main`, when a run finishes, then a new rox-dox PR exists from a new
  branch and every page in it names the same commit.
- Given a run in which one page fails its build, when it ends, then no PR is opened and the
  failing page is named.
- Given the schedule, when 00:00 UTC passes, then a run starts and finishes with no human step.
- Given the drafted `test_r8_*` conformance tests, when Marcus accepts them, then they are
  committed and pass.
- Errors and edge cases: a stale citation after rox-core changes is rewritten from the new code
  by the run, or the page fails and is named, never published stale.

## Definition of Done

- All acceptance criteria pass.
- Every requirement in `Satisfies` is ✅ in the spec's conformance table, with the
  conformance suite unchanged (`git diff --exit-code` over it is clean).
- Code is reviewed and merged.
- Appropriate automated and manual tests pass.
- Accessibility, security, and performance requirements are met.
- Documentation, analytics, and release notes are updated where applicable.
- The change is merged to rox-dox `main`, the daily schedule is active, and its first run has
  opened a rox-dox PR.
- No unresolved critical defects remain.

## Dependencies and constraints

- The run pushes to marcus-rox/rox-dox with the repo's personal token, since the org GitHub
  integration can't reach it.
- Assumption carried from the Proof of value: an agent-written page that passes the build is
  correct as often as a Task 5 page, with no spot check per run.
- Depends on: Task 5 (Wave 4).

## Proof of value

**Discharges:** Plan → Next step 3 — falsifier "an unattended run fails, or spot-checked pages
are wrong."

**Claim:** If every acceptance criterion of this task holds, then unattended runs succeed and
publish only pages that passed their build.

**Premises:**
1. A daily run starts and finishes with no human step — source: this task's Acceptance
   criteria.
2. A run with a failing page opens no PR and names the page — source: this task's Acceptance
   criteria.
3. Pages that pass the build are as accurate as Task 5's — source: Assumption (unverified).

**Argument:**
1. From Premise 1, the "unattended run fails" half does not fire on a healthy run.
2. From Premise 2, a failing run publishes nothing wrong and says why.
3. From Premise 3, spot checks of a published PR should find pages as accurate as Task 5's.
4. Therefore the falsifier fires only if Premise 3 is false.

**Attempted counterexample:** rox-core renames a service; the run rewrites a figure with the new
name but keeps an arrow whose cited line still exists with a changed meaning. The build passes
and the page is wrong, which is why Premise 3 is an assumption.

**Falsifier:** Marcus spot-checks a run's PR and finds pages wrong.

**Verdict:** Conditional on Premise 3, echoed in Dependencies and constraints.

## References

- Design: PLAN.md — Next step 3, Decided, Figure 2
- Technical specification: SPEC.md — R-8
- Related issues: Task 5; Task 6 — Every remaining domain has a feature map and pages

## Delivery

- Owner: TBD
- Priority: Medium (inferred)
- Estimate: TBD (PLAN.md gives 1–2 sessions for Next step 3 as a whole)
- Sprint: TBD
- Parent epic: Next step 3 — Every domain plus the scheduled run
