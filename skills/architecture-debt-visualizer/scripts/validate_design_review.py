#!/usr/bin/env python3
"""Validate a design-review run's findings.json/checks.json/context.json before
generate_design_review_report.py runs. Sibling to validate_findings.py, but for the
proposal-evaluation schema (see references/design-review.md) rather than the debt-audit
schema — classifications, dimensions, and the coverage model differ enough that forking
this into its own small script was clearer than overloading validate_findings.py with a
second mode.

Usage:
  python3 validate_design_review.py --findings findings.json --checks checks.json \
    --context context.json --repo-roots repos.json
"""
import argparse
import json
import os
import sys

CLASSIFICATIONS = {"risk", "strength", "open-question"}
DIMENSIONS = {
    "architecture-fit", "data-impact", "scalability-impact", "security-and-compliance",
    "operability", "migration-and-compatibility", "cost", "alternatives-and-tradeoffs",
    "testing-and-validation", "dependencies-and-integration", "objectives-and-prioritization",
    "presentation-and-completeness",
}
SEVERITIES = {"info", "low", "medium", "high"}
CHECK_STATUSES = {"risk", "strength", "open-question", "clean", "not-applicable", "not-assessed"}
EXTERNAL_EVIDENCE_TYPES = {"external-dependency", "runtime-only", "proposal-source"}


def load(path):
    if not path:
        return None
    with open(path) as fh:
        return json.load(fh)


def s(d, key, default=""):
    val = d.get(key)
    return val if val is not None else default


def manifest_ids():
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_review_rubric_manifest.json")
    ids = set()
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path))
        for dim_def in manifest.get("dimensions", {}).values():
            for chk in dim_def.get("checks", []):
                ids.add(chk["id"])
    return ids


def resolve_repo_roots(repo_roots_doc, default_root):
    """Evidence in a design-review finding can point into any accessible repo (primary or a
    cloned secondary) — build {label-or-host/owner/repo: dest} so evidence.repo can name which
    one, defaulting to the primary repo when evidence.repo is omitted."""
    roots = {".": default_root, "": default_root, "primary": default_root}
    if repo_roots_doc:
        for r in repo_roots_doc.get("repos", []):
            if r.get("dest"):
                key = f"{r['host']}/{r['owner']}/{r['repo']}" if r.get("owner") else "."
                roots[key] = r["dest"] if os.path.isabs(r["dest"]) else os.path.join(default_root, r["dest"])
    return roots


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--checks", default=None)
    ap.add_argument("--context", default=None)
    ap.add_argument("--repo-roots", default=None, help="discover_repos.py's repos.json, for evidence path resolution across multiple repos.")
    ap.add_argument("--repo-root", default=".", help="Primary repo root (default: cwd).")
    args = ap.parse_args()

    findings_doc = load(args.findings)
    checks_doc = load(args.checks)
    context_doc = load(args.context)
    repo_roots_doc = load(args.repo_roots)
    roots = resolve_repo_roots(repo_roots_doc, args.repo_root)
    m_ids = manifest_ids()

    errors = []
    warnings = []

    findings = findings_doc.get("findings", [])
    seen_finding_ids = {}
    for f in findings:
        fid = s(f, "id")
        where = f"finding {fid or '(no id)'}"

        if not fid:
            errors.append(f"{where}: missing required 'id'")
        elif fid in seen_finding_ids:
            errors.append(f"{where}: duplicate finding id")
        else:
            seen_finding_ids[fid] = f

        cls = f.get("classification")
        if cls not in CLASSIFICATIONS:
            errors.append(f"{where}: classification '{cls}' not in {sorted(CLASSIFICATIONS)}")

        dim = f.get("dimension")
        if dim not in DIMENSIONS:
            errors.append(f"{where}: dimension '{dim}' not in {sorted(DIMENSIONS)}")

        sev = f.get("severity")
        if sev is not None and sev not in SEVERITIES:
            errors.append(f"{where}: severity '{sev}' not in {sorted(SEVERITIES)}")

        if f.get("blocking") and cls != "risk":
            errors.append(f"{where}: 'blocking' is only meaningful on classification 'risk'")

        for field in ("claim", "doc_source", "doc_location"):
            if not s(f, field).strip():
                errors.append(f"{where}: '{field}' must be a non-empty string (doc_source/doc_location "
                               f"identify the PROPOSAL location, e.g. 'Slide 4' or 'Confluence: Rollout plan section')")

        if cls == "risk" and sev in ("medium", "high") and not s(f, "recommendation").strip():
            errors.append(f"{where}: risk finding at severity '{sev}' requires a non-empty 'recommendation'")

        if cls == "open-question" and not s(f, "question").strip():
            errors.append(f"{where}: classification 'open-question' requires a non-empty 'question' field "
                           f"(the specific thing the proposal needs to answer)")

        evidence = f.get("evidence") or []
        if cls != "open-question" and not evidence:
            errors.append(f"{where}: 'evidence' must have at least one entry (risk/strength findings need "
                           f"either target-repo code evidence or a proposal-source citation)")

        has_negative_search = False
        for i, ev in enumerate(evidence):
            ev_file = s(ev, "file")
            line = ev.get("line")
            if line is not None and (not isinstance(line, int) or line <= 0):
                errors.append(f"{where}: evidence[{i}].line must be a positive integer, got {line!r}")
            if not ev_file:
                has_negative_search = True
                continue
            if line is None:
                has_negative_search = True
            evidence_type = f.get("evidence_type") or []
            repo_key = s(ev, "repo", "primary")
            root = roots.get(repo_key)
            if root is None:
                errors.append(f"{where}: evidence[{i}].repo '{repo_key}' not found in --repo-roots manifest")
            elif not os.path.exists(os.path.join(root, ev_file)) and not (EXTERNAL_EVIDENCE_TYPES & set(evidence_type)):
                errors.append(
                    f"{where}: evidence[{i}].file '{ev_file}' does not exist under resolved root '{root}' "
                    f"(mark evidence_type external-dependency/runtime-only/proposal-source if that's why)"
                )

        if has_negative_search and not (f.get("searches_performed") or []):
            errors.append(f"{where}: negative-search evidence but 'searches_performed' is empty")

    # checks.json
    if checks_doc is not None:
        checks = checks_doc.get("checks", [])
        seen_instances = {}
        finding_id_owners = {}
        for c in checks:
            cid = c.get("id")
            where = f"check {cid or '(no id)'}"
            if not cid:
                errors.append(f"{where}: missing required 'id'")
            else:
                scope = frozenset(c.get("scope") or [])
                instances = seen_instances.setdefault(cid, [])
                for other_scope, _ in instances:
                    if scope == other_scope:
                        errors.append(f"{where}: duplicate check instance (same id and scope)")
                        break
                    if scope & other_scope:
                        errors.append(f"{where}: scope overlaps with another instance of the same id "
                                       f"(shared: {sorted(scope & other_scope)})")
                        break
                else:
                    instances.append((scope, c))
            if m_ids and cid and cid not in m_ids:
                errors.append(f"{where}: id not found in scripts/design_review_rubric_manifest.json")

            status = c.get("status")
            if status not in CHECK_STATUSES:
                errors.append(f"{where}: status '{status}' not in {sorted(CHECK_STATUSES)}")

            fids = c.get("finding_ids") or ([c["finding_id"]] if c.get("finding_id") else [])
            if status in ("risk", "strength", "open-question"):
                if not fids:
                    errors.append(f"{where}: status '{status}' requires non-empty 'finding_ids'")
                for fid in fids:
                    if fid not in seen_finding_ids:
                        errors.append(f"{where}: finding_ids references '{fid}', not present in findings.json")
            if status == "clean" and not (c.get("evidence") or []):
                errors.append(f"{where}: status 'clean' requires an 'evidence' entry")
            if status in ("not-applicable", "not-assessed") and not s(c, "reason").strip():
                errors.append(f"{where}: status '{status}' requires a non-empty 'reason'")

            for fid in fids:
                if fid in finding_id_owners:
                    errors.append(f"{where}: finding id '{fid}' already owned by check '{finding_id_owners[fid]}'")
                else:
                    finding_id_owners[fid] = cid

        if m_ids:
            covered_ids = {c.get("id") for c in checks if c.get("status") is not None}
            missing = m_ids - covered_ids
            if missing:
                errors.append(f"missing mandatory coverage record for: {sorted(missing)} "
                               f"(every design_review_rubric_manifest.json check is mandatory on every run)")
    elif context_doc is not None:
        warnings.append("--context supplied without --checks — coverage validation skipped")

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if errors:
        print(f"validate_design_review.py: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"validate_design_review.py: OK ({len(findings)} findings"
          + (f", {len(checks_doc.get('checks', []))} checks" if checks_doc else "")
          + f", {len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
