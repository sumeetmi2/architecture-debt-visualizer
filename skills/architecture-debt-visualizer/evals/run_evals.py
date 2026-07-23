#!/usr/bin/env python3
"""Grade an already-generated findings.json (+ optional checks.json) against a golden case in
cases.json. This does NOT invoke Claude/the skill itself — it's a scoring harness you run after a
real (cold-run or otherwise) skill invocation has already produced output, the same way you'd grade
a test someone else already took. For a harness that actually invokes Claude Code end-to-end and
grades the result, see run_e2e_eval.py in this directory — it calls grade_case() below internally
so both paths share one grading implementation.

Usage:
  python3 run_evals.py --case-id sample-service-docs-bad-must-find --findings findings.json
  python3 run_evals.py --case-id minimal-cli-tool-must-not-find --findings findings.json --checks checks.json

Matching is intentionally simple and disclosed as such: `match` is a case-insensitive regex
searched against each finding's `claim` + `explanation` text, optionally narrowed by
`classification`/`dimension`. This is a heuristic, not a semantic check — a case can pass on a
lucky substring match or fail on a real finding phrased unexpectedly. Treat results as a strong
signal worth reading the actual findings for, not a certified pass/fail.
"""
import argparse
import json
import os
import re
import sys


def load(path):
    with open(path) as fh:
        return json.load(fh)


def load_case(case_id, cases_path=None):
    cases_path = cases_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases.json")
    cases_doc = load(cases_path)
    case = next((c for c in cases_doc["cases"] if c["id"] == case_id), None)
    if not case:
        raise SystemExit(
            f"No case '{case_id}' in {cases_path}. Known ids: {[c['id'] for c in cases_doc['cases']]}"
        )
    return case


def finding_text(f):
    return f"{f.get('claim') or ''} {f.get('explanation') or ''}".lower()


def spec_matches(spec, findings):
    pattern = re.compile(spec["match"], re.IGNORECASE)
    hits = []
    for f in findings:
        if not pattern.search(finding_text(f)):
            continue
        if "classification" in spec and f.get("classification") != spec["classification"]:
            continue
        if "dimension" in spec and f.get("dimension") != spec["dimension"]:
            continue
        hits.append(f.get("id"))
    return hits


def grade_case(case, findings, checks):
    """checks may be None (not supplied) or a list of checks.json records (possibly with more than
    one instance per id — see report-schema.md's 'Scoped check instances'). Returns
    (passed, lines, failures) — lines is the full human-readable transcript, failures is just the
    subset that caused a FAIL."""
    instances_by_id = {}
    if checks is not None:
        for c in checks:
            instances_by_id.setdefault(c.get("id"), []).append(c)

    lines = []
    failures = []

    for spec in case.get("must_find", []):
        hits = spec_matches(spec, findings)
        status = f"FOUND ({', '.join(hits)})" if hits else "MISSING"
        lines.append(f"[must_find] {spec.get('note', spec['match'])}: {status}")
        if not hits:
            failures.append(f"must_find not satisfied: {spec.get('note', spec['match'])}")

    for spec in case.get("must_not_find", []):
        hits = spec_matches(spec, findings)
        status = f"VIOLATED ({', '.join(hits)})" if hits else "clean"
        lines.append(f"[must_not_find] {spec.get('note', spec['match'])}: {status}")
        if hits:
            failures.append(f"must_not_find violated: {spec.get('note', spec['match'])} — matched {hits}")

    for check_id in case.get("expected_not_applicable", []):
        if checks is None:
            lines.append(f"[expected_not_applicable] {check_id}: SKIPPED (no checks supplied)")
            continue
        recs = instances_by_id.get(check_id)
        if not recs:
            actual = "(no record)"
            ok = False
        else:
            statuses = {r.get("status") for r in recs}
            actual = ", ".join(sorted(statuses)) if len(statuses) > 1 else recs[0].get("status")
            ok = statuses == {"not-applicable"}
        lines.append(f"[expected_not_applicable] {check_id}: {'ok' if ok else 'MISMATCH'} (actual status: {actual})")
        if not ok:
            failures.append(f"expected_not_applicable mismatch: {check_id} has status '{actual}'")

    for spec in case.get("allowed_optional", []):
        hits = spec_matches(spec, findings)
        lines.append(f"[allowed_optional, informational only] {spec.get('note', spec['match'])}: "
                      f"{'present' if hits else 'absent'} (does not affect pass/fail)")

    return not failures, lines, failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--checks", default=None)
    ap.add_argument("--cases", default=None, help="Defaults to cases.json next to this script.")
    args = ap.parse_args()

    case = load_case(args.case_id, args.cases)
    findings = load(args.findings).get("findings", [])
    checks = load(args.checks).get("checks", []) if args.checks else None

    passed, lines, failures = grade_case(case, findings, checks)
    print("\n".join(lines))
    print()
    if not passed:
        print(f"FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"PASS — case '{args.case_id}'")


if __name__ == "__main__":
    main()
