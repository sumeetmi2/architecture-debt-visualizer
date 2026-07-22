#!/usr/bin/env python3
"""Render a self-contained HTML report from findings + dependency graph + churn data.

Inputs (all JSON):
  --findings   required. Schema:
    {
      "title": "optional report title",
      "doc_sources": ["docs/boundaries.md", "README.md"],
      "findings": [
        {
          "id": "f1",
          "claim": "short statement of the claim or architectural concern being assessed",
          "doc_source": "docs/boundaries.md",
          "doc_location": "line 74 / heading name",
          "classification": "confirmed" | "misaligned" | "gap" | "risk" | "strength",
          "dimension": "correctness" | "scale-requirements" | "extensibility-requirements" |
                       "scalability" | "extensibility" | "maintainability" | "performance-cost" |
                       "data-architecture" | "observability" | "vision-alignment",
          "severity": "info" | "low" | "medium" | "high",
          "packages": ["com.example.app.consumer"],
          "evidence": [{"file": "path", "line": 42, "note": "why this supports/contradicts the claim"}],
          "explanation": "grounded narrative, cites evidence",
          "recommendation": "optional: what an architect would actually do about it"
        }
      ]
    }
  --dep-graph  optional. Output of extract_dep_graph.py. Used for the static-analysis panel
               (package/class/coupling counts), not rendered as a graph.
  --churn      optional. Output of compute_churn.py. Used for the static-analysis panel
               (highest-churn packages).
  --out        output HTML path (default report.html).

`classification` drives correctness (confirmed/misaligned/gap, from doc-vs-code reconciliation);
`risk` and `strength` are for findings that don't map to a specific doc claim — standalone
architectural judgment calls. `dimension` and `severity` classify what KIND of concern it is and
how much it matters, independent of confirmed/misaligned/gap/risk/strength.

The report has three parts: an overall score (see SCORE PHILOSOPHY below), a static-analysis panel
(deterministic signals from the dep graph / churn data — no LLM judgment in these numbers), and the
findings themselves (a curated "key findings" shortlist plus the full filterable table).

No third-party dependencies: pure stdlib, single output file (inline CSS/JS).
"""
import argparse
import html
import json

CLASS_COLOR = {
    "gap": "#d97706",
    "misaligned": "#dc2626",
    "risk": "#a855f7",
    "confirmed": "#16a34a",
    "strength": "#0ea5e9",
}
CLASS_LABEL = {
    "gap": "Gap",
    "misaligned": "Misaligned",
    "risk": "Risk",
    "confirmed": "Confirmed",
    "strength": "Strength",
}
DIMENSION_LABEL = {
    "correctness": "Correctness",
    "scale-requirements": "Scale Requirements",
    "extensibility-requirements": "Extensibility Requirements",
    "scalability": "Scalability",
    "extensibility": "Extensibility",
    "maintainability": "Maintainability",
    "performance-cost": "Performance / Cost",
    "data-architecture": "Data Architecture",
    "observability": "Observability",
    "vision-alignment": "Vision Alignment",
}
SEVERITY_LABEL = {"info": "Info", "low": "Low", "medium": "Medium", "high": "High"}
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}

# --- SCORE PHILOSOPHY ---
# This is a heuristic, debt-weighted signal, not a certified quality metric. Only findings that
# represent unresolved concern (risk / misaligned / gap) count against the score; `confirmed`
# findings are the expected baseline (doc matches code) and don't move the score either way.
# `strength` findings give a small, capped bonus — crediting sound decisions without letting them
# buy back real debt found elsewhere. Penalty weights are deliberately mild per-finding (a single
# high-severity issue shouldn't zero out the score) but additive, so a system with many real
# concerns scores low even if no single one is catastrophic — that's intentional: architecture
# debt is usually death by a thousand cuts, not one dramatic flaw.
# Known limitations, stated plainly: (1) more thorough scrutiny surfaces more findings, so two runs
# at different depth aren't comparable — this score is for tracking one repo's trend over time as
# findings get fixed, not for ranking repos against each other. (2) findings aren't independent —
# several may share one root cause (see f38/f39/f40 in this report) and get penalized separately.
# (3) it can't weigh business impact or likelihood, only severity as judged during this review.
# Treat it as "how much unresolved, evidenced concern did this review surface," not a grade.
# Per-dimension penalty is capped (DIMENSION_PENALTY_CAP) before summing across dimensions: measured
# run-to-run variance showed one dimension happening to be unusually issue-rich (e.g. 5 high-severity
# data-architecture findings on one run vs. 2 on an equally-thorough run) swinging the headline score
# by 15-20+ points on its own — the cap bounds how much any single dimension can move the number,
# so score differences track genuine breadth-of-concern rather than which dimension got lucky/unlucky
# in what it happened to turn up.
SCORE_WEIGHTS = {"high": 6, "medium": 3, "low": 1, "info": 0}
DIMENSION_PENALTY_CAP = 15
STRENGTH_BONUS_PER = 1
STRENGTH_BONUS_CAP = 5
SCORE_BANDS = [
    (80, "Strong — few unresolved concerns"),
    (60, "Solid, with notable gaps"),
    (40, "Notable debt — worth active attention"),
    (20, "Significant debt — treat as a priority"),
    (0, "Critical — foundational concerns unresolved"),
]


def load(path):
    if not path:
        return None
    with open(path) as fh:
        return json.load(fh)


def s(d, key, default=""):
    """Null-safe string field access — a JSON `"key": null` (not just a missing key) is valid
    input for optional finding fields (evaluation-pass findings often have no doc claim), and
    dict.get(key, default) only substitutes for a MISSING key, not an explicit null value."""
    val = d.get(key)
    return val if val is not None else default


def compute_score(findings):
    penalty_by_dim = {}
    for f in findings:
        if f.get("classification") in ("risk", "misaligned", "gap"):
            dim = s(f, "dimension", "correctness")
            penalty_by_dim[dim] = penalty_by_dim.get(dim, 0) + SCORE_WEIGHTS.get(s(f, "severity", "info"), 0)
    penalty = sum(min(p, DIMENSION_PENALTY_CAP) for p in penalty_by_dim.values())
    bonus = min(STRENGTH_BONUS_CAP, STRENGTH_BONUS_PER * sum(1 for f in findings if f.get("classification") == "strength"))
    score = max(0, min(100, 100 - penalty + bonus))
    label = next(lbl for threshold, lbl in SCORE_BANDS if score >= threshold)
    return score, label, penalty, bonus


def build_score_card(findings):
    score, label, penalty, bonus = compute_score(findings)
    return f"""
    <div class="score-card">
      <div class="score-number">{score}<span class="score-max">/100</span></div>
      <div class="score-label">{html.escape(label)}</div>
      <div class="score-math muted">-{penalty} debt penalty, +{bonus} strength credit</div>
      <details class="score-philosophy">
        <summary>Score philosophy — read before treating this as a grade</summary>
        <p>Heuristic, debt-weighted signal, not a certified quality score. Only <b>risk</b>,
        <b>misaligned</b>, and <b>gap</b> findings count against it, weighted by severity
        (high=6, medium=3, low=1, info=0) and summed <b>per dimension, each dimension capped at
        15</b> before those capped totals are added together — <b>confirmed</b> findings are the
        expected baseline and don't move it; <b>strength</b> findings give a small capped bonus
        (+1 each, max +5) without buying back debt found elsewhere. The per-dimension cap exists so
        one unusually issue-rich dimension can't swing the whole score on its own — score
        differences should track breadth of concern across the system, not which single area
        happened to turn up the most.</p>
        <p><b>Known limitations:</b> deeper review surfaces more findings, so this number isn't
        comparable across repos or across runs at different scope/depth — use it to track one
        repo's trend as issues get fixed, not to rank systems against each other. Findings aren't
        independent (several here share one root cause and are still penalized separately). It
        reflects severity as judged during this review, not business impact or likelihood.</p>
      </details>
    </div>
    """


def build_static_analysis(dep_graph, churn):
    if not dep_graph and not churn:
        return "<p class='muted'>No dependency-graph or churn data supplied.</p>"

    parts = []

    if dep_graph:
        nodes = dep_graph.get("nodes", [])
        edges = dep_graph.get("edges", [])
        total_classes = sum(n["class_count"] for n in nodes)
        fan = {}
        for e in edges:
            fan[e["from"]] = fan.get(e["from"], 0) + e["weight"]
            fan[e["to"]] = fan.get(e["to"], 0) + e["weight"]
        top_coupled = sorted(fan.items(), key=lambda kv: -kv[1])[:5]
        top_size = sorted(nodes, key=lambda n: -n["class_count"])[:5]

        parts.append(f"""
        <div class="insight-block">
          <div class="insight-title">Dependency graph</div>
          <div class="insight-stats">{len(nodes)} packages · {total_classes} classes · {len(edges)} cross-package import edges</div>
          <div class="insight-sub">Most-coupled packages (fan-in + fan-out)</div>
          <ol class="insight-list">
            {"".join(f"<li><code>{html.escape(pkg.rsplit('.', 1)[-1])}</code><span class='muted'> — {pkg}</span><b>{w}</b></li>" for pkg, w in top_coupled)}
          </ol>
          <div class="insight-sub">Largest packages (class count)</div>
          <ol class="insight-list">
            {"".join(f"<li><code>{html.escape(n['id'].rsplit('.', 1)[-1])}</code><span class='muted'> — {n['id']}</span><b>{n['class_count']}</b></li>" for n in top_size)}
          </ol>
        </div>
        """)

    if churn:
        top_churn = list(churn.get("packages", {}).items())[:5]
        parts.append(f"""
        <div class="insight-block">
          <div class="insight-title">Git churn (since {html.escape(churn.get('since', 'n/a'))})</div>
          <div class="insight-sub">Highest-churn packages (commits touching them)</div>
          <ol class="insight-list">
            {"".join(f"<li><code>{html.escape(pkg.rsplit('.', 1)[-1])}</code><span class='muted'> — {pkg}</span><b>{c}</b></li>" for pkg, c in top_churn)}
          </ol>
        </div>
        """)

        bus_factor = churn.get("bus_factor_hotspots", [])
        diversity = churn.get("high_diversity_hotspots", [])
        if bus_factor or diversity:
            pkg_authors = churn.get("package_authors", {})

            def author_of(pkg):
                top = pkg_authors.get(pkg, {}).get("top_authors", [])
                return html.escape(top[0][0]) if top else "?"

            def top3(pkg):
                names = [a for a, _ in pkg_authors.get(pkg, {}).get("top_authors", [])[:3]]
                return html.escape(", ".join(names))

            parts.append(f"""
            <div class="insight-block">
              <div class="insight-title">Contributor concentration (bus factor)</div>
              <div class="insight-stats">Packages with ≥5 commits in the window, split by how many distinct people have touched them — a churn count alone doesn't say whether that knowledge is shared or sitting with one person.</div>
              <div class="insight-sub">Single-author hotspots (bus-factor risk)</div>
              <ol class="insight-list">
                {"".join(f"<li><code>{html.escape(pkg.rsplit('.', 1)[-1])}</code><span class='muted'> — {author_of(pkg)}</span><b>{c}</b></li>" for pkg, c in bus_factor[:5]) or "<li class='muted'>None found</li>"}
              </ol>
              <div class="insight-sub">Most contributor-diverse packages</div>
              <ol class="insight-list">
                {"".join(f"<li><code>{html.escape(pkg.rsplit('.', 1)[-1])}</code><span class='muted'> — {top3(pkg)}</span><b>{n} authors</b></li>" for pkg, n in diversity[:5]) or "<li class='muted'>None found</li>"}
              </ol>
            </div>
            """)

    return "\n".join(parts)


def build_key_findings(findings):
    pressing = [f for f in findings if f.get("classification") in ("risk", "misaligned", "gap")
                and SEVERITY_RANK.get(s(f, "severity", "info"), 0) >= 2]
    pressing.sort(key=lambda f: -SEVERITY_RANK.get(s(f, "severity", "info"), 0))
    pressing = pressing[:8]

    if not pressing:
        return "<p class='muted'>No high/medium-severity risks, gaps, or misalignments found.</p>"

    items = []
    for f in pressing:
        cls = s(f, "classification", "risk")
        sev = s(f, "severity", "info")
        items.append(f"""
        <li class="key-finding" data-sev="{sev}">
          <a href="#row-{html.escape(f['id'])}" class="key-finding-link">
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
        cls = s(f, "classification", "gap")
        dim = s(f, "dimension", "correctness")
        severity = s(f, "severity", "info")
        evidence_html = "<br>".join(
            f'{html.escape(s(ev, "file"))}'
            + (f':{ev["line"]}' if ev.get("line") else "")
            + (f' — {html.escape(s(ev, "note"))}' if ev.get("note") else "")
            for ev in (f.get("evidence") or [])
        )
        recommendation = s(f, "recommendation")
        rec_html = f'<div class="recommendation"><b>Recommendation:</b> {html.escape(recommendation)}</div>' if recommendation else ""
        rows.append(
            f'<tr class="finding-row" id="row-{html.escape(f["id"])}" data-cls="{cls}" data-dim="{dim}" data-sev="{severity}">'
            f'<td><span class="badge badge-{cls}">{CLASS_LABEL.get(cls, cls)}</span>'
            f'<div class="dim-tag">{DIMENSION_LABEL.get(dim, dim)} · {SEVERITY_LABEL.get(severity, severity)}</div></td>'
            f'<td>{html.escape(s(f, "claim"))}'
            f'<div class="explanation">{html.escape(s(f, "explanation"))}</div>'
            f'{rec_html}</td>'
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
  .summary {{ display: flex; gap: 12px; padding: 16px 32px; flex-wrap: wrap; }}
  .stat {{ padding: 10px 16px; border-radius: 8px; background: #1e293b; font-size: 13px; }}
  .stat b {{ font-size: 18px; display: block; }}
  .stat.confirmed {{ border-left: 4px solid #16a34a; }}
  .stat.misaligned {{ border-left: 4px solid #dc2626; }}
  .stat.gap {{ border-left: 4px solid #d97706; }}
  .stat.risk {{ border-left: 4px solid #a855f7; }}
  .stat.strength {{ border-left: 4px solid #0ea5e9; }}
  .score-card {{ margin: 0 32px 16px; padding: 16px 20px; border-radius: 12px; background: #111827;
                 border: 1px solid #1e293b; display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; }}
  .score-number {{ font-size: 36px; font-weight: 700; color: #e2e8f0; }}
  .score-max {{ font-size: 16px; color: #64748b; font-weight: 400; }}
  .score-label {{ font-size: 14px; color: #cbd5e1; }}
  .score-math {{ font-size: 12px; }}
  .score-philosophy {{ flex-basis: 100%; margin-top: 8px; }}
  .score-philosophy summary {{ cursor: pointer; font-size: 12px; color: #7dd3fc; }}
  .score-philosophy p {{ font-size: 12px; color: #94a3b8; line-height: 1.5; margin: 8px 0 0; }}
  main {{ display: flex; gap: 24px; padding: 0 32px 32px; flex-wrap: wrap; align-items: flex-start; }}
  .left-panel {{ flex: 1 1 380px; min-width: 300px; display: flex; flex-direction: column; gap: 20px; }}
  .panel-card {{ background: #111827; border-radius: 12px; padding: 16px; border: 1px solid #1e293b; }}
  .panel-title {{ font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 10px;
                   text-transform: uppercase; letter-spacing: .03em; }}
  .insight-block + .insight-block {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid #1e293b; }}
  .insight-title {{ font-size: 12.5px; font-weight: 600; color: #cbd5e1; }}
  .insight-stats {{ font-size: 12px; color: #94a3b8; margin: 4px 0 10px; }}
  .insight-sub {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .03em; margin: 10px 0 4px; }}
  .insight-list {{ list-style: none; margin: 0; padding: 0; font-size: 12.5px; }}
  .insight-list li {{ display: flex; align-items: baseline; gap: 6px; padding: 3px 0; }}
  .insight-list code {{ color: #7dd3fc; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11.5px; }}
  .insight-list .muted {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10.5px; }}
  .insight-list b {{ color: #e2e8f0; }}
  .key-findings-list {{ list-style: none; margin: 0; padding: 0; }}
  .key-finding {{ border-bottom: 1px solid #1e293b; }}
  .key-finding:last-child {{ border-bottom: none; }}
  .key-finding-link {{ display: flex; gap: 8px; align-items: baseline; padding: 8px 0; text-decoration: none; color: inherit; }}
  .key-finding-claim {{ font-size: 12.5px; color: #e2e8f0; }}
  .table-panel {{ flex: 2 1 640px; min-width: 320px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  th {{ color: #94a3b8; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
  .badge {{ padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .badge-confirmed {{ background: #16a34a33; color: #4ade80; }}
  .badge-misaligned {{ background: #dc262633; color: #f87171; }}
  .badge-gap {{ background: #d9770633; color: #fbbf24; }}
  .badge-risk {{ background: #a855f733; color: #d8b4fe; }}
  .badge-strength {{ background: #0ea5e933; color: #7dd3fc; }}
  .badge-sev-high {{ background: #7f1d1d; color: #fecaca; }}
  .badge-sev-medium {{ background: #78350f; color: #fde68a; }}
  .badge-sev-low {{ background: #1e293b; color: #94a3b8; }}
  .dim-tag {{ color: #64748b; font-size: 10.5px; margin-top: 4px; }}
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
  <div class="subtitle">Doc sources: {doc_sources}</div>
</header>
{score_card}
<div class="summary">
  <div class="stat confirmed"><b>{n_confirmed}</b>Confirmed</div>
  <div class="stat misaligned"><b>{n_misaligned}</b>Misaligned</div>
  <div class="stat gap"><b>{n_gap}</b>Gaps</div>
  <div class="stat risk"><b>{n_risk}</b>Architecture Risks</div>
  <div class="stat strength"><b>{n_strength}</b>Strengths</div>
</div>
<div class="filters" id="cls-filters">
  <span class="group-label">Type</span>
  <button class="active" data-filter-group="cls" data-filter="all">All</button>
  <button data-filter-group="cls" data-filter="confirmed">Confirmed</button>
  <button data-filter-group="cls" data-filter="misaligned">Misaligned</button>
  <button data-filter-group="cls" data-filter="gap">Gaps</button>
  <button data-filter-group="cls" data-filter="risk">Risks</button>
  <button data-filter-group="cls" data-filter="strength">Strengths</button>
</div>
<div class="filters" id="dim-filters">
  <span class="group-label">Dimension</span>
  <button class="active" data-filter-group="dim" data-filter="all">All</button>
  <button data-filter-group="dim" data-filter="correctness">Correctness</button>
  <button data-filter-group="dim" data-filter="scale-requirements">Scale Requirements</button>
  <button data-filter-group="dim" data-filter="extensibility-requirements">Extensibility Requirements</button>
  <button data-filter-group="dim" data-filter="scalability">Scalability</button>
  <button data-filter-group="dim" data-filter="extensibility">Extensibility</button>
  <button data-filter-group="dim" data-filter="maintainability">Maintainability</button>
  <button data-filter-group="dim" data-filter="performance-cost">Performance / Cost</button>
  <button data-filter-group="dim" data-filter="data-architecture">Data Architecture</button>
  <button data-filter-group="dim" data-filter="observability">Observability</button>
  <button data-filter-group="dim" data-filter="vision-alignment">Vision Alignment</button>
</div>
<main>
  <div class="left-panel">
    <div class="panel-card">
      <div class="panel-title">Key pressing findings</div>
      {key_findings}
    </div>
    <div class="panel-card">
      <div class="panel-title">Static code analysis</div>
      {static_analysis}
    </div>
  </div>
  <div class="table-panel">
    <table>
      <thead><tr><th>Finding</th><th>Claim / Explanation</th><th>Doc source</th><th>Code evidence</th></tr></thead>
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
    ap.add_argument("--dep-graph", default=None)
    ap.add_argument("--churn", default=None)
    ap.add_argument("--out", default="report.html")
    args = ap.parse_args()

    findings_doc = load(args.findings)
    dep_graph = load(args.dep_graph)
    churn = load(args.churn)

    findings = findings_doc.get("findings", [])
    title = s(findings_doc, "title", "Architecture Debt Visualizer Report")
    doc_sources = ", ".join(findings_doc.get("doc_sources", [])) or "n/a"

    counts = {"confirmed": 0, "misaligned": 0, "gap": 0, "risk": 0, "strength": 0}
    for f in findings:
        cls = s(f, "classification")
        if cls in counts:
            counts[cls] += 1

    html_out = TEMPLATE.format(
        title=html.escape(title),
        doc_sources=html.escape(doc_sources),
        score_card=build_score_card(findings),
        n_confirmed=counts["confirmed"],
        n_misaligned=counts["misaligned"],
        n_gap=counts["gap"],
        n_risk=counts["risk"],
        n_strength=counts["strength"],
        key_findings=build_key_findings(findings),
        static_analysis=build_static_analysis(dep_graph, churn),
        findings_rows=build_findings_table(findings),
    )

    with open(args.out, "w") as fh:
        fh.write(html_out)
    score, label, _, _ = compute_score(findings)
    print(f"Wrote {args.out} ({len(findings)} findings, score {score}/100 — {label})")


if __name__ == "__main__":
    main()
