#!/usr/bin/env python3
"""Bootstrap 95% CIs over items for results.jsonl files.

Rows sharing an `id` (several seeds or samples of one item) are averaged
first, then items are resampled. Seeds of one item always stay together.

Group mode (one CI per group):
  python scripts/bootstrap_ci.py runs/leg1/*/results.jsonl --group-by loops,kv_mode

Paired mode (CI of B minus A on the items both contain):
  python scripts/bootstrap_ci.py runs/leg2/*/results.jsonl \
      --a loops=1,kv_mode=per_loop --b loops=4,kv_mode=per_loop

Keys in --group-by, --a and --b are looked up in the row's `settings`
dict first, then at the top level. Values compare as strings.
A difference whose CI includes 0 is reported as "not distinguished".
Standard library only.
"""

import argparse
import json
import random
import sys
from collections import defaultdict


def load(paths, metric):
    rows = []
    for path in paths:
        with open(path) as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError as e:
                    sys.exit(f"{path}:{n}: bad JSON ({e})")
                if "id" not in row:
                    sys.exit(f"{path}:{n}: row has no 'id'")
                val = row.get(metric)
                if val is None:
                    continue
                row["_value"] = float(val)  # bools become 0.0 / 1.0
                rows.append(row)
    return rows


def lookup(row, key):
    settings = row.get("settings") or {}
    if key in settings:
        return settings[key]
    return row.get(key)


def parse_filter(text):
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        if "=" not in part:
            sys.exit(f"bad filter '{part}', expected key=value")
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def matches(row, flt):
    return all(str(lookup(row, k)) == v for k, v in flt.items())


def per_item(rows):
    acc = defaultdict(list)
    for r in rows:
        acc[str(r["id"])].append(r["_value"])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def percentile(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_mean(values, n_boot, rng, alpha=0.05):
    n = len(values)
    point = sum(values) / n
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return point, percentile(means, alpha / 2), percentile(means, 1 - alpha / 2)


def fmt(x, scale):
    return f"{x * scale:.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="results.jsonl files")
    ap.add_argument("--metric", default="score", help="numeric or bool field to average (default: score)")
    ap.add_argument("--group-by", default="", help="comma-separated keys, e.g. loops,kv_mode")
    ap.add_argument("--filter", default="", help="keep only rows matching key=value[,key=value]")
    ap.add_argument("--a", help="paired mode: filter for baseline A")
    ap.add_argument("--b", help="paired mode: filter for B (reports B minus A)")
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scale", type=float, default=100.0, help="multiply printed values (default 100, i.e. points)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a markdown table")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = load(args.files, args.metric)
    if args.filter:
        flt = parse_filter(args.filter)
        rows = [r for r in rows if matches(r, flt)]
    if not rows:
        sys.exit("no rows with the metric after filtering")

    if args.a or args.b:
        if not (args.a and args.b):
            sys.exit("paired mode needs both --a and --b")
        fa, fb = parse_filter(args.a), parse_filter(args.b)
        ia = per_item([r for r in rows if matches(r, fa)])
        ib = per_item([r for r in rows if matches(r, fb)])
        common = sorted(set(ia) & set(ib))
        if not common:
            sys.exit("A and B share no item ids")
        diffs = [ib[k] - ia[k] for k in common]
        d, lo, hi = bootstrap_mean(diffs, args.n_boot, rng)
        a_mean = sum(ia[k] for k in common) / len(common)
        b_mean = sum(ib[k] for k in common) / len(common)
        verdict = "not distinguished" if lo <= 0 <= hi else ("B higher" if d > 0 else "B lower")
        res = {
            "a": args.a, "b": args.b, "n_items_paired": len(common),
            "n_items_only_a": len(set(ia) - set(ib)), "n_items_only_b": len(set(ib) - set(ia)),
            "mean_a": a_mean, "mean_b": b_mean, "diff_b_minus_a": d, "ci95": [lo, hi], "verdict": verdict,
            "metric": args.metric, "n_boot": args.n_boot, "seed": args.seed,
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"| A | B | n paired | mean A | mean B | B - A | 95% CI | verdict |")
            print("|---|---|---|---|---|---|---|---|")
            print(f"| {args.a} | {args.b} | {len(common)} | {fmt(a_mean, args.scale)} | {fmt(b_mean, args.scale)} | "
                  f"{fmt(d, args.scale)} | [{fmt(lo, args.scale)}, {fmt(hi, args.scale)}] | {verdict} |")
            if res["n_items_only_a"] or res["n_items_only_b"]:
                print(f"\nnote: {res['n_items_only_a']} items only in A, {res['n_items_only_b']} only in B (excluded)",
                      file=sys.stderr)
        return

    keys = [k.strip() for k in args.group_by.split(",") if k.strip()]
    groups = defaultdict(list)
    for r in rows:
        if keys:
            g = tuple((k, str(lookup(r, k))) for k in keys)
        else:
            g = (("settings", json.dumps(r.get("settings") or {}, sort_keys=True)),)
        groups[g].append(r)

    results = []
    for g in sorted(groups):
        items = per_item(groups[g])
        mean, lo, hi = bootstrap_mean(list(items.values()), args.n_boot, rng)
        results.append({"group": dict(g), "n_items": len(items), "n_rows": len(groups[g]),
                        "mean": mean, "ci95": [lo, hi]})

    if args.json:
        print(json.dumps({"metric": args.metric, "n_boot": args.n_boot, "seed": args.seed, "groups": results}, indent=2))
        return
    head = keys or ["settings"]
    print("| " + " | ".join(head) + " | n items | n rows | mean | 95% CI |")
    print("|" + "---|" * (len(head) + 4))
    for r in results:
        cells = [r["group"][k] for k in head]
        lo, hi = r["ci95"]
        print("| " + " | ".join(cells) + f" | {r['n_items']} | {r['n_rows']} | {fmt(r['mean'], args.scale)} | "
              f"[{fmt(lo, args.scale)}, {fmt(hi, args.scale)}] |")


if __name__ == "__main__":
    main()
