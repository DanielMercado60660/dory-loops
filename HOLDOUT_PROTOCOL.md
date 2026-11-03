# Holdout protocol

The Leg 5 holdout is the only clean test of whether harness improvements generalize. The agent that improves the harness also builds the dev tasks, so the holdout must be **real tasks it never touched**.

## Task sources

| Set | Source | Used for | Who makes it |
|---|---|---|---|
| Synthetic dev bank | SWE-bench-style tasks the agent generates in Leg 4 (see `tasks/README.md`), on repos **not** in SWE-bench Verified | Harness iteration (80% "tune") and candidate selection (20% "check") | Executing agent, frozen before any harness iteration |
| Real dev | SWE-bench Verified tasks whose split bucket is dev | Leg 4 baseline sanity check against the card, occasional realism checks | Deterministic rule below |
| Real holdout | SWE-bench Verified tasks whose split bucket is holdout (about 100 of 500) | Leg 5 final comparison, once | Deterministic rule below |

## The split rule (fixed now, before any data exists)

```
bucket(id) = int(sha256("dory-loops/split-v1/" + id).hexdigest()[:8], 16) % 100
holdout    = bucket(id) < 20        (about 20%)
dev        = bucket(id) >= 20       (about 80%)
```

The code is `scripts/split.py`. Because the rule and salt were committed to `main` before any result existed, nobody can pick a convenient split after the fact, and anyone can verify it. The rule is public, so the protection is behavioral: the rules below.

## Rules for the executing agent

1. **Never touch holdout tasks before unsealing.** Do not list, print, inspect, build, run or compute statistics on any SWE-bench Verified task in the holdout bucket. When loading the dataset, pass IDs through `scripts/split.py filter-dev` (or `is_dev()` in code) immediately, and never print or save anything about the dropped rows except their count.
2. **Don't mine SWE-bench for the dev bank.** Do not use SWE-bench Verified repositories, issues or patches as material for synthetic tasks.
3. **Freeze before unsealing.** At Leg 5, freeze the candidate harness. Commit and push `runs/leg5/FREEZE.md` with:
   - the candidate commit SHA, the baseline commit SHA
   - every setting: loops, KV mode, sampling, step limits, timeouts
   - the holdout run order

   The push timestamp on GitHub is the audit trail.
4. **Unseal.** Only after FREEZE.md is on `origin/runs`, run `python scripts/split.py unseal --pool <id file>`. It refuses unless FREEZE.md is pushed. Post a "holdout unsealed" comment on the status issue.
5. **Build check without peeking.** Build each holdout task's environment (arm64). Tasks that fail to build are excluded from **both** arms (build failure doesn't depend on the harness) and listed by ID in the report. Do not read problem statements or patches while doing this.
6. **One run each.** Baseline and candidate run on all buildable holdout tasks exactly once each, with FREEZE.md settings. No reruns, including after crashes. A crashed item counts as failed and is reported as a crash. If infrastructure fails broadly (more than 10% of items crash for non-model reasons), stop and open a blocking issue. Do not rerun on your own.
7. **No peeking.** Do not open individual holdout trajectories or per-item scores until both runs have finished.
8. **Verbatim.** Results go into `runs/leg5/` verbatim (results.jsonl, summary.md, REVIEW.md). Commentary goes in REPORT.md. No edits to result files after the fact.
9. **Spent.** After Leg 5 the holdout is spent. Further harness work needs a new holdout (for example, fresh tasks from SWE-rebench-V2 dated after Dory's post-training cutoff), which Daniel approves.

## Known limits (state them in the final report)

- The split rule is public, so integrity rests on rules 1 and 2 and the git audit trail, not on secrecy.
- About 100 holdout tasks, minus arm64 build failures, gives a wide CI on a paired difference (roughly plus or minus 10 points). A null result there is expected unless the improvement is large.
- SWE-bench Verified predates Dory's training data, so absolute scores may be contaminated. This affects both arms equally, so the paired comparison is still fair.
