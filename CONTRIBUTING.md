# Contributing

Issues and PRs are welcome — rubric wording fixes, new system-type coverage, bug reports against
real runs, and new fixtures are all useful contributions.

## Where things live

- `skills/architecture-debt-visualizer/SKILL.md` — the workflow entry point.
- `skills/architecture-debt-visualizer/references/*.md` — the actual rubric prose (evidence
  standard, evaluation rubric, system classification, report schema). Most substantive
  contributions are edits here.
- `skills/architecture-debt-visualizer/scripts/*.py` — deterministic, zero-third-party-dependency
  helpers (`validate_findings.py`, `generate_report.py`, `extract_dep_graph.py`,
  `analyze_churn.py`). If you change what a script enforces, update the reference doc it enforces
  in the same PR — they're meant to stay in sync, not diverge into two sources of truth.
- `examples/` — fixtures used to validate rubric changes (see below).
- `docs/validation.md` — the methodology and every fixture's writeup.

## Validating a rubric change

This project's discipline, established over many rounds of real testing: **don't validate a
rubric change by reasoning about the prose — cold-test it.**

1. Make the change to a `references/*.md` file (and `rubric_manifest.json` if it affects
   check IDs or applicability).
2. Run the skill against a real or fixture repo with a **fresh agent that has no memory of the
   change you just made** — a subagent with no prior context, not the same conversation that
   wrote the change.
3. Independently re-derive the result from the raw `findings.json`/`checks.json` — don't trust the
   agent's own self-reported summary of what it found. Run `scripts/validate_findings.py`
   yourself against the output.
4. If the cold run surfaces friction (ambiguous wording, a missing worked example, a check that
   doesn't say what an absence should score as), fix the wording immediately and note it in
   `docs/validation.md`'s writeup for that fixture — expect nearly every new fixture to surface at
   least one real gap this way.

## Adding a new fixture

- Keep the fixture's own docs/README purely in-universe — no meta-framing ("this tests X"), no
  planted-issues table inside the fixture itself. That circularity has bitten this project before:
  a scoped run reads the fixture's own docs as part of normal doc discovery, so any answer key
  living inside the fixture partially invalidates the test.
- The golden spec (what a good run should find) goes in a matching `examples/<name>.expected.md`
  file **outside** the fixture directory, never inside it.
- Prefer a fixture that isolates one specific thing this repo doesn't yet have coverage for
  (a `system_type`, an evidence-handling edge case, a false-positive risk) over a generic "more
  debt" fixture — see `docs/validation.md` for what's already covered.

## Code of conduct

Be respectful. Assume good faith. Disagreements about rubric wording are welcome and expected —
that's how this project's rubric has actually improved so far.
