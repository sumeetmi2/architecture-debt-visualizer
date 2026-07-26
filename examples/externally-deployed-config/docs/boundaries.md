# Boundaries

Complete I/O map for `webhook-relay`.

## HTTP API

| Method | Path | Auth | Idempotent |
|---|---|---|---|
| GET | `/api/v1/deliveries/{id}` | `X-Auth-Credential` header, checked by `AuthenticationFilter` | Yes (read-only) |

Operator-facing only — this service has no inbound HTTP ingestion path; events arrive via Kafka
(see below). One endpoint, one global filter, no opt-out.

## Message Consumers

| Channel | Failure strategy | Concurrency |
|---|---|---|
| `domain-events` | none — no dead-letter topic configured, no failure-strategy override (defaults apply) | fixed at 4 (`domain-events-pool.max-concurrency`, no env override) |

## Scheduled Jobs

| Job | Interval | Idempotent |
|---|---|---|
| `DeliveryRetryJob` | `${RETRY_JOB_INTERVAL:1m}` | Yes on the delivery row itself (re-running only acts on rows still `PENDING` and due), but see `docs/technical-vision.md` for the retry-ceiling gap this doesn't solve |

## External calls

| Call | Guardrail |
|---|---|
| Subscriber resolution (`SubscriptionRegistryClient.resolveSubscribers`) | 500ms timeout, circuit breaker (10-request window, 50% failure ratio, 30s open), fallback returns an empty subscriber list rather than blocking event ingestion |
| Delivery attempt (`DeliverySender.attempt`) | None beyond the HTTP client's own defaults — subscriber URLs are third-party, a slow or hanging subscriber has no per-call timeout configured here |

## What's managed outside this repo

See `docs/architecture.md`'s "What's managed elsewhere" section — container resource limits,
replica count, autoscaling policy, and alerting thresholds are not in this repo at all.
