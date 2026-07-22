# Expected result: `minimal-cli-tool`

Deliberately kept **outside** `examples/minimal-cli-tool/` — a run scoped to that directory reads
its own `README.md` as part of normal doc discovery (`SKILL.md` step 1: "README.md at repo root"
of the scoped target), so stating the expected classification inside the fixture itself would make
the classification test partially circular (a real cold-run agent flagged exactly this during
Phase B validation of the system-classification feature). This file is the golden spec instead —
consumed by a human reviewer and by `skills/architecture-debt-visualizer/evals/cases.yaml`, never
by the agent under test.

`examples/minimal-cli-tool/` is a ~2-file Java CLI fixture built to test
**system-context classification** (`references/system-classification.md`): the skill should
classify this repo as `system_type: cli-tool` and, per `scripts/rubric_manifest.json`'s
`system_type_overrides`, should **not** flag the complete absence of a stated throughput/QPS
target, latency SLO, or observability instrumentation as a `risk` the way it would (correctly) on
`examples/sample-service`, a production service.

## What "pass" looks like

A run against this fixture should:
- Classify `system_type: cli-tool` (or `library`) with `confidence: high` — the evidence is
  explicit and unambiguous (`main()` entry point, no server/listener/consumer anywhere, and
  `docs/technical-vision.md` states outright that there's no throughput concept for this tool) —
  **derived from the code and docs, not asserted** (see the circularity note above).
- **Not** produce a `risk` finding for a missing scale-requirements target or missing
  observability instrumentation — those checks should resolve `not-applicable` (or the dimension's
  `informational` note) in `checks.json`, not `risk` in `findings.json`.
- Still evaluate the dimensions that aren't overridden for `cli-tool` — extensibility,
  maintainability, vision-alignment, data-architecture (expected to resolve mostly
  `not-applicable` here too, since there's no schema/database at all — that's a legitimate,
  distinct outcome from "missing and undocumented").

## First real run result (Phase B validation, cold agent, no memory of this file)

Passed. Classified `cli-tool`/`high confidence` from real evidence (grepped for server/listener/
consumer code, found none; `build.gradle` uses the `application` plugin, ruling out `library`).
`scale-requirements.a/b/c` and `observability.a/b` all resolved `not-applicable`, not `risk`.
Audit coverage 16/16 mandatory checks = 100%. 9 findings total (5 reconciliation `confirmed`, 2
`extensibility-requirements` risks, 1 `extensibility` risk, 1 `vision-alignment` strength) — see
`examples/minimal-cli-tool/report-v2skill.html`.

The same run flagged two real rubric gaps worth carrying into Phase D/C:
- `extensibility-requirements.a` bundles "named future use cases" and "a stated timeline" as one
  check — this fixture's vision doc names candidates (JSON5, YAML, `--compact`) with no timeline,
  a partial match the rubric doesn't say how to score. The agent treated it as a low-severity risk
  rather than a full pass/fail; worth an explicit rule in `evaluation-rubric.md`.
- Several checks (`maintainability.b`, `extensibility.b`) assume at least two instances exist to
  compare for inconsistency. A true single-behavior repo has zero/one instances, which the agent
  correctly reasoned through to `not-applicable`, but the reference docs don't say that
  explicitly — worth adding a line covering the "fewer than 2 instances exist" case.
