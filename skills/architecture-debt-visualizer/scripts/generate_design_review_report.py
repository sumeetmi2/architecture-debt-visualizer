#!/usr/bin/env python3
"""Render a self-contained HTML design-review report from findings + checks + context +
the discovered-repos manifest. Sibling to generate_report.py, but framed around a verdict
on a PROPOSAL rather than a debt score on an existing repo — see references/design-review.md.

Inputs (all JSON):
  --findings    required. {"title", "proposal_source", "target_repos": [...], "findings": [...]}
                See references/design-review.md for the finding schema (classification:
                risk/strength/open-question, optional 'blocking' bool on risk findings).
  --checks      optional. {"checks": [...]} against design_review_rubric_manifest.json ids.
  --context     optional. Proposal + target-system context (see design-review.md).
  --repos       optional. discover_repos.py's repos.json (which repos were in scope, access status).
  --out         output HTML path (default design-review-report.html).

No third-party dependencies: pure stdlib, single output file (inline CSS/JS).
"""
import argparse
import html
import json
import os

CLASS_COLOR = {"risk": "#dc2626", "strength": "#0ea5e9", "open-question": "#d97706"}
CLASS_LABEL = {"risk": "Risk", "strength": "Strength", "open-question": "Open Question"}
DIMENSION_LABEL = {
    "architecture-fit": "Architecture Fit",
    "data-impact": "Data Impact",
    "scalability-impact": "Scalability Impact",
    "security-and-compliance": "Security & Compliance",
    "operability": "Operability",
    "migration-and-compatibility": "Migration & Compatibility",
    "cost": "Cost",
    "alternatives-and-tradeoffs": "Alternatives & Tradeoffs",
    "testing-and-validation": "Testing & Validation",
    "dependencies-and-integration": "Dependencies & Integration",
    "objectives-and-prioritization": "Objectives & Prioritization",
    "presentation-and-completeness": "Presentation & Completeness",
}
SEVERITY_LABEL = {"info": "Info", "low": "Low", "medium": "Medium", "high": "High"}
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}

VERDICTS = [
    ("do-not-recommend", "Do Not Recommend As-Is", "#dc2626",
     "At least one blocking risk is unresolved — this needs to be addressed before the proposal can move forward."),
    ("recommend-with-changes", "Recommend With Changes", "#d97706",
     "No blocking risks, but at least one high-severity risk needs to be resolved first."),
    ("needs-more-info", "Needs More Information", "#0ea5e9",
     "No high/blocking risks found, but open questions or medium-severity concerns remain unanswered."),
    ("recommend", "Recommend", "#16a34a",
     "No unresolved risks or open questions surfaced by this review."),
]


def load(path):
    if not path:
        return None
    with open(path) as fh:
        return json.load(fh)


def load_manifest():
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_review_rubric_manifest.json")
    try:
        with open(manifest_path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def s(d, key, default=""):
    val = d.get(key)
    return val if val is not None else default


def compute_verdict(findings):
    blocking = [f for f in findings if f.get("classification") == "risk" and f.get("blocking")]
    high_risk = [f for f in findings if f.get("classification") == "risk" and s(f, "severity") == "high" and not f.get("blocking")]
    medium_risk = [f for f in findings if f.get("classification") == "risk" and s(f, "severity") == "medium"]
    open_qs = [f for f in findings if f.get("classification") == "open-question"]

    if blocking:
        key = "do-not-recommend"
    elif high_risk:
        key = "recommend-with-changes"
    elif medium_risk or open_qs:
        key = "needs-more-info"
    else:
        key = "recommend"
    verdict = next(v for v in VERDICTS if v[0] == key)
    return verdict, len(blocking), len(high_risk), len(medium_risk), len(open_qs)


def build_verdict_block(findings):
    (key, label, color, rationale), n_blocking, n_high, n_medium, n_open = compute_verdict(findings)
    detail_bits = []
    if n_blocking:
        detail_bits.append(f"{n_blocking} blocking risk(s)")
    if n_high:
        detail_bits.append(f"{n_high} high-severity risk(s)")
    if n_medium:
        detail_bits.append(f"{n_medium} medium-severity risk(s)")
    if n_open:
        detail_bits.append(f"{n_open} open question(s)")
    detail = " · ".join(detail_bits) if detail_bits else "no unresolved concerns"
    return f"""
    <div class="verdict-card" style="border-left-color: {color};">
      <div class="verdict-label" style="color: {color};">{html.escape(label)}</div>
      <div class="verdict-rationale">{html.escape(rationale)}</div>
      <div class="verdict-detail muted">{html.escape(detail)}</div>
    </div>
    """


def build_target_repos(repos_doc):
    if not repos_doc:
        return "<p class='muted'>No repos.json supplied — assumed single-repo (cwd) review.</p>"
    rows = []
    for r in repos_doc.get("repos", []):
        status = r.get("clone_status", "unknown")
        badge_color = {"primary": "#0ea5e9", "cloned": "#16a34a", "already-present": "#16a34a",
                       "failed": "#dc2626", "not-attempted": "#64748b"}.get(status, "#64748b")
        label = "primary (cwd)" if status == "primary" else f"{r.get('host', '')}/{r.get('owner', '')}/{r.get('repo', '')}"
        err = f" — {html.escape(r['error'])}" if r.get("error") else ""
        rows.append(
            f"<li><span class='repo-badge' style='background:{badge_color}33; color:{badge_color};'>"
            f"{html.escape(status)}</span> {html.escape(label)}{err}</li>"
        )
    return f"<ul class='repo-list'>{''.join(rows)}</ul>"


def build_check_coverage(checks_doc, manifest):
    if not checks_doc or not manifest:
        return None
    instances_by_id = {}
    for c in checks_doc.get("checks", []):
        instances_by_id.setdefault(c.get("id"), []).append(c)

    status_counts = {"risk": 0, "strength": 0, "open-question": 0, "clean": 0, "not-applicable": 0, "not-assessed": 0}
    total_mandatory = 0
    for dim_def in manifest.get("dimensions", {}).values():
        for chk in dim_def.get("checks", []):
            total_mandatory += 1
            recs = instances_by_id.get(chk["id"])
            statuses = [r.get("status") for r in recs] if recs else ["not-assessed"]
            for st in statuses:
                status_counts[st] = status_counts.get(st, 0) + 1

    covered = sum(1 for k, v in status_counts.items() if k != "not-assessed" for _ in range(v))
    summary = " · ".join(f"{v} {k}" for k, v in status_counts.items() if v)
    pct = round(100 * (total_mandatory - status_counts.get("not-assessed", 0)) / total_mandatory) if total_mandatory else 0
    return f"""
        <div class="insight-block">
          <div class="insight-stats">{total_mandatory} mandatory checks · {pct}% completed</div>
          <div class="insight-stats">{html.escape(summary)}</div>
        </div>
    """, pct


def build_key_findings(findings):
    pressing = [f for f in findings if f.get("classification") in ("risk", "open-question")]
    pressing.sort(key=lambda f: (-1 if f.get("blocking") else 0, -SEVERITY_RANK.get(s(f, "severity", "info"), 0)))
    pressing = pressing[:8]
    if not pressing:
        return "<p class='muted'>No risks or open questions found.</p>"
    items = []
    for f in pressing:
        cls = s(f, "classification", "risk")
        sev = s(f, "severity", "info")
        blocking_tag = "<span class='badge badge-blocking'>BLOCKING</span>" if f.get("blocking") else ""
        items.append(f"""
        <li class="key-finding" data-sev="{sev}">
          <a href="#row-{html.escape(f['id'])}" class="key-finding-link">
            {blocking_tag}
            <span class="badge badge-{cls}">{CLASS_LABEL.get(cls, cls)}</span>
            <span class="badge badge-sev-{sev}">{SEVERITY_LABEL.get(sev, sev)}</span>
            <span class="key-finding-claim">{html.escape(s(f, 'claim'))}</span>
          </a>
        </li>
        """)
    return f'<ul class="key-findings-list">{"".join(items)}</ul>'


def build_findings_table(findings):
    rows = []
    for f in findings:
        cls = s(f, "classification", "risk")
        dim = s(f, "dimension", "architecture-fit")
        severity = s(f, "severity", "info")
        evidence_html = "<br>".join(
            (f"[{html.escape(s(ev, 'repo', 'primary'))}] " if ev.get("repo") else "")
            + f'{html.escape(s(ev, "file"))}'
            + (f':{ev["line"]}' if ev.get("line") else "")
            + (f' — {html.escape(s(ev, "note"))}' if ev.get("note") else "")
            for ev in (f.get("evidence") or [])
        ) or "<span class='muted'>n/a</span>"
        recommendation = s(f, "recommendation")
        question = s(f, "question")
        rec_html = f'<div class="recommendation"><b>Recommendation:</b> {html.escape(recommendation)}</div>' if recommendation else ""
        q_html = f'<div class="recommendation"><b>Needs answer:</b> {html.escape(question)}</div>' if question else ""
        blocking_html = '<span class="badge badge-blocking">BLOCKING</span>' if f.get("blocking") else ""

        meta_bits = []
        for area in (f.get("impact_area") or []):
            meta_bits.append(f'<span class="meta-tag meta-tag-impact">{html.escape(area)}</span>')
        confidence = s(f, "confidence")
        if confidence:
            meta_bits.append(f'<span class="meta-tag meta-tag-confidence">confidence: {html.escape(confidence)}</span>')
        meta_html = f'<div class="meta-tags">{"".join(meta_bits)}</div>' if meta_bits else ""

        rows.append(
            f'<tr class="finding-row" id="row-{html.escape(f["id"])}" data-cls="{cls}" data-dim="{dim}" data-sev="{severity}">'
            f'<td>{blocking_html}<span class="badge badge-{cls}">{CLASS_LABEL.get(cls, cls)}</span>'
            f'<div class="dim-tag">{DIMENSION_LABEL.get(dim, dim)} · {SEVERITY_LABEL.get(severity, severity)}</div>'
            f'{meta_html}</td>'
            f'<td>{html.escape(s(f, "claim"))}'
            f'<div class="explanation">{html.escape(s(f, "explanation"))}</div>'
            f'{rec_html}{q_html}</td>'
            f'<td>{html.escape(s(f, "doc_source"))}'
            f'<div class="muted">{html.escape(s(f, "doc_location"))}</div></td>'
            f'<td class="evidence">{evidence_html}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0;
          background: #0f172a; color: #e2e8f0; }}
  header {{ padding: 24px 32px; border-bottom: 1px solid #1e293b; }}
  h1 {{ margin: 0 0 4px; font-size: 20px; }}
  .subtitle {{ color: #94a3b8; font-size: 13px; }}
  .verdict-card {{ margin: 16px 32px; padding: 18px 22px; border-radius: 12px; background: #111827;
                    border: 1px solid #1e293b; border-left: 6px solid #64748b; }}
  .verdict-label {{ font-size: 22px; font-weight: 700; }}
  .verdict-rationale {{ font-size: 13px; color: #cbd5e1; margin-top: 4px; }}
  .verdict-detail {{ font-size: 12px; margin-top: 6px; }}
  .summary {{ display: flex; gap: 12px; padding: 0 32px 16px; flex-wrap: wrap; }}
  .stat {{ padding: 10px 16px; border-radius: 8px; background: #1e293b; font-size: 13px; }}
  .stat b {{ font-size: 18px; display: block; }}
  .stat.risk {{ border-left: 4px solid #dc2626; }}
  .stat.strength {{ border-left: 4px solid #0ea5e9; }}
  .stat.open-question {{ border-left: 4px solid #d97706; }}
  main {{ display: flex; gap: 24px; padding: 0 32px 32px; flex-wrap: wrap; align-items: flex-start; }}
  .left-panel {{ flex: 1 1 380px; min-width: 300px; display: flex; flex-direction: column; gap: 20px; }}
  .panel-card {{ background: #111827; border-radius: 12px; padding: 16px; border: 1px solid #1e293b; }}
  .panel-title {{ font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 10px;
                   text-transform: uppercase; letter-spacing: .03em; }}
  .insight-block + .insight-block {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid #1e293b; }}
  .insight-stats {{ font-size: 12px; color: #94a3b8; margin: 4px 0 10px; }}
  .repo-list {{ list-style: none; margin: 0; padding: 0; font-size: 12.5px; }}
  .repo-list li {{ padding: 4px 0; }}
  .repo-badge {{ padding: 2px 8px; border-radius: 999px; font-size: 10.5px; font-weight: 600; margin-right: 6px; }}
  .key-findings-list {{ list-style: none; margin: 0; padding: 0; }}
  .key-finding {{ border-bottom: 1px solid #1e293b; }}
  .key-finding:last-child {{ border-bottom: none; }}
  .key-finding-link {{ display: flex; gap: 8px; align-items: baseline; padding: 8px 0; text-decoration: none; color: inherit; flex-wrap: wrap; }}
  .key-finding-claim {{ font-size: 12.5px; color: #e2e8f0; }}
  .table-panel {{ flex: 2 1 640px; min-width: 320px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  th {{ color: #94a3b8; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
  .badge {{ padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .badge-risk {{ background: #dc262633; color: #f87171; }}
  .badge-strength {{ background: #0ea5e933; color: #7dd3fc; }}
  .badge-open-question {{ background: #d9770633; color: #fbbf24; }}
  .badge-blocking {{ background: #7f1d1d; color: #fecaca; margin-right: 4px; }}
  .badge-sev-high {{ background: #7f1d1d; color: #fecaca; }}
  .badge-sev-medium {{ background: #78350f; color: #fde68a; }}
  .badge-sev-low {{ background: #1e293b; color: #94a3b8; }}
  .dim-tag {{ color: #64748b; font-size: 10.5px; margin-top: 4px; }}
  .meta-tags {{ margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }}
  .meta-tag {{ background: #1e293b; color: #94a3b8; border-radius: 4px; padding: 1px 6px; font-size: 10px; white-space: nowrap; }}
  .meta-tag-impact {{ color: #a5b4fc; }}
  .meta-tag-confidence {{ color: #86efac; }}
  .explanation {{ color: #94a3b8; font-size: 12px; margin-top: 4px; }}
  .recommendation {{ color: #d8b4fe; font-size: 12px; margin-top: 6px; }}
  .muted {{ color: #64748b; font-size: 11px; }}
  .evidence {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11.5px; }}
  .filters {{ padding: 4px 32px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
  .filters .group-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-right: 2px; }}
  .filters button {{ background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;
                      padding: 6px 12px; font-size: 12px; cursor: pointer; }}
  .filters button.active {{ background: #334155; border-color: #64748b; }}
  tr.hidden {{ display: none; }}
  tr.flash {{ outline: 2px solid #38bdf8; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="subtitle">Proposal source: {proposal_source}</div>
</header>
{verdict}
<div class="summary">
  <div class="stat risk"><b>{n_risk}</b>Risks</div>
  <div class="stat open-question"><b>{n_open}</b>Open Questions</div>
  <div class="stat strength"><b>{n_strength}</b>Strengths</div>
</div>
<div class="filters" id="cls-filters">
  <span class="group-label">Type</span>
  <button class="active" data-filter-group="cls" data-filter="all">All</button>
  <button data-filter-group="cls" data-filter="risk">Risks</button>
  <button data-filter-group="cls" data-filter="open-question">Open Questions</button>
  <button data-filter-group="cls" data-filter="strength">Strengths</button>
</div>
<div class="filters" id="dim-filters">
  <span class="group-label">Dimension</span>
  <button class="active" data-filter-group="dim" data-filter="all">All</button>
  {dim_buttons}
</div>
<main>
  <div class="left-panel">
    <div class="panel-card">
      <div class="panel-title">Key findings</div>
      {key_findings}
    </div>
    <div class="panel-card">
      <div class="panel-title">Target systems in scope</div>
      {target_repos}
    </div>
    {check_coverage_panel}
  </div>
  <div class="table-panel">
    <table>
      <thead><tr><th>Finding</th><th>Claim / Explanation</th><th>Proposal source</th><th>Evidence</th></tr></thead>
      <tbody id="findings-body">
        {findings_rows}
      </tbody>
    </table>
  </div>
</main>
<script>
  const state = {{ cls: 'all', dim: 'all' }};
  const rows = document.querySelectorAll('.finding-row');
  function applyFilters() {{
    rows.forEach(r => {{
      const clsOk = state.cls === 'all' || r.dataset.cls === state.cls;
      const dimOk = state.dim === 'all' || r.dataset.dim === state.dim;
      r.classList.toggle('hidden', !(clsOk && dimOk));
    }});
  }}
  document.querySelectorAll('.filters button').forEach(btn => btn.addEventListener('click', () => {{
    const group = btn.dataset.filterGroup;
    document.querySelectorAll(`.filters button[data-filter-group="${{group}}"]`).forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state[group] = btn.dataset.filter;
    applyFilters();
  }}));
  document.querySelectorAll('.key-finding-link').forEach(link => link.addEventListener('click', (ev) => {{
    const targetId = link.getAttribute('href').slice(1);
    const row = document.getElementById(targetId);
    if (!row) return;
    ev.preventDefault();
    document.querySelectorAll('.filters button[data-filter-group="cls"]')[0].click();
    document.querySelectorAll('.filters button[data-filter-group="dim"]')[0].click();
    row.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
    row.classList.add('flash');
    setTimeout(() => row.classList.remove('flash'), 2000);
  }}));
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--checks", default=None)
    ap.add_argument("--context", default=None)
    ap.add_argument("--repos", default=None)
    ap.add_argument("--out", default="design-review-report.html")
    args = ap.parse_args()

    findings_doc = load(args.findings)
    checks_doc = load(args.checks)
    repos_doc = load(args.repos)
    manifest = load_manifest()

    findings = findings_doc.get("findings", [])
    title = s(findings_doc, "title", "Design Review Report")
    proposal_source = s(findings_doc, "proposal_source", "n/a")

    counts = {"risk": 0, "strength": 0, "open-question": 0}
    for f in findings:
        cls = s(f, "classification")
        if cls in counts:
            counts[cls] += 1

    coverage = build_check_coverage(checks_doc, manifest)
    dim_buttons = "".join(
        f'<button data-filter-group="dim" data-filter="{dim_id}">{html.escape(label)}</button>'
        for dim_id, label in DIMENSION_LABEL.items()
    )

    html_out = TEMPLATE.format(
        title=html.escape(title),
        proposal_source=html.escape(proposal_source),
        verdict=build_verdict_block(findings),
        n_risk=counts["risk"],
        n_open=counts["open-question"],
        n_strength=counts["strength"],
        dim_buttons=dim_buttons,
        key_findings=build_key_findings(findings),
        target_repos=build_target_repos(repos_doc),
        check_coverage_panel=(
            f'<div class="panel-card"><div class="panel-title">Check coverage</div>{coverage[0]}</div>'
            if coverage else ""
        ),
        findings_rows=build_findings_table(findings),
    )

    with open(args.out, "w") as fh:
        fh.write(html_out)

    (key, label, _, _), n_blocking, n_high, n_medium, n_open = compute_verdict(findings)
    cov_msg = f", coverage {coverage[1]}%" if coverage else ""
    print(f"Wrote {args.out} ({len(findings)} findings — verdict: {label}{cov_msg})")


if __name__ == "__main__":
    main()
