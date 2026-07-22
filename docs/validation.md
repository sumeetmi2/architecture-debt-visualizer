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
  any doc claim) in one of the 9 evaluation dimensions.
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

**Compound checks and rubric breadth:** some lettered checks (e.g. `observability.a`, which asks
for all four golden signals across 2-3 critical paths in one pass) bundle several distinct facts
into one check id — real, not yet resolved. The 9-dimension rubric also doesn't yet have dedicated
checks for reliability/resilience (retries, idempotency, failure isolation), change/deployment
safety (schema migration, API versioning, rollback safety), or security/trust-boundary concerns —
flagged in a second external review as the next-highest-value rubric expansion, not yet built.

**Eval harness scope:** `evals/run_evals.py` grades already-generated output; it doesn't invoke the
skill itself, so it validates the grader and catches regressions in already-produced findings, but
won't catch a regression in triggering, reference-loading, or the investigation itself. An
end-to-end runner that actually invokes Claude Code against a fixture and grades the result is a
known gap, not yet built.
