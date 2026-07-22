# sample-service

A small, deliberately-imperfect Java service used to test and demonstrate the
architecture-debt-visualizer skill. The **code never changes** between the two scenarios below —
only the documentation quality does, which is the point: it isolates what better docs actually buy
you, holding the underlying architecture constant.

- **`docs-bad/`** — a stale, incomplete doc set: two of the service's real endpoints/consumers
  are simply missing from tables that present themselves as complete, the entity/schema
  documentation makes a claim the code contradicts, and the vision doc is empty scaffolding. Running
  the skill against this scope should produce mostly `gap`/`misaligned` reconciliation findings.
- **`docs-good/`** — the same service, accurately and completely documented, including honest
  disclosure of known architectural debt (the entity/schema mismatch, the column-naming drift, the
  unmaintained partition horizon) rather than hiding it. Running the skill against this scope should
  produce mostly `confirmed` reconciliation findings — but the *same* evaluation-pass risks still
  surface, because those are judged from the code directly, independent of how well the docs
  describe it. Doc accuracy and architecture quality are different axes; this scenario pair is
  built to make that visible.

Planted issues, for reference (see inline comments in the source for exactly where):

| Issue | Where | Dimension |
|---|---|---|
| Undocumented REST endpoint (`docs-bad` only) | `resource/TaskResource.java` | correctness (gap) |
| Undocumented consumer (`docs-bad` only) | `consumer/TaskReminderConsumer.java` | correctness (gap) |
| JPA `@Id` doesn't match the real composite DDL key | `entity/Task.java` vs. `sql/001-task.sql` | data-architecture |
| Column-naming convention drift (PascalCase → camelCase) | `sql/001-task.sql` | data-architecture |
| Partition list has a hardcoded horizon, no maintenance job | `sql/001-task.sql` | data-architecture / scalability |
| Hardcoded, non-overridable worker count | `application.properties` | scalability |
| Empty vision doc (`docs-bad` only) | `docs-bad/technical-vision.md` | vision-alignment |
| No stated QPS/latency/growth target (`docs-bad` only — `docs-good` states one, so the same hardcoded worker count gets judged against a real number instead of a guess) | `docs-good/technical-vision.md` "Scale & Extensibility Targets" section, absent from `docs-bad` | scale-requirements |
| No stated future-channel timeline (`docs-bad` only) | same section, absent from `docs-bad` | extensibility-requirements |

This is intentionally small (~10 files) so a cold run stays fast, not a realistic-scale production
codebase — treat the specific finding *count* as illustrative, not as a benchmark for what a real
repo should produce.

## Persisted static-analysis signals

`analysis/dep_graph.json` and `analysis/churn.json` are committed, not regenerated per run. Both
depend only on the code and git history, not on which doc set (`docs-good`/`docs-bad`) is in scope —
since the code is identical between the two scenarios, there's nothing to gain from re-running
`extract_dep_graph.py`/`compute_churn.py` for every test. A run against either doc set reads these
two files directly instead. If the source under `src/`/`sql/` ever changes, regenerate them:

```
python3 ../../skills/architecture-debt-visualizer/scripts/extract_dep_graph.py \
  --src src --out analysis/dep_graph.json
python3 ../../skills/architecture-debt-visualizer/scripts/compute_churn.py \
  --since "180 days ago" --path examples/sample-service --out analysis/churn.json
```

## `docs-good` run

One cold run against `docs-good` (same methodology as the `docs-bad` runs above):
[`reports/docs-good-run1.html`](reports/docs-good-run1.html) — score 41/100, 45 findings (15
confirmed, 1 misaligned, 1 gap, 20 risk, 8 strength).

Notably, this run caught a real, unplanted inconsistency in the "good" docs themselves: a
Versioning & Deprecation Policy bullet claimed REST endpoints were "unversioned today," which the
code (and `boundaries.md`) directly contradicted — `TaskResource` already carries an `/api/v1/`
prefix. That's not a planted issue; it was a mistake introduced while writing the fixture, caught the
same way it would catch one in a real repo. The doc has since been corrected (see git history) — the
linked report reflects the state at the time it was generated, kept as-is rather than scrubbed, the
same way the `docs-bad` runs above kept unplanted findings intact.
