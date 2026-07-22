# Boundaries

Complete I/O map for the tasks service.

## HTTP API

| Endpoint | Description |
|---|---|
| `POST /api/v1/tasks` | Create a task |
| `GET /api/v1/tasks/{id}` | Fetch a task |

## Message Consumers

| Channel | Description |
|---|---|
| `task-events` | Task lifecycle events. Failures are dropped (failure-strategy=ignore), best-effort delivery. |
