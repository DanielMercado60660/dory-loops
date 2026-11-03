#!/usr/bin/env python3
"""GitHub control channel for the executing agent.

Reads control.json (repo, allowed_logins, agent_marker). Token from
GITHUB_TOKEN or GH_TOKEN (never printed). Standard library only.

Commands:
  check                 new messages from allowed logins since the last check.
                        Exit 0 = nothing new, 20 = messages, 10 = STOP requested.
  wait                  poll every poll_minutes until messages or STOP, then exit
                        like `check`. Run it in the background while blocked.
                        --max-hours (default 72) exits 0 if nothing arrives.
  post --body-file F    comment on the status issue (created if missing).
  open --title T --body-file F [--label blocked|heads-up]
                        open a new issue, print its number and URL.
  comment --issue N --body-file F

Every body the agent posts gets agent_marker appended, and anything containing
the marker is ignored on read. The token may belong to Daniel, so the agent's
own posts can appear under an allowed login, and the marker tells them apart.

STOP: an open issue by an allowed login whose title starts with "STOP"
(any case) or that has the label "stop".

State (seen IDs, last check time) lives in ../artifacts/inbox_state.json.
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def load_control():
    return json.loads((ROOT / "control.json").read_text())


def state_path():
    art = os.environ.get("ART")
    base = Path(art) if art else ROOT.parent / "artifacts"
    return base / "inbox_state.json"


def load_state():
    p = state_path()
    if p.is_file():
        return json.loads(p.read_text())
    return {"since": None, "seen": []}


def save_state(st):
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    st["seen"] = st["seen"][-5000:]
    p.write_text(json.dumps(st, indent=1))


def request(method, path, body=None, params=None):
    url = API + path
    if params:
        url += "?" + "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f"GitHub API {method} {path}: HTTP {e.code} {e.read()[:300]!r}")
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f"GitHub API {method} {path}: {e}")


def paged(path, params):
    out, page = [], 1
    while True:
        batch = request("GET", path, params={**params, "per_page": 100, "page": page})
        out.extend(batch or [])
        if not batch or len(batch) < 100 or page >= 10:
            return out
        page += 1


def is_stop(issue):
    labels = {l["name"].lower() for l in issue.get("labels", [])}
    return issue.get("title", "").strip().upper().startswith("STOP") or "stop" in labels


def check(ctl, st):
    repo, allowed, marker = ctl["repo"], set(ctl["allowed_logins"]), ctl["agent_marker"]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    since = st.get("since") or (now - dt.timedelta(days=30)).isoformat()
    seen = set(st.get("seen", []))
    messages, stop = [], None

    issues = [i for i in paged(f"/repos/{repo}/issues", {"state": "open"}) if "pull_request" not in i]
    for i in issues:
        if i["user"]["login"] not in allowed or marker in (i.get("body") or ""):
            continue
        if is_stop(i) and stop is None:
            stop = {"issue": i["number"], "title": i["title"], "author": i["user"]["login"], "body": i.get("body") or ""}
        key = f"issue-{i['id']}"
        if key not in seen:
            seen.add(key)
            messages.append({"kind": "issue", "issue": i["number"], "title": i["title"], "author": i["user"]["login"],
                             "created_at": i["created_at"], "body": i.get("body") or ""})

    for c in paged(f"/repos/{repo}/issues/comments", {"since": since, "sort": "created", "direction": "asc"}):
        key = f"comment-{c['id']}"
        if key in seen or c["user"]["login"] not in allowed or marker in (c.get("body") or ""):
            continue
        seen.add(key)
        num = int(c["issue_url"].rstrip("/").split("/")[-1])
        messages.append({"kind": "comment", "issue": num, "author": c["user"]["login"],
                         "created_at": c["created_at"], "body": c.get("body") or ""})

    st["since"] = (now - dt.timedelta(minutes=5)).isoformat()  # small overlap, dedup by seen IDs
    st["seen"] = sorted(seen)
    save_state(st)
    return stop, messages


def report(stop, messages):
    print(json.dumps({"stop": stop, "messages": messages}, indent=2))
    if stop:
        return 10
    return 20 if messages else 0


def status_issue(ctl):
    repo, title = ctl["repo"], ctl["status_issue_title"]
    for i in paged(f"/repos/{repo}/issues", {"state": "open"}):
        if i.get("title") == title and "pull_request" not in i:
            return i["number"]
    body = "Running log from the executing agent. Comment here to talk to it.\n\n" + ctl["agent_marker"]
    return request("POST", f"/repos/{repo}/issues", {"title": title, "body": body})["number"]


def marked(text, ctl):
    return text.rstrip() + "\n\n" + ctl["agent_marker"] + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    w = sub.add_parser("wait")
    w.add_argument("--max-hours", type=float, default=72)
    p = sub.add_parser("post")
    p.add_argument("--body-file", required=True)
    o = sub.add_parser("open")
    o.add_argument("--title", required=True)
    o.add_argument("--body-file", required=True)
    o.add_argument("--label", action="append", default=[])
    c = sub.add_parser("comment")
    c.add_argument("--issue", type=int, required=True)
    c.add_argument("--body-file", required=True)
    args = ap.parse_args()
    ctl = load_control()

    if args.cmd == "check":
        sys.exit(report(*check(ctl, load_state())))
    if args.cmd == "wait":
        deadline = time.time() + args.max_hours * 3600
        while True:
            stop, msgs = check(ctl, load_state())
            if stop or msgs or time.time() > deadline:
                sys.exit(report(stop, msgs))
            time.sleep(60 * ctl.get("poll_minutes", 10))
    if args.cmd == "post":
        n = status_issue(ctl)
        r = request("POST", f"/repos/{ctl['repo']}/issues/{n}/comments", {"body": marked(Path(args.body_file).read_text(), ctl)})
        print(r["html_url"])
    if args.cmd == "open":
        body = {"title": args.title, "body": marked(Path(args.body_file).read_text(), ctl)}
        if args.label:
            body["labels"] = args.label
        r = request("POST", f"/repos/{ctl['repo']}/issues", body)
        print(r["number"], r["html_url"])
    if args.cmd == "comment":
        r = request("POST", f"/repos/{ctl['repo']}/issues/{args.issue}/comments", {"body": marked(Path(args.body_file).read_text(), ctl)})
        print(r["html_url"])


if __name__ == "__main__":
    main()
