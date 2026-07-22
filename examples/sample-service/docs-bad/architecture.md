# Architecture

The tasks service is a small REST + messaging backend for creating and tracking tasks.

Clients create and fetch tasks over REST. Task lifecycle events arrive over a message queue and
are handled by `TaskEventConsumer`. A scheduled job periodically archives old completed tasks.

## Key Components

| Component | Responsibility |
|---|---|
| `resource/TaskResource` | REST API for creating and fetching tasks |
| `consumer/TaskEventConsumer` | Handles task lifecycle events from the queue |
| `scheduler/TaskCleanupJob` | Archives old completed tasks on a schedule |
