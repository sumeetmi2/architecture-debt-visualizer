#!/usr/bin/env python3
"""Find GitHub/Bitbucket repo URLs in proposal text and attempt to clone each one.

A design proposal frequently touches more than one system ("Service A calls the new
endpoint in Service B") and names the other repo by URL rather than pasting its code.
This script is the deterministic half of that discovery step: given the proposal's raw
text, find every github.com/bitbucket.org repo URL, dedupe them, and attempt a shallow
clone of each into its own directory under --dest-root. It never invents access it
doesn't have — a clone failure is recorded, not retried with elevated privilege, and no
attempt is made to guess credentials.

The current working directory (the repo the skill was invoked in) is always emitted as
entry 0 with clone_status "primary" and dest "." — every other list index that
downstream steps prioritize/report should preserve that as the anchor.

Usage:
  python3 discover_repos.py --proposal-text proposal.txt --dest-root /tmp/adv-XXXXXX/repos \
    --out /tmp/adv-XXXXXX/repos.json

Cloning uses whatever the `git` CLI on PATH is already configured to do (SSH keys, stored
HTTPS credentials, gh credential helper, etc.) — this script does not talk to the
Bitbucket/GitHub MCP tools directly (a plain script has no MCP access). If a URL fails to
clone here, the calling skill should check whether an MCP tool (e.g. mcp__bitbucket__bb_clone)
is available as a second attempt before giving up and recording the repo as inaccessible.
"""
import argparse
import json
import os
import re
import subprocess
import sys

URL_RE = re.compile(
    r"https?://(?P<host>github\.com|bitbucket\.org)/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)"
    r"(?:\.git)?(?:[/?#][^\s)\]}>\"']*)?(?=[\s)\]}>\"'.,;]|$)",
    re.IGNORECASE,
)

# git@host:owner/repo(.git) SSH shorthand, sometimes pasted instead of an https:// URL.
SSH_RE = re.compile(
    r"git@(?P<host>github\.com|bitbucket\.org):(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?=[\s)\]}>\"']|$)",
    re.IGNORECASE,
)


def find_repo_urls(text):
    found = {}
    for m in URL_RE.finditer(text):
        host, owner, repo = m.group("host").lower(), m.group("owner"), m.group("repo")
        key = (host, owner.lower(), repo.lower())
        found.setdefault(key, f"https://{host}/{owner}/{repo}")
    for m in SSH_RE.finditer(text):
        host, owner, repo = m.group("host").lower(), m.group("owner"), m.group("repo")
        key = (host, owner.lower(), repo.lower())
        found.setdefault(key, f"https://{host}/{owner}/{repo}")
    return [
        {"host": host, "owner": owner, "repo": repo, "url": url}
        for (host, owner, repo), url in found.items()
    ]


def try_clone(url, dest, timeout_sec):
    if os.path.exists(dest) and os.listdir(dest):
        return "already-present", None
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", url, dest],
            capture_output=True, text=True, timeout=timeout_sec,
        )
    except FileNotFoundError:
        return "failed", "git CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return "failed", f"clone exceeded {timeout_sec}s timeout"
    if proc.returncode == 0:
        return "cloned", None
    return "failed", proc.stderr.strip()[-500:] or proc.stdout.strip()[-500:] or "git clone failed, no output captured"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--proposal-text", required=True, help="Path to a text file containing the proposal's extracted text.")
    ap.add_argument("--dest-root", required=True, help="Directory to clone discovered repos into (one subdir per repo).")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=60, help="Per-repo clone timeout in seconds (default 60).")
    ap.add_argument("--skip-clone", action="store_true", help="Only discover URLs, don't attempt to clone (for dry-run/preview).")
    args = ap.parse_args()

    with open(args.proposal_text) as fh:
        text = fh.read()

    repos = [{"host": "cwd", "owner": "", "repo": os.path.basename(os.path.abspath(".")),
              "url": None, "dest": ".", "clone_status": "primary"}]

    discovered = find_repo_urls(text)
    os.makedirs(args.dest_root, exist_ok=True)
    for r in discovered:
        dest = os.path.join(args.dest_root, f"{r['host']}__{r['owner']}__{r['repo']}")
        if args.skip_clone:
            status, error = "not-attempted", None
        else:
            status, error = try_clone(r["url"], dest, args.timeout)
        entry = dict(r, dest=dest if status in ("cloned", "already-present") else None, clone_status=status)
        if error:
            entry["error"] = error
        repos.append(entry)

    with open(args.out, "w") as fh:
        json.dump({"repos": repos}, fh, indent=2)

    accessible = sum(1 for r in repos if r["clone_status"] in ("primary", "cloned", "already-present"))
    print(f"discover_repos.py: {len(repos)} repo(s) total, {accessible} accessible, "
          f"{len(repos) - accessible} inaccessible. Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
