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
                       "data-architecture" | "observability" | "reliability-resilience" |
                       "change-safety" | "security-boundaries" | "vision-alignment",
          "severity": "info" | "low" | "medium" | "high",
          "packages": ["com.example.app.consumer"],
          "evidence": [{"file": "path", "line": 42, "note": "why this supports/contradicts the claim"}],
          "explanation": "grounded narrative, cites evidence",
          "recommendation": "optional: what an architect would actually do about it"
        }
      ]
    }
  --checks     optional. Output of the skill's checks.json (see references/report-schema.md):
               {"checks": [{"id", "dimension", "status", ...}]}. Drives the Audit coverage
               indicator and the "Check coverage" panel. Absent (reconcile-mode runs, or reports
               generated before this schema existed) degrades gracefully to "not run".
  --context    optional. Output of the skill's context.json (system_type classification). Needed
               alongside --checks to compute Audit coverage's mandatory-check denominator.
  --dep-graph  optional. Output of extract_dep_graph.py. Used for the static-analysis panel
               (package/class/coupling counts), not rendered as a graph.
  --churn      optional. Output of compute_churn.py. Used for the static-analysis panel
               (highest-churn packages).
  --out        output HTML path (default report.html).

`classification` drives correctness (confirmed/misaligned/gap, from doc-vs-code reconciliation);
`risk` and `strength` are for findings that don't map to a specific doc claim — standalone
architectural judgment calls. `dimension` and `severity` classify what KIND of concern it is and
how much it matters, independent of confirmed/misaligned/gap/risk/strength.

The report has four headline indicators (Documentation fidelity, Architecture risk, Audit
coverage, Evidence confidence — see INDICATOR PHILOSOPHY below) plus a legacy 0-100 Debt index
kept as a secondary figure, a static-analysis panel, a check-coverage panel (when --checks is
supplied), and the findings themselves (a curated "key findings" shortlist plus the full
filterable, severity-grouped card list).

No third-party dependencies: pure stdlib, single output file (inline CSS/JS).
"""
import argparse
import html
import json
import os

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
    "reliability-resilience": "Reliability / Resilience",
    "change-safety": "Change Safety",
    "security-boundaries": "Security Boundaries",
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
# several may share one root cause and get penalized separately. (3) it can't weigh business impact
# or likelihood, only severity as judged during this review.
# Treat it as "how much unresolved, evidenced concern did this review surface," not a grade.
# Per-dimension penalty is capped (DIMENSION_PENALTY_CAP) before summing across dimensions.
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
RISK_BANDS = [(80, "Low"), (55, "Medium"), (30, "High"), (0, "Critical")]


def load(path):
    if not path:
        return None
    with open(path) as fh:
        return json.load(fh)


def load_manifest():
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(
            "/Users/sumeetsharma/.claude/plugins/marketplaces/architecture-debt-visualizer/"
            "skills/architecture-debt-visualizer/scripts/generate_report.py"
        )),
        "rubric_manifest.json",
    )
    try:
        with open(manifest_path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def s(d, key, default=""):
    """Null-safe string field access — a JSON `"key": null` (not just a missing key) is valid
    input for optional finding fields (evaluation-pass findings often have no doc claim), and
    dict.get(key, default) only substitutes for a MISSING key, not an explicit null value."""
    val = d.get(key)
    return val if val is not None else default


def is_strength(f):
    """A finding counts as a strength if it's explicitly classified that way (standalone,
    no doc claim), OR tagged finding_type="architecture-strength" even when classification
    is "confirmed" (it reconciles against a real doc claim *and* is worth crediting as sound
    design)."""
    return f.get("classification") == "strength" or f.get("finding_type") == "architecture-strength"


def _capped_penalty(findings_subset):
    penalty_by_dim = {}
    for f in findings_subset:
        dim = s(f, "dimension", "correctness")
        penalty_by_dim[dim] = penalty_by_dim.get(dim, 0) + SCORE_WEIGHTS.get(s(f, "severity", "info"), 0)
    return sum(min(p, DIMENSION_PENALTY_CAP) for p in penalty_by_dim.values())


def compute_score(findings):
    """Legacy 0-100 debt index — unchanged formula, kept as the secondary indicator."""
    penalty = _capped_penalty([f for f in findings if f.get("classification") in ("risk", "misaligned", "gap")])
    bonus = min(STRENGTH_BONUS_CAP, STRENGTH_BONUS_PER * sum(1 for f in findings if is_strength(f)))
    score = max(0, min(100, 100 - penalty + bonus))
    label = next(lbl for threshold, lbl in SCORE_BANDS if score >= threshold)
    return score, label, penalty, bonus


def compute_doc_fidelity(findings):
    recon = [f for f in findings if f.get("classification") in ("confirmed", "misaligned", "gap")]
    if not recon:
        return None
    confirmed = sum(1 for f in recon if f.get("classification") == "confirmed")
    return round(100 * confirmed / len(recon)), len(recon)


def compute_architecture_risk(findings):
    eval_findings = [f for f in findings if s(f, "dimension", "correctness") != "correctness"]
    if not eval_findings:
        return None
    penalty = _capped_penalty([f for f in eval_findings if f.get("classification") == "risk"])
    bonus = min(STRENGTH_BONUS_CAP, STRENGTH_BONUS_PER * sum(1 for f in eval_findings if is_strength(f)))
    score = max(0, min(100, 100 - penalty + bonus))
    label = next(lbl for threshold, lbl in RISK_BANDS if score >= threshold)
    return label, score


def compute_audit_coverage(checks_doc, context_doc, manifest):
    if not checks_doc or not context_doc or not manifest:
        return None
    system_type = s(context_doc, "system_type", "production-service")
    overrides = manifest.get("system_type_overrides", {}).get(system_type, {})
    mandatory_ids = set()
    for dim, dim_def in manifest.get("dimensions", {}).items():
        if overrides.get(dim) in ("informational", "not-applicable"):
            continue
        for chk in dim_def.get("checks", []):
            mandatory_ids.add(chk["id"])
    if not mandatory_ids:
        return None
    statuses_by_id = {}
    for c in checks_doc.get("checks", []):
        statuses_by_id.setdefault(c.get("id"), []).append(c.get("status"))
    completed = sum(
        1 for cid in mandatory_ids
        if any(st not in (None, "not-assessed") for st in statuses_by_id.get(cid, []))
    )
    return round(100 * completed / len(mandatory_ids)), completed, len(mandatory_ids)


def compute_evidence_confidence(findings):
    rated = [f for f in findings if f.get("confidence")]
    if not rated:
        return None
    high = sum(1 for f in rated if f.get("confidence") == "high")
    return round(100 * high / len(rated)), len(rated)


# ------------------------------------------------------------------------------------------------
# NEW-LAYOUT template builders (ported from examples/minimal-cli-tool/report-v2skill.html)
# ------------------------------------------------------------------------------------------------

def build_meta_row(findings, dep_graph, checks_doc, context_doc, manifest):
    total_classes = "—"
    if dep_graph:
        nodes = dep_graph.get("nodes", [])
        total_classes = sum(n.get("class_count", 0) for n in nodes)

    coverage = compute_audit_coverage(checks_doc, context_doc, manifest)
    checks_run = f"{coverage[1]} / {coverage[2]}" if coverage else "—"
    system_type = s(context_doc or {}, "system_type", "—")

    items = [
        (str(total_classes), "Classes analyzed"),
        (checks_run, "Mandatory checks run"),
        (str(len(findings)), "Scoped findings"),
        (html.escape(system_type), "System type"),
    ]
    return "".join(
        f'<div class="meta-item"><div class="meta-value">{v}</div><div class="meta-label">{html.escape(l)}</div></div>'
        for v, l in items
    )


def build_score_card(findings):
    score, label, penalty, bonus = compute_score(findings)
    return f"""
<div class="score-card">
  <div class="score-left">
    <div class="eyebrow">Debt index (secondary)</div>
    <div class="score-number">{score}</div>
    <div class="score-caption">-{penalty} debt penalty, +{bonus} strength credit — {html.escape(label)}</div>
  </div>
  <div class="score-right">
    <b>The four indicators below separate two different questions</b> this skill used to blend into
    one number: whether the docs are accurate (Documentation fidelity) is a different axis from
    whether the architecture is sound (Architecture risk) — a repo can improve one and regress the
    other. Audit coverage says how much of the mandatory checklist actually got run; Evidence
    confidence says how much of what's reported rests on direct citation versus inference.
    <details class="score-philosophy">
      <summary>Read before treating any of this as a grade</summary>
      <p>Only <b>risk</b>, <b>misaligned</b>, and <b>gap</b> findings count against the debt index,
      weighted by severity (high=6, medium=3, low=1, info=0) and summed per dimension, each
      dimension capped at 15, before those capped totals are added together; <b>strength</b>
      findings give a small capped bonus (+1 each, max +5). Deeper review surfaces more findings,
      so it isn't comparable across repos or across runs at different scope/depth — use it to
      track one repo's trend, not to rank systems against each other. Findings aren't independent
      (several may share one root cause and still get penalized separately). It reflects severity
      as judged during this review, not business impact or likelihood.</p>
    </details>
  </div>
</div>
"""


def build_indicators_grid(findings, checks_doc, context_doc, manifest):
    doc_fidelity = compute_doc_fidelity(findings)
    arch_risk = compute_architecture_risk(findings)
    coverage = compute_audit_coverage(checks_doc, context_doc, manifest)
    confidence = compute_evidence_confidence(findings)

    blocks = [
        (
            "Documentation fidelity",
            f"{doc_fidelity[0]}%" if doc_fidelity else "—",
            f"{doc_fidelity[1]} reconciliation findings" if doc_fidelity else "Not run in this mode",
        ),
        (
            "Architecture risk",
            html.escape(arch_risk[0]) if arch_risk else "—",
            f"risk index {arch_risk[1]}/100" if arch_risk else "Not run in this mode",
        ),
        (
            "Audit coverage",
            f"{coverage[0]}%" if coverage else "—",
            f"{coverage[1]}/{coverage[2]} mandatory checks" if coverage else "checks.json/context.json not supplied",
        ),
        (
            "Evidence confidence",
            f"{confidence[0]}%" if confidence else "—",
            f"high-confidence, of {confidence[1]} rated" if confidence else "Not specified on these findings",
        ),
    ]
    return "".join(
        f'<div class="indicator"><div class="indicator-value">{v}</div>'
        f'<div class="indicator-label">{html.escape(l)}</div>'
        f'<div class="indicator-detail">{d}</div></div>'
        for l, v, d in blocks
    )


def build_stat_cards(counts):
    order = [
        ("risk", "Risks"),
        ("strength", "Strengths"),
        ("confirmed", "Confirmed"),
        ("gap", "Gaps"),
        ("misaligned", "Misaligned"),
    ]
    return "".join(
        f'<div class="stat-card {k}" data-filter-cls="{k}"><div class="num">{counts.get(k, 0)}</div>'
        f'<div class="label">{html.escape(lbl)}</div></div>'
        for k, lbl in order
    )


def build_sev_card(findings):
    """Judgment call: the mockup's per-severity `.desc` text (e.g. "Extensibility-requirements and
    extensibility gaps around undocumented growth priorities") reads as hand-written narrative
    summarizing the findings at that severity. There's no such narrative field in findings.json, so
    this generates a short programmatic summary instead — counts by classification at that
    severity, or an explicit "none found" message when empty."""
    sev_order = ["high", "medium", "low", "info"]
    counts = {sv: 0 for sv in sev_order}
    by_cls = {sv: {} for sv in sev_order}
    for f in findings:
        sev = s(f, "severity", "info")
        if sev not in counts:
            continue
        counts[sev] += 1
        cls = s(f, "classification", "confirmed")
        by_cls[sev][cls] = by_cls[sev].get(cls, 0) + 1

    def desc(sev):
        if counts[sev] == 0:
            return f"No {SEVERITY_LABEL[sev].lower()}-severity findings."
        parts = [
            f"{v} {CLASS_LABEL.get(k, k).lower()}"
            for k, v in sorted(by_cls[sev].items(), key=lambda kv: -kv[1])
        ]
        return ", ".join(parts) + "."

    return "".join(
        f'<div class="sev-col {sv}" data-filter-sev="{sv}"><div class="num">{counts[sv]}</div>'
        f'<div class="label">{SEVERITY_LABEL[sv]}</div>'
        f'<div class="desc">{html.escape(desc(sv))}</div></div>'
        for sv in sev_order
    )


def build_check_coverage(checks_doc, context_doc, manifest):
    if not checks_doc or not manifest:
        return None
    instances_by_id = {}
    for c in checks_doc.get("checks", []):
        instances_by_id.setdefault(c.get("id"), []).append(c)
    system_type = s(context_doc or {}, "system_type", "production-service")
    overrides = manifest.get("system_type_overrides", {}).get(system_type, {})

    status_counts = {"risk": 0, "strength": 0, "clean": 0, "not-applicable": 0, "not-assessed": 0}
    mandatory_total = 0
    for dim, dim_def in manifest.get("dimensions", {}).items():
        applicability = overrides.get(dim, "mandatory")
        for chk in dim_def.get("checks", []):
            recs = instances_by_id.get(chk["id"])
            statuses = [r.get("status") for r in recs] if recs else ["not-assessed"]
            for status in statuses:
                status_counts[status] = status_counts.get(status, 0) + 1
            if applicability == "mandatory":
                mandatory_total += 1

    summary = " · ".join(f"{v} {k}" for k, v in status_counts.items() if v)
    total_instances = sum(status_counts.values())
    checks_label = (
        f"{mandatory_total} mandatory checks ({total_instances} scoped instances)"
        if total_instances != mandatory_total else f"{mandatory_total} mandatory checks"
    )
    informational = [k for k, v in overrides.items() if v != "mandatory"]
    context_note = (
        f"System type: <b>{html.escape(system_type)}</b>"
        + (f" (informational dimensions: {html.escape(', '.join(informational))})" if informational else "")
    ) if context_doc else "No context.json supplied — assumed production-service for display only."

    return f"""
        <div class="insight-block">
          <div class="insight-stats">{checks_label} · {html.escape(summary)}</div>
          <div class="insight-stats">{context_note}</div>
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
        return "<p class='empty-note'>No high/medium-severity risks, gaps, or misalignments found.</p>"

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


def build_finding_card(f, num):
    cls = s(f, "classification", "gap")
    dim = s(f, "dimension", "correctness")
    severity = s(f, "severity", "info")

    evidence_html = "<br>".join(
        f'{html.escape(s(ev, "file"))}'
        + (f':{ev["line"]}' if ev.get("line") else "")
        + (f' — {html.escape(s(ev, "note"))}' if ev.get("note") else "")
        for ev in (f.get("evidence") or [])
    )
    evidence_block = f'<div class="evidence">{evidence_html}</div>' if evidence_html else ""

    recommendation = s(f, "recommendation")
    rec_html = f'<div class="recommendation"><b>Recommendation:</b> {html.escape(recommendation)}</div>' if recommendation else ""

    meta_bits = []
    finding_type = s(f, "finding_type")
    if finding_type:
        meta_bits.append(f'<span class="meta-tag">{html.escape(finding_type)}</span>')
    for area in (f.get("impact_area") or []):
        meta_bits.append(f'<span class="meta-tag meta-tag-impact">{html.escape(area)}</span>')
    confidence = s(f, "confidence")
    if confidence:
        meta_bits.append(f'<span class="meta-tag meta-tag-confidence">confidence: {html.escape(confidence)}</span>')
    meta_html = f'<div class="meta-tags">{"".join(meta_bits)}</div>' if meta_bits else ""

    doc_source = s(f, "doc_source")
    source_html = ""
    if doc_source:
        loc = s(f, "doc_location")
        loc_html = f'<span class="muted"> — {html.escape(loc)}</span>' if loc else ""
        source_html = f'<div class="source-line">{html.escape(doc_source)}{loc_html}</div>'

    strength_attr = ' data-strength="true"' if is_strength(f) else ""

    return f"""
  <div class="finding" id="row-{html.escape(f['id'])}" data-sev="{severity}" data-cls="{cls}" data-dim="{dim}"{strength_attr}>
    <div class="finding-num">{num:02d}</div>
    <div class="finding-body">
      <div class="finding-tags"><span class="badge badge-{cls}">{CLASS_LABEL.get(cls, cls)}</span><span class="dim-tag">{DIMENSION_LABEL.get(dim, dim)} · {SEVERITY_LABEL.get(severity, severity)}</span></div>
      <div class="finding-claim">{html.escape(s(f, 'claim'))}</div>
      <div class="explanation">{html.escape(s(f, 'explanation'))}</div>
      {evidence_block}
      {rec_html}
      {meta_html}
      {source_html}
    </div>
  </div>
"""


def build_findings_groups(findings):
    """Judgment call: the mockup groups findings under semantic headings ("Low severity",
    "Confirmed & strengths") rather than strictly "{Severity} severity" for all four buckets — the
    mockup's info-severity group happened to be all confirmed/strength findings and was labeled
    accordingly. This generalizes that: high/medium/low buckets get "{Severity} severity" headings;
    the info bucket is labeled "Confirmed & strengths" (matching the mockup) since info-severity
    findings are, by convention in this rubric, almost always confirmed/strength baseline findings.
    Numbering is sequential across all groups, high -> medium -> low -> info, matching the mockup's
    single running counter."""
    sev_order = ["high", "medium", "low", "info"]
    grouped = {sv: [] for sv in sev_order}
    for f in findings:
        sev = s(f, "severity", "info")
        grouped.setdefault(sev, []).append(f)
    for sev in list(grouped.keys()):
        if sev not in sev_order:
            sev_order.append(sev)

    titles = {
        "high": "High severity",
        "medium": "Medium severity",
        "low": "Low severity",
        "info": "Confirmed & strengths",
    }

    parts = []
    counter = 0
    for sev in sev_order:
        items = grouped.get(sev) or []
        if not items:
            continue
        cards = []
        for f in items:
            counter += 1
            cards.append(build_finding_card(f, counter))
        title = titles.get(sev, f"{SEVERITY_LABEL.get(sev, sev)} severity")
        plural = "finding" if len(items) == 1 else "findings"
        parts.append(f'<div class="sev-group-title">{html.escape(title)}</div>')
        parts.append(f'<div class="sev-group-sub">{len(items)} {plural} — evidence shown inline</div>')
        parts.extend(cards)
    return "\n".join(parts)


DIM_FILTER_BUTTONS = "".join(
    f'<button data-filter-group="dim" data-filter="{dim}">{html.escape(label)}</button>'
    for dim, label in DIMENSION_LABEL.items()
)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0;
          background: #F8F9EB; color: #1a1a1a; }}
  .wrap {{ max-width: 920px; margin: 0 auto; padding: 48px 32px 80px; }}

  .eyebrow {{ font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #8a8a7a; }}
  header {{ margin-bottom: 6px; }}
  h1 {{ margin: 6px 0 10px; font-size: 40px; letter-spacing: -0.02em; }}
  .subtitle {{ color: #6b6b60; font-size: 13px; line-height: 1.5; max-width: 640px; }}

  .meta-row {{ display: flex; gap: 28px; flex-wrap: wrap; margin: 22px 0 32px; padding: 16px 0;
               border-top: 1px solid #dcdccb; border-bottom: 1px solid #dcdccb; }}
  .meta-item .meta-value {{ font-size: 15px; font-weight: 700; }}
  .meta-item .meta-label {{ font-size: 10.5px; color: #8a8a7a; text-transform: uppercase; letter-spacing: .05em; margin-top: 2px; }}

  .score-card {{ background: #1c1c1a; color: #f2f2ea; border-radius: 24px; padding: 32px; display: flex;
                 gap: 32px; flex-wrap: wrap; margin-bottom: 32px; }}
  .score-left {{ flex: 0 0 200px; }}
  .score-left .eyebrow {{ color: #8a8a80; }}
  .score-number {{ font-size: 96px; font-weight: 800; line-height: 1; color: #4EAAFF; margin-top: 6px; }}
  .score-caption {{ font-size: 12px; color: #a9a99c; margin-top: 10px; }}
  .score-right {{ flex: 1 1 320px; font-size: 13.5px; line-height: 1.6; color: #d4d4c8; }}
  .score-right b {{ color: #f2f2ea; }}
  .score-philosophy {{ margin-top: 14px; }}
  .score-philosophy summary {{ cursor: pointer; font-size: 12px; color: #4EAAFF; }}
  .score-philosophy[open] summary {{ margin-bottom: 8px; }}
  .score-philosophy p {{ font-size: 12px; color: #a9a99c; line-height: 1.6; margin: 6px 0 0; }}

  .indicators {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 20px;
                 margin-bottom: 40px; }}
  .indicator-value {{ font-size: 22px; font-weight: 700; }}
  .indicator-label {{ font-size: 11.5px; color: #6b6b60; margin-top: 3px; }}
  .indicator-detail {{ font-size: 10.5px; color: #9a9a8c; margin-top: 3px; }}

  section.found > h2 {{ font-size: 22px; margin: 0 0 2px; }}
  section.found > .subtitle {{ margin-bottom: 18px; }}

  .stat-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 14px;
                 margin-bottom: 16px; }}
  .stat-card {{ background: #1c1c1a; border-radius: 16px; padding: 18px 20px; border-top: 4px solid var(--accent);
                cursor: pointer; transition: transform .1s ease; }}
  .stat-card:hover {{ transform: translateY(-2px); }}
  .stat-card.selected {{ outline: 2px solid #4EAAFF; }}
  .stat-card.risk {{ --accent: #e05a4a; }}
  .stat-card.strength {{ --accent: #4EAAFF; }}
  .stat-card.confirmed {{ --accent: #3fb95f; }}
  .stat-card.gap {{ --accent: #e0a83f; }}
  .stat-card.misaligned {{ --accent: #b06fe0; }}
  .stat-card .num {{ font-size: 34px; font-weight: 800; color: #f2f2ea; }}
  .stat-card .label {{ font-size: 11.5px; color: #b8b8a8; text-transform: uppercase; letter-spacing: .04em; margin-top: 2px; }}

  .sev-card {{ background: #1c1c1a; border-radius: 16px; padding: 22px 24px; display: flex; gap: 24px;
               flex-wrap: wrap; margin-bottom: 32px; }}
  .sev-col {{ flex: 1 1 160px; cursor: pointer; border-radius: 12px; padding: 6px 8px; margin: -6px -8px; }}
  .sev-col:hover {{ background: #262622; }}
  .sev-col.selected {{ outline: 2px solid #4EAAFF; }}
  .sev-col .num {{ font-size: 26px; font-weight: 800; }}
  .sev-col.high .num {{ color: #ff6b57; }}
  .sev-col.medium .num {{ color: #f0b64a; }}
  .sev-col.low .num {{ color: #7fb8ff; }}
  .sev-col.info .num {{ color: #b8b8a8; }}
  .sev-col .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #b8b8a8; margin: 2px 0 8px; }}
  .sev-col .desc {{ font-size: 11.5px; color: #8a8a80; line-height: 1.5; }}

  .filters {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }}
  .filters .group-label {{ color: #8a8a7a; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-right: 2px; }}
  .filters button {{ background: #ece9d8; color: #1a1a1a; border: 1px solid #dcdccb; border-radius: 999px;
                      padding: 6px 14px; font-size: 12px; cursor: pointer; }}
  .filters button.active {{ background: #1c1c1a; color: #f2f2ea; border-color: #1c1c1a; }}
  .filters {{ margin-bottom: 12px; }}
  #dim-filters {{ margin-bottom: 28px; }}

  .sev-group-title {{ font-size: 18px; font-weight: 700; margin: 32px 0 4px; }}
  .sev-group-sub {{ font-size: 12.5px; color: #8a8a7a; margin-bottom: 14px; }}

  .finding {{ display: flex; gap: 16px; padding: 20px 0; border-top: 1px solid #dcdccb; }}
  .finding.hidden {{ display: none; }}
  .finding-num {{ flex: 0 0 30px; height: 30px; border-radius: 50%; background: #1c1c1a; color: #f2f2ea;
                  display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }}
  .finding-body {{ flex: 1; min-width: 0; }}
  .finding-tags {{ display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }}
  .badge {{ padding: 2px 10px; border-radius: 999px; font-size: 10.5px; font-weight: 700; text-transform: uppercase;
            letter-spacing: .03em; white-space: nowrap; }}
  .badge-confirmed {{ background: #dcf3e1; color: #1e7a3c; }}
  .badge-misaligned {{ background: #fbe2e0; color: #b3392c; }}
  .badge-gap {{ background: #fbebd2; color: #a06a10; }}
  .badge-risk {{ background: #fbe2e0; color: #b3392c; }}
  .badge-strength {{ background: #dbeafe; color: #1d5fb3; }}
  .badge-sev-high {{ background: #fbe2e0; color: #b3392c; }}
  .badge-sev-medium {{ background: #fbebd2; color: #a06a10; }}
  .badge-sev-low {{ background: #eaf2fc; color: #1d5fb3; }}
  .badge-sev-info {{ background: #ece9d8; color: #6b6b60; }}
  .dim-tag {{ font-size: 10.5px; color: #8a8a7a; text-transform: uppercase; letter-spacing: .03em; }}
  .finding-claim {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
  .explanation {{ color: #4a4a42; font-size: 13px; line-height: 1.55; margin-top: 4px; }}
  .recommendation {{ color: #1d5fb3; font-size: 12.5px; margin-top: 8px; background: #eaf2fc; border-radius: 8px;
                      padding: 8px 12px; }}
  .evidence {{ font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11.5px; color: #d4d4c8;
               background: #1c1c1a; border-radius: 10px; padding: 10px 14px; margin-top: 10px; overflow-x: auto;
               line-height: 1.6; }}
  .source-line {{ font-size: 11px; color: #8a8a7a; margin-top: 8px; }}
  .source-line .muted {{ color: #a9a99c; }}
  .meta-tags {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
  .meta-tag {{ background: #ece9d8; color: #6b6b60; border-radius: 4px; padding: 1px 8px;
               font-size: 10px; white-space: nowrap; }}
  .meta-tag-impact {{ color: #4a3fa0; }}
  .meta-tag-confidence {{ color: #1e7a3c; }}

  .side-panels {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;
                  margin-top: 48px; }}
  .panel-card {{ background: #1c1c1a; color: #d4d4c8; border-radius: 16px; padding: 18px 20px; }}
  .panel-title {{ font-size: 11.5px; font-weight: 700; color: #f2f2ea; margin-bottom: 10px;
                   text-transform: uppercase; letter-spacing: .04em; }}
  .insight-block + .insight-block {{ margin-top: 14px; padding-top: 14px; border-top: 1px solid #33332e; }}
  .insight-title {{ font-size: 12px; font-weight: 600; color: #d4d4c8; }}
  .insight-stats {{ font-size: 11.5px; color: #a9a99c; margin: 4px 0 8px; }}
  .insight-sub {{ font-size: 10.5px; color: #8a8a80; text-transform: uppercase; letter-spacing: .03em; margin: 8px 0 4px; }}
  .insight-list {{ list-style: none; margin: 0; padding: 0; font-size: 12px; }}
  .insight-list li {{ display: flex; align-items: baseline; gap: 6px; padding: 3px 0; }}
  .insight-list code {{ color: #7fb8ff; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px; }}
  .insight-list .muted {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; color: #8a8a80; }}
  .insight-list b {{ color: #f2f2ea; }}
  .empty-note {{ color: #8a8a7a; font-size: 12.5px; }}
  .muted {{ color: #8a8a7a; font-size: 12.5px; }}

  .key-findings-list {{ list-style: none; margin: 0; padding: 0; }}
  .key-finding {{ border-bottom: 1px solid #33332e; }}
  .key-finding:last-child {{ border-bottom: none; }}
  .key-finding-link {{ display: flex; gap: 8px; align-items: baseline; padding: 8px 0; text-decoration: none; color: inherit; flex-wrap: wrap; }}
  .key-finding-claim {{ font-size: 12.5px; color: #f2f2ea; }}

  tr.flash, .finding.flash {{ outline: 2px solid #4EAAFF; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="eyebrow">Architecture debt report</div>
  <h1>{title}</h1>
  <div class="subtitle">Doc sources: {doc_sources}</div>
</header>

<div class="meta-row">
  {meta_row}
</div>

{score_card}

<div class="indicators">
  {indicators}
</div>

<section class="found">
  <h2>What the review found</h2>
  <div class="subtitle">{n_findings} findings across {n_dims} dimensions</div>

  <div class="stat-cards">
    {stat_cards}
  </div>

  <div class="sev-card">
    {sev_card}
  </div>
</section>

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
  {dim_filter_buttons}
</div>

<div id="findings-body">
{findings_groups}
</div>

<div class="side-panels">
  <div class="panel-card">
    <div class="panel-title">Key pressing findings</div>
    {key_findings}
  </div>
  <div class="panel-card">
    <div class="panel-title">Static code analysis</div>
    {static_analysis}
  </div>
  {check_coverage_panel}
</div>

</div>
<script>
  const state = {{ cls: 'all', dim: 'all', sev: 'all' }};
  const rows = document.querySelectorAll('.finding');

  function matchCls(r) {{
    if (state.cls === 'all') return true;
    if (state.cls === 'strength') return r.dataset.cls === 'strength' || r.dataset.strength === 'true';
    return r.dataset.cls === state.cls;
  }}

  function applyFilters() {{
    rows.forEach(r => {{
      const clsOk = matchCls(r);
      const dimOk = state.dim === 'all' || r.dataset.dim === state.dim;
      const sevOk = state.sev === 'all' || r.dataset.sev === state.sev;
      r.classList.toggle('hidden', !(clsOk && dimOk && sevOk));
    }});
  }}

  function scrollToFirstMatch() {{
    const first = Array.from(rows).find(r => !r.classList.contains('hidden'));
    if (!first) return;
    first.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
    first.classList.add('flash');
    setTimeout(() => first.classList.remove('flash'), 2000);
  }}

  document.querySelectorAll('.filters button').forEach(btn => btn.addEventListener('click', () => {{
    const group = btn.dataset.filterGroup;
    document.querySelectorAll(`.filters button[data-filter-group="${{group}}"]`).forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state[group] = btn.dataset.filter;
    applyFilters();
  }}));

  document.querySelectorAll('.stat-card').forEach(card => card.addEventListener('click', () => {{
    const filter = card.dataset.filterCls;
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.sev-col').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.sev = 'all';
    state.cls = filter;
    document.querySelectorAll('.filters button[data-filter-group="cls"]').forEach(b =>
      b.classList.toggle('active', b.dataset.filter === filter));
    document.querySelectorAll('.filters button[data-filter-group="dim"]')[0].click();
    applyFilters();
    scrollToFirstMatch();
  }}));

  document.querySelectorAll('.sev-col').forEach(col => col.addEventListener('click', () => {{
    const filter = col.dataset.filterSev;
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.sev-col').forEach(c => c.classList.remove('selected'));
    col.classList.add('selected');
    state.cls = 'all';
    state.sev = filter;
    document.querySelectorAll('.filters button[data-filter-group="cls"]')[0].click();
    document.querySelectorAll('.filters button[data-filter-group="dim"]')[0].click();
    state.sev = filter;
    applyFilters();
    scrollToFirstMatch();
  }}));

  document.querySelectorAll('.key-finding-link').forEach(link => link.addEventListener('click', (ev) => {{
    const targetId = link.getAttribute('href').slice(1);
    const row = document.getElementById(targetId);
    if (!row) return;
    ev.preventDefault();
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.sev-col').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('.filters button[data-filter-group="cls"]')[0].click();
    document.querySelectorAll('.filters button[data-filter-group="dim"]')[0].click();
    state.sev = 'all';
    applyFilters();
    row.classList.remove('hidden');
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
    ap.add_argument("--dep-graph", default=None)
    ap.add_argument("--churn", default=None)
    ap.add_argument("--out", default="report.html")
    args = ap.parse_args()

    findings_doc = load(args.findings)
    checks_doc = load(args.checks)
    context_doc = load(args.context)
    dep_graph = load(args.dep_graph)
    churn = load(args.churn)
    manifest = load_manifest()

    findings = findings_doc.get("findings", [])
    title = s(findings_doc, "title", "Architecture Debt Visualizer Report")
    doc_sources = ", ".join(findings_doc.get("doc_sources", [])) or "n/a"

    counts = {"confirmed": 0, "misaligned": 0, "gap": 0, "risk": 0, "strength": 0}
    for f in findings:
        cls = s(f, "classification")
        if cls in counts:
            counts[cls] += 1
    counts["strength"] = sum(1 for f in findings if is_strength(f))

    n_dims = len({s(f, "dimension", "correctness") for f in findings}) if findings else 0

    check_coverage_panel = build_check_coverage(checks_doc, context_doc, manifest)

    html_out = TEMPLATE.format(
        title=html.escape(title),
        doc_sources=html.escape(doc_sources),
        meta_row=build_meta_row(findings, dep_graph, checks_doc, context_doc, manifest),
        score_card=build_score_card(findings),
        indicators=build_indicators_grid(findings, checks_doc, context_doc, manifest),
        n_findings=len(findings),
        n_dims=n_dims,
        stat_cards=build_stat_cards(counts),
        sev_card=build_sev_card(findings),
        dim_filter_buttons=DIM_FILTER_BUTTONS,
        findings_groups=build_findings_groups(findings),
        key_findings=build_key_findings(findings),
        static_analysis=build_static_analysis(dep_graph, churn),
        check_coverage_panel=(
            f'<div class="panel-card"><div class="panel-title">Check coverage</div>{check_coverage_panel}</div>'
            if check_coverage_panel else ""
        ),
    )

    with open(args.out, "w") as fh:
        fh.write(html_out)
    score, label, _, _ = compute_score(findings)
    coverage = compute_audit_coverage(checks_doc, context_doc, manifest)
    coverage_msg = f", audit coverage {coverage[0]}%" if coverage else ""
    print(f"Wrote {args.out} ({len(findings)} findings, debt index {score}/100 — {label}{coverage_msg})")


if __name__ == "__main__":
    main()
