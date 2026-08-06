# Design review mode — evaluating a new feature proposal

`design-review` mode answers a different question than reconcile/evaluate: not "is this repo's
architecture sound," but **"should this proposal be built, as written, against the systems it
actually touches?"** The target repo(s) exist to give the review real context (existing patterns,
boundaries, capacity) — the proposal is the thing under evaluation, not the code.

**Act as a staff/principal engineer running a design review**, the same posture step 5 asks for in
evaluate mode: independent judgment, not a checklist recital. A proposal that "sounds reasonable"
still needs its concrete claims checked against what the target system(s) actually do today.

## A. Ingest the proposal

Determine the source type and extract full text before doing anything else:

- **Confluence page** — `mcp__claude_ai_Atlassian_Rovo__getConfluencePage` (by URL or page ID).
  Also pull `getConfluencePageInlineComments`/`getConfluencePageFooterComments` if present — review
  comments on the page frequently contain unresolved objections worth folding into open-questions.
- **Google Slides/Docs** — `mcp__claude_ai_Google_Drive__read_file_content` (or
  `download_file_content` if the file needs exporting first).
- **Local slide deck (.pptx)** — `scripts/extract_pptx_text.py --pptx <path> --out <run_dir>/proposal.txt`.
  Deterministic, pure-stdlib slide-text extraction (no python-pptx dependency). Slide numbers are
  preserved in the output — cite them in `doc_location` (e.g. `"Slide 6"`).
- **Local PDF** — use the `Read` tool directly (already handles PDF; use its `pages` param for a
  long deck).
- **Local Keynote (.key)** — not supported by the extractor; ask the user to export to `.pptx` or
  `.pdf` first rather than guessing at binary content.
- **Pasted text/markdown** — use as-is, no extraction step needed.

Write the extracted text to `<run_dir>/proposal.txt` regardless of source — step B's repo-discovery
script reads from a file, not from conversation context.

**Text extraction alone is not enough whenever the proposal contains an architecture diagram —
you must also view the diagram-bearing slides as images.** Confirmed by dogfooding: a Google
Slides architecture diagram's entire set of component labels (box names, data-flow annotations,
even an explicit "store audit logs" label) was completely absent from `read_file_content`'s
extracted text — not garbled, just silently missing, because the diagram was a grouped
drawing/shape object rather than native text boxes the extractor recognizes. A review run on text
alone drew a wrong conclusion from this (claimed audit logging had no architecture behind it, when
the diagram showed it did) and had to be corrected once the actual image was viewed. Don't let that
happen silently again:

1. Export the source to PDF and view it directly:
   - Google Slides/Docs → `mcp__claude_ai_Google_Drive__download_file_content` with
     `exportMimeType: "application/pdf"`, decode the returned base64 `content` field, write it to
     `<run_dir>/proposal.pdf`.
   - Confluence → export/download as PDF if the page has embedded diagrams (draw.io macros,
     attached images); check `getConfluencePage`'s response for attachment/image references you'd
     otherwise miss.
   - Local `.pptx`/`.pdf` → already a file; skip straight to viewing it.
2. View the diagram-bearing slides with `Read` on the PDF, using its `pages` parameter (e.g.
   `pages: "5-8"` for a proposal's architecture section) — this renders each page as an image via
   `pdftoppm`. **If `Read` errors that `pdftoppm`/poppler isn't installed, install it yourself**
   (`brew install poppler` on macOS, `apt-get install poppler-utils` on Linux) rather than skipping
   the diagram — this is a one-time environment dependency, not a reason to fall back to text-only.
3. Treat what you see in the diagram as a first-class claim source, same as slide text — box
   labels, data-flow arrows, and annotations are claims about the design just as much as bullet
   points are, and findings drawn from them cite the diagram the same way (`doc_location`: name the
   diagram, e.g. "Northstar Architecture diagram — Authentication box").
4. **Never send proposal diagrams to a third-party image/diagram-conversion web tool** (image-to-
   Mermaid converters and similar) to work around a missing local capability — that uploads a
   client's internal architecture to an outside service. Viewing the image directly (step 2) is not
   just a substitute for that, it's the correct approach: it stays local and needs no third party.

## B. Discover and prepare target repos

The proposal's primary target is always the repo the skill is invoked in (cwd) — no argument
needed, consistent with reconcile/evaluate mode. But a proposal frequently touches *other* systems
by name or link ("Service A calls the new endpoint added to Service B"). Don't limit the review to
cwd alone when the proposal itself names other repos.

1. Run the discovery script against the extracted proposal text:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/discover_repos.py \
     --proposal-text "$RUN_DIR/proposal.txt" \
     --dest-root "$RUN_DIR/repos" \
     --out "$RUN_DIR/repos.json"
   ```
   This finds every `github.com`/`bitbucket.org` URL (https or `git@host:` form) in the proposal
   text, dedupes them, and attempts a shallow `git clone --depth 1` of each using whatever
   credentials the `git` CLI already has configured (SSH keys, stored HTTPS creds, `gh` credential
   helper). It always emits the primary repo (cwd) as entry 0 with `clone_status: "primary"`.
2. **For any entry where `clone_status` is `"failed"`**, check whether an MCP tool can succeed
   where the bare `git` CLI couldn't — a plain Python script has no MCP access, so this step
   necessarily happens as a tool call, not inside the script:
   - GitHub URL → try `gh repo clone <owner>/<repo> <dest>` via Bash if the `gh` CLI is
     authenticated, or ask the user if they have GitHub access configured another way.
   - Bitbucket URL → check whether `mcp__bitbucket__bb_clone` is available (it may be a deferred
     tool — `ToolSearch` for it) and use it to clone into the same `dest` path the script recorded.
   - If neither succeeds, **don't fabricate what that repo contains.** Record it as an inaccessible
     secondary system: note it in the report's target-systems panel and in any finding whose
     confidence depends on it (`confidence: "low"`, a `limitations` entry naming the repo as
     unreachable). The review still proceeds against every repo it *does* have access to — an
     inaccessible secondary repo narrows scope, it doesn't block the whole review.
3. Re-run `discover_repos.py` is unnecessary once repos are cloned — read cloned repos directly
   with normal file tools from their `dest` path in `repos.json`.

## C. Establish context per target repo

For the primary repo and every successfully-cloned secondary, run the same classification
procedure as `references/system-classification.md` (step 1.5), once per repo. Record all of them
in `context.json` as an array keyed by the same repo label `discover_repos.py` used
(`host/owner/repo`, or `"primary"` for cwd):

```json
{
  "proposal_summary": "One or two sentences: what is actually being proposed.",
  "repos": {
    "primary": { "system_type": "production-service", "confidence": "high", "...": "..." },
    "github.com/acme/billing-service": { "system_type": "production-service", "confidence": "medium", "...": "..." }
  }
}
```

This context is what makes the review *fair* rather than generic — a proposal adding a new queue
consumer gets judged against whether the target repo already has a consumer pattern to follow, not
against an abstract ideal.

## D. Extract the proposal's concrete claims

Pull out every falsifiable technical claim the proposal makes, the same spirit as reconciliation's
step 2 but the source is the proposal, not existing docs:

- New/changed components, endpoints, data stores, queues, or entry points.
- Stated scale/load expectations, SLAs, or capacity assumptions.
- Stated integration points with other systems (including any repo found in step B).
- Stated rollout plan, ownership, and dependencies on other teams' work.
- Anything the proposal is silent on that its own scope would normally require an answer for
  (missing rollout plan, no mention of who owns on-call for the new surface) — silence is itself a
  claim ("we don't need one") worth checking, not something to skip past.

## E. Run the design-review checklist

See `scripts/design_review_rubric_manifest.json` for the full checklist (12 dimensions,
architecture-fit through presentation-and-completeness). Two dimensions were added after real
reviews surfaced gaps the other 10 didn't cover:
- `objectives-and-prioritization` — does the design actually serve its own stated objectives,
  proportionate to how the proposal itself prioritizes them? A proposal can pass every
  architecture-fit/data-impact/etc. check individually while still spending most of its design
  depth on its least-important stated objective and almost none on its most-important one.
- `presentation-and-completeness` — is the proposal itself well-structured and complete as a
  *document*, separate from whether its technical content holds up? Covers narrative flow
  (agenda matches what's presented, no duplicated slides, each slide has one clear takeaway),
  audience-fit (density/verbosity appropriate for a time-boxed senior review, implementation
  plumbing not crowding out risk discussion), a presence/absence checklist against standard
  design-doc sections (deployment strategy, rollout/rollback, testing, observability, ownership,
  security review, cost, alternatives, success metrics) — this checks whether a section *exists*,
  not its quality, which the other 11 dimensions already grade, don't double-penalize the same
  underlying gap in both places — and **narrative proportionality**: does the deck's story keep
  returning to its own single most load-bearing dependency (in Objectives, Risks & Mitigation, and
  the Roadmap), proportionate to how much the proposal's value proposition rests on it, or does
  that dependency appear once — often just as an unlabeled diagram arrow — while lower-stakes,
  better-understood implementation detail gets dedicated slides? A proposal can be well-organized
  (agenda matches content, no duplicate slides) and still tell an inverted story. This check is
  usually only answerable *after* the other dimensions have run — the "most load-bearing element"
  is frequently something evaluate-mode digging surfaces (a `dependencies-and-integration.b`
  finding, say), not something visible from the deck alone. Unlike the debt-audit manifest, **every
check here is mandatory on every run** — there's no `system_type_overrides` table, because
applicability varies by what the *proposal* touches, not by what kind of repo the target is. A
proposal with no data-model changes still gets a `data-impact.a` coverage record — just one with
`status: "not-applicable"` and a `reason`, not a skipped check.

For each check, cross-reference the proposal's claim (step D) against the target repo(s)' actual
code (step C's context, plus direct reading) — same evidence discipline as evaluate mode: cite
`file:line` from the target repo, or the specific proposal location (`doc_source`/`doc_location`)
when the finding is about what the proposal does or doesn't say.

Actively look for **strengths** (a proposal that correctly follows an existing pattern, states a
realistic rollout plan, or picks a sound alternative deserves that recorded, not just risks) and
for **open questions** (a proposal isn't wrong to be silent on something if it hasn't been decided
yet — record that as `open-question`, not manufacture a `risk` finding that presumes an answer the
proposal never gave).

## F. Findings schema

Findings use a distinct classification vocabulary from debt-audit mode — `risk`, `strength`, or
`open-question` (not `confirmed`/`misaligned`/`gap`):

```json
{
  "title": "Design Review — <proposal name>",
  "proposal_source": "Confluence: 'New Billing Webhook Proposal' (page 123456)",
  "target_repos": ["primary", "github.com/acme/billing-service"],
  "findings": [
    {
      "id": "f1",
      "check_id": "data-impact.a",
      "claim": "New `webhook_events` table has no migration plan for the 40M existing rows in `events`",
      "doc_source": "Confluence page",
      "doc_location": "Data model section, paragraph 3",
      "classification": "risk",
      "dimension": "data-impact",
      "severity": "high",
      "blocking": true,
      "evidence": [
        {"repo": "primary", "file": "src/main/resources/db/migration/V42__events.sql", "line": 1,
         "note": "existing events table has no backfill tooling referenced anywhere in this repo"}
      ],
      "explanation": "The proposal describes the new table's shape but never addresses the existing 40M-row events table it's meant to supersede — no backfill script, dual-write period, or cutover plan exists in either the proposal or the target repo's migration history.",
      "recommendation": "Add an explicit backfill/dual-write plan before implementation starts; this blocks safe rollout.",
      "confidence": "high",
      "evidence_type": ["direct-code"],
      "limitations": []
    },
    {
      "id": "f2",
      "check_id": "alternatives-and-tradeoffs.a",
      "claim": "Proposal doesn't say whether an existing internal event bus was considered instead of a new webhook",
      "doc_source": "Confluence page",
      "doc_location": "whole page — no alternatives section",
      "classification": "open-question",
      "dimension": "alternatives-and-tradeoffs",
      "severity": "medium",
      "question": "Was the existing internal event bus (used by 3 other services in this repo) evaluated and rejected, or just not considered?",
      "evidence": [{"repo": "primary", "file": "src/main/java/.../EventBusPublisher.java", "line": 1,
                     "note": "existing internal event bus already used by OrderService, InventoryService"}],
      "explanation": "The target repo already has a working internal event bus three other services use for similar fan-out; the proposal doesn't explain why a new external webhook mechanism is needed instead.",
      "confidence": "medium",
      "evidence_type": ["direct-code"],
      "limitations": []
    }
  ]
}
```

Field notes (only what differs from `report-schema.md`'s debt-audit schema):

- `classification` — `risk` / `strength` / `open-question`. No `confirmed`/`misaligned`/`gap`.
- `blocking` — optional bool, only meaningful on `risk` findings. Marks something that must be
  resolved before the proposal should proceed at all (vs. a risk worth flagging but not
  launch-blocking). Reserve it for genuine blockers — data loss, irrecoverable migration,
  security hole in a new surface — not every high-severity finding.
- `question` — required on `open-question` findings: the specific thing that needs an answer.
- `dimension` — one of the 10 `design_review_rubric_manifest.json` dimension ids (see above), not
  the debt-audit dimension list.
- `doc_source`/`doc_location` — identify the **proposal's** location (slide number, Confluence
  section, doc heading), not a repo doc.
- `evidence[].repo` — optional, one of the labels from `repos.json`/`context.json` (defaults to
  `"primary"`). Lets a finding cite code in whichever target repo it's actually about.
- `evidence_type` — same vocabulary as `evidence-standard.md`, plus `"proposal-source"` for
  evidence that's a citation into the proposal itself rather than target-repo code (used on
  `open-question` findings whose evidence is "the proposal says nothing here").

## G. checks.json and context.json

Same shape as debt-audit `checks.json` (`report-schema.md`), against
`design_review_rubric_manifest.json` ids instead of `rubric_manifest.json` ids, **plus one extra
status value: `"open-question"`** (alongside `risk`/`strength`/`clean`/`not-applicable`/
`not-assessed`) — a check whose answer is "the proposal doesn't say" needs a coverage record too,
and forcing that into `risk` or `not-assessed` would misrepresent it (it's not a defect, and it
wasn't skipped). `open-question` requires non-empty `finding_ids`, same as `risk`/`strength`. Every
manifest check needs a coverage record — no system-type-based exemption exists here (see step E).
When the target repo behind a check is genuinely inaccessible (not cloned, no URL found), use
`not-assessed` with a `reason` naming which repo was missing — don't guess at what it would have
shown.

## H. Validate and generate the report

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_design_review.py \
  --findings "$RUN_DIR/findings.json" \
  --checks "$RUN_DIR/checks.json" \
  --context "$RUN_DIR/context.json" \
  --repo-roots "$RUN_DIR/repos.json" \
  --repo-root .
```

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_design_review_report.py \
  --findings "$RUN_DIR/findings.json" \
  --checks "$RUN_DIR/checks.json" \
  --context "$RUN_DIR/context.json" \
  --repos "$RUN_DIR/repos.json" \
  --out "$RUN_DIR/design-review-report.html"
```

The report leads with a **verdict** (`Recommend` / `Recommend With Changes` / `Needs More
Information` / `Do Not Recommend As-Is`), computed mechanically from findings — any `blocking` risk
forces "Do Not Recommend As-Is"; otherwise any high-severity risk forces "Recommend With Changes";
otherwise any medium-severity risk or open question forces "Needs More Information"; only a review
with no unresolved risk or open question earns a plain "Recommend." This is deliberately
conservative — the verdict can't be talked up by strengths, only earned by the absence of
unresolved concerns.

## I. Summarize in chat

Lead with the verdict and why (name the specific blocking/high-severity finding driving it, don't
just state the label). Then: 1-2 open questions worth raising with the proposal's author, 1-2
strengths worth calling out, and which target repos were and weren't accessible (don't bury an
inaccessible secondary repo — it's a real limitation on how complete this review is).
