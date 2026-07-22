# Data Model

## Link

Single table, partitioned by `createdDate` with a `MAXVALUE` catch-all partition — no hardcoded
horizon to run out and no maintenance job needed to keep one from running out.

Fields: `id`, `createdDate` (together the composite primary key, matched exactly by the JPA
`@EmbeddedId` `LinkId` — no identity mismatch), `shortCode` (unique), `targetUrl`,
`idempotencyKey` (unique — backs create-endpoint idempotency), `clickCount`, `expiresAt`,
`status`, `createdAt`, `tag` (nullable, added in `002-add-tag-column.sql` as an expand step, not
yet enforced non-null).

No foreign keys: this is a single-table schema today. If a second related table is ever added
(e.g. a `LinkOwner` table), the referential-integrity strategy (real FK vs. app-level convention)
should be decided explicitly at that point, not defaulted into whichever is easier to ship.

No monetary or currency fields exist in this schema.
