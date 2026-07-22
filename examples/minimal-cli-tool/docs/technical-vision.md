# Technical Vision

`json-formatter` is deliberately a minimal, single-purpose CLI tool — not a service.

## Why this shape

- **No server, no throughput target.** Every invocation is a fresh, single-threaded process that
  reads one file and exits. There is no concept of "requests per second" for a tool a human runs
  by hand or a script calls once per file — a QPS/latency target would be a made-up number for a
  workload that doesn't exist here.
- **No persistence, no schema.** The tool holds no state between invocations. There is nothing to
  partition, index, or evolve a schema for.
- **Growth means "more file formats or flags," not "more load."** If this tool grows, it grows by
  supporting more input shapes (e.g. JSON5, YAML) or more CLI flags (e.g. `--compact`), not by
  needing to handle more concurrent traffic. Extensibility here means "how many lines of code to
  add a new output mode," not "how many requests per second can this absorb."

## Non-goals

This is intentionally not going to become a long-running service. If a use case needs that
(a hosted formatting API, say), that's a different, new project — not a natural evolution of this
one, and the two shouldn't be conflated when judging this codebase's readiness for anything.
