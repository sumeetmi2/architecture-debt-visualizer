# Boundaries

Complete I/O map for `clean-service`.

## HTTP API

| Method | Path | Auth | Idempotent |
|---|---|---|---|
| POST | `/api/v1/links` | `X-Auth-Credential` header, checked by `AuthenticationFilter` | Yes, via `Idempotency-Key` header |
| GET | `/api/v1/links/{code}` | `X-Auth-Credential` header, checked by `AuthenticationFilter` | Yes (read-only) |

Both endpoints are covered by the same global auth filter — there is no endpoint in this service
that skips it.

## Message Consumers

| Channel | Failure strategy | Concurrency |
|---|---|---|
| `click-events` | `dead-letter-queue` (topic `click-events-dlq`) | `${CLICK_EVENTS_CONCURRENCY:3}` |

## Scheduled Jobs

| Job | Interval | Idempotent |
|---|---|---|
| `LinkExpiryJob` | `${EXPIRY_JOB_INTERVAL:1h}` | Yes — re-running is a no-op on already-expired rows |

## External calls

| Call | Guardrail |
|---|---|
| Analytics forwarding (`AnalyticsClient.forwardClickEvent`) | 500ms timeout, circuit breaker (10-request window, 50% failure ratio, 30s open), fallback that never blocks the click-counting path |
