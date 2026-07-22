#!/usr/bin/env python3
"""Compute git churn (commit frequency + author diversity) per file and per package, over a
lookback window.

Used as a secondary prioritization signal, two ways:
- Raw churn: a misalignment in a file that changes every week matters more than one in a file
  nobody has touched in two years.
- Author diversity: a high-churn package touched by only one author is a bus-factor risk (nobody
  else has current context on it); a high-churn package touched by many different authors can
  indicate unclear ownership or thrashing (repeated rework/disagreement on the same code) rather
  than healthy shared ownership — read it alongside what the code actually looks like, this signal
  only tells you where to look, not which explanation applies.

Output is plain JSON on stdout:
{
  "since": ...,
  "files": {file: commit_count},                                   # sorted desc by commit_count
  "packages": {package: commit_count},                             # sorted desc by commit_count
  "package_authors": {
    package: {"distinct_authors": N, "top_authors": [[name, commit_count], ...]}
  },
  "bus_factor_hotspots": [[package, commit_count], ...],            # high churn, single author
  "high_diversity_hotspots": [[package, distinct_author_count], ...] # high churn, many authors
}
"""
import argparse
import json
import re
import subprocess
from collections import defaultdict

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;")
COMMIT_SENTINEL = "__COMMIT__"


def file_package(path):
    if not path.endswith(".java"):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = PACKAGE_RE.match(line)
                if m:
                    return m.group(1)
    except OSError:
        return None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="180 days ago",
                     help="git log --since value, e.g. '180 days ago' or '2025-01-01'")
    ap.add_argument("--path", action="append", default=None,
                     help="Restrict to this path prefix (repeatable). Defaults to whole repo.")
    ap.add_argument("--hotspot-min-commits", type=int, default=5,
                     help="Minimum commit count for a package to be eligible for the "
                          "bus-factor/high-diversity hotspot lists (default 5).")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cmd = ["git", "log", f"--since={args.since}", "--name-only",
           f"--pretty=format:{COMMIT_SENTINEL}%an"]
    if args.path:
        cmd += ["--"] + args.path

    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

    file_commits = defaultdict(int)
    file_authors = defaultdict(set)
    for block in raw.split(COMMIT_SENTINEL):
        if not block.strip():
            continue
        lines = block.splitlines()
        author = lines[0].strip() if lines else "unknown"
        seen_in_commit = {line.strip() for line in lines[1:] if line.strip()}
        for f in seen_in_commit:
            file_commits[f] += 1
            file_authors[f].add(author)

    package_commits = defaultdict(int)
    package_author_commits = defaultdict(lambda: defaultdict(int))
    pkg_cache = {}
    for f, count in file_commits.items():
        pkg = pkg_cache.get(f)
        if pkg is None:
            pkg = file_package(f) or ""
            pkg_cache[f] = pkg
        if not pkg:
            continue
        package_commits[pkg] += count
        for author in file_authors[f]:
            package_author_commits[pkg][author] += count

    package_authors = {}
    for pkg, author_counts in package_author_commits.items():
        top = sorted(author_counts.items(), key=lambda kv: -kv[1])
        package_authors[pkg] = {
            "distinct_authors": len(author_counts),
            "top_authors": top[:5],
        }

    eligible = {pkg: c for pkg, c in package_commits.items() if c >= args.hotspot_min_commits}
    bus_factor_hotspots = sorted(
        [(pkg, c) for pkg, c in eligible.items() if package_authors.get(pkg, {}).get("distinct_authors", 0) == 1],
        key=lambda kv: -kv[1],
    )
    high_diversity_hotspots = sorted(
        [(pkg, package_authors[pkg]["distinct_authors"]) for pkg in eligible if package_authors.get(pkg, {}).get("distinct_authors", 0) >= 3],
        key=lambda kv: -kv[1],
    )

    result = {
        "since": args.since,
        "files": dict(sorted(file_commits.items(), key=lambda kv: -kv[1])),
        "packages": dict(sorted(package_commits.items(), key=lambda kv: -kv[1])),
        "package_authors": package_authors,
        "bus_factor_hotspots": bus_factor_hotspots[:10],
        "high_diversity_hotspots": high_diversity_hotspots[:10],
    }
    output = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
