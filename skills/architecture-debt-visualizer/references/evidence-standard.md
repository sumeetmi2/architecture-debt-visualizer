# Evidence standard

Applies to every finding in both passes. `scripts/validate_findings.py` hard-enforces the
mechanically-checkable parts of this (schema, required fields, evidence-file existence); the rest
requires your own judgment and can't be fully automated.

## Non-negotiable rules

- **Every finding needs cited evidence.** A classification without a `file:line` (or explicit
  "searched X, Y, Z and found nothing" for a Gap/Risk) is not a finding — go verify it or drop it.
- **Verify data-architecture claims against the actual DDL/schema files, not a doc's prose
  description of them.** A doc's own claim about its schema is exactly the kind of thing this
  skill exists to check — don't cite it as its own evidence.
- **Don't invent claims the doc doesn't make**, and don't invent architectural risk where none
  exists — every `risk` finding needs the same evidence bar as a `misaligned` finding. Speculation
  ("this might not scale") isn't a finding; a concrete mechanism ("fixed worker-count=1 with no
  documented horizontal-scaling path, and no distributed locking if that assumption ever breaks")
  is.
- **A Gap is architecturally significant code with no doc mention** (a whole consumer, a whole
  external integration, a call path that crosses a boundary) — not every undocumented private
  method. Use judgment; low-value gaps drown the signal.
- **Static-analysis signals (churn, dependency graph) are for prioritization only.** They never
  produce a finding by themselves — they help you decide which findings to spend more time
  verifying and which to surface first in the summary. Churn is also a scalability/maintainability
  signal in its own right: a high-churn package with fragile patterns (duplicated logic, no tests)
  is a materially higher-priority risk than the same pattern in dead code.
- Scripts in `scripts/` are deterministic helpers (no LLM judgment) — run them, don't reimplement
  their logic by hand.
- **Don't modify the audited repository.** This skill reads and reports; it never edits the code,
  docs, or config it's evaluating.

## Confidence, evidence type, and limitations

Not all evidence carries equal weight — a direct call-site citation is stronger than an inferred
conclusion from a package import; a DDL-plus-entity-mapping mismatch is stronger than a guess from
class names; a three-search negative result is stronger than "I didn't notice it." Say so on every
finding:

```json
{
  "confidence": "high",
  "evidence_type": ["direct-code", "schema", "configuration"],
  "limitations": []
}
```

- `confidence` — `high` / `medium` / `low`. `high` for a direct code citation that unambiguously
  supports the claim; `medium` for a correct-but-indirect inference (e.g. import-graph coupling
  without confirming call semantics); `low` for anything resting on an assumption you couldn't
  verify in-repo.
- `evidence_type` — array from: `direct-code`, `schema`, `configuration`, `git-history`,
  `negative-search`, `external-dependency`, `runtime-only`.
- `limitations` — free-text array, e.g. `["Runtime infrastructure configuration is not stored in
  this repository."]`. Empty array if none.

**For any finding built on an absence** (a negative search — "no DLQ producer exists," "no metric
found") — record what you actually searched, not just the conclusion:

```json
{
  "confidence": "medium",
  "evidence_type": ["negative-search"],
  "searches_performed": [
    "grep for DLQ producers across the consumer package",
    "searched messaging configuration for dead-letter topic config",
    "searched deployment manifests for a DLQ resource — none exist in this repo"
  ],
  "limitations": [
    "Runtime infrastructure configuration is not stored in this repository."
  ]
}
```

This distinction matters because it's the difference between two very different claims: **"No
horizontal scaling path exists"** (a strong, repo-wide negative claim) versus **"No horizontal
scaling configuration exists in this repository; deployment manifests were unavailable"** (a
narrower, defensible one). The second is what most absence-based findings actually are — say the
narrower thing, backed by what you actually searched, rather than the sweeping one.

## Phrasing rule for `claim` — an unresolved positive hypothesis must be visibly marked as one

For an evaluation-pass finding with no doc quote to react to, there are two acceptable ways to
phrase `claim`, and one unacceptable one:

- **Preferred: state the concern or fact directly**, as a declarative sentence — "Payment-event
  consumer concurrency is hardcoded to 1 with no env override, on the always-enabled revenue path"
  rather than "the payment consumer can absorb load increases without a config change." This is
  usually the clearer choice and matches how a reconciliation finding with a real doc quote reads.
- **Acceptable: phrase it as the hypothesis being tested, but prefix it** with `(Architectural
  evaluation)` (or `(Implicit)` for a reconciliation-pass finding inferred from a doc's silence
  rather than a direct quote) — "(Architectural evaluation) The system has a written technical
  vision explaining why it's shaped the way it is." The prefix is what makes this safe: it tells a
  skimming reader "this is a claim under test, not an assertion," so the badge/explanation
  resolving it negatively doesn't read as a surprise reversal.
- **Never**: a hypothesis-phrased claim with no prefix and no doc quote behind it. On a skim of the
  key-findings list, every one of these reads as a *confirmed strength* rather than the risk it
  actually is, and a reader has to open the badge and explanation to discover the reversal. That
  defeats the point of a findings report, which exists to be scannable. **This is a known,
  recurring regression in past runs of this skill** — the instruction alone hasn't reliably
  prevented it without an explicit self-audit step; `validate_findings.py` now flags likely-bare
  positive hypotheses as a warning (not a hard block — this needs semantic judgment a script can't
  fully make) specifically because the prose rule alone wasn't enough.

Pick one of the two acceptable styles and use it consistently for the whole report — don't mix
prefixed-hypothesis and bare-hypothesis phrasing, since the bare form is only safe when every claim
around it is *also* stated as a direct fact and the reader can trust that convention throughout.

## Required fields, always

`claim`, `doc_source`, and `doc_location` must always be non-empty strings, never `null` or
omitted — `generate_report.py` treats a missing key and an explicit `null` the same (defaults to
empty), so this won't crash the report either way, but empty cells read as broken output.
Reconciliation-pass findings have a natural claim from the doc; for evaluation-pass findings
(`risk`/`strength` with no specific doc claim prompting them) write a short synthesized `claim`
describing what's being evaluated, and set `doc_source`/`doc_location` to the most relevant doc if
one exists, or the literal string `"no explicit doc claim — evaluated directly against code"` if
none does.

`recommendation` is required for any `risk` finding rated `medium` or higher — not "this is a
risk," but the concrete next step an architect would actually tell the team to take.
