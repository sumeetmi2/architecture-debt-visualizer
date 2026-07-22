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

This is intentionally small (~10 files) so a cold run stays fast, not a realistic-scale production
codebase — treat the specific finding *count* as illustrative, not as a benchmark for what a real
repo should produce.
