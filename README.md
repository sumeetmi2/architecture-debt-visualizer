# architecture-debt-visualizer

A Claude Code skill that reconciles a repo's design docs against its actual code, then evaluates
the architecture itself the way a senior/staff architect would — scalability, extensibility,
long-term maintainability, performance/operational cost, data-architecture, observability, and
whether the implementation still serves the product's stated technical vision.

Produces a self-contained, scored HTML report: a static-analysis panel (dependency coupling, git
churn, contributor/bus-factor signals), a curated shortlist of the most pressing findings, and a
full findings table filterable by classification and evaluation dimension.

## What it does

1. **Reconciliation** — extracts checkable claims from your docs (`docs/*.md`, Mermaid diagrams,
   READMEs) and verifies each against the real code: confirmed, misaligned, or a gap.
2. **Evaluation** — independent of any doc claim, judges the architecture on its own merits across
   7 dimensions using a fixed rubric (not open-ended "look around"), so results are reproducible
   run to run: scalability, extensibility, maintainability, performance/cost, data-architecture,
   observability, vision-alignment.
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

## Validation

### Methodology

Tested against a real, private production monorepo (multi-module Java/Gradle, reactive + batch
microservices, financial domain — name withheld, not affiliated with this project) rather than a
toy example. Terms used below:

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

## License

MIT — see [LICENSE](LICENSE).
