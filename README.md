# architecture-debt-visualizer

A Claude Code skill that reconciles a repo's design docs against its actual code, then evaluates
the architecture itself the way a senior/staff architect would — scalability, extensibility,
long-term maintainability, performance/operational cost, data-architecture, observability, and
whether the implementation still serves the product's stated technical vision. It also checks
whether the docs state the scale and extensibility *targets* the architecture is supposed to be
judged against in the first place — a hardcoded worker count is a very different finding at 50 QPS
than at 5,000 QPS, and most repos never write down which one applies.

Produces a self-contained HTML report with four headline indicators — Documentation fidelity,
Architecture risk, Audit coverage, Evidence confidence — plus a static-analysis panel (dependency
coupling, git churn, contributor/bus-factor signals), a curated shortlist of the most pressing
findings, and a full findings table filterable by classification and evaluation dimension.

## What it does

1. **Reconciliation** — extracts checkable claims from your docs (`docs/*.md`, Mermaid diagrams,
   READMEs) and verifies each against the real code: confirmed, misaligned, or a gap.
2. **System classification** — before judging the architecture, classifies what kind of repo this
   actually is (`production-service` / `library` / `cli-tool` / `batch-job` / `prototype` /
   `archived`), evidence-first, defaulting to the strictest tier (`production-service`) whenever
   it's genuinely unclear. A missing QPS target isn't the same finding on a CLI tool as it is on a
   payments service — this is what keeps the evaluation pass from judging every repo as if it were
   the production system this skill was originally built and tested against.
3. **Evaluation** — independent of any doc claim, judges the architecture on its own merits across
   12 dimensions: scale-requirements, extensibility-requirements, scalability, extensibility,
   maintainability, performance/cost, data-architecture, observability, reliability/resilience,
   change safety, security boundaries, vision-alignment. Every mandatory check (mandatory per the
   system classification above) gets exactly one coverage
   record — `risk`, `strength`, `clean`, `not-applicable`, or `not-assessed` — so *what gets
   checked* is fixed and reproducible, without forcing a minimum or maximum number of findings the
   way an earlier version of this rubric did.
4. **Report** — Documentation fidelity and Architecture risk separate "are the docs accurate" from
   "is the architecture good," so improving one doesn't silently move the other; Audit coverage
   says how much of the mandatory checklist actually ran; Evidence confidence says how much of
   what's reported rests on direct citation vs. inference. A legacy 0-100 debt index (the original
   single-number score) is kept as a fifth, secondary figure for continuity with earlier reports.

Optionally run in a narrower **mode** — `reconcile` (docs-accuracy only), `evaluate`
(architecture-judgment only), or `full` (both, and the default whenever intent is ambiguous) — so a
narrow request like "is `boundaries.md` stale?" doesn't pay for a full evaluation pass it didn't ask
for.

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
  component touches. This is the single highest-value doc for the reconciliation pass, and — along
  with `conventions.md` — is where your **functional requirements** actually live: what the system
  does and the rules it follows, as opposed to the non-functional targets below.
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

**State your actual scale and throughput targets somewhere, even roughly** — this is what the
`scale-requirements` dimension checks for. "We expect X requests/second at peak, Y% growth over the
next N months, and a Z-ms latency budget" turns every scalability finding from a guess into a
calibrated judgment — the same hardcoded worker count is a non-issue against a low target and a real
problem against a high one, and the skill can't tell which without a number to check against. If
this is missing, the skill flags the absence itself as a finding rather than silently guessing; put
the number in and every downstream scalability/performance finding gets sharper for it.

**Separately, state your extensibility targets** — this is what the `extensibility-requirements`
dimension checks for, and it's a different question from scale. Name the things you expect to add
and roughly how fast: a new integration type, a new tenant class, a new channel — "one new message
channel per quarter" is the kind of concrete figure that lets the skill judge whether today's
pattern (a `patterns/add-*.md` guide, a plugin point, a config-driven registry) can actually keep up,
instead of just noting that extension points exist.

**Name what "evolving" means for things that already exist, not just what's coming next.** A short
note on versioning/deprecation policy — how a breaking API or schema change gets rolled out, how long
an old consumer or endpoint stays supported, what "retired" looks like in practice — closes the loop
on extensibility: it's not just "can we add new things" but "can we retire or change old ones without
an incident." Repos that only document growth and never document deprecation tend to accumulate
exactly the kind of dead/duplicate code paths this skill flags as maintainability debt.

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

Validated through repeated cold-agent runs (fresh agent, no memory of prior runs, no memory of
each other) on:
- a production-shaped Java fixture ([`examples/sample-service`](examples/sample-service),
  stale-docs scenario),
- the same fixture accurately documented (`docs-good` scenario),
- a CLI-tool fixture built specifically to test false-positive suppression
  ([`examples/minimal-cli-tool`](examples/minimal-cli-tool)),
- and a private production monorepo (name/domain withheld).

A `validate_findings.py` script hard-enforces the evidence/schema rules rather than leaving them to
prose, and `skills/architecture-debt-visualizer/evals/` is a golden-test harness with
must-find/must-not-find specs graded against real run output.

See [`docs/validation.md`](docs/validation.md) for the full methodology, terminology, raw linked
reports, the rubric's evolution (open-ended target → min/max finding count → check-coverage model),
and known limitations — including one honest one: the eval harness grades already-generated output
rather than invoking the skill end to end, and the 9-dimension rubric doesn't yet have dedicated
checks for reliability/resilience, change-safety, or security/trust-boundary concerns.

## License

MIT — see [LICENSE](LICENSE).
