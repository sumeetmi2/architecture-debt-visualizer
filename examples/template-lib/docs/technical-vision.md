# Technical Vision

`template-lib` is a small, embeddable templating library, published as a versioned Maven artifact
and linked directly into other services' processes — not a service of its own.

## Why this shape

- **No throughput target of its own.** `TemplateEngine.render()` runs in-process, on the calling
  service's own thread, as part of whatever request that service is already handling. There is no
  independent "requests per second" for this library to have an SLO about — its latency and
  concurrency profile are entirely the calling service's to define and measure, not something
  `template-lib` deploys or scales on its own.
- **No persistence of its own.** Compiled templates are cached in memory for the lifetime of the
  calling process; nothing is written to disk or a database by this library.
- **Consumed by multiple internal services**, each embedding a different version — this is exactly
  why API stability and a real deprecation policy matter here more than for a single-deployment
  service: a breaking change doesn't get fixed by redeploying one thing, it has to be adopted by
  every consumer independently, on their own schedule.

## Non-goals

This is not a templating *service* (no hosted rendering endpoint, no multi-tenant isolation
concerns) — if a use case needs template rendering as a network call, that's a different, new
project, not a natural evolution of this one.
