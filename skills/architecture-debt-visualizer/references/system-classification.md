# System context classification

Run this before the evaluation pass (step 1.5 of `SKILL.md`), whenever the run includes an
evaluation pass (`evaluate` or `full` mode). It exists because a missing QPS target means
something completely different on a payments service than on a CLI tool — treating every repo as
a production, revenue-critical system (this skill's original test bed) over-penalizes prototypes,
libraries, batch jobs, and archived code.

## What to record

Write `context.json` in the run directory:

```json
{
  "system_type": "production-service",
  "criticality": "financially-critical",
  "lifecycle": "active",
  "deployment_model": "multi-instance-service",
  "data_sensitivity": "financial",
  "expected_scale": "unknown",
  "confidence": "medium",
  "classification_evidence": [
    "src/main/resources/application.properties defines HTTP server port and multiple message consumers — a running service, not a library",
    "No explicit scale target found in docs, so expected_scale is 'unknown' not a guess"
  ]
}
```

- `system_type` — one of `production-service`, `library`, `cli-tool`, `batch-job`, `prototype`,
  `archived`. Pick evidence-first: a server/listener/consumer entry point and a deployment
  manifest → `production-service`; a packaged/published artifact with a public API surface and no
  server → `library`; an entry point with a `main`/`bin` and no long-running process → `cli-tool`;
  a scheduled job with no HTTP surface → `batch-job`; explicit `WIP`/`experimental`/`spike`
  language in the README or a very recent, thin commit history → `prototype`; a repo whose README
  or last commits say it's deprecated/frozen/superseded → `archived`.
- `criticality` — free text, e.g. `financially-critical`, `internal-tooling`, `customer-facing`,
  `low-stakes`. Informational, not used for applicability gating today.
- `lifecycle` — `active`, `maintenance`, or `archived` (redundant with `system_type: archived` in
  the common case, but a repo can be `production-service` + `maintenance`).
- `deployment_model` — `multi-instance-service`, `single-instance`, `serverless`, `library-consumed`,
  `not-deployed` (prototype/library).
- `data_sensitivity` — `financial`, `pii`, `internal-only`, `none`/`unknown`. Informational.
- `expected_scale` — the actual number if step 1's scale-requirements check found one, otherwise
  literally `"unknown"` — never a guessed figure.
- `confidence` — `high`/`medium`/`low`, your own confidence in `system_type`.

## Default on low confidence: `production-service`

**If `confidence` is `low`, or you genuinely can't tell, classify as `production-service` anyway
and say so in `classification_evidence`.** This is a deliberate strictness default, not laziness:
this skill's whole track record was built and validated against a real production fintech system,
and defaulting an uncertain repo to a *lenient* tier would silently weaken scrutiny for the common
case this skill actually exists to serve. Leniency is earned by positive evidence of a smaller
blast radius (a library, a CLI tool, a prototype), never assumed by default.

## How applicability changes downstream

`scripts/rubric_manifest.json`'s `system_type_overrides` maps `(system_type, dimension)` to
`informational` where a dimension's absence-based checks shouldn't count as a `risk` for that kind
of system. Any pair not listed there — including everything for `production-service`, and
everything for any `system_type` this file doesn't cover — stays `mandatory`, the strict default.

When a dimension is `informational` for the classified `system_type`:
- An absence that would be a `risk` finding at `mandatory` becomes a `strength`-neutral
  `not-applicable` or a `clean`-with-note coverage record instead — record it in `checks.json`
  either way, just don't classify it as `risk`.
- Say so explicitly in the finding/coverage note: *"No stated throughput target — expected for a
  `cli-tool`, not counted as a risk here"* is the kind of sentence that should appear, not a
  silently-dropped check.
- `checks.json`'s coverage-record requirement (every *mandatory* check needs a record) does not
  relax for `informational` checks — you can still run them and record what you found, it just
  doesn't count toward the audit-coverage denominator and an absence doesn't get penalized as a
  `risk`.

## Worked example

A single-file CLI utility with no server, no scale claims anywhere, and a `bin` entry in its
`package.json`: `system_type: cli-tool`, `confidence: high` (clear positive evidence — packaged
CLI entry point, no listener anywhere). Under `cli-tool`'s overrides, `scale-requirements` and
`observability` become `informational` — no stated QPS target here is not a finding, and no
metrics/logging is not a finding either. `data-architecture` and `extensibility` stay `mandatory`
(nothing about being a CLI tool excuses a bad data model or a hard-to-extend command structure).
