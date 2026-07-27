# Expected result: `batch-reconciliation`

Kept **outside** `examples/batch-reconciliation/` for the same reason as every other
`.expected.md` in this directory — a scoped run reads the fixture's own `README.md`/`docs/` as
part of normal doc discovery, so stating the expected outcome inside the fixture would make the
test partially circular. This file is the golden spec, consumed by a human reviewer and (once
added) `evals/cases.json`, never by the agent under test.

## What this fixture is for

Zero prior `batch-job` coverage. Unlike `library`/`cli-tool`, `rubric_manifest.json`'s
`system_type_overrides` gives `batch-job` an empty override set (`{}`) — every dimension stays
`mandatory`, same strictness as `production-service`. The interesting failure mode this fixture
tests isn't suppression, it's **misclassification**: a scheduled job with no HTTP listener and no
interactive entry point looks superficially like it could be waved off as a `cli-tool` (which *does*
suppress `scale-requirements`/`observability`/`scalability`/`reliability-resilience`/`change-safety`)
or dismissed as a `prototype`. `batch-reconciliation` has clear positive `batch-job` evidence (a
`CronJob` manifest with a `schedule`, a `main()` that runs one pass and exits, no `bin`/interactive
CLI surface, no server) and should get the full mandatory check set applied — including a real,
serious `reliability-resilience.a` finding (non-idempotent retry on a scheduled job, the exact
example the checklist itself names) that a `cli-tool` misclassification would have suppressed
entirely.

## What "pass" looks like

| Check | Expected outcome | Why |
|---|---|---|
| `reliability-resilience.a` | `risk` | `AdjustmentWriter.applyAdjustment` has no idempotency key/unique constraint/upsert; a rerun after a partial failure (the job's own retry model — Kubernetes Jobs rerun on failure) reapplies every already-corrected adjustment on top of itself |
| `reliability-resilience.b` | `risk` | Neither `LedgerClient` nor `AdjustmentWriter` configures a connection/login/read timeout on `DriverManager.getConnection` — a slow/unavailable ledger DB has nothing isolating the job from hanging on it |
| `reliability-resilience.c` | `risk` | `AdjustmentWriter.applyAdjustment` swallows its own exception and returns `void`; `ReconciliationJob.main` increments its `adjusted` counter unconditionally right after the call, so a failed write is silently counted as a success in the run's own summary |
| `reliability-resilience.d` | `not-applicable`, citing `.a` | Same underlying non-idempotency fact as `.a` (multi-step fetch-then-write with no compensating action on partial failure) — don't double-count it from a second angle |
| `reliability-resilience.e` | `risk` | `docs/technical-vision.md` frames drift correction as a financial-reporting-risk concern, but there's no stated recovery path if the job itself fails to run for several days (no backfill/replay window documented) |
| `observability.a` | `risk` | The write path (`AdjustmentWriter`) has no traffic/error/latency/saturation signal of any kind — only an unstructured `System.out.println` |
| `observability.b` | `risk` | The one failure-recovery path that exists (`ReconciliationJob.main`'s catch block) traces to a stdout log line, no metric, and the process still exits 0 — a failed run reports as succeeded to whatever's watching the CronJob |
| `scale-requirements.a` | `risk` | No stated throughput/latency ceiling anywhere, and `docs/technical-vision.md` explicitly admits no maximum run-time is scoped |
| `scale-requirements.b` | `risk` | `docs/technical-vision.md` explicitly admits no settlement-volume growth target is scoped, distinct fact from `.a` |
| `scale-requirements.c` | `clean` | Both absences correctly carried into `scalability.a`/`performance-cost.a` below rather than scored blind |
| `scalability.a` | `risk` | `LedgerClient.fetchSettlements` is a single unpaged query per ledger per run, and `ReconciliationJob.main`'s matching loop is an O(n·m) nested scan with no index-by-settlement-ID — both fine at today's volume, neither has a growth path |
| `performance-cost.a` | `risk` | `build.gradle` declares HikariCP but nothing in the code uses it — `AdjustmentWriter`/`LedgerClient` open a new `DriverManager` connection per call, including once per mismatch inside the comparison loop, with no pooling or batching guardrail |
| `change-safety.a` | `not-applicable` | No externally-consumed API/event schema — the `adjustments` table is written, not exposed |
| `change-safety.b` | `risk` | No `sql/`/`migrations/` directory and no Flyway/Liquibase-equivalent anywhere in the repo for the `settlements`/`adjustments` schema this job depends on — no established migration convention to point to |
| `change-safety.c` | `strength` | `LedgerClient`'s fetch query uses an explicit column list (`SELECT settlement_id, amount, currency`), not `SELECT *` — forward-compatible with additive schema changes |
| `change-safety.d` | `risk` | `CHANGELOG.md`'s own "Unreleased" entry documents switching the CronJob image from a pinned digest to `:latest` — no versioned rollback path for a job whose reruns are already unsafe per `reliability-resilience.a` |
| `change-safety.e` | `risk` | No flag/config/env-based conditional path anywhere in the 4 Java source files or `deploy/cronjob.yaml` beyond the 3 fixed env vars — any change to this job ships to every run at once |
| `security-boundaries.b` | `risk` | Both `LedgerClient` and `AdjustmentWriter` fall back to a hardcoded `"changeme"` password when the secret env var is unset or empty |
| `security-boundaries.d` | `risk` | `LedgerRecord.matches` does no null-check on `amount`/`currency` before comparing fetched records from ledger DBs (a boundary this job doesn't control); a resulting `NullPointerException` is caught by the same top-level catch-all and swallowed |
| `security-boundaries.e` | `risk` | `ReconciliationJob.main` writes every mismatch unconditionally via `applyAdjustment` — no anomaly/magnitude gate before an auto-applied correction hits `ledger-mirror` |
| `data-architecture.a`–`.g` | mostly `not-applicable`/`clean` | Small, well-typed settlement schema (`BigDecimal` for amount, no PK mismatch, no sharding, no JSON-blob duplication) — nothing here is the interesting part of this fixture |
| `extensibility.a` | `not-applicable` | No "how to add X" pattern doc to test against |
| `extensibility.b` | `risk` | `LedgerClient` and `AdjustmentWriter` independently reimplement near-identical connection-setup boilerplate (same URL/password-fallback pattern, no shared helper) — the same shape of inconsistency `.a` looks for, found without a pattern doc |
| `extensibility-requirements.a`/`.b` | `risk` | Mandatory for `batch-job` (no override); no future ledger pairs, integrations, or extension-cost bar named anywhere |
| `vision-alignment.a` | `clean` | `docs/technical-vision.md` exists and states real rationale, not boilerplate |
| `vision-alignment.b` | `risk` (or `plausibly risk`) | The vision doc explicitly states an adjustment "should never be applied twice" — directly contradicted by `AdjustmentWriter`'s actual non-idempotent implementation; same core fact as `reliability-resilience.a` viewed against a specific written promise, not a duplicate the way `.d` above would be |
| `maintainability.a` | `clean` or low-severity `risk`, **not** `not-applicable` | Thin history at this fixture's scale — see evaluation-rubric.md's thin-history guidance (added after `template-lib`'s cold run) |
| `maintainability.b` | `not-applicable` | No pattern-doc adoption question here |

**Anything a cold run finds that isn't listed here and is backed by real evidence** should be
trusted over this table, not dismissed to protect it — this fixture wasn't reviewed by a second
person before being used as a benchmark, so a genuine miss here is possible.

## System-type classification

Expect `system_type: "batch-job"`, high confidence: `deploy/cronjob.yaml` is a Kubernetes `CronJob`
with a `schedule`, `concurrencyPolicy: Forbid`, and `backoffLimit: 0` (positive scheduled-job
evidence, not just absence of a server); `ReconciliationJob.main` runs one pass and returns, no
listener, no loop, no `bin`/interactive CLI entry; README explicitly states "not run interactively
... no HTTP endpoint, no long-running process."

## Actual first-run result

Cold, no-memory agent (`Skill` tool didn't have this plugin registered in that session, so the
agent followed `SKILL.md`/`references/*.md` manually and ran the real `scripts/*.py` helpers rather
than reimplementing their logic — same effective coverage, just not through the `Skill` tool
itself), `full` mode. `system_type` classified `batch-job`, confidence **high** — matched, citing
the `CronJob` manifest, the README's explicit "not run interactively" framing, and
`ReconciliationJob.main`'s single-pass-then-exit shape. `validate_findings.py`: `OK (34 findings, 37
checks, 0 warnings)` after two rounds of fixes (first run used the outer repo as `--repo-root`
instead of the fixture root, producing 46 spurious path errors; second run needed
`searches_performed` added to 3 negative-search evidence entries) — both are agent-execution
corrections, not rubric-wording gaps. 100% coverage (37/37 mandatory checks, `batch-job`'s override
set is empty so all 37 apply), debt index 10/100 (Critical).

Every row in the table above now matches the actual run **except this table was originally wrong
in 8 places**, all corrected above after independently verifying `findings.json`'s evidence:
`reliability-resilience.b`/`.c`, `change-safety.b`/`.c`/`.e`, `extensibility.b`, and
`security-boundaries.d`/`.e` were all originally predicted `not-applicable`/`clean` but the cold run
found real, evidence-backed findings for each (unconfigured DB timeouts, a silently-incorrect
success counter, no migration convention at all, a forward-compatible explicit-column `SELECT`, no
gradual-rollout path, duplicated connection boilerplate across two classes, and no anomaly gate
before an auto-applied financial correction, respectively). No rubric-wording gap surfaced this
time — these were genuine misses in this hand-written table, not a rubric or fixture defect, and
are corrected in place per this repo's own "trust real evidence over the table" rule rather than
left standing.
