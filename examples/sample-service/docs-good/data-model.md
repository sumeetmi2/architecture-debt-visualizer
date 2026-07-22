---
last-generated: 2026-06-01
sources:
  - sql/001-task.sql
  - src/main/java/com/example/tasks/entity/Task.java
---

# Data Model

## Task

Schema source of truth is `sql/001-task.sql`. Fields: `status`, `assigneeId`, `priority`,
`createdAt`, `completedAt`.

**Known limitation, disclosed honestly:** the JPA entity's `@Id` is a single column (`id`), but the
real DDL primary key is composite (`CreatedDate`, `Id`) and the table is partitioned by
`CreatedDate`. This is a real identity/equality risk in Hibernate's model, not just a documentation
gap — disclosing it here doesn't fix it, it just means anyone auditing this repo can find it
without re-deriving it from scratch. See the architecture-debt-visualizer report's data-architecture
findings for the specific risk this creates.

**Also known:** the table's column casing drifted (`Id`/`Status`/`CreatedDate` are PascalCase;
`priority`/`assigneeId` were added later in camelCase without normalizing), and the partition list
has a hardcoded horizon with no automated job to extend it. Both are tracked as open debt, not
silently accepted.
