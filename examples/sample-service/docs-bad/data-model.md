---
last-generated: 2026-01-15
sources:
  - sql/001-task.sql
  - src/main/java/com/example/tasks/entity/Task.java
---

# Data Model

## Task

The core entity. Primary key is a single `id` field (JPA `@Id`). Fields: `status`, `assigneeId`,
`priority`, `createdAt`, `completedAt`.
