# Expected result: `template-lib`

Kept **outside** `examples/template-lib/` for the same reason as `minimal-cli-tool.expected.md` and
`clean-service.expected.md` — a scoped run reads the fixture's own `README.md`/`docs/` as part of
normal doc discovery, so stating the expected outcome inside the fixture would make the test
partially circular. This file is the golden spec, consumed by a human reviewer and (once added)
`evals/cases.json`, never by the agent under test.

## What this fixture is for

Every fixture so far classified as `production-service` (`sample-service`, `clean-service`) or
`cli-tool` (`minimal-cli-tool`) — zero coverage on `library`, despite it having a genuinely
different suppression profile: `rubric_manifest.json`'s `system_type_overrides` marks
`scale-requirements`/`observability`/`reliability-resilience` informational for `library`, but
(unlike `cli-tool`) leaves `scalability` and `change-safety` mandatory. `template-lib` tests that
distinction specifically — a real hardcoded-capacity finding (`scalability.a`) and two real
API-stability findings (`change-safety`) should survive even though this is a `library`, while the
suppressed dimensions should cleanly resolve `not-applicable` rather than manufacturing a risk out
of a throughput/observability concept that doesn't apply to in-process code with no I/O of its own.

## What "pass" looks like

| Check | Expected outcome | Why |
|---|---|---|
| `scale-requirements.a`/`.b` | `not-applicable` (informational for `library`) | No throughput/growth concept for an in-process call |
| `observability.a`/`.b` | `not-applicable` (informational for `library`) | No golden-signal concept without a deployed service boundary |
| `reliability-resilience.a`–`.e` | `not-applicable` (informational for `library`) | No downstream I/O, no queues, no multi-step writes anywhere in this library |
| `scalability.a` | `risk` | `TemplateCache.MAX_SIZE = 200` is a literal, no override mechanism — every embedding service gets the same ceiling |
| `change-safety.a` | `risk`, two findings under this one check | Both API-stability facts belong here, not split across checks: the `vars` parameter widening (`Map<String,String>`→`Map<String,Object>`, 1.2.0) and the `renderSafe()` removal (1.1.0) are both "breaking change shipped as a non-major bump, no deprecation cycle" — exactly what `change-safety.a` asks about. A check can own more than one independent finding (see `scalability.a`'s own "list them all" pattern) — don't split one fact-type across `.a`/`.b`/`.c`/`.d` just to spread credit around |
| `change-safety.b` | `not-applicable` | No DB migrations exist in this library at all |
| `change-safety.c` | `not-applicable`, citing `.a` | Removing a method a consumer still calls is the same underlying fact `.a`'s `renderSafe()` finding already covers — don't double-count it from a second angle (see evaluation-rubric.md's chained-check rule) |
| `change-safety.d` | `not-applicable` | No deploy/rollback concept for a versioned library artifact — consumers choose when to upgrade, there's no "roll back this deploy" event the way a service has |
| `change-safety.e` | `not-applicable` | No gradual-rollout/feature-flag concept for a library release |
| `security-boundaries.d` | `risk` | `TemplateEngine.loadTemplateBody` resolves caller-supplied `templateName` straight into a filesystem path with no traversal/allowlist check |
| `extensibility.a` | `risk` | `dateFormat` bypasses `HelperRegistry` with an inline special-case, unlike every other helper, contradicting `docs/architecture.md`'s documented pattern — this is `.a`'s territory (does reality still match the documented "how to add X" pattern), not `.b` (which is for inconsistency found *without* any pattern doc existing at all) |
| `data-architecture.a`–`.g` | mostly `not-applicable` | No database/schema anywhere in this library |
| `performance-cost.a` | `not-applicable` | No external/expensive calls — everything is in-memory |
| `vision-alignment.b` | plausibly `risk` | `docs/technical-vision.md` explicitly says API stability matters *more* here because "a breaking change... has to be adopted by every consumer independently" — the `change-safety.a` findings above are exactly the pattern that vision text warns against, not a hypothetical |
| `maintainability.a` | `clean` or low-severity `risk`, **not** `not-applicable` | Thin/single-author history at this fixture's scale — the bus-factor concept still exists (any codebase with an author has one), it's just low-confidence; see evaluation-rubric.md's now-explicit thin-history guidance, added after this fixture's first cold run got this wrong |

**Anything a cold run finds that isn't listed here and is backed by real evidence** should be
trusted over this table, not dismissed to protect it — this fixture wasn't reviewed by a second
person before being used as a benchmark, so a genuine miss here is possible.

## System-type classification

Expect `system_type: "library"`, reasonably high confidence: `java-library`/`maven-publish`
Gradle plugins (no `application` plugin, no `main`), a versioned artifact (`build.gradle`'s
`group`/`version`), and `docs/technical-vision.md` explicitly framing it as "linked directly into
other services' processes" and "consumed by multiple internal services, each embedding a different
version" are all first-class positive signals for `library`, not just an absence of
production-service signals.

## Actual first-run result

Cold, no-memory agent, `full` mode. `system_type` classified `library`, confidence **high** —
matched. `validate_findings.py`: `OK (16 findings, 39 checks, 0 warnings)`. **16 findings** (8 risk,
4 confirmed, 2 misaligned, 2 strength; severities 2 high/5 medium/3 low/6 info), **39 check
records** (7 risk, 3 strength, 1 clean, 28 not-applicable), **27/27 mandatory checks covered
(100%)**, debt index 72/100.

Every row in the table above matched **except** `maintainability.a` — the agent recorded
`not-applicable` (reasoning: the fixture was still untracked, zero commits, at the time it ran).
That's arguably defensible for the literal state at run time (there truly was no git history at
all, not just thin history), but diverges from this repo's own established convention (every other
fixture's actual `maintainability.a` result is `risk` or `clean` with a disclosed thinness caveat,
never `not-applicable`) — evaluation-rubric.md didn't say so explicitly before this run, which is
exactly the gap now fixed (see the "Maintainability" checklist's new thin-history clause). Once
this fixture is committed it'll have real (if minimal) git history for any future run to work with.

Two rubric-wording gaps this run surfaced, fixed directly in the reference docs, same session:
`extensibility-requirements.b` didn't state what an absent cost-bar should score as (unlike `.a`,
which explicitly says absence is a risk) — now explicit, mirroring `.a`. And this very expected-
outcome table originally hedged the two `change-safety` facts as "`.a` and/or `.d`" / "`.a` and/or
`.b`" — a real tension with evaluation-rubric.md's "checks aren't interchangeable" rule that the
cold-test agent correctly called out; resolved above by committing `change-safety.a` as sole owner
of both facts (as two independent findings under one check, per the check's own "list them all"
pattern) and marking `.b`/`.c`/`.d`/`.e` `not-applicable` for a library with no deploy/migration/
rollout surface.

**Process note:** this fixture's own `README.md` originally included a planted-issues table and
explicit "used to test the skill" framing — a second answer key sitting inside the audited repo
itself, not just this sibling `.expected.md`, contradicting this project's own established
fixture-circularity-avoidance discipline (`clean-service`/`minimal-cli-tool`'s READMEs stay purely
in-universe; only `sample-service`'s README predates that discipline being written down and still
has this same drift, not yet backfilled). The cold-test agent that ran against this fixture caught
and disclosed it unprompted, verified every finding independently against real `file:line` evidence
rather than the leaked table regardless, and its result was trusted on that basis rather than
discarded — but the README has since been rewritten to be purely in-universe, so a future cold run
against this fixture won't have the same exposure.
