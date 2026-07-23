#!/usr/bin/env python3
"""Actually invoke Claude Code (the `claude` CLI, headless `-p` mode) to run the
architecture-debt-visualizer skill against a fixture repo, then grade the result via
run_evals.grade_case(). Complements run_evals.py, which only grades output someone already
produced — this drives the real thing end to end, closing the "Eval harness scope" gap disclosed
in docs/validation.md.

Costs real Claude API spend and takes several minutes per case (comparable to a real cold-run
review). This is a manual/on-demand harness, not something to wire into CI-on-every-commit.

Usage:
  python3 run_e2e_eval.py --case-id minimal-cli-tool-must-not-find
  python3 run_e2e_eval.py --case-id sample-service-docs-bad-must-find --max-budget-usd 5
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_evals  # local module: load, load_case, grade_case

PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
VALIDATE_SCRIPT = os.path.join(PLUGIN_ROOT, "skills", "architecture-debt-visualizer", "scripts", "validate_findings.py")


def build_prompt(case, run_dir):
    mode = case.get("mode", "full")
    docs_path = case.get("docs_path", "docs")
    return (
        f"Invoke the architecture-debt-visualizer skill in `{mode}` mode against the docs folder "
        f"`{docs_path}` in this repository (the current directory). Follow SKILL.md exactly, with "
        f"one deliberate exception to its own instructions: instead of making your own `mktemp -d` "
        f"run directory, use exactly this directory for every output file — {run_dir} — since a "
        f"test harness already created it fresh for this single invocation (the "
        f"never-reuse-a-fixed-path concern SKILL.md raises doesn't apply here, it's not reused "
        f"across runs). Write findings.json, checks.json, and context.json (context.json only if "
        f"mode isn't reconcile) directly into that directory before finishing."
    )


def run_claude(prompt, cwd, run_dir, model, max_budget_usd, timeout_s):
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
        "--plugin-dir", PLUGIN_ROOT,
        "--add-dir", run_dir,
        "--max-budget-usd", str(max_budget_usd),
    ]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}\nstderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude did not return valid JSON:\n{proc.stdout}")


def fixture_diff(fixture_repo_abs):
    proc = subprocess.run(
        ["git", "status", "--porcelain", fixture_repo_abs],
        cwd=PLUGIN_ROOT, capture_output=True, text=True,
    )
    return proc.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--cases", default=None)
    ap.add_argument("--model", default="sonnet", help="Passed to `claude --model`. Empty string uses the CLI's own default.")
    ap.add_argument("--max-budget-usd", type=float, default=3.0)
    ap.add_argument("--timeout-s", type=int, default=1800)
    args = ap.parse_args()

    case = run_evals.load_case(args.case_id, args.cases)
    for field in ("fixture_repo", "mode"):
        if field not in case:
            raise SystemExit(f"case '{args.case_id}' has no '{field}' — add it to cases.json to use the e2e runner")

    fixture_repo_abs = os.path.join(PLUGIN_ROOT, case["fixture_repo"])
    run_dir = tempfile.mkdtemp(prefix=f"adv-e2e-{args.case_id}-")
    prompt = build_prompt(case, run_dir)

    print(f"Invoking claude -p against {fixture_repo_abs} (mode={case.get('mode')}, model={args.model or 'default'}) ...")
    print(f"Run dir (kept for inspection regardless of outcome): {run_dir}")
    result = run_claude(prompt, cwd=fixture_repo_abs, run_dir=run_dir, model=args.model,
                         max_budget_usd=args.max_budget_usd, timeout_s=args.timeout_s)

    print(f"claude finished: subtype={result.get('subtype')} cost=${result.get('total_cost_usd', 0):.4f} "
          f"duration={result.get('duration_ms', 0) / 1000:.0f}s turns={result.get('num_turns')}")
    if result.get("is_error"):
        print(f"claude reported an error:\n{result.get('result')}", file=sys.stderr)
        sys.exit(2)

    findings_path = os.path.join(run_dir, "findings.json")
    checks_path = os.path.join(run_dir, "checks.json")
    context_path = os.path.join(run_dir, "context.json")
    if not os.path.exists(findings_path):
        print(f"FAIL — agent finished but never wrote findings.json to {run_dir}", file=sys.stderr)
        print(f"Its final message was:\n{result.get('result')}", file=sys.stderr)
        sys.exit(2)

    dirty = fixture_diff(fixture_repo_abs)
    if dirty:
        print(
            f"WARNING: fixture repo has uncommitted changes after the run (SKILL.md rule 9 says "
            f"don't modify the audited repo) — investigate before trusting this result:\n{dirty}",
            file=sys.stderr,
        )

    validate_cmd = [sys.executable, VALIDATE_SCRIPT, "--findings", findings_path, "--repo-root", fixture_repo_abs]
    if os.path.exists(checks_path):
        validate_cmd += ["--checks", checks_path]
    if os.path.exists(context_path):
        validate_cmd += ["--context", context_path]
    validate_proc = subprocess.run(validate_cmd, capture_output=True, text=True)
    print(validate_proc.stdout)
    if validate_proc.returncode != 0:
        print(validate_proc.stderr, file=sys.stderr)
        print(f"FAIL — validate_findings.py rejected the agent's output (see above). Run dir kept at {run_dir}", file=sys.stderr)
        sys.exit(1)

    findings = run_evals.load(findings_path).get("findings", [])
    checks = run_evals.load(checks_path).get("checks", []) if os.path.exists(checks_path) else None
    passed, lines, failures = run_evals.grade_case(case, findings, checks)
    print("\n".join(lines))
    print()
    if not passed:
        print(f"FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        print(f"Run dir kept at {run_dir} for inspection.")
        sys.exit(1)

    print(f"PASS — case '{args.case_id}' (run dir kept at {run_dir})")


if __name__ == "__main__":
    main()
