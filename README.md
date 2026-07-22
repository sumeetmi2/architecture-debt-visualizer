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

Tested against a real, private production monorepo (multi-module Java/Gradle, reactive +
batch microservices, financial domain — name withheld, not affiliated with this project) rather
than a toy example, using a cold-testing methodology: fresh Claude Code agents with zero memory of
prior runs or of each other, given only the repo and a request to run the skill, so results reflect
what someone installing this cold would actually get.

**Reliability, before vs. after tuning the rubric:**

| | Before | After |
|---|---|---|
| Score range across identical-scope runs | 68 points (12-80) | 13 points (28-41) |
| Finding-count range across identical-scope runs | 17 (11-28) | 6 (30-36) |
| Per-dimension checklist coverage | ad hoc, agent's own judgment | 7/7 mandatory sub-checks hit, 3 runs straight |

Every high-severity finding from a deep, human-guided reference pass was independently
rediscovered by cold agents that never saw that reference — including cases where two separate
agents, given the identical prompt and scope, found the exact same issue via different evidence
paths.

**Representative findings** (patterns, not verbatim — specifics of the tested repo are withheld):

- A shared internal library was quietly extracted from the repo into an external package
  dependency; five separate documentation pages still described it as in-repo source, including
  frontmatter citing a file path that had been deleted weeks earlier.
- An entire message-queue consumer existed in production code with zero documentation, silently
  invalidating a doc's own "here is the complete list" claim elsewhere.
- A core database table's date-based partitioning was hardcoded to run out within months, with no
  automated job anywhere in the codebase to extend it — a scaling cliff with a forecastable date.
- A live, traffic-serving code path had solid request/error counters but no latency or backlog
  signal, while a *disabled*, dormant sibling path was fully instrumented — the reverse of where
  observability investment should have gone.
- A "distinct contributor count" signal that looked like healthy shared ownership was actually one
  person dominating every package it flagged — invisible unless you cross-check the raw commit
  data instead of trusting the aggregate.

## License

MIT — see [LICENSE](LICENSE).
