# Architecture

`clean-service` is a small link-shortening service: create a short code for a URL, resolve a
short code back to its target, count clicks asynchronously.

## Key Components

| Component | Responsibility |
|---|---|
| `resource/LinkResource` | REST API — create and resolve links. Versioned `/api/v1`. |
| `security/AuthenticationFilter` | Global request auth, applied to every endpoint by construction. |
| `consumer/ClickEventConsumer` | Consumes `click-events`, increments the click counter, forwards to analytics. |
| `client/AnalyticsClient` | Best-effort outbound call to the analytics backend — timeout + circuit breaker + fallback. |
| `scheduler/LinkExpiryJob` | Hourly (configurable) sweep marking expired links. Idempotent. |

## Data flow

1. `POST /api/v1/links` creates a link, keyed by a client-supplied idempotency key.
2. `GET /api/v1/links/{code}` resolves a short code to its target URL.
3. Click events arrive independently on the `click-events` topic (produced by whatever surface
   actually redirects visitors — outside this service's boundary) and are consumed to increment
   `Link.clickCount` and forward to analytics.
4. `LinkExpiryJob` runs on an interval, marking links past `expiresAt` as `expired`.

No component in this service performs a database write and a message publish as one logical
operation — link creation is DB-only, and click counting is message-triggered but single-table —
so there's no dual-write/outbox question anywhere in this design (see
`technical-vision.md`).
