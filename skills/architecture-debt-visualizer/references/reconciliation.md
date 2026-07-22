# Reconciliation pass — docs vs. code

Read this for `SKILL.md` steps 2 and 4 (`reconcile` and `full` modes only — skipped entirely in
`evaluate` mode).

## Locate the docs

Default scope: **every** `docs/` folder in the repo, not just the top-level one — a repo with
multiple deployables/modules (e.g. a monorepo with `modules/<name>/docs/`) typically has one docs
tree per component, and each one can drift independently. Find them all:

```
find . -type d -iname docs -not -path "*/node_modules/*" -not -path "*/build/*" -not -path "*/.git/*"
```

Read every `.md` file recursively under each discovered `docs/` folder, plus `README.md` at repo
root and any `*/README*.md` one level down. **Also read non-Markdown diagram sources in those
folders** — `.mmd` (Mermaid) files diff and grep cleanly, so treat them as first-class claim
sources; render/view any `.png`/`.svg`/`.excalidraw` diagrams too (the Read tool handles images
directly). If a doc states which artifact is the source of truth when diagrams disagree (Mermaid
vs. a frozen PNG export, for instance), trust that doc's stated policy — but still check the two
actually agree, because "we said the PNG shouldn't go stale" is not the same as "it hasn't."

If the user names specific doc file(s) or a narrower path, use those instead — don't silently
expand scope in that case. Note that this restriction applies to which docs are treated as
**reconciliation sources** (what claims get extracted and checked). It does not limit the
evaluation pass — that pass is fundamentally a code/config/git investigation, not a doc-reading
exercise, and techniques like "find the vision doc" or "check the pattern docs' adoption rate"
still apply and may reference docs outside the user's named scope, since the evaluation pass isn't
answering "does this named doc match the code," it's answering "is the architecture sound."

Read every doc in scope. Note the ones that look auto-generated or recently touched (e.g.
frontmatter like `last-generated:`) — those are more likely to still be accurate, which is itself
useful context when you explain a finding.

## Extract checkable claims

For each doc, pull out concrete, falsifiable architectural claims. Good claims name specific
components and a specific relationship or behavior:

- "Service A must not call Service B directly" (boundary claim)
- "All payment writes go through the ledger service" (data-flow claim)
- "The `PaymentEventConsumer` failures are dropped, not sent to a DLQ" (behavioral claim)
- "No gRPC server exists despite the generated protos" (negative/absence claim)
- "`OrderResource` handles `/api/v1/orders/calculate`" (routing claim)

Skip claims that are subjective, aspirational without a concrete referent, or already phrased as
open questions (docs sometimes literally write `(?)` — that's the doc admitting uncertainty, not
a claim to verify).

Keep a running list with: claim text, source doc, and location (line number or heading).

## Verify each claim against the code

For each claim, search the codebase (Grep/Glob/Read — whatever's fastest) for the components it
names. Confirm or contradict it with actual file/line evidence. Classify:

- **Confirmed** — code matches the claim. Cite the evidence that confirms it (don't skip this just
  because it's a positive result).
- **Misaligned** — code contradicts the claim. Cite evidence from both sides: what the doc says
  (with location) and what the code actually does (with file:line).
- **Gap** — code does something architecturally significant the doc never mentions. Cite the code
  evidence and note where in the doc you'd expect it to be mentioned (or that the doc has no
  relevant section at all).

While verifying named claims, also scan (using the dep graph / churn output as a guide) for
undocumented architecturally-significant elements — a whole consumer, an external client, a queue,
a cross-boundary call path — and log those as additional Gap findings even though no doc claim
prompted them.

**Cross-reference every finding you produce against the rest of the docs before moving on** — a
finding is also a lead. If you found an undocumented instance of something (a consumer, an
endpoint, a table), check whether any *other* doc claim assumes a fixed count or a "complete list"
that the new instance now contradicts (e.g. "all six X" becoming wrong the moment you found a
7th X) — this is frequently where the highest-confidence, easiest-to-verify findings come from, and
it's easy to miss if you treat each claim as fully independent. Similarly, if a doc's frontmatter
or body cites a specific file/module path as a source, verify that path actually exists and is
current — `git log --diff-filter=D -- <path>` and checking the actual build/dependency
configuration (`settings.gradle`/`build.gradle`/`package.json`, not the doc's description of it)
for whether that path is still part of the build has repeatedly surfaced the single highest-value
finding in past runs of this skill. Do this check whenever a doc names a specific module as
"shared" or "in-repo" — don't take the doc's word for its own architecture.

Reconciliation findings default to `dimension: correctness`, `severity: info`, except a
`misaligned`/`gap` finding you judge to actually matter architecturally, which can carry a higher
severity — see `evidence-standard.md` for the full field requirements.
