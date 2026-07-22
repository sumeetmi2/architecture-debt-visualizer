---
last-generated: 2026-06-01
sources:
  - src/main/java/com/example/tasks/resource/**
  - src/main/java/com/example/tasks/consumer/**
  - src/main/resources/application.properties
---

# Boundaries

Complete I/O map for the tasks service.

## HTTP API

| Endpoint | Description |
|---|---|
| `POST /api/v1/tasks` | Create a task |
| `GET /api/v1/tasks/{id}` | Fetch a task |
| `POST /api/v1/tasks/bulk-import` | Bulk-create tasks from an external source |

## Message Consumers

| Channel | Description |
|---|---|
| `task-events` | Task lifecycle events. Enabled by default. Failures are dropped (failure-strategy=ignore), not retried or dead-lettered. |
| `task-reminders` | Due-reminder triggers. Enabled by default. Same drop-on-failure behavior as `task-events`. |

Both channels' failure handling is a deliberate tradeoff, not an oversight — see
[Technical Vision](technical-vision.md).
