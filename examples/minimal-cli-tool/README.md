# minimal-cli-tool

A ~2-file Java CLI fixture, built specifically to test the `architecture-debt-visualizer` skill's
**system-context classification** (see `references/system-classification.md`): the skill should
classify this repo as `system_type: cli-tool` and, per
`scripts/rubric_manifest.json`'s `system_type_overrides`, should **not** flag the complete absence
of a stated throughput/QPS target, latency SLO, or observability instrumentation as a `risk` the
way it would (correctly) on `examples/sample-service`, a production service.

This is the golden case for the check-coverage model's `not-applicable`/informational path: a
missing scale target here is expected and correct, not undocumented debt.

## What "pass" looks like

A run against this fixture should:
- Classify `system_type: cli-tool` (or `library`) with `confidence: high` — the evidence is
  explicit and unambiguous (`main()` entry point, no server/listener/consumer anywhere, and
  `docs/technical-vision.md` states outright that there's no throughput concept for this tool).
- **Not** produce a `risk` finding for a missing scale-requirements target or missing
  observability instrumentation — those checks should resolve `not-applicable` (or the dimension's
  `informational` note) in `checks.json`, not `risk` in `findings.json`.
- Still evaluate the dimensions that aren't overridden for `cli-tool` — extensibility,
  maintainability, vision-alignment, data-architecture (expected to resolve mostly
  `not-applicable` here too, since there's no schema/database at all — that's a legitimate,
  distinct outcome from "missing and undocumented").
