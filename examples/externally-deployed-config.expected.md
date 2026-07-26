# Expected result: `externally-deployed-config`

Kept **outside** `examples/externally-deployed-config/` for the same reason as the other
`.expected.md` files — a scoped run reads the fixture's own docs as part of normal doc discovery,
so stating the expected outcome inside the fixture would make the test partially circular. This
file is the golden spec, consumed by a human reviewer, never by the agent under test.

## What this fixture is for

Every prior fixture assumes the repo under audit is either the single source of truth for its own
operational posture (`sample-service`, `clean-service`) or is a small/atypical shape
(`minimal-cli-tool`, `template-lib`). None of them test the very common real-world case: a
production service whose application code lives in this repo, but whose **deployment/infra
config genuinely lives in a separate repo** (a platform team's centralized IaC repo), and whose
**subscriber/registry data lives in a separate service** entirely. `webhook-relay` is that
fixture — same rough shape as `clean-service` (Kafka consumer, scheduled job, one REST endpoint,
a real schema), but with two things deliberately unresolvable from inside this repo alone:

1. Capacity/scaling/alerting configuration (no k8s manifests, no HPA, no alerting rules anywhere
   in this repo — `docs/architecture.md`'s "What's managed elsewhere" section explains why and
   points at `platform-infra/webhook-relay/`, a real, specific, external location, not a vague
   shrug).
2. Subscriber identity (owned by the separate `subscription-registry` service, called over the
   network — `SubscriptionRegistryClient`).

This exercises `references/evidence-standard.md`'s "narrower, defensible claim" discipline: **"No
horizontal scaling configuration exists in this repository; deployment manifests were
unavailable"** is the correct, narrow claim here — not the sweeping **"No horizontal scaling path
exists"** (which would be a false, unverifiable claim about the actual system, not just this repo).

## What "pass" looks like

- `system_type` classified `production-service` (Kafka consumer + scheduled job + REST endpoint
  is unambiguous), **not** `unknown` or `prototype` — the absence of deployment manifests here is
  explained by docs, not a sign this system is unbuilt or undeployed. `deployment_model` may
  reasonably be recorded as `unknown` or with a classification-evidence note explaining the split,
  since none of the existing enum values (`multi-instance-service`/`single-instance`/`serverless`/
  `library-consumed`/`not-deployed`) cleanly fit "deployed, but the manifest lives elsewhere" —
  this itself is a legitimate, worth-noting rubric gap if a cold run flags it.
- `scale-requirements` stays **mandatory** for `production-service` (this fixture doesn't get
  library/cli-tool-style suppression) — the check should still run and produce a finding, but
  that finding should read as *"no QPS/throughput target found in this repo; docs state the
  authoritative figure lives in `platform-infra`'s HPA config, not duplicated here"* with
  `confidence: low`–`medium` and a `limitations` entry, **not** a bare "no scale target stated"
  risk indistinguishable from a repo that never thought about scale at all, and not silently
  dropped either.
- Same treatment expected for the observability/alerting-threshold angle: metrics/counters that
  *are* in-repo (if any are added) should be evaluated normally; alerting *thresholds*, which live
  in `platform-infra`, should be flagged as unverifiable-from-here rather than assumed absent.
- **Real, in-repo findings that should NOT get an externally-managed pass:**
  - `domain-events-pool.max-concurrency=4` (`DomainEventConsumer`) — hardcoded, no env override,
    called out explicitly in both the code comment and `docs/architecture.md` as an
    application-level (not infra-level) concern. This should be a genuine `scalability` risk, full
    confidence, `direct-code` evidence — the "config lives elsewhere" framing must not bleed into
    excusing this one, since it demonstrably doesn't live elsewhere.
  - `DeliveryRetryJob.retryDue()` — no `attempt_count` ceiling, no `FAILED` transition, forever-retrying
    poison deliveries. `docs/technical-vision.md` discloses this as a known gap, so reconciliation
    should read as **confirmed** (docs accurately describe the gap), while the evaluation pass
    should still flag it as a real `reliability-resilience` **risk** — disclosed debt is still
    debt, same principle already established by `sample-service`'s `docs-good` variant.
  - `DeliverySender.attempt()` has no per-call timeout on the outbound HTTP client, undisclosed
    anywhere — a plain, undocumented `reliability-resilience` gap/risk, unrelated to the
    externally-managed theme, there to confirm the run doesn't get lulled into treating every
    finding in this fixture as "that's someone else's problem."
  - `reliability-resilience.d` (dual-write/transaction boundaries) — **this bullet was wrong when
    first written; corrected after the first cold run below.** The fixture's own
    `docs/technical-vision.md` claims "no dual-write anywhere" and `not-applicable` on the theory
    that there's only one *database* write path. A good cold run should reject that: within
    `DeliveryRetryJob.retryDue()`'s `@Transactional` method, `DeliverySender.attempt()`'s outbound
    POST happens before the entity mutation/commit — that POST is itself an external side effect,
    making this a real two-step operation (external call, then local commit) with a genuine
    inconsistency window if the commit fails after the POST already succeeded. The correct read is
    a `misaligned` reconciliation finding (the doc's confident claim doesn't hold) plus a real
    `risk` on `reliability-resilience.d`, not `not-applicable`. This is the fixture's best proof
    point: a run needs to independently re-derive this from the code, not accept even an honest,
    otherwise-well-written doc's own analysis at face value.
  - `subscription_id` has no DB-level FK (by design, cross-service reference) —
    `data-architecture.c` should read this as an intentional, documented boundary
    (`docs/data-model.md`), not an unexplained referential-integrity gap.
  - `maintainability.a` (bus factor) — single-author, same disclosed limitation as every other
    fixture in this repo.

## What would count as a rubric-wording gap worth fixing

- If a cold run defaults `confidence: high` on the scale-requirements/alerting absence findings
  (treating "not in this repo" the same as "verified not to exist anywhere") — the evidence
  standard's narrow-claim language may need a more explicit worked example for the
  "genuinely lives in a different repo, and the docs say so specifically" case, not just the
  generic "infrastructure config isn't in this repo" example already in
  `references/evidence-standard.md`.
- If a cold run suppresses `domain-events-pool.max-concurrency=4` as "probably managed
  externally too" by association with the surrounding externally-managed framing — that's exactly
  the false-negative failure mode this fixture exists to catch.
- If `system_type` gets classified as anything other than `production-service`, or
  `applicability_profile` gets loosened, on the theory that a repo missing deployment manifests
  must not be a real production service.

## Actual first-run result (`reports/run1.*`)

Cold, no-memory agent, `full` mode. `system_type` classified `production-service`, confidence
**high** — correctly reasoned through the "illustrative only, not buildable" build.gradle
disclaimer and the total absence of deployment manifests, per `system-classification.md`'s
explicit guidance on both. `deployment_model: multi-instance-service` recorded as inferred (Kafka
consumer-group semantics + the docs' own mention of replica count as a platform-infra concept),
explicitly flagged as not confirmable from this repo alone. `expected_scale` correctly recorded as
current volume only, not a target, with a note pointing at the scale-requirements findings for the
absence of either a stated target or growth horizon.

**47 findings** — 16 confirmed, 1 misaligned, 3 gap, 22 risk (7 high, 6 medium, 9 low), 5 strength.
`validate_findings.py`: **OK (47 findings, 38 checks, 0 warnings)**, independently re-run against
the raw output, not taken from the agent's own summary. Audit coverage **38/38 (100%)**. Report
indicators: **Documentation fidelity 80%, Architecture risk High, Audit coverage 100%, Evidence
confidence 79%** — exactly the split this fixture exists to prove: docs here are mostly accurate
(one real misaligned claim, three real gaps) while the underlying architecture still reads as
genuinely high-risk, and the two numbers move independently rather than one masking the other.

The externally-deployed-config absences (`scale-requirements.a`/`.b`) were both recorded
`confidence: high` with an explicit limitation distinguishing "absent from this repo, disclosed as
living in platform-infra" from "doesn't exist anywhere" — the narrow-claim discipline held without
needing a rubric-wording fix. The one genuinely new thing this run surfaced was **this file's own
error**, not a rubric gap: see the corrected `reliability-resilience.d` bullet above. The run also
correctly kept `domain-events-pool.max-concurrency=4` as a full-confidence, undiscounted risk
(f29) rather than letting the externally-managed framing bleed into excusing it — the specific
false-negative failure mode this fixture was built to catch didn't happen.
