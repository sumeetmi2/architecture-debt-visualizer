# Architectural evaluation pass — mindset, checklist, and coverage rule

Read this for `SKILL.md` step 5 (`evaluate` and `full` modes only — skipped entirely in
`reconcile` mode). This is a **separate, mandatory pass**, not something done opportunistically
while reconciling — it doesn't wait for a doc claim to react to, and doesn't defer to what the
docs (or the team) believe about their own system. Form your own judgment from the code, the
schema, and the metrics actually emitted, the same way an outside architect brought in to assess
the system would. A `confirmed` reconciliation result (doc and code agree) does not make a bad
pattern acceptable — agreement is a statement about honesty, not about quality. Judge quality
separately, here.

## Mindset

Read every architectural decision the way an experienced staff/principal architect reviewing a
system they're about to inherit would — not "does this technically work" but "will this still be
a good decision in two years, at 10x the data, with a bigger team touching it." Concretely, for
every significant component/pattern/decision you encounter, ask:

- **Scale requirements — check this before judging scalability, not after.** A hardcoded
  `concurrency=1` is a completely different finding at 50 QPS than at 5,000 QPS, and you can't tell
  which without knowing the target. Search the docs for anything stating target
  throughput/QPS/TPS, a latency or response-time SLO, an expected growth horizon ("10x users by
  2027"), or peak-vs-average load characteristics. If none of this is documented anywhere, that
  absence is a finding under `scale-requirements` *when that dimension is mandatory for this
  repo's classified system type* (see `system-classification.md`) — and it means every scalability
  judgment you make elsewhere in this pass is necessarily uncalibrated; say so explicitly rather
  than asserting a confident severity you can't actually justify. If a target *is* documented,
  carry it forward and cite the actual number in your scalability/performance-cost findings later —
  "stated target is X QPS; current hardcoded concurrency=1 caps throughput well below that" is a
  sharper, more useful finding than "this is hardcoded, no override."
- **Extensibility requirements — same principle, checked first.** Before judging whether the
  codebase's actual extensibility is good or bad, find out what the docs say it actually needs to
  extend to: named future tenants/integrations/use cases, and any stated bar for how fast a new one
  should be addable. Absence is a finding under `extensibility-requirements` (same
  applicability caveat as above). When present, judge the codebase's extension points against that
  concrete target, not a generic "is this well factored" standard — and when you get to the
  **Extensibility** and **Data architecture** checks below, reference whatever you found here
  rather than treating them as unrelated passes.
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
- **Maintainability** — duplication instead of abstraction, mixed conventions doing the same job
  two ways (two cron syntaxes, two error-handling styles), tech debt the team has already flagged
  in comments/docs but not fixed, contributor/bus-factor concentration, anything that makes
  onboarding or debugging harder than it needs to be. Kept as its own dimension, distinct from
  extensibility above — a highly extensible plugin system can still be poorly maintainable (dynamic
  registration, weak typing, hidden control flow), and the reverse is just as real.
- **Performance / operational cost** — expensive external calls (data-warehouse queries, third-
  party APIs) with no visible cost guardrail, missing caching/indexing where access patterns
  clearly demand it, and governance gaps (tests/lint/coverage tooling that exists but isn't
  enforced anywhere). For a `batch-job` system type, also weigh idempotency and restartability here
  — can a failed run safely re-run without double-processing, and is there a documented recovery
  path?
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
    a drop counter. Go find the code path that's supposed to be the safety net and check whether
    its *outcome* is a metric or just a log line — text logs are not a golden signal.
  - Also check where instrumentation exists but is dormant — a well-built metric on a code path
    that's disabled by default, while the currently-live path has weaker coverage, is a real gap
    dressed up as a non-issue.
- **Data architecture / entity design** — this needs its own deliberate pass, not a byproduct of
  reading prose. Go read the actual DDL/schema (not just a doc's description of it) and the ORM
  mapping code — see the lettered checklist below for the specific things to check.
- **Vision alignment** — locate whatever the repo treats as its source of product/technical intent
  (a `technical-vision.md`, ADRs, a roadmap doc, a strategy section in the main README). If it
  exists, check whether current architecture decisions actually serve it, or have drifted from it.
  If it's missing, empty, or pure scaffolding, that absence is a finding *when this dimension is
  mandatory for this repo's system type* — a `prototype` gets this treated as informational, not a
  risk (see `system-classification.md`).

**Credit strengths, not just debt.** An architect who only ever reports problems isn't giving a
useful review. When a pattern is genuinely well-designed (a clean extension point, a reader/writer
split that matches the actual access pattern, a shared calculation module used by two otherwise-
divergent code paths so a fix lands once) — say so explicitly as a `strength` finding. It tells
future maintainers what to preserve, and it's the honest baseline for judging what *should* look
like that but doesn't. Past runs of this skill measurably skewed toward risk-hunting and away from
strength-crediting — counteract this deliberately: for every dimension, after logging risks, spend
one more pass asking "what did this codebase get *right* here." Read the sections of the docs that
are dense with forward-looking or design-rationale content (a "known gaps / forward-looking work"
section, a conventions doc's stated design choices) as closely as the structural/boundary
sections — that's where both strength-credit and vision-readiness findings tend to live, and
they're easy to skim past if you're scanning for problems only.

## Coverage rule — replaces any notion of a minimum/maximum finding count

**There is no minimum or maximum number of findings for any dimension.** An earlier version of
this rubric required "at least 2, at most N" findings per dimension to control run-to-run
variance. It worked for reducing the *count* swing, but it mixed up two different things: checks
performed and problems found, and it created a real incentive to manufacture a weak finding just
to hit a floor.

The actual rule: **every check listed in `scripts/rubric_manifest.json` that is `mandatory` for
this repo's classified `system_type` (see `system-classification.md`) must produce exactly one
coverage record** in `checks.json`, with a status of `risk`, `strength`, `clean`,
`not-applicable`, or `not-assessed`:

- `risk` / `strength` — becomes a full entry in `findings.json` too (see `report-schema.md`),
  linked back to the check id.
- `clean` — you ran the check and found nothing worth flagging either way. Cite what you looked at
  (e.g. "checked all 3 DDL files for FK constraints — none needed, single-table schema").
- `not-applicable` — the check doesn't apply to this repo's shape (e.g. `data-architecture.g`,
  shadow representations, on a repo with no database at all) or the dimension is `informational`
  for this `system_type` and the underlying condition (e.g. no stated scale target) isn't being
  penalized. Say why. **A consistency-style check that needs at least two instances to compare**
  (`extensibility.b`, `maintainability.b` — "is X modeled the same way everywhere") is legitimately
  `not-applicable`, not `clean`, when the repo has zero or one instance of the thing being compared
  — there's nothing to be consistent *or* inconsistent with yet. Don't force a `clean` verdict onto
  a check that had nothing to actually check.
- `not-assessed` — you didn't get to it. This is a legitimate status to ship with, but it should be
  rare and should show up in your chat summary (step 8) as an explicit limitation, not buried.

This gives reproducibility (every mandatory check gets touched, every run) without pressure to
inflate finding counts to hit a floor, and without silently capping a dimension that legitimately
has more real issues than another. A dimension can produce 0 risk findings and 7 `clean` records —
that's a fully reproducible, fully covered, genuinely clean result, not evidence the pass was
rushed.

**When one check's prerequisite is itself absent, downstream checks resolve `not-applicable` citing
the upstream absence — they don't restate the same risk a second time.** Several checks are chained
by design (`vision-alignment.b` needs `vision-alignment.a`'s vision content to exist before it can
compare decisions against it; `data-architecture.f`'s forward-readiness check needs the same vision
content to know what's coming). When the prerequisite check already recorded the absence as a
`risk`, mark the dependent check `not-applicable` with a reason like *"no vision doc content exists
to compare against — see vision-alignment.a"* rather than either leaving it `not-assessed` or
logging a second, redundant risk finding about the same missing doc.

**Every lettered check is individually mandatory — not a menu to pick from, and not interchangeable
with another check in the same dimension.** A measured failure mode from the old rubric: two
parallel runs each produced their required finding count for `data-architecture`, but one run spent
its budget on money-type precision *twice* and never ran the naming-convention check at all, while
the other caught it. Coverage records fix this directly: `data-architecture.b` (naming/
normalization) and `data-architecture.e` (type choices) are different check IDs and both need their
own record, regardless of how many risks either one turns up.

**A finding belongs to exactly one check; a check can produce more than one finding.** A measured
failure mode from the check-coverage model's first validation run: one run noticed
`scale-requirements.a` and `scale-requirements.b` were both answered by the same vision-doc
paragraph, and wrote one combined finding referenced by both checks' coverage records — 13
findings, fully covered on paper. A second, independent run wrote a separate finding per check —
22 findings, also fully covered on paper. Both technically satisfied "every mandatory check has a
coverage record," but the finding *count* swung by nearly 2x anyway, which defeats the whole point
of replacing the old min/max-count rubric with a coverage model in the first place: coverage was
supposed to make finding count an *output*, not something still subject to a judgment call. The
fix: shared evidence is fine and expected (the same file/line can support multiple findings); a
finding credited to more than one check is not. If two checks are answered by the same underlying
fact, write two findings that both cite it, each with its own id, each linked only from its own
check's `finding_ids` — never merge them into one, and never let one finding sit in two checks'
`finding_ids` arrays.

**That fix doesn't mean force every check down to exactly one finding either — a check's
`finding_ids` is an array for a reason.** Several lettered checks explicitly ask you to enumerate
everything, not stop at the first hit — `scalability.a` says "don't stop after finding one; list
them." If a check turns up several genuinely independent issues (three separate hardcoded capacity
numbers with different evidence, different consequences, different fixes), write one finding per
issue and list all of them in that check's `finding_ids`. Cramming three independent risks into one
oversized finding just to keep a tidy 1:1 shape hides two of them from anyone scanning the findings
table by severity/dimension, and picking only the "best" one to report silently drops real, already-
discovered risk. The one-owner rule above is about *credit* (a finding isn't shared property of two
checks); it was never meant to cap a check at one finding.

## Dimension checklists

The lettered items below are the same set enumerated in `scripts/rubric_manifest.json` — that file
is canonical for IDs; this section is the investigative "how," not a second copy of the list to
keep in sync by hand.

**Scale requirements** (do this one first — its output calibrates Scalability below):
(a) search all docs for a stated target throughput/QPS/TPS or latency/response-time SLO;
(b) search for a stated growth horizon or expected-scale-in-N-years figure — a distinct check from
(a), not a duplicate;
(c) carry whatever you found (or its absence) forward explicitly into the Scalability and
Performance/cost checks later.

**Extensibility requirements** (also do this first — calibrates Extensibility below):
(a) search docs for named future tenants/integrations/use cases and any stated timeline. This is a
compound check — **named-but-no-timeline is a distinct, lower-severity outcome from both "fully
stated" and "nothing named at all," not a forced binary.** If the docs name concrete candidates
with no timeline, record it as a `risk` at `low` (not `medium`+) severity noting specifically what's
missing (the timeline, not the whole requirement) — don't score it as either a full pass or as
equivalent to a `high`-severity total absence;
(b) search for a stated bar on how fast/cheaply a new instance of the system's core extension point
must be addable — if found, carry it into the Extensibility check and judge actual cost against it.

**Vision alignment**:
(a) find and read the vision/strategy doc(s) — empty/missing is the finding for this letter;
(b) check 2-3 concrete, currently in-flight or recently-made architecture decisions (grep recent
git history / open feature flags / disabled-by-default code) against what the vision claims or
should claim.

**Data architecture** — open the actual schema/DDL/migration files directly, not a doc's
description of them, for every table connected to the domain's core write-heavy entities:
(a) identity/PK consistency — does the ORM's `@Id` match the real DDL key?;
(b) normalization/naming — count and categorize columns; a naming-convention shift or a cluster of
near-duplicate columns is direct historical evidence of ad hoc growth — run an actual script/grep
across all columns, don't eyeball it;
(c) referential-integrity strategy — grep `FOREIGN KEY`/`REFERENCES` across *all* DDL files, not
just one table's (a rate like "3 of 26 files" is a finding; "this one table has no FK" alone is
not);
(d) partitioning/sharding maintenance — grep for the actual maintenance job before assuming
automation exists; check the partition list's date range against today's date;
(e) type choices — decimal vs float, currency handling;
(f) forward-readiness — check the schema against whatever the product vision names as coming next;
(g) shadow/parallel representations — does any table store a JSON-blob or otherwise schemaless
duplicate of an entity that's normally columnar elsewhere? Its own distinct check, not a byproduct
of (b) or (e).

**Scalability**:
(a) grep config files for *every* hardcoded capacity number (thread/worker/concurrency counts,
timeouts, batch sizes, partition/date horizons) — don't stop after finding one; list them, compare
which are env-overridable vs. literal, note which sit on the highest-traffic path.

**Performance / cost**:
(a) for every expensive external call (data-warehouse queries, third-party APIs, anything that
scales with data scanned), check for a cost/rate guardrail, and compare it against how a *similar*
call elsewhere in the same codebase is guarded — an inconsistency between two structurally similar
call sites is a stronger finding than "there's no rate limit" in isolation. For a `batch-job`
system type, also check idempotency/restartability of the job itself here.

**Extensibility** (this dimension only — see Maintainability below for the related but distinct
contributor/pattern-cost angle; an earlier version of this checklist bundled both under one
"Extensibility & maintainability" heading, which was a stale, confusing label, not an actual shared
rubric — they're independent checks producing independent `extensibility`/`maintainability`
dimension findings):
(a) use the repo's own "how to add X" pattern docs (if any) as a test — do the described steps
still match reality, and how many actual instances of "X" follow the pattern vs. duplicate logic
inline? Get the exact count (`grep -c` / `grep -l | wc -l`), don't estimate;
(b) look for the same shape of inconsistency in places with no pattern doc at all — two
conceptually-identical concerns modeled two structurally different ways elsewhere in the codebase
is the same finding pattern, just undocumented.

**Observability**:
(a) pick the 2-3 most critical logic paths (highest business impact and/or highest churn — use the
churn/dep-graph output, don't guess) and check all four golden signals for each, *separately* —
explicitly note which of traffic/errors/latency/saturation you found evidence for and which you
didn't, per path;
(b) trace whatever code path is responsible for recovering from/reporting on a known failure mode
(a reconciliation job, a retry sweep, a dead-letter consumer, an "expected vs. actual" completeness
check) all the way to its output, and check whether that output is a metric or just a log line.

**Maintainability**:
(a) use `compute_churn.py`'s `bus_factor_hotspots` and `high_diversity_hotspots` output — for any
single-author high-churn package, cross-reference it against what that code actually does;
bus-factor risk on routine CRUD is low-priority, bus-factor risk on the most architecturally
complex or currently-dormant code is a real, specific finding. Sanity-check with
`git log --no-merges --pretty=format:%an | sort | uniq -c` before citing it, to rule out
merge-commit attribution skew;
(b) check the "how to add X" pattern-doc adoption rate from Extensibility(a) again here
specifically for what inconsistent adoption *costs* going forward (a fix/change now has to be
replicated N times instead of landing once) — a distinct finding from Extensibility(a)'s
existence-of-inconsistency one, not a restatement of it.

Classify each evaluation-pass finding as `risk` (a concern, no accompanying doc claim to be
"misaligned" against) or `strength` (a decision worth crediting), tag it with a `dimension` and a
`severity` (`info` / `low` / `medium` / `high`), and — for anything `medium` or higher — write a
one- or two-sentence `recommendation`: what an architect would actually tell the team to do about
it. See `evidence-standard.md` for evidence, confidence, and phrasing requirements.
