---
name: eval-architecture
description: "Run the architecture-debt-visualizer skill end-to-end against the current repo, and optionally auto-apply fixes and open a pull request per finding above a chosen risk threshold. Combines the audit skill with the architecture-debt-patcher skill in a single call. Can also skip the audit entirely and patch straight from an existing report run directory."
argument-hint: "[docs-path, default: docs/] [--mode reconcile|evaluate|full, default: full] [--patch] [--min-risk low|medium|high|critical, default: high when --patch is set] [--from-report <path to existing run dir>]"
---

# /eval-architecture — audit-then-optionally-patch

This is a **caller command**. It does not do audit or patching work itself — it orchestrates two
skills:

1. `architecture-debt-visualizer` — runs the audit and produces `findings.json` + HTML report.
2. `architecture-debt-patcher` — (optional) opens one PR per finding at or above the chosen risk
   threshold.

The patcher skill only runs when the caller explicitly asks for it. If it runs without a risk
level, the default is **High or higher** (i.e. `high` and `critical` only). This default is a
deliberately conservative safety net: automated patches to real repos should not silently touch
`low`/`medium` findings without the user opting in.

## Arguments

| Argument | Default | Meaning |
| --- | --- | --- |
| `[docs-path]` | `docs/` | Passed straight through to `architecture-debt-visualizer`. |
| `--mode <reconcile\|evaluate\|full>` | `full` | Passed straight through to `architecture-debt-visualizer`. |
| `--patch` | *absent* | If present, chain to `architecture-debt-patcher` after the audit. If absent, stop after the report is generated — no code changes, no PRs. |
| `--min-risk <low\|medium\|high\|critical>` | `high` (only when `--patch` is set) | Lowest `severity` value the patcher is allowed to touch. Ignored when `--patch` is not set. |
| `--from-report <path>` | *absent* | Skip the audit skill entirely and patch straight from an existing audit run directory containing `findings.json`. Implies `--patch`; the audit is not re-run. Mutually exclusive with `[docs-path]` and `--mode` (audit-only args), which are ignored with a warning if both are given. |

Ordering / spelling: accept `--patch` and `--min-risk=high` or `--min-risk high` interchangeably.
Case-insensitive risk levels. Map to `findings.json`'s `severity` field, whose canonical values are
`info` / `low` / `medium` / `high` / `critical`. `--min-risk=high` selects `high` and `critical`;
`--min-risk=medium` selects `medium`, `high`, `critical`; etc. `info` is never eligible for
patching regardless of threshold — informational findings by definition don't carry a
recommendation to act on.

## Workflow

### 1. Parse the caller's arguments

Extract `docs-path`, `--mode`, `--patch`, `--min-risk`, `--from-report` from the user's
invocation. Normalize `--min-risk` to lowercase.

- If `--from-report <path>` is present, treat it as an implicit `--patch` (there's no reason to
  supply a pre-existing report unless the user wants to patch from it). Warn if `[docs-path]` or
  `--mode` were also given — the audit isn't going to re-run, so those flags are dead. Skip to
  step 2b (patch-only path).
- If `--patch` is present without `--min-risk`, set the effective threshold to `high`.
- If `--min-risk` is present *without* `--patch` and *without* `--from-report`, warn the user
  that the flag has no effect on its own, then continue — don't silently start patching just
  because a threshold was named.

### 2a. Run the audit skill (normal path, when `--from-report` is not set)

Load and run the `architecture-debt-visualizer` skill following its own `SKILL.md` verbatim.
Forward the resolved `docs-path` and `--mode`. Do not reimplement any of its steps here — this
command is a caller, not a fork of the audit workflow.

When the audit skill finishes, it will have written to a unique `mktemp` run directory (see the
audit skill's step 3):

- `findings.json`
- `checks.json` (evaluate/full modes)
- `context.json` (evaluate/full modes)
- `report.html`

**Capture and remember the literal run directory path** — the patcher skill in step 4 needs the
exact same path. Do not re-derive it or guess it; pass it explicitly.

### 2b. Reuse an existing report (patch-only path, when `--from-report` is set)

Skip the audit skill entirely. Instead:

1. Resolve `--from-report` to an absolute path.
2. Verify it's a directory and contains at minimum a readable `findings.json`. If not, stop with
   a clear error — don't silently fall back to running a fresh audit, because the user explicitly
   asked to skip it.
3. Note whether `checks.json`/`context.json`/`report.html` are also present; missing ones are
   fine (the patcher only strictly needs `findings.json`), but call it out in the step-3 summary
   so the user knows what context is available.
4. Read `findings.json` enough to render the step-3 summary (top severities, counts). Don't
   re-verify any evidence — the patcher will do that per-finding in its own step 3.
5. **Freshness sanity check:** compare the mtime of `findings.json` against the repo's latest
   commit. If the report is older than the latest commit on the current branch, warn the user
   explicitly — the report may be stale relative to code, and the patcher's `stale-evidence`
   skips are likely to be more common. Continue anyway if the user confirms; this is a warning,
   not a hard stop, because sometimes a slightly stale report is exactly the input the user
   intends to work from.

Then proceed to step 3 and step 4 with the resolved `--from-report` path as the run directory.
There is no "did the audit succeed" question on this path — the audit didn't run.

### 3. Report to the user

Summarize the findings in chat the way the audit skill's step 9 prescribes (top misalignments,
highest-severity risks with their recommendations, coverage). Tell the user where the HTML report
landed (or, on the `--from-report` path, that it's being reused as-is).

### 4. Optionally invoke the patcher skill

If neither `--patch` nor `--from-report` was set, stop here. The user did not ask for code
changes.

Otherwise (either `--patch` was set, or `--from-report` was — the latter implies the former),
load and run the `architecture-debt-patcher` skill, forwarding:

- the audit run directory (from step 2a's `mktemp` path, or from `--from-report`),
- the effective `--min-risk` threshold (defaulted to `high` per step 1 if not stated),
- the repo root (current working directory).

The patcher skill decides which findings qualify, applies fixes, and opens PRs. This command does
not itself write to any file or run `git` — all of that lives in the patcher skill.

### 5. Final summary

After the patcher returns (if invoked), summarize:

- how many findings met the risk threshold,
- how many PRs were opened (with URLs),
- how many were skipped and why (e.g. no actionable `recommendation`, patch was ambiguous,
  requires human judgment — the patcher skill is responsible for reporting these back to this
  command with a structured reason per skipped finding).

Never silently drop findings — if the patcher couldn't handle one, name it in the summary so the
user can pick it up manually.

## Non-negotiable rules

1. **Never patch without `--patch` or `--from-report`.** The absence of both flags is a hard
   signal the user wants a report only. Do not "helpfully" open PRs on their behalf.
2. **When patching without an explicit `--min-risk`, default to `high`.** Never default lower.
   This is the whole point of the threshold — a conservative floor when the user hasn't set one.
3. **Never patch `info` findings**, even if the threshold nominally includes them (it shouldn't;
   `low` is the floor). `info` is reserved for confirmed/reconciliation findings that don't
   describe a problem to fix.
4. **One PR per finding, not one PR per run.** This is enforced by the patcher skill — this
   command must not batch-combine findings into a mega-PR to save round trips.
5. **Do not modify the audit run directory.** The patcher reads it; it should treat it as
   read-only input.

## Examples

Audit only, default mode, default docs path:

```
/eval-architecture
```

Audit only, evaluate mode against a non-default docs folder:

```
/eval-architecture design-docs/ --mode evaluate
```

Audit, then patch High and Critical findings only (the safe default):

```
/eval-architecture --patch
```

Audit, then patch Medium and above:

```
/eval-architecture --patch --min-risk medium
```

Audit only — the `--min-risk` here is ignored with a warning, since `--patch` isn't set:

```
/eval-architecture --min-risk high
```

Skip the audit and patch straight from an existing report — useful when a report was already
generated (in this session or a previous one) and you now want to act on it without paying to
regenerate it:

```
/eval-architecture --from-report /tmp/adv-abc123
```

Same, but override the default threshold for this patch run:

```
/eval-architecture --from-report /tmp/adv-abc123 --min-risk medium
```
