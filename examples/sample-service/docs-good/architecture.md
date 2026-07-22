---
last-generated: 2026-06-01
sources:
  - src/main/java/com/example/tasks/**
---

# Architecture

The tasks service is a small REST + messaging backend for creating, tracking, and reminding on
tasks.

Clients create and fetch tasks over REST, including a bulk-import path for backfilling tasks from
external sources. Two independent message channels feed the service: task lifecycle events
(`task-events`) and due-reminder triggers (`task-reminders`). A scheduled job periodically archives
old completed tasks into partitioned storage.

## Key Components

| Component | Responsibility |
|---|---|
| `resource/TaskResource` | REST API: create, fetch, and bulk-import tasks |
| `consumer/TaskEventConsumer` | Handles task lifecycle events from `task-events` |
| `consumer/TaskReminderConsumer` | Handles due-reminder triggers from `task-reminders` |
| `scheduler/TaskCleanupJob` | Archives old completed tasks on a schedule |

## Data Flow

1. **Create/fetch** — synchronous REST calls against `TaskResource`, backed by `TaskRepository`.
2. **Lifecycle events** — `task-events` messages update task state asynchronously; failures are
   dropped (`failure-strategy=ignore`), not retried, per the same tradeoff described in
   [Technical Vision](technical-vision.md).
3. **Reminders** — `task-reminders` messages trigger reminder notifications for incomplete tasks
   past their due date; same drop-on-failure behavior as the events channel.
4. **Archival** — `TaskCleanupJob` runs hourly and moves old completed tasks into partitioned
   storage (see [Data Model](data-model.md) for the partitioning scheme and its current limits).
