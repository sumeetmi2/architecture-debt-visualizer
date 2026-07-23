# Validation methodology, raw reports, and history

Moved out of the main README to keep that page scannable — this is the detailed record for anyone
who wants the methodology, the raw numbers, and the history of what changed and why. See the
[README](../README.md#validation)'s short summary and link back here.

## Methodology

Tested against a real, private production monorepo (a large multi-module Java/Gradle microservices
codebase — name and domain withheld, not affiliated with this project) rather than a toy example.
Terms used below:

- **Cold agent run** — a fresh Claude Code agent with no memory of any prior run and no visibility
  into other runs, given only the target repo and a plain-language request ("evaluate our
  architecture and check if the docs are still accurate"). This is what someone installing the
  skill for the first time actually experiences — not a run I tuned by hand.
- **Identical-scope runs** — two or more cold agent runs pointed at the exact same repo and the
  exact same restricted set of docs, so any difference between their outputs is purely run-to-run
  variation, not a different task or a different amount of material to review.
- **Score** — the report's own heuristic 0-100 number (documented in `SKILL.md` and inside every
  generated report): lower means more, or more severe, unresolved findings. It's designed to track
  one repo's trend across repeated runs, not to compare different repos or grade "quality" in the
  abstract.
- **Finding** — one row in the report: a reconciliation result (confirmed / misaligned / gap,
  checked against a real doc claim) or an evaluation result (risk / strength, judged independent of
  any doc claim) in one of the 12 evaluation dimensions (9 as of the original check-coverage
  rewrite; reliability-resilience, change-safety, and security-boundaries added afterward — see
  below).
- **Per-dimension checklist coverage** — the evaluation pass defines a fixed set of mandatory,
  individually-named sub-checks per dimension (7 for data-architecture, e.g. identity/PK
  consistency, naming-convention drift, referential integrity, partition maintenance, type choices,
  forward-readiness, shadow representations). This measures whether a run actually executed every
  one of them separately, rather than skipping some or merging two into one finding to save time.

## Reliability, before vs. after tuning the rubric

Earlier versions of the evaluation pass gave agents an open-ended target ("be thorough, find
15-25+ issues") and left it to each run's own judgment when a dimension was "done." That produced
wide swings between identical-scope runs. The rubric was changed to a fixed minimum/maximum finding
count per dimension, a capped scoring formula (no single dimension can dominate the score), and the
named per-dimension checklist described above.

| Metric | Before the rubric fix | After the rubric fix |
|---|---|---|
| Score range across identical-scope runs | 68 points (lowest 12, highest 80) | 13 points (lowest 28, highest 41) |
| Finding-count range across identical-scope runs | 17 (lowest 11, highest 28) | 6 (lowest 30, highest 36) |
| Per-dimension checklist coverage | Not tracked — left to each run's judgment | All 7 named sub-checks hit individually, confirmed across 3 separate identical-scope runs |

Separately, every high-severity finding produced by a deep, human-guided reference pass over the
same repo was independently rediscovered by cold agents that never saw that reference pass or its
findings — including cases where two agents, given the identical prompt and scope, arrived at the
same conclusion via different evidence.

## Evolving further: check-coverage model + system classification

The fixed min/max finding-count rubric above fixed the *count* variance, but an external review
pointed out it mixed up two different things: checks performed and problems found, and it created
a real incentive to manufacture a weak finding just to hit a floor. It was replaced with a
check-coverage model — every mandatory lettered check gets exactly one coverage record
(`risk`/`strength`/`clean`/`not-applicable`/`not-assessed`), with no minimum or maximum finding
count anywhere — plus system classification, so a missing scale target isn't penalized the same
way on a CLI tool as on a production service (see the [README](../README.md#what-it-does)).

Three fresh cold runs validated this end to end:

| Run | system_type | Findings | Audit coverage |
|---|---|---|---|
| [sample-service/docs-bad](../examples/sample-service/reports/docs-bad-run4-v2skill.html) | production-service | 20 | 100% (22/22) |
| [sample-service/docs-good](../examples/sample-service/reports/docs-good-run2-v2skill.html) | production-service | 23 | 100% (22/22) |
| [minimal-cli-tool](../examples/minimal-cli-tool/report-v2skill.html) | cli-tool | 9 | 100% (16/16) |

The `minimal-cli-tool` run is the golden case for system classification: it classified `cli-tool`
from real evidence (a `main()` entry point, no server/listener/consumer anywhere, an
`application`-plugin Gradle config) and correctly resolved the missing scale-requirements and
observability checks `not-applicable` rather than flagging them as `risk` — see
[`examples/minimal-cli-tool.expected.md`](../examples/minimal-cli-tool.expected.md) for the full
golden spec.

These same three runs also surfaced a real defect in the new model itself: one run shared a single
`finding_id` across two checks it judged were "answered by the same paragraph," producing 13
findings, while an independent identical-scope run wrote a distinct finding per check and produced
22 — both technically satisfied full coverage, but the count still swung ~2x, undercutting the
whole point of replacing a count-based rubric with a coverage-based one. Fixed with an explicit
rule (shared evidence is fine, a finding owned by two checks is not) now enforced by
`validate_findings.py`, not just documented in prose. A second external review later caught that
the fix, applied too literally, also capped every check at exactly one finding — contradicting
checks that explicitly ask you to enumerate every instance of a problem, not stop at the first.
Fixed again: `checks.json`'s `finding_id` became `finding_ids` (array) — a finding still belongs to
exactly one check, but a check can list as many findings as it genuinely turned up.

**`skills/architecture-debt-visualizer/scripts/validate_findings.py`** turns the skill's evidence
rules into an enforced gate instead of prose the agent might skip under time pressure: duplicate
finding/check IDs, invalid enum values, empty required fields, medium/high risk findings missing a
recommendation, evidence files that don't exist on disk, negative-search findings missing
`searches_performed`, missing mandatory coverage records, and the finding-ownership rule above all
hard-fail with a specific message. A likely-bare-hypothesis phrasing check (the recurring
regression noted below) is a non-blocking warning — that one needs semantic judgment a keyword
heuristic can't fully make.

**`skills/architecture-debt-visualizer/evals/`** is a golden-test harness — `cases.json` (JSON, not
YAML: every script here is deliberately zero-third-party-dependency, and PyYAML isn't guaranteed
installed) defines `must_find`/`must_not_find`/`expected_not_applicable` specs, and `run_evals.py`
grades an already-generated `findings.json`/`checks.json` against them. It doesn't invoke the skill
itself — it's a scoring pass over output a real run already produced. Both seed cases (all 9
`docs-bad` planted issues; the `minimal-cli-tool` false-positive suppression) pass against the runs
in the table above, and the suppression case correctly *fails* when pointed at the `docs-bad` run
instead, confirming it actually discriminates.

## Public, reproducible test: `examples/sample-service`

The reliability numbers above come from a private repo whose specifics can't be shared. This repo
also ships a small, purpose-built fixture — [`examples/sample-service`](../examples/sample-service)
— so the same kind of test is fully reproducible by anyone, with real, non-obfuscated reports you
can open and check. See [its own README](../examples/sample-service/README.md) for what's in it: a
~10-file Java service with deliberately planted architecture debt, documented against two doc sets
(`docs-bad`, stale/incomplete; `docs-good`, accurate and complete) that share identical code.

Three independent cold runs against `docs-bad` (fresh agent, no memory of prior runs, no memory of
each other, no knowledge of what was deliberately planted):

| Run | Score | Findings | data-architecture evaluation findings (cap 7) |
|---|---|---|---|
| [1 — human-reviewed, benchmark](../examples/sample-service/reports/docs-bad-run1-benchmark.html) | 30/100 | 32 | 7/7 |
| [2](../examples/sample-service/reports/docs-bad-run2.html) | 32/100 | 32 | 7/7 |
| [3](../examples/sample-service/reports/docs-bad-run3.html) | 25/100 | 33 | 6/7 |

7-point score spread, 1-finding spread. All three independently caught every deliberately-planted
issue (the entity/DDL primary-key mismatch, the undocumented endpoint, the undocumented consumer,
the empty vision doc) plus real issues nobody planted — run 3, for instance, caught that the
table's partition key (`CreatedDate`) doesn't actually match the column the archival job filters on
(`CompletedAt`), a genuine mismatch that fell out of the investigation rather than being seeded.
Run 1 was manually reviewed before being treated as the benchmark for runs 2 and 3.

A separate cold run against the accurately-documented `docs-good` scope (same code, better docs) —
[report](../examples/sample-service/reports/docs-good-run1.html) — scored 41/100 with 45 findings
(15 confirmed, 1 misaligned, 1 gap, 20 risk, 8 strength): mostly `confirmed` reconciliation as
expected, plus the same evaluation-pass risks the `docs-bad` runs found, since those are judged
from the code directly. It also caught a real, unplanted mistake in the "good" docs themselves —
see [`examples/sample-service/README.md`](../examples/sample-service/README.md#docs-good-run) for
details.

## False-positive test: `examples/clean-service`

Every fixture above is either deliberately debt-laden (`sample-service`) or too small to have much
evaluation surface (`minimal-cli-tool`). Neither answers the question that matters most for a tool
whose whole job is flagging risk: **does it over-flag on real, non-trivial, deliberately
well-built code?** [`examples/clean-service`](../examples/clean-service) is a same-scale,
same-shape sibling of `sample-service` (REST API, message consumer, scheduled job, real schema)
where every pattern planted as debt in `sample-service` was instead built correctly — real
idempotency keys, circuit breaker + fallback on the one outbound call, DLQ-configured consumer,
input validation, versioned API, secrets from env vars, matching PK/entity, partition catch-all
with no dated horizon. See [`examples/clean-service.expected.md`](../examples/clean-service.expected.md)
for the full pass bar and the actual first-run result.

One cold run (fresh agent, no memory), `full` mode: **43 findings — 19 confirmed, 18 strength, 0
misaligned, 0 gap, 6 risk (0 high, 1 medium, 5 low)**, audit coverage **37/37 (100%)**. The single
medium-severity risk was verified legitimate on review, not a stretch: a documented p99&lt;150ms
SLA on one endpoint with zero latency instrumentation to check it against — a real, evidenced gap,
not manufactured to hit a quota. Zero high-severity findings, zero misaligned/gap reconciliation
results, against code deliberately built to have none. This run surfaced two real rubric wording
gaps (missing `documentation` evidence-type bucket; the double-counting-avoidance rule only named
two check pairs instead of stating the general principle) — both fixed directly in
`references/evidence-standard.md` and `references/evaluation-rubric.md`.

## System-type coverage test: `examples/template-lib`

Every fixture above classifies as `production-service` (`sample-service`, `clean-service`) or
`cli-tool` (`minimal-cli-tool`) — zero coverage on `library`, despite it having a genuinely
different suppression profile from `cli-tool`: `rubric_manifest.json`'s `system_type_overrides`
marks `scale-requirements`/`observability`/`reliability-resilience` informational for `library`,
but (unlike `cli-tool`) leaves `scalability` and `change-safety` mandatory.
[`examples/template-lib`](../examples/template-lib) is a small embeddable Java templating library
(no server, no `main`, `java-library`/`maven-publish` Gradle plugins) with real planted issues in
exactly the dimensions that should stay mandatory: a hardcoded, non-overridable cache-size ceiling
(`scalability`), two breaking API changes shipped as non-major version bumps with no deprecation
cycle (`change-safety`), an unsandboxed template-path resolution (`security-boundaries`), and a
helper-dispatch mechanism implemented two structurally different ways (`extensibility`). See
[`examples/template-lib.expected.md`](../examples/template-lib.expected.md) for the full pass bar
and the actual first-run result.

One cold run (fresh agent, no memory), `full` mode: `system_type` classified `library`, confidence
**high** — matched. `validate_findings.py`: `OK (16 findings, 39 checks, 0 warnings)`. **16
findings** (8 risk, 4 confirmed, 2 misaligned, 2 strength), **27/27 mandatory checks covered
(100%)**. Every planted issue survived as a finding under the expected dimension; every suppressed
dimension (`scale-requirements`/`observability`/`reliability-resilience`) correctly resolved
`not-applicable` rather than manufacturing risk from a throughput/observability concept that
doesn't apply to in-process code with no I/O of its own.

One real mismatch, one real process gap, both fixed the same session:
- **`maintainability.a`** came back `not-applicable` (fixture was still untracked, zero git history,
  at run time) instead of this repo's established `clean`/low-`risk`-with-caveat convention for thin
  history. `evaluation-rubric.md`'s Maintainability checklist didn't say so explicitly before this
  run — now it does (bus-factor concept always exists once there's any code and any author; thin
  history caps confidence, it doesn't make the check `not-applicable`).
- **`extensibility-requirements.b`** didn't state what an absent cost-bar should score as (unlike
  `.a`, explicit that absence is a risk) — now explicit, mirroring `.a`, both fixed in
  `evaluation-rubric.md` and `rubric_manifest.json`.
- The fixture's own `README.md` originally carried a planted-issues table and "used to test the
  skill" framing inside the audited repo itself — a second answer key beyond
  `template-lib.expected.md`, contradicting this project's own fixture-circularity-avoidance
  discipline (only `sample-service`'s README, written before that discipline existed, still has this
  same drift, not yet backfilled). The cold-test agent caught and disclosed this itself, verified
  every finding independently against real `file:line` evidence regardless, and the result was kept
  on that basis — but the README was rewritten to stay purely in-universe so a future run against
  this fixture isn't exposed to it.
- This run's own expected-outcome table had a defect of its own: it hedged two `change-safety`
  facts as landing on "`.a` and/or `.d`" / "`.a` and/or `.b`" — a real tension with
  evaluation-rubric.md's "checks aren't interchangeable" rule that the cold-test agent correctly
  flagged. Resolved by committing `change-safety.a` as the sole owner of both facts (two independent
  findings under one check, per that check's own "list them all" pattern), with `.b`/`.c`/`.d`/`.e`
  `not-applicable` for a library with no deploy/migration/rollout surface — not a rubric bug, a
  fixture-doc bug.

## Known limitations, disclosed rather than hidden

**Phrasing rule recurrence:** a phrasing rule exists (state findings as direct facts, not as an
unresolved positive-sounding hypothesis with no marker — see
[`references/evidence-standard.md`](../skills/architecture-debt-visualizer/references/evidence-standard.md))
specifically because early testing showed the wrong phrasing reads as a false "this is fine" on a
skim. It's followed reliably when a run is explicitly told to self-audit before finalizing, but
recurs in some ordinary cold runs (visible in a few rows across the reports linked above) because
the instruction currently isn't self-enforcing on its own. `validate_findings.py` now flags likely
violations as a warning — a partial mitigation (a human or agent still has to act on the warning),
not a fix, since reliably detecting a bare hypothesis is a semantic judgment a keyword heuristic
can't fully make. Content and evidence are unaffected — only the wording of some claim sentences
reads more ambiguously than intended. Tracked as follow-up work, not swept under the rug.

**Report schema versions:** the `docs-bad-run1/2/3` and `docs-good-run1` reports above predate the
check-coverage model and use the original single 0-100-score format — `generate_report.py` still
renders them correctly, but the four headline indicators show `—` since those runs have no
`checks.json`/`context.json`/confidence fields to compute them from. The `*-v2skill` reports are
the first generated after the schema change. Neither set was regenerated to match the other — a
schema change shouldn't quietly rewrite history.

**Compound checks:** some lettered checks (e.g. `observability.a`, which asks for all four golden
signals across 2-3 critical paths in one pass) bundle several distinct facts into one check id. A
second external review's suggested fix — scoped/parameterized check instances (one check id,
multiple scope-tagged sub-results) rather than one flat check per lettered item — is now built:
`checks.json` accepts multiple instances of the same id, each tagged with a disjoint `scope` and
its own status (`references/report-schema.md`'s "Scoped check instances"); `validate_findings.py`
flags overlapping scope between instances of the same id as an error; `generate_report.py`'s
audit-coverage and check-coverage computations were fixed to consider every instance of an id
(they previously only saw the last one in file order, which both under- and over-counted coverage
depending on instance order — never exercised in practice before this, since no run had emitted
more than one instance per id). Verified with a synthetic fixture exercising a clean+risk
scoped-instance pair alongside a same-scope duplicate (correctly rejected), plus a regression run
against the existing `clean-service` fixture showing byte-identical coverage output to before the
change.

One cold run (fresh agent, no memory), `evaluate` mode against `examples/clean-service`:
`validate_findings.py` passed clean (26 findings, 41 checks). The agent used scoped instances on
its own, unprompted beyond the rubric text, for 3 ids (7 instances total against 37 base checks):
`observability.a` split across three critical paths that genuinely landed on different golden-signal
counts (1/4, 1/4, 3/4 signals present), `scalability.a` split across one env-overridable config
(strength) vs. one hardcoded fault-tolerance threshold (risk), `reliability-resilience.b` split
across an implemented client (strength) vs. an unimplemented stub with nothing to assess
(not-assessed). It correctly did *not* split the two consistency-style checks
(`extensibility.b`/`maintainability.b`) despite the temptation, since this repo only has one
instance of each compared thing — marked `not-applicable` instead, per the existing rule. No
friction reported reading either the `report-schema.md` or `evaluation-rubric.md` guidance. 4 of
its 6 substantive risk findings matched the original `run1` cold run almost exactly (resolve-
latency gap, DLQ-reprocessing gap, no feature-flag mechanism), with two defensible severity/
judgment divergences given the same thin evidence — not a rubric problem.

**Reliability/resilience, change-safety, and security-boundaries dimensions** were added after the
same review (12 dimensions total now, up from 9) with 5 lettered checks each, following the exact
manifest/applicability-override pattern the original 9 already used.

First cold run: [`examples/sample-service/reports/docs-good-run3-newdims.html`](../examples/sample-service/reports/docs-good-run3-newdims.html)
— 40 findings (11 confirmed, 1 gap, 20 risk, 8 strength), 37/37 checks covered (100%, up from 22),
`validate_findings.py` passed clean on the first attempt. The 16 new-dimension findings were all
concrete and evidence-backed (no idempotency-key mechanism on the write endpoints, no timeout/
circuit-breaker config anywhere, zero authN/authZ on any REST endpoint, a credited strength for the
`/api/v1/` versioning + documented deprecation policy). The run surfaced four real checklist-wording
gaps, since fixed directly in `references/evaluation-rubric.md`:
- `reliability-resilience.d` didn't say what to do when no multi-step write path exists at all
  (now explicit: `not-applicable`, distinct from "exists but couldn't verify").
- `change-safety.b`'s framing implied catching a breaking change "in the act"; a young repo with
  too little history to show either pattern is still a real finding (absence of established
  convention), just a different claim — now stated explicitly.
- `security-boundaries.a` read as only asking about inconsistency between endpoints; uniform
  absence of auth across all endpoints is an equally real, often more severe finding under the
  same letter — now stated explicitly.
- Stubbed/illustrative persistence code (this fixture's repository layer) can only be assessed at
  the API-contract level for `reliability-resilience.a`/`security-boundaries.d`, not observed
  runtime behavior — now noted as a legitimate, narrower way to answer those checks.

**Eval harness scope:** `evals/run_evals.py` grades already-generated output; it doesn't invoke the
skill itself, so it validates the grader and catches regressions in already-produced findings, but
on its own won't catch a regression in triggering, reference-loading, or the investigation itself.
`evals/run_e2e_eval.py` closes that gap — it shells out to `claude -p` (headless, `--plugin-dir`
pointed at this checkout so `${CLAUDE_PLUGIN_ROOT}` resolves to it, not any globally-installed
version) against a fixture repo's real directory, runs `validate_findings.py` against whatever the
agent produced, confirms the fixture repo itself was left untouched (`git status --porcelain`), and
grades the result with the same `grade_case()` `run_evals.py` uses (refactored out of `main()` so
both paths share one grading implementation instead of forking the logic). `cases.json` entries
gained `fixture_repo`/`docs_path`/`mode` fields so a case knows what to actually run, not just what
to grade.

Real proof run: `minimal-cli-tool-must-not-find` end to end — `claude -p` invocation succeeded
(cost $1.46, 373s, 31 turns), `validate_findings.py` passed (5 findings, 37 checks, 1 non-blocking
warning), fixture confirmed untouched, and the case graded PASS (both `must_not_find` clean, all 4
`expected_not_applicable` checks correctly resolved `not-applicable`). Costs real API spend and
takes several minutes per case — intentionally a manual/on-demand harness, not wired into
CI-on-every-commit.
