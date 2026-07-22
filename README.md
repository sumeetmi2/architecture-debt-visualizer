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
/plugin marketplace add <your-github-owner>/architecture-debt-visualizer
/plugin install architecture-debt-visualizer@architecture-debt-visualizer
```

## Use

In any repo, ask Claude Code something like:

> Can you evaluate our architecture and check if the docs are still accurate?

The skill triggers automatically on phrases like that, or invoke it explicitly. See
[`skills/architecture-debt-visualizer/SKILL.md`](skills/architecture-debt-visualizer/SKILL.md) for
the full workflow, scoring methodology, and the specific investigation techniques it applies per
dimension.

## License

MIT — see [LICENSE](LICENSE).
