# webhook-relay

Consumes domain events from Kafka and relays each one, as an HTTP POST, to every external
subscriber registered for that event type. Subscriber identity lives in the separate
`subscription-registry` service; this service only relays.

See `docs/architecture.md` for the component layout, including the "What's managed elsewhere"
section describing what's deliberately not tracked in this repo (deployment manifests,
autoscaling, alerting — owned centrally by the platform team's `platform-infra` repo), and
`docs/technical-vision.md` for why that split exists and for the one known, disclosed gap in the
retry path.
