# Expected result: `clean-service`

Kept **outside** `examples/clean-service/` for the same reason as `minimal-cli-tool.expected.md` —
a scoped run reads the fixture's own `README.md` as part of normal doc discovery, so stating the
expected outcome inside the fixture would make the test partially circular. This file is the
golden spec, consumed by a human reviewer and `evals/cases.json`, never by the agent under test.

## What this fixture is for

Every other fixture in this repo (`sample-service`, `minimal-cli-tool`) is either deliberately
debt-laden or trivially small (a 2-file CLI with almost no evaluation surface). Neither one answers
the question a false-positive/hallucination check actually needs: **does the skill over-flag risk
on real, non-trivial, deliberately well-built code?** `clean-service` is that fixture — same rough
scale and shape as `sample-service` (REST API, a message consumer, a scheduled job, a real schema),
but every pattern that was planted as debt in `sample-service` was deliberately built correctly
here instead.

## What "pass" looks like

A run against this fixture should produce **mostly `confirmed`/`strength`, very few `risk`, and
ideally zero `high`-severity risk** — not because the checklist is skipped, but because the
patterns it checks for are genuinely present:

| Check | What's actually right here |
|---|---|
| `data-architecture.a` (identity/PK) | `@EmbeddedId LinkId(createdDate, id)` matches the DDL composite key exactly |
| `data-architecture.d` (partition maintenance) | `MAXVALUE` catch-all partition, no dated horizon to run out |
| `security-boundaries.a` (authN/authZ) | Global `@Provider` filter covers every endpoint by construction |
| `security-boundaries.b` (secrets) | Auth credential sourced from `${AUTH_CREDENTIAL}` env var, never hardcoded |
| `security-boundaries.d` (input validation) | `@Valid` + Bean Validation constraints on the create request |
| `reliability-resilience.a` (idempotency) | Create endpoint requires `Idempotency-Key`, backed by a unique DB index |
| `reliability-resilience.b` (failure isolation) | `AnalyticsClient` has `@Timeout`/`@CircuitBreaker`/`@Fallback` |
| `reliability-resilience.c` (poison messages) | `click-events` uses `failure-strategy=dead-letter-queue`, not `ignore` |
| `reliability-resilience.d` (transaction boundaries) | No multi-step write path exists anywhere — legitimately `not-applicable`, not a gap (see `technical-vision.md`'s "No dual-write anywhere" decision) |
| `change-safety.a` (API versioning) | `/api/v1/` from the start, documented deprecation policy |
| `change-safety.b` (migration pattern) | `002-add-tag-column.sql` is a real expand-step (nullable add, not-yet-enforced) |
| `scalability.a` (hardcoded capacity) | Consumer concurrency and job interval are both env-overridable |
| `observability.a` (golden signals) | Counters + timer on the consumer, counters on both endpoints, a gauge on the expiry job |

**What should still show up as a real, legitimate finding** (this fixture isn't claiming to be
flawless, just deliberately not debt-laden where the checklist looks):
- `maintainability.a` (bus factor) — single-author, same disclosed limitation as `sample-service`
  and `minimal-cli-tool` (churn threshold too coarse at this fixture's scale to mean much).
- `data-architecture.c` (referential integrity) — no FK exists because there's only one table;
  legitimately `clean` or `not-applicable`, not a risk, but worth the check running anyway.
- Anything a cold run finds that isn't listed here and is backed by real evidence — this fixture
  wasn't reviewed by a second person before being used as a benchmark, so a genuine miss is
  possible and should be trusted over this list, not dismissed to protect the "clean" framing.

If a run instead produces a long list of `high`-severity risk findings against patterns that match
the table above, that's a false positive worth investigating — this fixture's whole purpose is
catching exactly that.
