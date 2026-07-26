# Data model

One table, `webhook_delivery` (`sql/001-deliveries.sql`) — one row per attempted delivery of one
domain event to one subscriber.

| Column | Notes |
|---|---|
| `id` (PK, UUID) | Matches `WebhookDelivery`'s `@Id` exactly — no composite-key or partial-mapping mismatch |
| `subscription_id` | Foreign reference into the separate `subscription-registry` service's own storage — not a DB-enforced FK, since that data lives in a different service's database |
| `target_url` | Subscriber-owned endpoint, resolved once at ingestion time and stored on the row rather than re-resolved on every retry |
| `payload` | Raw JSON body of the domain event, stored as-is |
| `status` | `PENDING` / `DELIVERED` / `FAILED` — see `docs/technical-vision.md` for why `FAILED` is currently unreachable in code |
| `attempt_count` | Incremented on every failed retry, uncapped |
| `next_attempt_at` | Backing the retry job's poll query; indexed together with `status` |

No partitioning, no archival/retention job for `DELIVERED` rows — at this service's current volume
(low hundreds of events/day per `docs/technical-vision.md`) that's a legitimate `not-applicable`,
not a gap, but would need revisiting if volume grew an order of magnitude.
