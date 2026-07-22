# How to: add a new consumed event type

1. Add a properties block in `application.properties`: connector, topic, concurrency (env-
   overridable), and `failure-strategy=dead-letter-queue` with a matching `-dlq` topic — every
   channel in this service uses this failure strategy, not `ignore`.
2. Add an `@ApplicationScoped` class with a single `@Incoming` method, following
   `ClickEventConsumer`'s shape: a `Timer.Sample` around the body, a processed counter, a failed
   counter, both registered on the injected `MeterRegistry`.
3. Add a row to `boundaries.md`'s Message Consumers table.

Followed by 1 of 1 real consumers today (`ClickEventConsumer`) — the next instance
(`link-shared`, see `technical-vision.md`) is expected to be the first real test of whether this
pattern holds up with a second consumer.
