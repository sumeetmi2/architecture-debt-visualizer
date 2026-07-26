# Architecture

`webhook-relay` consumes domain events published to Kafka, resolves which external subscribers
care about each event via the `subscription-registry` service, and delivers a copy of the event to
each subscriber's `target_url` over HTTP, retrying failed attempts on an interval.

```
Kafka (domain-events)
      |
      v
DomainEventConsumer --> SubscriptionRegistryClient (external service call)
      |
      v
webhook_delivery table (status=PENDING)
      |
      v
DeliveryRetryJob --> DeliverySender --> subscriber target_url
      |
      v
DeliveryResource (GET /api/v1/deliveries/{id}, operator read-only)
```

## Two things this repo deliberately does not own

**Subscriber identity and target URLs** live in the `subscription-registry` service (separate
repo, separate deploy, separate on-call rotation). This repo only calls it
(`SubscriptionRegistryClient`) and stores the resolved `target_url` on the delivery row at
ingestion time — it never stores or manages the subscription itself. See `docs/data-model.md`.

**Runtime infrastructure configuration** — container resource requests/limits, replica count,
horizontal autoscaling policy, and alerting thresholds — is defined in the `platform-infra` repo's
`webhook-relay/` overlay (Kustomize + a shared Grafana/alerting stack managed by the platform
team), not in this repo. This repo's own `application.properties` intentionally has no equivalent
of a Kubernetes `Deployment` manifest, `HorizontalPodAutoscaler`, or alerting-rule file — those
don't exist here by design, not by omission. Concretely, that means:

- There is no stated QPS/throughput target anywhere in this repo. The number that actually governs
  autoscaling behavior lives in `platform-infra`'s HPA config for this service, not here — an
  architect reading only this repo cannot answer "what load is this sized for," and that's a real,
  disclosed limitation of reviewing this repo in isolation, not a claim that no such number exists
  anywhere.
- There is no alerting-threshold definition for delivery failure rate, retry-queue depth, or
  consumer lag in this repo. Those alerts exist (owned by the platform team's shared alerting
  stack), but their current thresholds aren't visible from here.
- `domain-events-pool.max-concurrency=4` (see `application.properties`) is the one piece of
  capacity tuning that *does* live in this repo, because it's an application-level concern (JVM
  thread pool sizing), not an infrastructure one — it is genuinely hardcoded with no env override,
  unlike the platform-level scaling knobs above, and unlike this repo's other tunables
  (`RETRY_JOB_INTERVAL`, `SUBSCRIPTION_REGISTRY_URL`).

This split is deliberate — see `docs/technical-vision.md` for the reasoning — but it does mean an
audit of this repo alone cannot verify capacity, autoscaling, or alerting posture end-to-end; only
what's actually checked into `platform-infra` can answer that.
