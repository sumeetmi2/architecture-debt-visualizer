# Technical Vision

## Scale & Extensibility Targets

- **Target load**: 200 requests/second peak across all three HTTP endpoints combined; 50
  messages/second sustained on each of `task-events` and `task-reminders`. Expected growth: 3x
  within 12 months as the reminder feature rolls out to all users, not just the current beta cohort.
- **Latency budget**: p99 under 300ms for the synchronous REST endpoints; no hard SLA on message
  processing latency today (deliberately — see the drop-on-failure tradeoff below), but a 5-second
  p99 is the informal internal expectation.
- **Extensibility target**: the team expects to add one new message channel per quarter for the
  next year (task-assigned, task-overdue, task-escalated are the named candidates) and wants each
  addition to take under a day of engineering time given the existing pattern.

## Design Philosophy

The tasks service favors availability over strict delivery guarantees on its message channels: a
failed event is dropped rather than retried or dead-lettered, on the assumption that missing a
single lifecycle update or reminder is low-cost compared to blocking the queue. This tradeoff is
deliberate and revisited if drop rates ever become visible in practice — there is currently no
metric confirming the actual drop rate, which is itself tracked as a gap.

## Key Architectural Decisions

- **Two independent consumers, not one.** `task-events` and `task-reminders` are handled by
  separate consumer classes even though both are "task updates," because they have different
  failure semantics and different downstream effects (state change vs. notification send). Keeping
  them separate means one channel's throughput problems don't block the other.
- **Composite, partitioned key on `Task`.** Partitioning by `CreatedDate` keeps the archival job
  (`TaskCleanupJob`) cheap — it only has to touch old partitions, not scan the whole table. The
  known JPA `@Id`/DDL mismatch (see [Data Model](data-model.md)) is an accepted, tracked risk from
  this decision, not an oversight.

## Future Direction

- **Recurring tasks** are the next planned feature — a task that reschedules itself on completion
  instead of being created fresh each time. This will need a new relationship between `Task` rows
  across cycles that the current schema doesn't model yet; expect this to be a real test of whether
  the current partition/identity design holds up under a new access pattern.
- The partition list in `sql/001-task.sql` needs an automated extension job before it runs out —
  not yet built. Tracked as near-term work, not a someday-maybe.
