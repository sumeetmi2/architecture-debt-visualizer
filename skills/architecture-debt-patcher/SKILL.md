---
name: architecture-debt-patcher
description: "Turns an already-produced architecture-debt-visualizer findings.json into one pull request per actionable finding at or above a caller-specified risk threshold. Applies the finding's own recommendation as a code change, opens a branch, commits, and pushes a PR via the gh CLI. Never runs without explicit invocation — always driven by the /eval-architecture caller or an explicit user request. Triggers on phrases like 'apply the fixes from the architecture report', 'open PRs for the high-risk findings', 'auto-patch the architecture debt findings'."
argument-hint: "--run-dir <path to audit run directory> [--min-risk low|medium|high|critical, default: high]"
---

# Architecture Debt Patcher

Given a `findings.json` already written by the `architecture-debt-visualizer` skill, this skill
opens **one pull request per qualifying finding** — where "qualifying" means:

- `severity` is at or above the caller's `--min-risk` threshold (default `high`),
- the finding has a non-empty, actionable `recommendation`,
- the change implied by that recommendation is small and localized enough to attempt
  automatically without human judgment.

Anything that doesn't meet all three is **skipped, not force-fitted into a PR**. Skipped findings
are reported back with a structured reason so the caller (`/eval-architecture`) can surface them.

## When this skill runs

Only when explicitly invoked — either by the `/eval-architecture` caller command (with `--patch`
or `--from-report`), or by a direct user request naming this skill. It **never runs as a
side-effect of running the audit skill on its own**. The audit skill and this skill are decoupled
on purpose: an audit is always safe to run; a patch run mutates real code and opens real PRs.

The `--run-dir` supplied to this skill may point at either:

1. A fresh `mktemp` directory the audit skill just wrote to in this session, or
2. An older audit run directory the user is deliberately reusing (via `/eval-architecture
   --from-report <path>` or by naming it in a direct request).

This skill treats both the same way — it re-verifies every evidence citation in step 3 before
touching code, so a slightly stale report doesn't cause bad patches; it just causes more
`stale-evidence` skips. The caller is responsible for warning the user about report age; this
skill enforces correctness per-finding regardless.


## Non-negotiable rules

1. **Read-only against the audit run directory.** The `findings.json`/`checks.json`/`context.json`
   the audit skill produced are inputs, never outputs. Don't rewrite them; don't move them.
2. **One PR per finding.** Never combine findings into a single PR, even related ones on the same
   file. Each finding gets its own branch, its own commit, its own PR, its own review context.
3. **Never patch below the threshold, ever.** Default is `high`. `info` is never eligible
   regardless of what the threshold nominally allows — see caller command's rule 3.
4. **Never patch a finding without a `recommendation`.** A finding with no `recommendation` field
   (or an empty/`null` one) is by definition not actionable — skip it with reason
   `no-recommendation`.
5. **Skip, don't guess.** If the recommendation is vague ("consider adopting a DLQ pattern"), if
   it names multiple alternatives without picking one, or if the change would touch more than
   a small handful of files, **skip with reason `requires-human-judgment`** and report back. Do
   not invent an interpretation and ship it.
6. **Never push to `main`/`master`/`trunk` directly.** Every change goes through a fresh branch
   and a PR opened via `gh pr create`.
7. **Never force-push, never rewrite an existing branch.** If a branch name collides (e.g. a
   previous run), append a short unique suffix (`-2`, `-3`, …) rather than overwriting.
8. **The audited repo's working tree must be clean before this skill starts.** If it isn't,
   abort — mixing this skill's changes into unrelated in-flight work is exactly the kind of
   footgun that erodes trust in automated tooling.

## 1. Resolve inputs

The caller passes:

- `--run-dir` — the literal `mktemp` path from the audit skill's step 3, containing
  `findings.json` at minimum.
- `--min-risk` — one of `low` / `medium` / `high` / `critical`, defaulting to `high` if the
  caller doesn't supply one.

Verify:

- `$RUN_DIR/findings.json` exists and is valid JSON,
- the current working directory is a clean git worktree (`git status --porcelain` is empty),
- `gh auth status` succeeds — no point starting if we can't open a PR at the end.

If any of those fail, stop and report why. Don't proceed part-way.

## 2. Filter findings by threshold

`findings.json` follows the schema in the audit skill's `references/report-schema.md`. Each entry
has a `severity` string in `info` / `low` / `medium` / `high` / `critical`.

Build the eligible set:

```
severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
threshold_rank = severity_rank[min_risk]
eligible = [f for f in findings
            if severity_rank.get(f["severity"], 0) >= threshold_rank
            and f["severity"] != "info"
            and f.get("recommendation")]
```

For each finding **not** eligible, record it in a skip list with one of these structured reasons:

- `below-threshold` — severity ranked below the threshold.
- `info-severity` — `info` findings are never eligible (see rule 3).
- `no-recommendation` — missing/empty `recommendation`.

The skip list is reported at the end (step 6); it is not an error.

## 3. Plan the patch for each eligible finding

For each eligible finding, before touching any code, decide:

- **Which file(s) does this touch?** Prefer the `evidence[].file` paths on the finding itself.
  If the recommendation implies changes elsewhere (e.g. "extract this into a new
  `OrderRepository`"), enumerate the target files explicitly. If the set is larger than ~3 files
  or the finding requires designing a new abstraction, skip with reason `requires-human-judgment`.
- **Is the change mechanical?** A mechanical change is one where the recommendation names a
  specific, concrete edit — "replace `float` with `BigDecimal` for the `amount` field", "add a
  `@Retryable(maxAttempts = 3)` annotation to the consumer method", "add a DLQ producer at
  `src/main/java/.../consumer/OrderEventConsumer.java`". A non-mechanical change is one that
  requires design judgment — "improve the data model", "reconsider the boundary between service
  X and Y". Skip non-mechanical ones with `requires-human-judgment`.
- **Are the evidence citations still valid?** Re-verify each `evidence[].file:line` still exists
  and still says what the finding claims. If the code has moved since the audit, skip with
  reason `stale-evidence` — re-run the audit first.

Write the plan for each eligible finding (target files, exact edit, branch name, PR title/body)
into memory before any commit — this is the artifact you'll act on in step 4.

## 4. Apply, one finding at a time

For each finding whose plan survived step 3, in order of severity (`critical` first, then `high`,
then down):

1. **Start from the default branch, clean.** `git switch <default-branch>` then `git pull
   --ff-only`. If any step fails, stop the whole run — don't leave the tree in a half-applied
   state.
2. **Create a branch.** Name it `arch-debt/<finding-id>-<short-slug>`, e.g.
   `arch-debt/f17-add-dlq-order-events`. If the branch exists, append `-2`, `-3`, … (rule 7).
3. **Apply the edit.** Use targeted `replace_in_file`-style edits driven by the finding's
   evidence — never a full-file rewrite. Keep the change surface minimal; the reviewer needs to
   see exactly what the recommendation implied, and nothing else.
4. **Verify the change compiles/parses if there's an obvious way to.** For Java repos:
   `./gradlew compileJava` on the affected module if a `build.gradle` is present. For Python:
   `python -m py_compile <file>` on touched files. Don't run full test suites — that's slow and
   out of scope; the reviewer will. If the quick compile check fails, revert the branch and skip
   the finding with reason `patch-broke-build`.
5. **Commit.** One commit per PR, message format:
   ```
   arch-debt(<finding-id>): <one-line recommendation summary>

   Auto-generated by the architecture-debt-patcher skill in response to a finding
   from an architecture-debt-visualizer audit run. Review the linked finding in the
   report before merging — the recommendation applied here is mechanical; the
   architectural judgment behind it belongs to the reviewer.

   Finding severity: <severity>
   Finding dimension: <dimension>
   Evidence: <file:line list>
   ```
6. **Push and open the PR.** `git push -u origin <branch>` then:
   ```
   gh pr create \
     --title "arch-debt(<finding-id>): <one-line summary>" \
     --body "<PR body — see below>" \
     --base <default-branch> \
     --head <branch>
   ```
   PR body must include:
   - the finding's `claim`,
   - its `doc_source` / `doc_location` (or "no explicit doc claim — direct evaluation" for
     evaluation-pass findings),
   - its `recommendation` verbatim,
   - the exact evidence citations,
   - a "how this PR interprets the recommendation" section explaining what edit was applied,
   - an explicit note that the audit skill's judgment does not remove the need for a human
     reviewer to approve.
7. **Return to the default branch** before starting the next finding.

If any step within a single finding fails after the branch is created, delete the local branch
and continue with the next finding — don't abort the whole run for one bad patch.

## 5. Handle the "already fixed" case

Before applying the edit in step 4.3, check whether the code already reflects the recommendation
(the audit may be slightly stale, or a previous patcher run may have already fixed it). If yes,
skip with reason `already-fixed` and don't open an empty PR.

## 6. Report back to the caller

Return a structured summary the caller (`/eval-architecture`) can render:

```json
{
  "eligible_count": <n>,
  "prs_opened": [
    {"finding_id": "f17", "severity": "high", "pr_url": "https://github.com/..."}
  ],
  "skipped": [
    {"finding_id": "f3", "severity": "medium", "reason": "below-threshold"},
    {"finding_id": "f8", "severity": "high", "reason": "requires-human-judgment",
     "detail": "Recommendation names two alternatives without picking one."}
  ],
  "aborted": false,
  "abort_reason": null
}
```

If the run was aborted before finishing (e.g. dirty worktree, `gh` not authed, evidence broadly
stale), set `aborted: true` and populate `abort_reason` with a one-line human explanation. Any
PRs opened before the abort still count and go in `prs_opened`.

## Skip-reason vocabulary (fixed set)

- `below-threshold` — severity below `--min-risk`.
- `info-severity` — `info` findings are never eligible.
- `no-recommendation` — missing/empty `recommendation` field.
- `requires-human-judgment` — vague recommendation, multiple alternatives, or new-abstraction
  design work.
- `too-many-files` — recommendation would touch more than ~3 files.
- `stale-evidence` — one or more evidence citations no longer resolve.
- `patch-broke-build` — mechanical patch applied but the quick compile check failed.
- `already-fixed` — code already reflects the recommendation.
- `branch-push-failed` — `git push` or `gh pr create` failed (include stderr snippet in
  `detail`).

Any other reason means the skill is trying to guess — see rule 5. Add a new fixed reason to this
list rather than emitting free-text.

## Not in scope

- Changing docs to match code (the reverse direction). If the audit found a `misaligned` claim
  where the code is correct and the doc is wrong, patching the doc is often the right move — but
  it's a different workflow with a different review lens and is not this skill.
- Rewriting test suites. If a recommendation requires new tests, skip with
  `requires-human-judgment`.
- Multi-finding refactors. If two findings would obviously be fixed by one edit, still open two
  PRs (rule 2) — or, better, skip both with `requires-human-judgment` and let a human decide
  whether to combine them.
