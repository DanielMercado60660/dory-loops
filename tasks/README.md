# tasks/: synthetic dev bank (built in Leg 4)

SWE-bench-style tasks the executing agent generates for harness iteration. They are small text files only. Repositories are cloned into `../artifacts/task-repos/`, never into this repo.

## Rules

- **Source repos:** 4 to 8 permissively licensed, pure-Python (or pure-Python-installable on aarch64) projects with test suites that finish in under 2 minutes. **None of the 12 SWE-bench Verified repositories** (django, sympy, astropy, matplotlib, scikit-learn, sphinx, pytest, xarray, requests, pylint, seaborn, flask). Pin each repo to a commit SHA.
- **Generation methods** (record which one per task):
  - `revert`: pick a real historical commit that changed source plus tests. Revert only the source part, so the commit's new tests become FAIL_TO_PASS. Closest to real SWE-bench.
  - `mutate`: a procedural bug (flipped comparison, off-by-one, dropped branch, swapped arguments, wrong default), as in SWE-smith.
  - `authored`: a realistic bug or small missing feature written by the agent.
- **Issue text:** written as a user's bug report or feature request. Symptoms, reproduction, expected behavior. **No hints at the fix location or the patch.**
- **Validation (all required):** FAIL_TO_PASS tests fail on the broken tree and pass with the reference patch, 3 runs each (drop flaky tasks). PASS_TO_PASS tests pass on both trees.
- **Pilot, then freeze:**
  - Build 20 pilot tasks, run the baseline harness on them at loops 2, and adjust the generator so the bank has a spread of difficulty (target baseline solve rate 20 to 60% overall). Pilot tasks are then discarded.
  - Build the bank (target about 150 tasks) and split it 80% `tune` / 20% `check` with `bucket(id) % 5 == 0` meaning check (same hashing as `scripts/split.py`, salt `dory-loops/bank-v1/`).
  - Commit the bank and record its commit SHA in `runs/leg4/BANK_FREEZE.md` **before the first harness-iteration run**.
  - After that, no edits or deletions, and no filtering by model results. A broken task is marked `void` with a reason and stays in the file.

## Layout

```
tasks/
  bank.jsonl          one line per task (fields below)
  patches/<id>.broken.diff     applied to the pinned repo to create the task
  patches/<id>.fix.diff        reference patch, never shown to the harness
```

`bank.jsonl` fields: `id`, `repo`, `repo_sha`, `method`, `issue`, `fail_to_pass` (list), `pass_to_pass` (list), `split` (tune | check), `difficulty_note`, `void` (null or reason).

## Sandbox

The harness runs model-written bash. Every task runs in a fresh Docker container with `--network none`, CPU and memory limits, a non-root user, and only that task's working copy mounted. Never run task code on the host.
