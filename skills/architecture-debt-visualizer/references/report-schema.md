# Output schemas — findings.json, checks.json, context.json

Write these to the run directory (`SKILL.md` step 3's `mktemp -d`). `context.json` and
`checks.json` are new; `findings.json` is the original schema plus the fields described in
`evidence-standard.md`. All three are optional inputs to `generate_report.py` except
`findings.json` — a `reconcile`-mode run legitimately has no `checks.json`/`context.json` at all,
and old reports generated before this schema existed have none of the new fields; the report
renders correctly either way, just with fewer indicators populated.

## `context.json` (evaluate/full modes only)

See `system-classification.md` for the full field meanings and the classification procedure.

```json
{
  "system_type": "production-service",
  "criticality": "financially-critical",
  "lifecycle": "active",
  "deployment_model": "multi-instance-service",
  "data_sensitivity": "financial",
  "expected_scale": "unknown",
  "confidence": "medium",
  "classification_evidence": ["..."]
}
```

## `checks.json` (evaluate/full modes only)

One entry per mandatory (and optionally, non-mandatory) check from `scripts/rubric_manifest.json`.

```json
{
  "checks": [
    {
      "id": "observability.a",
      "dimension": "observability",
      "status": "risk",
      "scope": ["OrderEventConsumer"],
      "confidence": "high",
      "finding_id": "f17"
    },
    {
      "id": "observability.b",
      "dimension": "observability",
      "status": "clean",
      "scope": ["OrderEventConsumer"],
      "confidence": "high",
      "evidence": [{"file": "src/main/java/.../OrderMetrics.java", "line": 38}]
    },
    {
      "id": "scalability.a",
      "dimension": "scalability",
      "status": "not-applicable",
      "scope": ["serverless-handler"],
      "reason": "No long-lived worker pool exists — request concurrency is managed by the platform, not app config."
    }
  ]
}
```

- `id` — must match an id in `scripts/rubric_manifest.json`.
- `status` — `risk` / `strength` / `clean` / `not-applicable` / `not-assessed`.
- `scope` — free-text array naming what the check was actually run against: a class/file name for
  a code-scoped check (`"OrderEventConsumer"`), a doc path for a doc-scoped check
  (`"docs/technical-vision.md"`), or a component/deployment-unit label when neither applies
  (`"serverless-handler"`). Not the same namespace as `findings.json`'s `packages` field (which is
  specifically dotted package IDs matching `dep_graph.json` node names) — `scope` is looser and
  exists for human readability in the report, not for cross-referencing against the dep graph.
- `finding_id` — required when `status` is `risk` or `strength`; must match a `findings.json`
  entry's `id`.
- `evidence` — required when `status` is `clean` (what you looked at to conclude "nothing here").
- `reason` — required when `status` is `not-applicable` or `not-assessed`.

**`not-applicable` vs. `clean` — the line is whether the underlying concept exists in this repo at
all, not whether the result was good.** `clean` means the thing the check is about *exists* here
and you looked at it and found no issue — e.g. `data-architecture.e` (type choices) is `clean` on a
repo that has monetary fields and uses the correct decimal type for them. `not-applicable` means
the thing the check is about *doesn't exist* here to check in the first place — the same
`data-architecture.e` is `not-applicable` on a repo with no monetary/quantity fields anywhere, since
there's no type-choice decision to have gotten right or wrong. Don't force `clean` onto a check that
had nothing to actually examine.

## `findings.json`

```json
{
  "title": "Architecture Debt Report — <repo/doc name>",
  "doc_sources": ["docs/boundaries.md", "README.md"],
  "findings": [
    {
      "id": "f1",
      "claim": "Kafka consumer failures on the order-events channel are dropped, not sent to a DLQ",
      "doc_source": "docs/boundaries.md",
      "doc_location": "Kafka consumers table, order-events-fulfilled row",
      "classification": "confirmed",
      "dimension": "correctness",
      "severity": "info",
      "packages": ["com.example.app.consumer"],
      "evidence": [
        {"file": "src/main/java/.../OrderEventConsumer.java", "line": 42, "note": "failure-strategy=ignore annotation, no DLQ producer"}
      ],
      "explanation": "Code matches: the consumer's @Incoming annotation sets failure-strategy=ignore and there is no -dlq producer anywhere in the consumer package.",
      "confidence": "high",
      "evidence_type": ["direct-code", "configuration"],
      "limitations": []
    },
    {
      "id": "f2",
      "check_id": "data-architecture.a",
      "claim": "Order's JPA @Id doesn't match its real (composite, partitioned) DDL primary key",
      "doc_source": "docs/data-model.md",
      "doc_location": "Entities by domain > Orders",
      "classification": "risk",
      "dimension": "data-architecture",
      "severity": "high",
      "packages": [],
      "evidence": [
        {"file": "sql/0007-Order.sql", "line": 93, "note": "PRIMARY KEY (`CompletedDate`, `OrderId`)"},
        {"note": "entity source lives outside this repo (published dependency) — doc states JPA @Id orderId only, a single column"}
      ],
      "explanation": "Hibernate's identity/equality/caching model is keyed on orderId alone while the real relational key is composite. Two rows with the same orderId but different completedDate would collide as 'the same entity' from the ORM's point of view.",
      "recommendation": "Confirm whether this has ever caused a merge/cache collision in production; if the composite key is load-bearing, map it as an @IdClass/@EmbeddedId instead of a single @Id.",
      "confidence": "high",
      "evidence_type": ["schema", "external-dependency"],
      "limitations": ["Order entity source lives in a published dependency, not this repo — mapping verified from the compiled artifact's javadoc, not source."],
      "finding_type": "architecture-risk",
      "impact_area": ["data-integrity", "correctness"]
    }
  ]
}
```

New/changed fields since the original schema:

- `check_id` — optional, links an evaluation-pass finding back to its `scripts/rubric_manifest.json`
  id (matches `checks.json`'s `id` for the same finding). Reconciliation findings don't have one.
- `confidence`, `evidence_type`, `limitations` — see `evidence-standard.md`. Optional but strongly
  recommended on every finding; required in practice by `validate_findings.py` only where the
  finding is absence-based (see `searches_performed` below).
- `searches_performed` — required (by `validate_findings.py`) on any finding whose evidence is a
  negative search rather than a positive citation (i.e., an `evidence` entry with a `note` and no
  `line`). Array of what was actually searched.
- `finding_type` — optional. One of `doc-code-contradiction`, `undocumented-component`,
  `missing-requirement`, `architecture-risk`, `architecture-strength`, `planned-but-unimplemented`,
  `stale-reference`, `coverage-limitation`. Sharper than `classification` alone — `gap` covers
  several structurally different situations (undocumented code vs. a missing requirement vs. an
  unimplemented planned feature), and this field disambiguates which one a given finding actually
  is.
- `impact_area` — optional array from: `correctness`, `availability`, `operability`,
  `delivery-speed`, `cost`, `security`, `data-integrity`, `change-safety`, `compliance`. Answers
  "why does this matter to engineering leadership," not just "what kind of architectural concern is
  this" (which `dimension` already answers).

`packages` should list the Java package(s) (matching node IDs from `dep_graph.json`) most relevant
to the finding, for context and to make it easy to cross-check against the static-analysis panel's
coupling/churn numbers by hand — the report doesn't currently auto-cross-reference it, so treat it
as useful metadata, not a required field. Leave it empty if the finding doesn't map to one package.
`dimension` and `severity` are required on every finding (reconciliation findings default to
`dimension: correctness`, `severity: info`); `recommendation` is required for any `risk` finding
rated `medium` or higher.

See `evidence-standard.md` for the full rules on `claim`/`doc_source`/`doc_location` non-emptiness
and the phrasing rule.
