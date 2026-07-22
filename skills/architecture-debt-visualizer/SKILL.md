---
name: architecture-debt-visualizer
description: "Reconcile a repo's design docs against its actual code AND evaluate the architecture itself like a senior/staff architect — scalability, extensibility, long-term maintainability, performance/operational cost, data/entity-model soundness, and whether the implementation still serves the product's stated technical vision. Produces a color-coded visual report. Use when the user asks to check if docs are stale, find architecture drift, audit docs vs. code, evaluate technical architecture, review data model / entity design, assess scalability or tech debt, or run an 'architecture debt' / 'architecture review' report. Triggers on phrases like 'check if our docs are still accurate', 'find architecture drift', 'evaluate our architecture', 'review the data model', 'is this scalable', 'architecture debt visualizer'."
argument-hint: "[path to docs folder, default: docs/]"
---

# Architecture Debt Visualizer: Docs vs. Code Reconciliation + Architectural Evaluation

Two jobs, not one:

1. **Reconciliation** — does the code still do what the docs say it does? (textual accuracy)
2. **Evaluation** — judging as a senior architect would, is the *architecture itself* sound, and
   does it still serve where the product is actually headed? (engineering judgment)

Job 1 catches drift. Job 2 catches debt that was never wrong on paper because no doc ever made a
claim about it — a scaling ceiling nobody wrote down, a data model that will not survive the next
6 months of growth, a governance gap, an entity design decision nobody revisited after the
business model changed. **Both are mandatory for every run.** A report that only reconciles text
and never passes judgment is doing half the job.

**Act as an independent evaluator, not a transcription service.** Job 2 does not wait for a doc
claim to react to, and it does not defer to what the docs (or the team) believe about their own
system. Form your own judgment from the code, the schema, and the metrics actually emitted, the
same way an outside architect brought in to assess the system would — cross-checking what's
claimed against what's true, and willing to say a pattern is bad even when nobody ever wrote a doc
claiming it was good. A `confirmed` reconciliation result (doc and code agree) does not make a bad
pattern acceptable — agreement is a statement about honesty, not about quality. Judge quality
separately, on its own merits, in job 2.

Point this at a repo's docs folder (default: every `docs/` folder in the repo — see step 1) and
its source tree.

## Mindset for the evaluation pass (job 2)

Read every architectural decision the way an experienced staff/principal architect reviewing a
system they're about to inherit would — not "does this technically work" but "will this still be
a good decision in two years, at 10x the data, with a bigger team touching it." Concretely, for
every significant component/pattern/decision you encounter, ask:

- **Scalability** — what's the ceiling? Fixed thread/worker/concurrency counts, single-instance
  assumptions, hardcoded horizons (a date range, a partition list, a capacity number), anything
  that degrades silently rather than failing loudly as load grows. "Works fine today" is not the
  same question as "what breaks first as this scales, and when."
- **Extensibility** — how much does it cost to add the next tenant / consumer / calculator /
  fee type? Count the files a change like that actually touches (the repo's own "How to: Add X"
  pattern docs, if present, are strong signal here — read them and check the described steps
  against reality). Inconsistent patterns for conceptually-identical things (two different ways to
  model "an extra line item on an order," some jobs following a base class and others not) are an
  extensibility tax paid on every future addition, not just an aesthetic complaint.
- **Long-term maintainability** — duplication instead of abstraction, mixed conventions doing the
  same job two ways (two cron syntaxes, two error-handling styles), tech debt the team has already
  flagged in comments/docs but not fixed, anything that makes onboarding or debugging harder than
  it needs to be.
- **Performance / operational cost** — expensive external calls (data-warehouse queries, third-
  party APIs) with no visible cost guardrail, missing caching/indexing where access patterns
  clearly demand it, and governance gaps (tests/lint/coverage tooling that exists but isn't
  enforced anywhere).
- **Observability / golden signals** — its own deliberate pass, not a footnote under performance.
  For every critical logic path (the ones on the money/data-integrity critical path, the highest-
  churn packages, anything a "drop and recover later" pattern depends on), check for the four
  golden signals — **traffic**, **errors**, **latency**, **saturation** — separately, because teams
  routinely nail 2 of 4 and never notice the other 2 are missing:
  - Traffic/errors are usually the easiest and most commonly present (request/message counters,
    success/failure counters) — verify they exist, but don't stop here.
  - Latency: is there an actual duration/histogram/timer on the critical step, or only counters?
    Counting requests tells you nothing about a path getting slower.
  - Saturation: is there a signal for "this is falling behind" — queue/consumer lag, thread-pool
    utilization, worker backlog — distinct from a plain throughput counter?
  - **The metric that actually matters is often not the one that exists.** A component can be
    heavily instrumented (many counters, many histograms) and still be missing the *one* signal
    that would tell an operator the specific failure mode they care about is happening — e.g. a
    system that deliberately drops-and-recovers-later needs a metric on recovery completeness
    (how much of what was dropped actually got recovered, and what's still outstanding), not just
    a drop counter. A drop counter alone says "sometimes we lose messages," which the team already
    knows and accepted — it doesn't say whether the safety net is actually catching them. Go find
    the code path that's supposed to be the safety net and check whether its *outcome* is a metric
    or just a log line — text logs are not a golden signal; nobody alerts on log volume by default,
    and a "processed N rows" log line is not the same as a Prometheus gauge tracking backlog size.
  - Also check where instrumentation exists but is dormant — a well-built metric on a code path
    that's disabled by default, while the currently-live path has weaker coverage, is a real gap
    dressed up as a non-issue.
- **Data architecture / entity design** — this needs its own deliberate pass, not a byproduct of
  reading prose. Go read the actual DDL/schema (not just a doc's description of it) and the ORM
  mapping code, and evaluate:
  - Does the ORM's notion of entity identity (e.g. a single-column `@Id`) match the real primary
    key in the DDL (composite/partitioned)? A mismatch here is a correctness landmine (identity/
    equality/caching bugs), not a style nit.
  - Wide, flat tables that should be normalized into child entities (compare against a sibling
    table that already got this right, if one exists) — every new attribute becoming a new column
    is an extensibility cost that compounds.
  - Shadow/parallel representations of the same conceptual entity (e.g. a JSON blob variant living
    alongside the normal columnar table) — these create query/analytics blind spots and drift risk
    over time.
  - Referential integrity strategy: are relationships enforced by real FKs, or app-level only? Is
    that a deliberate, documented scaling tradeoff, or just an accident of how each table happened
    to get written? Check consistently across the schema, not just one table.
  - Partitioning/sharding strategy: is it automated, or hardcoded to a horizon that will run out?
    Grep for the actual maintenance job before assuming one exists.
  - Precision/typing choices for money/quantities (decimal vs float, currency handling) — credit
    correct choices, flag incorrect ones.
  - **Extensibility of the table designs themselves, read against the product's own stated future**
    (not just against current use). A schema is not evaluated in a vacuum — cross-reference it
    against whatever the docs/vision/roadmap already say is coming (new tenants, new business
    models, new fee/adjustment types, planned future entities sketched in a diagram). For the
    highest-traffic/most-central tables: read the actual column list and look for evidence of *how*
    the table has grown historically — naming-convention drift between column batches, clusters of
    near-duplicate columns (e.g. many variants of the same concept for slightly different
    jurisdictions/rules), and ad hoc schemaless escape valves (a JSON/blob column bolted on because
    the rigid shape couldn't express something) are all direct historical evidence of *how well the
    current shape has actually scaled to new requirements* — better evidence than guessing forward.
    If the product vision already names a future requirement (a new tenant, a new adjustment
    mechanism), check whether the schema has a designed extension point for it or whether it will
    predictably repeat whatever ad hoc pattern the column history already shows. Credit forward-
    looking design intent that breaks the bad pattern (e.g. a *planned* entity in a diagram that's
    correctly modeled as its own table rather than more columns) — but note when it's unbuilt intent
    only, and weigh that against the team's actual track record on the same kind of decision.
- **Vision alignment** — locate whatever the repo treats as its source of product/technical intent
  (a `technical-vision.md`, ADRs, a roadmap doc, a strategy section in the main README). If it
  exists, check whether current architecture decisions actually serve it, or have drifted from it.
  **If it's missing, empty, or pure scaffolding (template headers with no real content filled in),
  that absence is itself a finding** — a system past a certain size or criticality operating
  without any written technical vision has no anchor for judging whether new work is on-strategy,
  and that's a real risk worth surfacing, not a non-finding.

**Credit strengths, not just debt.** An architect who only ever reports problems isn't giving a
useful review. When a pattern is genuinely well-designed (a clean extension point, a reader/writer
split that matches the actual access pattern, a shared calculation module used by two otherwise-
divergent code paths so a fix lands once) — say so explicitly as a `strength` finding. It tells
future maintainers what to preserve, and it's the honest baseline for judging what *should* look
like that but doesn't.

## Critical rules

- **Every finding needs cited evidence.** A classification without a `file:line` (or explicit
  "searched X, Y, Z and found nothing" for a Gap/Risk) is not a finding — go verify it or drop it.
- **Verify data-architecture claims against the actual DDL/schema files, not a doc's prose
  description of them.** A doc's own claim about its schema is exactly the kind of thing this
  skill exists to check — don't cite it as its own evidence.
- **Don't invent claims the doc doesn't make**, and don't invent architectural risk where none
  exists — every `risk` finding needs the same evidence bar as a `misaligned` finding. Speculation
  ("this might not scale") isn't a finding; a concrete mechanism ("fixed worker-count=1 with no
  documented horizontal-scaling path, and no distributed locking if that assumption ever breaks")
  is.
- **A Gap is architecturally significant code with no doc mention** (a whole consumer, a whole
  external integration, a call path that crosses a boundary) — not every undocumented private
  method. Use judgment; low-value gaps drown the signal.
- **Static-analysis signals (churn, dependency graph) are for prioritization only.** They never
  produce a finding by themselves — they help you decide which findings to spend more time
  verifying and which to surface first in the summary. Churn is also a scalability/maintainability
  signal in its own right: a high-churn package with fragile patterns (duplicated logic, no tests)
  is a materially higher-priority risk than the same pattern in dead code.
- Scripts in `scripts/` are deterministic helpers (no LLM judgment) — run them, don't reimplement
  their logic by hand.

## Workflow

### 1. Locate the docs

Default scope: **every** `docs/` folder in the repo, not just the top-level one — a repo with
multiple deployables/modules (e.g. a monorepo with `modules/<name>/docs/`) typically has one docs
tree per component, and each one can drift independently. Find them all:

```
find . -type d -iname docs -not -path "*/node_modules/*" -not -path "*/build/*" -not -path "*/.git/*"
```

Read every `.md` file recursively under each discovered `docs/` folder, plus `README.md` at repo
root and any `*/README*.md` one level down. **Also read non-Markdown diagram sources in those
folders** — `.mmd` (Mermaid) files diff and grep cleanly, so treat them as first-class claim
sources; render/view any `.png`/`.svg`/`.excalidraw` diagrams too (the Read tool handles images
directly). If a doc states which artifact is the source of truth when diagrams disagree (Mermaid
vs. a frozen PNG export, for instance), trust that doc's stated policy — but still check the two
actually agree, because "we said the PNG shouldn't go stale" is not the same as "it hasn't."

If the user names specific doc file(s) or a narrower path, use those instead — don't silently
expand scope in that case. Note that this restriction applies to which docs are treated as
**reconciliation sources** (steps 1-2: what claims get extracted and checked). It does not limit
step 5's evaluation pass — that pass is fundamentally a code/config/git investigation, not a
doc-reading exercise, and techniques like "find the vision doc" or "check the pattern docs' adoption
rate" still apply and may reference docs outside the user's named scope, since the evaluation pass
isn't answering "does this named doc match the code," it's answering "is the architecture sound."

Read every doc in scope. Note the ones that look auto-generated or recently touched (e.g.
frontmatter like `last-generated:`) — those are more likely to still be accurate, which is itself
useful context when you explain a finding.

### 2. Extract checkable claims (for reconciliation)

For each doc, pull out concrete, falsifiable architectural claims. Good claims name specific
components and a specific relationship or behavior:

- "Service A must not call Service B directly" (boundary claim)
- "All payment writes go through the ledger service" (data-flow claim)
- "The `PaymentEventConsumer` failures are dropped, not sent to a DLQ" (behavioral claim)
- "No gRPC server exists despite the generated protos" (negative/absence claim)
- "`OrderResource` handles `/api/v1/orders/calculate`" (routing claim)

Skip claims that are subjective, aspirational without a concrete referent, or already phrased as
open questions (docs sometimes literally write `(?)` — that's the doc admitting uncertainty, not
a claim to verify).

Keep a running list with: claim text, source doc, and location (line number or heading).

### 3. Build the deterministic signals

**First, make a unique run directory — do not reuse a fixed literal path like `/tmp/adv_findings.json`
across invocations.** Two runs (a re-run, a parallel/nested agent, a different repo in the same
session) sharing the same hardcoded path will silently clobber each other's intermediate files —
this has actually happened in testing. Use the session's scratchpad directory if one is available,
otherwise `mktemp -d`:

```
mktemp -d /tmp/adv-XXXXXX
```

**Take the literal directory path that command prints and use that literal string in every command
below — don't rely on a `$RUN_DIR` shell variable persisting across separate tool calls.** Some
harnesses start a fresh shell per command, so a variable set in one call is gone by the next; a
literal path (e.g. `/tmp/adv-jIwu68/dep_graph.json`) always works regardless. (`$RUN_DIR` is used
in this doc's examples below purely for readability — substitute your actual resolved path.)

Use that directory for every intermediate path in the steps below (dep graph, churn, findings.json,
report). Run once per invocation, from the repo root:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_dep_graph.py \
  --src src/main/java --out "$RUN_DIR/dep_graph.json"
```

(Add one `--src` per source root if the repo has more than one module, e.g. a second
`--src modules/<other-module>/src/main/java`. If the codebase isn't Java, see "Non-Java repos"
below before running this.)

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compute_churn.py \
  --since "180 days ago" --out "$RUN_DIR/churn.json"
```

These give you a package-level import graph (who depends on whom) and a churn signal (which
files/packages change often, and by how many distinct people — `compute_churn.py` tracks author
diversity per package alongside raw commit counts, and precomputes `bus_factor_hotspots`
(high-churn, single-author) and `high_diversity_hotspots` (high-churn, many authors) lists). Use
them to:
- Sanity-check boundary claims quickly (does the dep graph actually show an edge the doc says
  shouldn't exist?).
- Prioritize which packages deserve close manual reading for Gaps and architectural risks (high
  churn + high class count + central in the graph = worth checking even if the doc says nothing).
- Spot maintainability red flags directly: a package with unusually high fan-in/fan-out relative to
  its size is a coupling risk worth a closer look regardless of what any doc claims.
- Spot bus-factor risk: a high-churn package with exactly one author is a knowledge-concentration
  risk on its own, and a genuinely serious one when it coincides with high complexity or a
  currently-dormant feature (disabled-by-default code gets no incidental review/exposure from
  normal operation, so single-author dormant complexity compounds). Conversely, don't assume a
  high distinct-author-count package has healthy shared ownership without checking the actual
  split — one dominant contributor can still show up as "top author" across most of the repo's
  high-diversity list, which means true distributed knowledge is rarer than the raw count implies.
  Sanity-check this with `git log --since=... --no-merges --pretty=format:%an | sort | uniq -c` to
  rule out merge-commit attribution skewing the picture before citing it as evidence.

They are a starting point, not proof — always confirm with an actual grep/read before citing
`file:line` evidence, since the graph only captures import-level coupling, not call semantics.

### 4. Reconciliation pass — verify each claim against the code

For each claim, search the codebase (Grep/Glob/Read — whatever's fastest) for the components it
names. Confirm or contradict it with actual file/line evidence. Classify:

- **Confirmed** — code matches the claim. Cite the evidence that confirms it (don't skip this just
  because it's a positive result).
- **Misaligned** — code contradicts the claim. Cite evidence from both sides: what the doc says
  (with location) and what the code actually does (with file:line).
- **Gap** — code does something architecturally significant the doc never mentions. Cite the code
  evidence and note where in the doc you'd expect it to be mentioned (or that the doc has no
  relevant section at all).

While verifying named claims, also scan (using the dep graph / churn output from step 3 as a
guide) for undocumented architecturally-significant elements — a whole consumer, an external
client, a queue, a cross-boundary call path — and log those as additional Gap findings even though
no doc claim prompted them.

### 5. Architectural evaluation pass — judge the architecture itself

This is a **separate, mandatory pass**, not something you do opportunistically while reconciling.

**Calibration — a fixed rubric, not an open-ended target.** Run-to-run variance in this skill's
output has been measured and was too wide when this pass was governed by an open-ended target
("15-25+ findings, keep digging until it feels thorough") — different runs against the *identical*
scope produced anywhere from 11 to 28 total findings, because "thorough" was left to each run's own
judgment about when to stop. Replace that judgment call with a fixed rubric, applied identically
every time:

**For each of the 7 dimensions below: produce a minimum of 2 evaluation findings, and a maximum
equal to that dimension's number of lettered mandatory sub-checks (never fewer than 5 even if a
dimension has fewer lettered items) — then move to the next dimension.** Data-architecture has 7
lettered sub-checks below, so its cap is 6, not 5 — **do not combine two lettered sub-checks into
one finding to fit a smaller cap; that has already happened once and silently dropped a real
finding (a tenant-readiness check got merged away because 6 items didn't fit a 5-slot cap — now 7
lettered items, cap raised to match).** Every
lettered sub-check gets its own finding-or-explicitly-noted-clean-result, full stop — the cap
exists to bound *extra* digging beyond the mandatory items, never to force the mandatory items
to share slots. Concretely:
- Fewer than 2 after running through that dimension's listed techniques once → you stopped too
  early; go back and apply at least one technique you skipped before concluding "clean." A
  dimension with zero or one finding after genuine effort is a legitimate outcome — state that
  explicitly (e.g. in your summary: "data-architecture: checked X/Y/Z, only 1 finding, rest came
  back clean") — but reach that conclusion by actually running the techniques, not by stopping
  after the first one.
- More than that dimension's cap → stop and move on, even if more findings are available beyond
  the mandatory lettered ones. Log the most significant extras (by severity, then by how central
  the affected code is) up to the cap, and note in your summary that this dimension had more
  findings available than the cap — don't let one target-rich dimension consume the time budget the
  other 6 dimensions need. This ceiling exists specifically to narrow run-to-run variance: a run
  that happens to notice `data-architecture` is unusually rich in issues should not produce 3x the
  findings of a run that spends proportionate time across all 7 — but the cap bounds *extra* depth,
  it never shrinks below the dimension's mandatory lettered-item count.

This yields a **predictable total band of roughly 14-36 evaluation findings** (2 minimum ×
7 dimensions, up to each dimension's lettered-item cap — 7 for data-architecture, 5 for the rest)
regardless of run, replacing the much wider variance an open-ended target produced. This rubric is
scope-independent — it applies whether you're reconciling against 3 docs or 30, because most of
what drives evaluation-pass findings is *code and config investigation*, not how many docs you
read.

**This calibration applies to `strength` findings too, and past runs have skewed away from them —
watch for this specifically.** It's easy to read "find 15-25+ findings" as "find 15-25+ problems"
and put all the digging effort into risk-hunting while treating strengths as a bonus you note only
if one falls in your lap. Don't. A pass that produces 20 risks and 1 strength on a codebase that
also has genuinely well-designed patterns (which most real codebases do — shared calculators,
correct type choices, sound partition keys) isn't more thorough, it's lopsided, and it usually
means two specific things got skipped: (1) actively looking for strengths with the same rigor as
risks — for every dimension, after you've logged the risks, spend one more pass asking "what did
this codebase get *right* here that's worth crediting" before moving on; (2) reading the sections
of the docs that are dense with forward-looking or design-rationale content (a deep-dive doc's
"known gaps / forward-looking work" section, a conventions doc's stated design choices) as closely
as the structural/boundary sections — those are where both strength-credit findings and
vision-readiness findings (does the schema/architecture already anticipate what the doc says is
coming next) tend to live, and they're easy to skim past if you're scanning for problems only.

Work through each dimension deliberately, and for each one, don't stop at the first technique that
turns up nothing — run through all of them:

**Each lettered sub-check below is mandatory and individually accounted-for — not a menu to pick
from.** Measured failure mode: two parallel runs with identical scope and instructions each
produced 5 data-architecture findings (satisfying the count rubric), but one run spent its 5 slots
on money-type precision *twice* and never ran the naming-convention check at all, while the other
run caught it. The count rubric bounds volume; it does not by itself guarantee the same *content*
gets checked every time — that's what turns "usually finds real things" into "reliably finds the
same class of real things." For every lettered item in every dimension: produce a finding from it,
*or* explicitly note in your own tracking that you ran the check and it came back clean — but do
not skip a lettered item to spend its budget on a second finding from an item you already covered.
If a dimension's cap (5) is smaller than its lettered-item count, prioritize breadth (touch every
letter once) over depth (multiple findings from one letter) unless one letter is clearly empty.

1. **Vision alignment**: 
   (a) find and read the vision/strategy doc(s) — empty/missing is a `risk` finding on its own, but
   that's one letter, not the whole dimension;
   (b) check 2-3 *concrete, currently in-flight or recently-made* architecture decisions (grep
   recent git history / open feature flags / disabled-by-default code for what's actively being
   worked on) against what the vision claims or should claim, and note agreement or drift.
2. **Data architecture** — open the actual schema/DDL/migration files directly, not a doc's
   description of them, for every table connected to the domain's core write-heavy entities:
   (a) identity/PK consistency — does the ORM's `@Id` match the real DDL key?;
   (b) normalization/naming — count the columns; if there are many, categorize them (clusters of
   near-duplicate columns, or a naming-convention shift between column groups, is direct historical
   evidence of ad hoc growth) — run an actual script/grep across all columns for this, don't eyeball
   it, and don't substitute a second finding from a different letter in its place;
   (c) referential-integrity strategy — grep `FOREIGN KEY`/`REFERENCES` across *all* DDL files, not
   just one table's (a rate like "3 of 26 files" is a finding; "this one table has no FK" alone is
   not);
   (d) partitioning/sharding maintenance — grep for the actual maintenance job before assuming
   automation exists; check the partition list's date range against today's date;
   (e) type choices — decimal vs float, currency handling;
   (f) forward-readiness — check the schema against whatever the product vision names as coming
   next (a new tenant, a new business model, a new entity sketched in a diagram);
   (g) shadow/parallel representations — does any table store a JSON-blob or otherwise schemaless
   duplicate of an entity that's normally columnar elsewhere (a "tiered" or "variant" version of a
   core table storing the whole record as one JSON column, for instance)? This creates an
   analytics/query blind spot for whatever subset uses the shadow form, and is easy to miss because
   it doesn't show up under any of (a)-(f) above — it's its own distinct check, not a byproduct of
   normalization or type-choice review.
   Data-architecture's cap is 7, matching these 7 lettered items — do not combine any two into one
   finding to save room.
3. **Scalability & performance/cost**:
   (a) grep config files for *every* hardcoded capacity number (thread/worker/concurrency counts,
   timeouts, batch sizes, partition/date horizons) — don't stop after finding one; list them,
   compare which are env-overridable vs. literal, note which sit on the highest-traffic path;
   (b) for every expensive external call (data-warehouse queries, third-party APIs, anything that
   scales with data scanned), check for a cost/rate guardrail, and compare it against how a
   *similar* endpoint elsewhere in the same codebase is guarded — an inconsistency between two
   structurally similar endpoints is a stronger finding than "there's no rate limit" in isolation.
4. **Extensibility & maintainability**:
   (a) use the repo's own "how to add X" pattern docs (if any) as a test — do the described steps
   still match reality, and how many actual instances of "X" follow the pattern vs. duplicate logic
   inline? Get the exact count (`grep -c` / `grep -l | wc -l`), don't estimate;
   (b) look for the same shape of inconsistency in places with no pattern doc at all — two
   conceptually-identical concerns modeled two structurally different ways elsewhere in the codebase
   is the same finding pattern, just undocumented — actively look for at least one of these beyond
   whatever (a) already covered.
5. **Observability**:
   (a) pick the 2-3 most critical logic paths (highest business impact and/or highest churn — use
   the churn/dep-graph output from step 3, don't guess) and check all four golden signals for each,
   *separately* — explicitly note which of traffic/errors/latency/saturation you found evidence for
   and which you didn't, per path;
   (b) trace whatever code path is responsible for recovering from/reporting on a known failure mode
   (a reconciliation job, a retry sweep, a dead-letter consumer, an "expected vs. actual"
   completeness check) all the way to its output, and check whether that output is a metric
   (gauge/counter you could alert on) or just a log line — this single check has reliably produced
   the highest-value observability finding in past runs; do it every time, not opportunistically.
6. **Maintainability / contributor concentration**:
   (a) use `compute_churn.py`'s `bus_factor_hotspots` and `high_diversity_hotspots` output (already
   computed in step 3 — don't skip re-checking it here) — for any single-author high-churn package,
   cross-reference it against what that code actually does; bus-factor risk on routine CRUD is
   low-priority, bus-factor risk on the most architecturally complex or currently-dormant code is a
   real, specific finding. Sanity-check with `git log --no-merges --pretty=format:%an | sort | uniq
   -c` before citing it, to rule out merge-commit attribution skew;
   (b) check the "how to add X" pattern-doc adoption rate from item 4(a) again here specifically for
   what inconsistent adoption *costs* going forward (a fix/change now has to be replicated N times
   instead of landing once) — this is a distinct finding from 4(a)'s existence-of-inconsistency one.

**Cross-reference every finding you produce against the rest of the docs before moving on** — a
finding is also a lead. If you found an undocumented instance of something (a consumer, an
endpoint, a table), check whether any *other* doc claim assumes a fixed count or a "complete list"
that the new instance now contradicts (e.g. "all six X" becoming wrong the moment you found a
7th X) — this is frequently where the highest-confidence, easiest-to-verify findings come from, and
it's easy to miss if you treat each claim as fully independent. Similarly, if a doc's frontmatter or
body cites a specific file/module path as a source, verify that path actually exists and is
current — `git log --diff-filter=D -- <path>` and checking the actual build/dependency
configuration (`settings.gradle`/`build.gradle`/`package.json`, not the doc's description of it)
for whether that path is still part of the build has repeatedly surfaced the single highest-value
finding in past runs of this skill. Do this check whenever a doc names a specific module as
"shared" or "in-repo" — don't take the doc's word for its own architecture.

Classify each evaluation-pass finding as `risk` (a concern, no accompanying doc claim to be
"misaligned" against) or `strength` (a decision worth crediting), tag it with a `dimension`
(`scalability` / `extensibility` / `maintainability` / `performance-cost` / `data-architecture` /
`observability` / `vision-alignment`) and a `severity` (`info` / `low` / `medium` / `high`), and —
for anything `medium` or higher — write a one- or two-sentence `recommendation`: what an architect
would actually tell the team to do about it. Not "this is a risk" — "here's the next concrete
step."

**Phrasing rule for `claim` — an unresolved positive hypothesis must be visibly marked as one; it
can never stand bare.** For an evaluation-pass finding with no doc quote to react to, there are two
acceptable ways to phrase `claim`, and one unacceptable one:

- **Preferred: state the concern or fact directly**, as a declarative sentence — "Payment-event
  consumer concurrency is hardcoded to 1 with no env override, on the always-enabled revenue path"
  rather than "the payment consumer can absorb load increases without a config change." This is
  usually the clearer choice and matches how a reconciliation finding with a real doc quote reads.
- **Acceptable: phrase it as the hypothesis being tested, but prefix it** with `(Architectural
  evaluation)` (or `(Implicit)` for a reconciliation-pass finding inferred from a doc's silence
  rather than a direct quote) — "(Architectural evaluation) The system has a written technical
  vision explaining why it's shaped the way it is." The prefix is what makes this safe: it tells a
  skimming reader "this is a claim under test, not an assertion," so the badge/explanation resolving
  it negatively doesn't read as a surprise reversal.
- **Never**: a hypothesis-phrased claim with no prefix and no doc quote behind it — e.g. "coda-
  pricing-engine has a written technical vision that architecture decisions can be checked against"
  with nothing marking it as unresolved. This has caused real, measured quality regressions in past
  runs of this skill: on a skim of the key-findings list, every one of these reads as a *confirmed
  strength* rather than the risk it actually is, and a reader has to open the badge and explanation
  to discover the reversal. That defeats the point of a findings report, which exists to be
  scannable.

Pick one of the two acceptable styles and use it consistently for the whole report — don't mix
prefixed-hypothesis and bare-hypothesis phrasing, since the bare form is only safe when every claim
around it is *also* stated as a direct fact and the reader can trust that convention throughout.

### 6. Write `findings.json`

Write a file (`$RUN_DIR/findings.json`) matching this schema:

```json
{
  "title": "Architecture Debt Report — <repo/doc name>",
  "doc_sources": ["docs/boundaries.md", "README.md"],
  "findings": [
    {
      "id": "f1",
      "claim": "Kafka consumer failures on the order-events channel are dropped, not sent to a DLQ",
      "doc_source": "docs/boundaries.md",
      "doc_location": "Kafka consumers table, order-events-fulfilled row",
      "classification": "confirmed",
      "dimension": "correctness",
      "severity": "info",
      "packages": ["com.example.app.consumer"],
      "evidence": [
        {"file": "src/main/java/.../OrderEventConsumer.java", "line": 42, "note": "failure-strategy=ignore annotation, no DLQ producer"}
      ],
      "explanation": "Code matches: the consumer's @Incoming annotation sets failure-strategy=ignore and there is no -dlq producer anywhere in the consumer package."
    },
    {
      "id": "f2",
      "claim": "Order's JPA @Id doesn't match its real (composite, partitioned) DDL primary key",
      "doc_source": "docs/data-model.md",
      "doc_location": "Entities by domain > Orders",
      "classification": "risk",
      "dimension": "data-architecture",
      "severity": "high",
      "packages": [],
      "evidence": [
        {"file": "sql/0007-Order.sql", "line": 93, "note": "PRIMARY KEY (`CompletedDate`, `OrderId`)"},
        {"note": "entity source lives outside this repo (published dependency) — doc states JPA @Id orderId only, a single column"}
      ],
      "explanation": "Hibernate's identity/equality/caching model is keyed on orderId alone while the real relational key is composite. Two rows with the same orderId but different completedDate would collide as 'the same entity' from the ORM's point of view.",
      "recommendation": "Confirm whether this has ever caused a merge/cache collision in production; if the composite key is load-bearing, map it as an @IdClass/@EmbeddedId instead of a single @Id."
    }
  ]
}
```

`packages` should list the Java package(s) (matching node IDs from `dep_graph.json`) most relevant
to the finding, for context and to make it easy to cross-check against the static-analysis panel's
coupling/churn numbers by hand — the report doesn't currently auto-cross-reference it, so treat it
as useful metadata, not a required field. Leave it empty if the finding doesn't map to one package.
`dimension` and `severity` are required on every finding (reconciliation findings default to
`dimension: correctness`, `severity: info`); `recommendation` is required for any `risk` finding
rated `medium` or higher.

**`claim`, `doc_source`, and `doc_location` must always be non-empty strings, never `null` or
omitted** — `generate_report.py` treats a missing key and an explicit `null` the same (defaults to
empty), so this won't crash the report either way, but empty cells read as broken output to
whoever's reading it. Reconciliation-pass findings have a natural claim from the doc; for
evaluation-pass findings (`risk`/`strength` with no specific doc claim prompting them — see step 5)
write a short synthesized `claim` describing what's being evaluated (e.g. "The batch-processor's
job execution layer can scale horizontally if load grows"), and set `doc_source`/`doc_location` to
the most relevant doc if one exists, or a literal note like `"no explicit doc claim — evaluated
directly against code"` if none does.

### 7. Generate the report

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py \
  --findings "$RUN_DIR/findings.json" \
  --dep-graph "$RUN_DIR/dep_graph.json" \
  --churn "$RUN_DIR/churn.json" \
  --out "$RUN_DIR/report.html"
```

This produces one self-contained HTML file:
- An **overall score** (0-100, heuristic/debt-weighted — see the script's SCORE PHILOSOPHY comment
  and the report's own "Score philosophy" disclosure; it's a trend signal for this repo over time,
  not a grade to compare across repos).
- Summary counts across all five classifications (Confirmed / Misaligned / Gap / Risk / Strength).
- A **static code analysis** panel — deterministic numbers straight from the dep-graph/churn data
  (package/class/edge counts, most-coupled packages, highest-churn packages), no LLM judgment in
  these figures.
- A **key pressing findings** shortlist (the highest-severity risk/misaligned/gap findings, capped
  at 8) that jumps to the matching row in the full table on click.
- The full findings table, filterable by both classification and evaluation dimension.

No network access needed to view it — it's plain inline CSS/JS, no graph/canvas rendering.

Tell the user where the report landed and open/reference it. If the user wants it published for
sharing rather than left as a local file, use the Artifact tool on the generated HTML (load the
`artifact-design` skill first per its own rules) — but default to just leaving the file locally
unless asked.

### 8. Summarize in chat

Give a short summary in the conversation, and don't let the reconciliation counts crowd out the
evaluation findings — they're the more valuable half for a reader who already trusts the docs are
roughly accurate:
- Reconciliation: total Confirmed / Misaligned / Gap counts, and the 1-2 most consequential.
- Evaluation: the highest-severity Risk findings (with the concrete recommendation for each), and
  1-2 Strengths worth explicitly preserving. Prioritize using the churn signal — a risk in a
  file that changes weekly matters more than the same risk in dead code.

Don't just say "see the report" — name the actual finding and its concrete consequence.

## Non-Java repos

`extract_dep_graph.py` parses Java `package`/`import` statements only. For a non-Java repo, either:
- Skip the dependency graph (`generate_report.py` works fine with `--dep-graph` omitted — the
  report just shows the findings table, no graph panel), or
- Ask the user if they want a language-specific extractor added; don't silently fabricate a graph.

`compute_churn.py` is language-agnostic (pure `git log`) and works in any repo.

## Demo mode (thin doc vs. improved doc)

If the user wants to demonstrate the tool's value rather than run a one-shot audit, run the whole
workflow twice against two versions of the same doc (e.g. a deliberately thin version, then a
detailed one) and compare: a thin doc should yield mostly Gaps (little is asserted, so little can
be confirmed or contradicted); a detailed doc should yield a mix including genuine Misaligned
findings. Note that the evaluation pass (step 5) is independent of doc quality — it runs against
the code either way, so it's a good way to show that this skill still finds real, high-value issues
even when there's no doc to reconcile against at all.
