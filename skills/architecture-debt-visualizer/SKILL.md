---
name: architecture-debt-visualizer
description: "Reconcile a repo's design docs against its actual code AND/OR evaluate the architecture itself like a senior/staff architect — scalability, extensibility, long-term maintainability, performance/operational cost, data/entity-model soundness, observability, and whether the implementation still serves the product's stated technical vision. Classifies the repo's system type first so requirements are judged against what it actually is, not assumed to be a production service. Produces a scored, filterable HTML report. Use when the user asks to check if docs are stale, find architecture drift, audit docs vs. code, evaluate technical architecture, review data model / entity design, assess scalability or tech debt, or run an 'architecture debt' / 'architecture review' report. Triggers on phrases like 'check if our docs are still accurate' (reconcile mode), 'evaluate our architecture' / 'is this scalable' / 'review the data model' (evaluate mode), 'run an architecture debt audit' (full mode), 'architecture debt visualizer'."
argument-hint: "[path to docs folder, default: docs/] [--mode reconcile|evaluate|full, default: full]"
---

# Architecture Debt Visualizer

Two independent jobs:

1. **Reconciliation** — does the code still do what the docs say it does? (textual accuracy)
2. **Evaluation** — judging as a senior architect would, is the *architecture itself* sound, and
   does it still serve where the product is actually headed? (engineering judgment, classified
   against what kind of system this actually is — see step 1.5)

Job 1 catches drift. Job 2 catches debt that was never wrong on paper because no doc ever made a
claim about it. **Act as an independent evaluator, not a transcription service** in job 2 — it
does not wait for a doc claim to react to. A `confirmed` reconciliation result does not make a bad
pattern acceptable; judge quality separately, on its own merits.

Full technique detail lives in `references/` — this file is the workflow skeleton and the
non-negotiable rules. Read the referenced file at the point you reach that step; don't front-load
all of them.

## Non-negotiable rules

1. Every finding needs cited evidence — see `references/evidence-standard.md`.
2. Verify data-architecture claims against actual DDL/schema, never a doc's prose description of
   its own schema.
3. Don't invent claims or risk without evidence — speculation isn't a finding.
4. Distinguish repository evidence from runtime/externally-managed configuration explicitly (see
   `evidence_type`/`limitations` in `references/report-schema.md`).
5. No minimum or maximum finding count, anywhere — see the coverage rule in
   `references/evaluation-rubric.md`.
6. Every mandatory check gets a `checks.json` coverage record (`risk`/`strength`/`clean`/
   `not-applicable`/`not-assessed`) — mandatory is determined by system-type classification, see
   step 1.5.
7. State limitations and confidence explicitly rather than implying more certainty than you have.
8. `scripts/*.py` are deterministic helpers — run them, don't reimplement their logic by hand.
9. Don't modify the audited repository.

## 0. Resolve mode

- **`reconcile`** — docs-accuracy questions ("is `boundaries.md` stale?", "did this diagram
  drift?", "audit our docs against code"). Runs steps 1, 2, 4, 6-9. Skips system context and the
  evaluation pass entirely.
- **`evaluate`** — architecture-judgment questions ("is this scalable?", "review our data model",
  "what architecture debt exists here?"). Runs steps 1.5, 3, 5, 6-9. Skips reconciliation.
- **`full`** — explicit "architecture audit" / "architecture debt report" requests, **and the
  default whenever intent is ambiguous or unstated**. Runs everything. Defaulting ambiguity to
  `full` preserves this skill's original always-both behavior rather than silently narrowing scope
  the user didn't ask to narrow.

An explicit `--mode` argument always overrides inference.

## 1. Locate the docs (`reconcile`/`full`)

See `references/reconciliation.md` for the full technique. In short: find every `docs/` folder
repo-wide by default (`find . -type d -iname docs ...`), read every `.md` plus Mermaid/image
diagrams under each, and honor a user-named narrower doc scope without silently expanding it
(that restriction applies to reconciliation sources only — it doesn't limit step 5).

## 1.5. Establish system context (`evaluate`/`full`)

See `references/system-classification.md`. Classify `system_type`/`criticality`/`lifecycle`/
`deployment_model`/`data_sensitivity`/`expected_scale`/`confidence` into `context.json` in the run
directory. **Default to `production-service` (the strictest tier) whenever confidence is low** —
leniency is earned by positive evidence, never assumed. This classification determines which
checks in step 5 are mandatory vs. informational for this repo.

## 2. Extract checkable claims (`reconcile`/`full`)

See `references/reconciliation.md`. Pull concrete, falsifiable claims from each doc in scope —
component relationships, boundary rules, behavioral guarantees — skipping subjective or
already-flagged-uncertain statements.

## 3. Build the deterministic signals (all modes)

**First, make a unique run directory — never reuse a fixed literal path.** Two runs (a re-run, a
parallel/nested agent) sharing a hardcoded path will silently clobber each other's files — this
has actually happened in testing.

```
mktemp -d /tmp/adv-XXXXXX
```

**Take the literal directory path that command prints and use that literal string in every command
below** — don't rely on a `$RUN_DIR` shell variable persisting across separate tool calls; some
harnesses start a fresh shell per command, so a variable set in one call is gone by the next.
(`$RUN_DIR` appears below purely for readability — substitute your actual resolved path.)

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_dep_graph.py \
  --src src/main/java --out "$RUN_DIR/dep_graph.json"
```

(Add one `--src` per source root for a multi-module repo. Non-Java repo → see "Non-Java repos"
below.)

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compute_churn.py \
  --since "180 days ago" --out "$RUN_DIR/churn.json"
```

These give a package-level import graph and a churn/author-diversity signal
(`bus_factor_hotspots`, `high_diversity_hotspots`). Use them to prioritize which packages deserve
close reading, sanity-check boundary claims quickly, and spot coupling/bus-factor red flags
directly. They are a starting point, not proof — always confirm with an actual grep/read before
citing `file:line` evidence.

**If the underlying code hasn't changed since a prior run against this same repo** (e.g. testing
two doc-quality scenarios against identical code, as in `examples/sample-service`), these two
files can be reused instead of regenerated — both are code/git-derived only, not doc-derived.

## 4. Reconciliation pass (`reconcile`/`full`)

See `references/reconciliation.md`. For each claim, verify against the code and classify
`confirmed` / `misaligned` / `gap`, with `file:line` evidence on every result including confirmed
ones. Also scan for undocumented architecturally-significant elements the claims didn't prompt.
Cross-reference every finding against the rest of the docs before moving on — it's frequently
where the highest-value findings come from.

## 5. Architectural evaluation pass (`evaluate`/`full`)

See `references/evaluation-rubric.md` for the mindset, the full lettered checklist per dimension,
and the coverage rule (**no minimum/maximum finding count** — every check in
`scripts/rubric_manifest.json` that's mandatory for this repo's classified `system_type` gets one
coverage record in `checks.json`; only `risk`/`strength` records become `findings.json` entries).
Actively hunt for strengths, not just risks — past runs measurably skewed toward risk-only. See
`references/evidence-standard.md` for the phrasing rule before writing any `claim` text.

## 6. Write `findings.json` / `checks.json` / `context.json`

See `references/report-schema.md` for the full schemas. `claim`, `doc_source`, `doc_location` must
always be non-empty strings, never `null`. Evaluation-pass findings without a doc claim get a
synthesized `claim` and `doc_source: "no explicit doc claim — evaluated directly against code"`.

## 7. Validate before generating the report

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_findings.py \
  --findings "$RUN_DIR/findings.json" \
  --checks "$RUN_DIR/checks.json" \
  --context "$RUN_DIR/context.json" \
  --repo-root .
```

(Omit `--checks`/`--context` in `reconcile` mode.) Fix everything it hard-fails on before
continuing — duplicate IDs, missing required fields, evidence files that don't exist, missing
recommendations on medium/high risks, missing coverage records for mandatory checks. It also
prints non-blocking warnings (e.g. likely-bare-hypothesis phrasing) worth a second look but not a
hard stop.

## 8. Generate the report

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py \
  --findings "$RUN_DIR/findings.json" \
  --checks "$RUN_DIR/checks.json" \
  --context "$RUN_DIR/context.json" \
  --dep-graph "$RUN_DIR/dep_graph.json" \
  --churn "$RUN_DIR/churn.json" \
  --out "$RUN_DIR/report.html"
```

(`--checks`/`--context`/`--dep-graph`/`--churn` are all optional — omit what a given mode didn't
produce.) Produces one self-contained HTML file with four headline indicators — **Documentation
fidelity**, **Architecture risk**, **Audit coverage**, **Evidence confidence** — plus the legacy
0-100 **Debt index** as a secondary figure (see the report's own "Score philosophy" disclosure), a
static-analysis panel, a curated key-findings shortlist, and the full filterable findings table.
No network access needed to view it.

Tell the user where the report landed. If they want it published for sharing, use the Artifact
tool (load the `artifact-design` skill first) — default to leaving it as a local file unless asked.

## 9. Summarize in chat

- Reconciliation: total Confirmed/Misaligned/Gap counts, the 1-2 most consequential.
- Evaluation: highest-severity Risk findings with their concrete recommendation, 1-2 Strengths
  worth preserving, and audit coverage (X/Y mandatory checks completed — name anything
  `not-assessed`).

Don't just say "see the report" — name the actual finding and its concrete consequence.

## Non-Java repos

`extract_dep_graph.py` parses Java `package`/`import` statements only. For a non-Java repo, either
skip the dependency graph (`generate_report.py` works fine with `--dep-graph` omitted) or ask the
user if they want a language-specific extractor added — don't silently fabricate a graph.
`compute_churn.py` is language-agnostic (pure `git log`) and works in any repo.

## Demo mode (thin doc vs. improved doc)

To demonstrate the tool's value rather than run a one-shot audit, run the whole workflow twice
against two doc versions of the same code (a thin one, then a detailed one) and compare: a thin
doc yields mostly Gaps; a detailed doc yields a mix including genuine Misaligned findings. The
evaluation pass (step 5) is independent of doc quality — it runs against the code either way, which
is a good way to show real findings surface even with no docs to reconcile against at all.
