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
  `archived`, `unknown` (see below). Pick evidence-first: a server/listener/consumer entry point
  and a deployment manifest → `production-service`; a packaged/published artifact with a public API
  surface and no server → `library`; an entry point with a `main`/`bin` and no long-running process
  → `cli-tool`; a scheduled job with no HTTP surface → `batch-job`; a repo whose README or last
  commits say it's deprecated/frozen/superseded → `archived`.

  **`prototype` needs *positive* evidence, not just the absence of maturity signals.** A genuinely
  new production service can also have a thin, recent commit history — that alone doesn't make it
  a prototype, and treating it as one would wrongly suppress mandatory checks on a system that's
  about to go live. Classify `prototype` only on affirmative evidence: explicit
  `WIP`/`experimental`/`spike`/`POC`/`not for production` language in the README or docs, no
  deployment path anywhere (no manifest, no CI deploy step), mock/fixture-only integrations, missing
  persistence or operational config where the architecture would need one, or a roadmap doc that
  explicitly frames the work as validation/exploration. Thin history alone should lower your
  `confidence`, or prompt you to look for one of the above before deciding — it should never by
  itself be the deciding signal.

  **Illustrative/non-buildable teaching fixtures still classify by architectural shape, not by
  disclaimer.** A repo whose build config says "illustrative only, not buildable, nothing to
  compile or run here" but whose code has real entry points (REST resources, message consumers, a
  cron job) is still shaped like a `production-service` — classify it that way (with `confidence:
  low` if the tension is worth flagging), don't invent a "fixture"/"example" bucket. The taxonomy
  exists to size the blast radius of the *architecture*, and a teaching fixture built to demonstrate
  production-shaped debt has exactly that shape regardless of whether it's ever actually deployed —
  a "just a fixture" carve-out would also let real, deployable code dodge scrutiny by claiming the
  same disclaimer.
- `criticality` — free text, e.g. `financially-critical`, `internal-tooling`, `customer-facing`,
  `low-stakes`. Informational, not used for applicability gating today.
- `lifecycle` — `active`, `maintenance`, or `archived`. **This is the precise, primary signal for
  where a repo is in its life; `system_type: prototype`/`archived` are convenience shorthand for
  the common case where architectural shape and lifecycle point the same direction, not a second,
  competing source of truth.** A second external review correctly flagged that folding lifecycle
  concepts into `system_type` muddles two different questions (what shape is this vs. where is it
  in its life) — a repo can genuinely be `production-service` + `lifecycle: archived` (a real
  deployed service shape that's since been frozen) or `production-service` + `lifecycle: maintenance`
  (still shaped like a production service, no longer under active feature development). When
  `system_type` and `lifecycle` would point to different overrides, `lifecycle` is informational
  today (not yet wired into `rubric_manifest.json`'s applicability gating — that still keys off
  `system_type` alone) but should still be recorded honestly; don't force `system_type: archived`
  just to make the two fields agree.
- `deployment_model` — `multi-instance-service`, `single-instance`, `serverless`, `library-consumed`,
  `not-deployed` (prototype/library).
- `data_sensitivity` — `financial`, `pii`, `internal-only`, `none`/`unknown`. Informational.
- `expected_scale` — the actual number if step 1's scale-requirements check found one, otherwise
  literally `"unknown"` — never a guessed figure.
- `confidence` — `high`/`medium`/`low`, your own confidence in `system_type`.

## Genuinely can't tell: `system_type: "unknown"`, strict rules still apply

**If you genuinely can't tell what this repo is, say so honestly — set `system_type: "unknown"`,
not `"production-service"`.** An earlier version of this rule said to classify uncertain repos as
`production-service` outright. That conflated two different things: *what the repo is* (a factual
question `context.json` should answer honestly) and *how strictly to apply the rubric* (a policy
question, separate from the fact). Calling something a production service when you don't actually
have that evidence makes `context.json` misleading, even in service of a reasonable goal.

The strictness still applies — it just applies as policy, not as a fabricated fact:

```json
{
  "system_type": "unknown",
  "applicability_profile": "production-strict",
  "confidence": "low",
  "classification_evidence": [
    "No server/listener, no packaged-library manifest, no CLI entry point found — couldn't
     positively identify a shape; applying the strict production-service check set as policy
     rather than guessing a type the evidence doesn't support"
  ]
}
```

`applicability_profile` is what `scripts/rubric_manifest.json`'s `system_type_overrides` actually
keys off downstream, and it defaults to `"production-strict"` (all checks mandatory — the same
behavior `system_type_overrides` already gives any key it doesn't recognize, including
`"unknown"`, so this needs no lookup-table change). Set it to a specific `system_type`'s profile
(e.g. `"library"`) only when you have real evidence for that leniency — leniency is earned by a
positive finding of a smaller blast radius, never assumed by default or granted just because the
type is uncertain.

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
