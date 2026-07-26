# Technical vision

## Why infrastructure config lives in a separate repo

The platform team owns deployment manifests, autoscaling policy, and alerting for every service in
the fleet from one central `platform-infra` repo, not per-service. The tradeoff: a service repo
like this one can never be a complete picture of its own operational posture by itself — capacity,
scaling, and alerting all live one repo over. We accept that tradeoff fleet-wide for consistency
(one alerting stack, one autoscaling approach, one place platform engineers look), not because
this service specifically doesn't need those things stated. If you're auditing this repo and need
the current QPS target, replica count, or alert thresholds, they're real and current in
`platform-infra/webhook-relay/` — they're just not duplicated here, to avoid the two copies
drifting.

## Why subscriber management is a separate service

`subscription-registry` predates this service and is shared by multiple event-relaying consumers,
not just this one — subscriber CRUD, target-URL validation, and per-subscriber delivery
preferences all belong to it. `webhook-relay` is deliberately kept dumb: given an event type, ask
the registry who cares, deliver to what it says. This keeps the relay stateless with respect to
subscriber identity and lets the registry evolve subscription semantics without a relay redeploy.

## Known gap: retries have no ceiling

`DeliveryRetryJob` will retry a failing delivery forever — there is no `attempt_count` cap, no
transition to `FAILED`, and consequently no dead-letter path for a delivery whose `target_url` is
permanently gone. This is a real, current gap, not a deliberate design choice — it's on the
roadmap, not yet built. Current volume (low hundreds of events/day) means it hasn't caused an
incident yet, but a subscriber decommissioning their endpoint without unsubscribing first will
quietly accumulate forever-retrying rows.

## No dual-write anywhere

There is exactly one write path per delivery attempt (update the `webhook_delivery` row via
`DeliveryRetryJob`'s transaction) — no code path writes to this table and a second system in the
same operation, so `reliability-resilience.d` (transaction-boundary correctness across dual
writes) is legitimately `not-applicable` here, not a gap.
