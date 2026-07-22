# architecture-debt-visualizer

A Claude Code skill that reconciles a repo's design docs against its actual code, then evaluates
the architecture itself the way a senior/staff architect would — scalability, extensibility,
long-term maintainability, performance/operational cost, data-architecture, observability, and
whether the implementation still serves the product's stated technical vision. It also checks
whether the docs state the scale and extensibility *targets* the architecture is supposed to be
judged against in the first place — a hardcoded worker count is a very different finding at 50 QPS
than at 5,000 QPS, and most repos never write down which one applies.

Produces a self-contained, scored HTML report: a static-analysis panel (dependency coupling, git
churn, contributor/bus-factor signals), a curated shortlist of the most pressing findings, and a
full findings table filterable by classification and evaluation dimension.

## What it does

1. **Reconciliation** — extracts checkable claims from your docs (`docs/*.md`, Mermaid diagrams,
   READMEs) and verifies each against the real code: confirmed, misaligned, or a gap.
2. **Evaluation** — independent of any doc claim, judges the architecture on its own merits across
   9 dimensions using a fixed rubric (not open-ended "look around"), so results are reproducible
   run to run: scale-requirements, extensibility-requirements, scalability, extensibility,
   maintainability, performance/cost, data-architecture, observability, vision-alignment. The two
   "requirements" dimensions run first and feed the rest — they check whether the docs ever state a
   target throughput/latency/growth figure or a named future extensibility need, and if one exists,
   later scalability/extensibility findings cite it directly instead of judging against an implicit
   standard. If no target is documented anywhere, that absence is itself a finding.
3. **Score** — a heuristic, debt-weighted 0-100 score with a per-dimension penalty cap, meant for
   tracking one repo's trend over time, not for ranking systems against each other.

Currently ships one deterministic script for dependency-graph extraction that's Java/Gradle-specific
(`extract_dep_graph.py` parses `package`/`import` syntax); the report generator and churn analysis
are language-agnostic. On a non-Java repo, the skill runs fine without the dependency graph.

## Install

```
/plugin marketplace add sumeetmi2/architecture-debt-visualizer
/plugin install architecture-debt-visualizer@architecture-debt-visualizer
```

## Use

In any repo, ask Claude Code something like:

> Can you evaluate our architecture and check if the docs are still accurate?

The skill triggers automatically on phrases like that, or invoke it explicitly. See
[`skills/architecture-debt-visualizer/SKILL.md`](skills/architecture-debt-visualizer/SKILL.md) for
the full workflow, scoring methodology, and the specific investigation techniques it applies per
dimension.

## What a good `docs/` folder looks like

The skill works with whatever docs you have — including none — but the more of the following you
have, the sharper and more useful its findings get. This list is drawn directly from what actually
made a difference across testing, not a generic "write good docs" checklist.

**A recommended file set** (one per repo, or one per deployable if it's a monorepo with several):

- `architecture.md` — module/component topology, data flow, entry points.
- `boundaries.md` — every REST endpoint, queue/topic, cron job, external API and datastore this
  component touches. This is the single highest-value doc for the reconciliation pass.
- `data-model.md` — entities, keys, invariants. Point it at the real schema/DDL, not just at ORM
  classes — the skill checks both and the two disagreeing is one of its most common findings.
- `conventions.md` — naming, layering, testing, and error-handling conventions actually in force.
  Concrete stated conventions ("every repository extends X") are directly checkable; "we try to
  keep things consistent" is not.
- `glossary.md` — domain terms and acronyms. Low effort, and it sharpens every other doc's claims.
- `technical-vision.md` — **why** the system is shaped the way it is: key architectural decisions,
  trade-offs accepted, and what's coming next. This is the single most commonly *missing* piece —
  across every real test run, an empty or template-only vision doc was found and flagged. If you
  only add one thing from this list, add real content here, not scaffolding.
- `patterns/add-<thing>.md` — short "how to add a new handler / endpoint / job type" guides. These
  give the extensibility dimension a concrete, checkable baseline: the skill counts how many actual
  instances of "X" in your code follow the documented pattern vs. duplicate logic inline.

**Claims should be concrete and falsifiable.** "Service A must not call Service B directly," "all
writes to the `orders` table go through `OrderRepository`," "the notification consumer retries a
failed message up to 3 times before dropping it" — these can be checked against code and produce a
real finding either way, whatever your actual domain is. "The service is scalable" or "we follow
best practices" cannot be checked against anything and are silently skipped, regardless of domain.

**Be careful with "complete list" claims.** A table that enumerates "every message consumer" or
"every REST endpoint" is extremely useful when accurate — but it's also the single most common
source of a *gap* finding, because it silently becomes wrong the moment one more consumer or
endpoint is added without a matching doc update. This isn't a reason to avoid such tables (they're
worth having), just an expectation to set: if you have one, expect the skill to occasionally catch
it lagging behind, and that's the point.

**Name what's coming next, not just what exists today.** A short "known gaps / forward direction"
section — a new integration, customer segment, data source, or migration you're about to take
on — lets the evaluation pass check whether your current architecture is actually ready for it,
instead of only judging against today's usage. Some of the most valuable findings in testing came
from checking a design against a stated future requirement, not its current one.

**State your actual scale and throughput targets somewhere, even roughly.** "We expect X requests/
second at peak, Y% growth over the next N months, and a Z-ms latency budget" turns every scalability
finding from a guess into a calibrated judgment — the same hardcoded worker count is a non-issue
against a low target and a real problem against a high one, and the skill can't tell which without
a number to check against. If this is missing, the skill flags the absence itself as a finding
rather than silently guessing; put the number in and every downstream scalability/performance
finding gets sharper for it.

**If you keep diagrams, prefer a text format (Mermaid) as the source of truth**, and if you also
keep a frozen image export (PNG/SVG) alongside it, say explicitly which one wins if they disagree.
The skill treats this as an explicit reconciliation target — a frozen export that's drifted from
its own source diagram is a real, common, and easy-to-fix finding.

**Add frontmatter metadata if you can** — a `last-generated:` date and the source file globs a doc
was written from. It's a strong freshness signal, but keep it honest: a doc that cites a source
path that no longer exists (because a module was extracted, deleted, or moved) is exactly the kind
of drift this skill is built to catch, and citing a real path is what makes that catchable at all.

**In a monorepo, scope docs per deployable.** If the repo has more than one independently-deployed
component, give each its own `docs/` tree rather than one shared root folder — each one drifts on
its own schedule, and the skill discovers and reconciles all of them separately by default.

## Validation

### Methodology

Tested against a real, private production monorepo (a large multi-module Java/Gradle microservices
codebase — name and domain withheld, not affiliated with this project) rather than a toy example.
Terms used below:

- **Cold agent run** — a fresh Claude Code agent with no memory of any prior run and no visibility
  into other runs, given only the target repo and a plain-language request ("evaluate our
  architecture and check if the docs are still accurate"). This is what someone installing the
  skill for the first time actually experiences — not a run I tuned by hand.
- **Identical-scope runs** — two or more cold agent runs pointed at the exact same repo and the
  exact same restricted set of docs, so any difference between their outputs is purely run-to-run
  variation, not a different task or a different amount of material to review.
- **Score** — the report's own heuristic 0-100 number (documented in `SKILL.md` and inside every
  generated report): lower means more, or more severe, unresolved findings. It's designed to track
  one repo's trend across repeated runs, not to compare different repos or grade "quality" in the
  abstract.
- **Finding** — one row in the report: a reconciliation result (confirmed / misaligned / gap,
  checked against a real doc claim) or an evaluation result (risk / strength, judged independent of
  any doc claim) in one of the 7 evaluation dimensions.
- **Per-dimension checklist coverage** — the evaluation pass defines a fixed set of mandatory,
  individually-named sub-checks per dimension (7 for data-architecture, e.g. identity/PK
  consistency, naming-convention drift, referential integrity, partition maintenance, type choices,
  forward-readiness, shadow representations). This measures whether a run actually executed every
  one of them separately, rather than skipping some or merging two into one finding to save time.

### Reliability, before vs. after tuning the rubric

Earlier versions of the evaluation pass gave agents an open-ended target ("be thorough, find
15-25+ issues") and left it to each run's own judgment when a dimension was "done." That produced
wide swings between identical-scope runs. The rubric was changed to a fixed minimum/maximum finding
count per dimension, a capped scoring formula (no single dimension can dominate the score), and the
named per-dimension checklist described above.

| Metric | Before the rubric fix | After the rubric fix |
|---|---|---|
| Score range across identical-scope runs | 68 points (lowest 12, highest 80) | 13 points (lowest 28, highest 41) |
| Finding-count range across identical-scope runs | 17 (lowest 11, highest 28) | 6 (lowest 30, highest 36) |
| Per-dimension checklist coverage | Not tracked — left to each run's judgment | All 7 named sub-checks hit individually, confirmed across 3 separate identical-scope runs |

Separately, every high-severity finding produced by a deep, human-guided reference pass over the
same repo was independently rediscovered by cold agents that never saw that reference pass or its
findings — including cases where two agents, given the identical prompt and scope, arrived at the
same conclusion via different evidence.

### Public, reproducible test: `examples/sample-service`

The reliability numbers above come from a private repo whose specifics can't be shared. This repo
also ships a small, purpose-built fixture — [`examples/sample-service`](examples/sample-service) —
so the same kind of test is fully reproducible by anyone, with real, non-obfuscated reports you can
open and check. See [its own README](examples/sample-service/README.md) for what's in it: a ~10-file
Java service with deliberately planted architecture debt, documented against two doc sets
(`docs-bad`, stale/incomplete; `docs-good`, accurate and complete) that share identical code.

Three independent cold runs against `docs-bad` (fresh agent, no memory of prior runs, no memory of
each other, no knowledge of what was deliberately planted):

| Run | Score | Findings | data-architecture evaluation findings (cap 7) |
|---|---|---|---|
| [1 — human-reviewed, benchmark](examples/sample-service/reports/docs-bad-run1-benchmark.html) | 30/100 | 32 | 7/7 |
| [2](examples/sample-service/reports/docs-bad-run2.html) | 32/100 | 32 | 7/7 |
| [3](examples/sample-service/reports/docs-bad-run3.html) | 25/100 | 33 | 6/7 |

7-point score spread, 1-finding spread. All three independently caught every deliberately-planted
issue (the entity/DDL primary-key mismatch, the undocumented endpoint, the undocumented consumer,
the empty vision doc) plus real issues nobody planted — run 3, for instance, caught that the
table's partition key (`CreatedDate`) doesn't actually match the column the archival job filters on
(`CompletedAt`), a genuine mismatch that fell out of the investigation rather than being seeded.
Run 1 was manually reviewed before being treated as the benchmark for runs 2 and 3.

**Known limitation, disclosed rather than hidden:** a phrasing rule exists (state findings as direct
facts, not as an unresolved positive-sounding hypothesis with no marker — see `SKILL.md`) specifically
because early testing showed the wrong phrasing reads as a false "this is fine" on a skim. It's
followed reliably when a run is explicitly told to self-audit before finalizing, but recurs in some
ordinary cold runs (visible in a few rows across the reports linked above) because the instruction
currently isn't self-enforcing. Content and evidence are unaffected — only the wording of some claim
sentences reads more ambiguously than intended. Tracked as follow-up work, not swept under the rug.

## License

MIT — see [LICENSE](LICENSE).
