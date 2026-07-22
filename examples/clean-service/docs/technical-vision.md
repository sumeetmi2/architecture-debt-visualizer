# Technical Vision

## Scale & Extensibility Targets

- **Target load**: 100 requests/second peak across both HTTP endpoints; 200 messages/second
  sustained on `click-events`. Expected growth: 2x within 12 months.
- **Latency budget**: p99 under 150ms for `GET /api/v1/links/{code}` (the read-heavy, redirect-
  critical path); no hard SLA on click-event processing latency, since it's an async analytics
  signal, not user-facing.
- **Extensibility target**: the team expects to support one new event type (beyond `click-events`)
  per half-year — the next candidate is `link-shared` events for social-share tracking — and wants
  each addition to take under a day given the existing consumer pattern.

## Versioning & Deprecation Policy

- REST endpoints are versioned (`/api/v1/`) from the start. A `v2` would only be introduced for a
  genuinely breaking change to the request/response shape; additive fields ship on `v1` without a
  version bump.
- Message channels: a channel is never repurposed once it has a consumer — a semantic change ships
  as a new channel name, and the old one is drained and removed after confirming zero producers/
  consumers reference it.
- No formal deprecation has happened yet — this is the stated policy for when one does.

## Design Philosophy

Click counting favors availability over exactness: a redelivered `click-events` message can
double-count a click (see `ClickEventConsumer`), an accepted trade-off since this is an analytics
signal, not a billing-relevant count. Link creation and resolution, by contrast, are exact —
idempotency-key-backed creation and a unique `shortCode` index rule out duplicates on the path that
actually matters for correctness.

Analytics forwarding is deliberately decoupled from the click-counting write via a circuit breaker
and fallback (`AnalyticsClient`) — an analytics-backend outage must never affect the service's own
counters, which are the source of truth.

## Key Architectural Decisions

- **No dual-write anywhere in this design.** Link creation is a single-table write with no
  accompanying event to publish. Click counting is triggered by an inbound message, not paired
  with an outbound one. This sidesteps the DB-write-plus-event-publish consistency problem
  entirely, rather than solving it with an outbox pattern — judged not worth the complexity given
  neither write path actually needs a second system kept in sync.
- **Partition catch-all, not a dated horizon.** `Link`'s partition list ends in a `MAXVALUE`
  catch-all rather than a fixed list of dated partitions, specifically to avoid the maintenance-job
  dependency a fixed horizon creates.

## Future Direction

- `link-shared` events (see Extensibility Targets above) are the next planned consumer. The
  existing `click-events` consumer's shape (a single `@Incoming` method, DLQ-configured,
  metered) is the pattern it's expected to follow.
- No other near-term architectural changes are planned.
