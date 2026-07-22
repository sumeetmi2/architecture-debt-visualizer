#!/usr/bin/env python3
"""Validate findings.json (+ optional checks.json/context.json) before generate_report.py runs.

Converts the skill's soft prose rules (references/evidence-standard.md,
references/report-schema.md, references/evaluation-rubric.md) into an enforced gate. Exits
nonzero with specific, actionable errors on anything mechanically checkable; prints non-blocking
warnings (exit 0) for the one rule that genuinely needs semantic judgment a script can't make
reliably (the bare-hypothesis phrasing rule) — flagged for review, not blocked.

Usage:
  python3 validate_findings.py --findings findings.json --repo-root . \
    [--checks checks.json] [--context context.json]

--checks/--context are optional (a reconcile-mode run has neither) — coverage-record checks are
skipped entirely when --checks is omitted, not silently passed.
"""
import argparse
import json
import os
import re
import sys

CLASSIFICATIONS = {"confirmed", "misaligned", "gap", "risk", "strength"}
DIMENSIONS = {
    "correctness", "scale-requirements", "extensibility-requirements", "scalability",
    "extensibility", "maintainability", "performance-cost", "data-architecture",
    "observability", "vision-alignment",
}
SEVERITIES = {"info", "low", "medium", "high"}
CHECK_STATUSES = {"risk", "strength", "clean", "not-applicable", "not-assessed"}
EXTERNAL_EVIDENCE_TYPES = {"external-dependency", "runtime-only"}

POSITIVE_SIGNAL = re.compile(
    r"\b(is scalable|is extensible|handles|supports|correctly|properly|ensures|guarantees|"
    r"robust|reliable|well[- ]designed|well[- ]factored|can absorb|scales (well|fine))\b",
    re.IGNORECASE,
)
NEGATIVE_SIGNAL = re.compile(
    r"\b(no|not|never|missing|hardcoded|lacks?|absent|fails?|doesn'?t|without|zero|none)\b",
    re.IGNORECASE,
)
PREFIXES = ("(Architectural evaluation)", "(Implicit)")


def load(path):
    if not path:
        return None
    with open(path) as fh:
        return json.load(fh)


def s(d, key, default=""):
    val = d.get(key)
    return val if val is not None else default


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--checks", default=None)
    ap.add_argument("--context", default=None)
    ap.add_argument("--repo-root", required=True)
    args = ap.parse_args()

    findings_doc = load(args.findings)
    checks_doc = load(args.checks)
    context_doc = load(args.context)
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rubric_manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else None

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
            errors.append(f"{where}: duplicate finding id (also used by an earlier finding)")
        else:
            seen_finding_ids[fid] = f

        cls = f.get("classification")
        if cls not in CLASSIFICATIONS:
            errors.append(f"{where}: classification '{cls}' not in {sorted(CLASSIFICATIONS)}")

        dim = f.get("dimension")
        if dim is not None and dim not in DIMENSIONS:
            errors.append(f"{where}: dimension '{dim}' not in {sorted(DIMENSIONS)}")

        sev = f.get("severity")
        if sev is not None and sev not in SEVERITIES:
            errors.append(f"{where}: severity '{sev}' not in {sorted(SEVERITIES)}")

        for field in ("claim", "doc_source", "doc_location"):
            if not s(f, field).strip():
                errors.append(f"{where}: '{field}' must be a non-empty string, never null/missing/empty")

        if cls == "risk" and sev in ("medium", "high") and not s(f, "recommendation").strip():
            errors.append(f"{where}: risk finding at severity '{sev}' requires a non-empty 'recommendation'")

        evidence = f.get("evidence") or []
        if not evidence:
            errors.append(f"{where}: 'evidence' must have at least one entry")

        has_negative_search_evidence = False
        for i, ev in enumerate(evidence):
            ev_file = s(ev, "file")
            line = ev.get("line")
            if line is not None and (not isinstance(line, int) or line <= 0):
                errors.append(f"{where}: evidence[{i}].line must be a positive integer, got {line!r}")
            if not ev_file:
                has_negative_search_evidence = True
                continue
            if line is None:
                has_negative_search_evidence = True
            evidence_type = f.get("evidence_type") or []
            full_path = os.path.join(args.repo_root, ev_file)
            if not os.path.exists(full_path) and not (EXTERNAL_EVIDENCE_TYPES & set(evidence_type)):
                errors.append(
                    f"{where}: evidence[{i}].file '{ev_file}' does not exist under --repo-root "
                    f"'{args.repo_root}' (mark evidence_type external-dependency/runtime-only if that's why)"
                )

        if has_negative_search_evidence and not (f.get("searches_performed") or []):
            errors.append(
                f"{where}: evidence includes a negative-search entry (no file, or no line) but "
                f"'searches_performed' is empty — record what was actually searched"
            )

        if cls == "risk" and dim and dim != "correctness":
            claim = s(f, "claim")
            has_prefix = claim.startswith(PREFIXES)
            if not has_prefix and POSITIVE_SIGNAL.search(claim) and not NEGATIVE_SIGNAL.search(claim):
                warnings.append(
                    f"{where}: claim reads as an unprefixed positive statement for a 'risk' finding "
                    f"— possible bare-hypothesis phrasing rule violation (see evidence-standard.md). "
                    f"claim: {claim!r}"
                )

    # checks.json validation
    if checks_doc is not None:
        checks = checks_doc.get("checks", [])
        seen_check_ids = set()
        finding_id_owners = {}
        manifest_ids = set()
        if manifest:
            for dim_def in manifest.get("dimensions", {}).values():
                for chk in dim_def.get("checks", []):
                    manifest_ids.add(chk["id"])

        for c in checks:
            cid = c.get("id")
            where = f"check {cid or '(no id)'}"
            if not cid:
                errors.append(f"{where}: missing required 'id'")
            elif cid in seen_check_ids:
                errors.append(f"{where}: duplicate check id")
            else:
                seen_check_ids.add(cid)
            if manifest_ids and cid and cid not in manifest_ids:
                errors.append(f"{where}: id not found in scripts/rubric_manifest.json")

            status = c.get("status")
            if status not in CHECK_STATUSES:
                errors.append(f"{where}: status '{status}' not in {sorted(CHECK_STATUSES)}")

            fid = c.get("finding_id")
            if status in ("risk", "strength"):
                if not fid:
                    errors.append(f"{where}: status '{status}' requires a 'finding_id'")
                elif fid not in seen_finding_ids:
                    errors.append(f"{where}: finding_id '{fid}' does not exist in findings.json")
            if status == "clean" and not (c.get("evidence") or []):
                errors.append(f"{where}: status 'clean' requires an 'evidence' entry")
            if status in ("not-applicable", "not-assessed") and not s(c, "reason").strip():
                errors.append(f"{where}: status '{status}' requires a non-empty 'reason'")

            if fid:
                if fid in finding_id_owners:
                    errors.append(
                        f"{where}: finding_id '{fid}' is already referenced by check "
                        f"'{finding_id_owners[fid]}' — every check needs its own finding, "
                        f"sharing one across checks defeats the coverage model "
                        f"(see evaluation-rubric.md's shared-evidence-vs-shared-finding_id rule)"
                    )
                else:
                    finding_id_owners[fid] = cid

        # mandatory-coverage check, only meaningful with both checks.json and context.json
        if manifest and context_doc is not None:
            system_type = s(context_doc, "system_type", "production-service")
            overrides = manifest.get("system_type_overrides", {}).get(system_type, {})
            by_id = {c.get("id"): c for c in checks}
            for dim, dim_def in manifest.get("dimensions", {}).items():
                if overrides.get(dim) in ("informational", "not-applicable"):
                    continue
                for chk in dim_def.get("checks", []):
                    rec = by_id.get(chk["id"])
                    if not rec or rec.get("status") is None:
                        errors.append(
                            f"missing mandatory coverage record for '{chk['id']}' "
                            f"(dimension '{dim}', mandatory for system_type '{system_type}')"
                        )
    elif context_doc is not None:
        warnings.append("--context supplied without --checks — coverage-record validation skipped entirely")

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if errors:
        print(f"validate_findings.py: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"validate_findings.py: OK ({len(findings)} findings"
          + (f", {len(checks_doc.get('checks', []))} checks" if checks_doc else "")
          + f", {len(warnings)} warning(s))")


if __name__ == "__main__":
    main()
