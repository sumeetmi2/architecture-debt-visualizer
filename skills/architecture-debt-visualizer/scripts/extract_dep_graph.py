#!/usr/bin/env python3
"""Extract a package-level dependency graph from a Java source tree.

Node = Java package (dir containing .java files with that `package` declaration).
Edge = one package importing a class from another package, restricted to imports
that share the project's own prefix (so JDK/library imports are excluded).

Output is plain JSON on stdout: {"nodes": [...], "edges": [...]}.
No third-party dependencies; stdlib only, so it runs anywhere Python 3 runs.
"""
import argparse
import json
import os
import re
from collections import defaultdict

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;")
IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)(?:\.\*)?\s*;")


def find_java_files(src_root):
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for f in filenames:
            if f.endswith(".java"):
                yield os.path.join(dirpath, f)


def parse_file(path):
    package = None
    imports = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, start=1):
            if package is None:
                m = PACKAGE_RE.match(line)
                if m:
                    package = m.group(1)
                    continue
            m = IMPORT_RE.match(line)
            if m:
                imports.append((lineno, m.group(1)))
    return package, imports


def infer_prefix(packages):
    if not packages:
        return ""
    split = [p.split(".") for p in packages]
    common = split[0]
    for parts in split[1:]:
        i = 0
        while i < len(common) and i < len(parts) and common[i] == parts[i]:
            i += 1
        common = common[:i]
    return ".".join(common)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", action="append", required=True,
                     help="Java source root to scan (repeatable, e.g. --src src/main/java)")
    ap.add_argument("--prefix", default=None,
                     help="Only edges whose target import starts with this package prefix are kept. "
                          "Defaults to the longest common prefix of all discovered packages.")
    ap.add_argument("--out", default=None, help="Write JSON here instead of stdout")
    args = ap.parse_args()

    files = []
    for root in args.src:
        files.extend(find_java_files(root))

    parsed = {}
    all_packages = set()
    for path in files:
        package, imports = parse_file(path)
        if package is None:
            continue
        parsed[path] = (package, imports)
        all_packages.add(package)

    prefix = args.prefix or infer_prefix(all_packages)

    class_count = defaultdict(int)
    for path, (package, _imports) in parsed.items():
        class_count[package] += 1

    edge_weight = defaultdict(int)
    edge_examples = defaultdict(list)
    for path, (package, imports) in parsed.items():
        for lineno, imported in imports:
            if not imported.startswith(prefix + "."):
                continue
            target_package = imported.rsplit(".", 1)[0]
            if target_package == package:
                continue
            key = (package, target_package)
            edge_weight[key] += 1
            if len(edge_examples[key]) < 5:
                edge_examples[key].append({
                    "file": os.path.relpath(path),
                    "line": lineno,
                    "imported_class": imported,
                })

    nodes = [
        {"id": pkg, "class_count": count}
        for pkg, count in sorted(class_count.items())
    ]
    edges = [
        {
            "from": src,
            "to": dst,
            "weight": edge_weight[(src, dst)],
            "examples": edge_examples[(src, dst)],
        }
        for (src, dst) in sorted(edge_weight.keys())
    ]

    result = {"prefix": prefix, "nodes": nodes, "edges": edges}
    output = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
