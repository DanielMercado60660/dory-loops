#!/usr/bin/env python3
"""Deterministic dev/holdout split for SWE-bench Verified task IDs.

Rule (fixed in HOLDOUT_PROTOCOL.md, never change it):
  bucket(id) = int(sha256("dory-loops/split-v1/" + id)[:8], 16) % 100
  holdout if bucket < 20, else dev.

Commands:
  filter-dev            read IDs on stdin, print only dev IDs (dropped count to stderr)
  is-dev ID             exit 0 if dev, 1 if holdout. Prints nothing.
  unseal --pool FILE    print holdout IDs from FILE, sorted by hash order.
                        Refuses unless runs/leg5/FREEZE.md is pushed to origin/runs.

In Python:  from split import is_dev   (scripts/ on sys.path)
Standard library only.
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

SALT = "dory-loops/split-v1/"
HOLDOUT_PERCENT = 20
REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE = "runs/leg5/FREEZE.md"


def _digest(task_id):
    return hashlib.sha256((SALT + task_id.strip()).encode("utf-8")).hexdigest()


def bucket(task_id):
    return int(_digest(task_id)[:8], 16) % 100


def is_dev(task_id):
    return bucket(task_id) >= HOLDOUT_PERCENT


def _freeze_pushed():
    """True if FREEZE.md exists on origin/runs (after a fetch)."""
    def git(*a):
        return subprocess.run(["git", "-C", str(REPO_ROOT), *a], capture_output=True, text=True)
    git("fetch", "--quiet", "origin", "runs")
    out = git("log", "--format=%H %cI", "-1", "origin/runs", "--", FREEZE)
    return out.returncode == 0 and out.stdout.strip() != "", out.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("filter-dev")
    p_is = sub.add_parser("is-dev")
    p_is.add_argument("task_id")
    p_un = sub.add_parser("unseal")
    p_un.add_argument("--pool", required=True, help="file with all pool IDs, one per line")
    args = ap.parse_args()

    if args.cmd == "filter-dev":
        dropped = 0
        for line in sys.stdin:
            tid = line.strip()
            if not tid:
                continue
            if is_dev(tid):
                print(tid)
            else:
                dropped += 1
        print(f"dropped {dropped} holdout ids", file=sys.stderr)
        return

    if args.cmd == "is-dev":
        sys.exit(0 if is_dev(args.task_id) else 1)

    if args.cmd == "unseal":
        ok, info = _freeze_pushed()
        if not ok:
            sys.exit(f"refusing: {FREEZE} is not on origin/runs. Freeze and push first (HOLDOUT_PROTOCOL.md rule 3).")
        print(f"FREEZE.md on origin/runs: {info}", file=sys.stderr)
        ids = [l.strip() for l in Path(args.pool).read_text().splitlines() if l.strip()]
        hold = sorted((tid for tid in ids if not is_dev(tid)), key=_digest)
        for tid in hold:
            print(tid)
        print(f"{len(hold)} holdout of {len(ids)} pool ids", file=sys.stderr)


if __name__ == "__main__":
    main()
