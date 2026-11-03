# dory-loops

Public research repo and pre-registration. It studies test-time compute in a looped language model, NVIDIA Nemotron Labs **Dory1.0-4B**, on one NVIDIA GB10 (DGX Spark). Experiments are run by a mostly unattended Claude Code agent on Collin's machine. Daniel follows and steers it through GitHub: the `runs` branch, `runs/STATUS.md`, and the "dory-loops status" issue.

## Research question

Dory exposes test-time compute as **depth**: how many times its shared recurrent block runs (1 to 4 loops), all on one checkpoint. We ask:

1. What does extra depth buy, per task type (math, code, science, instruction following, knowledge, long context)?
2. At matched compute, how does **depth** (loops) compare with **length** (reasoning token budget) and **width** (majority vote)?
3. Does a fixed-depth looped model contain an **implicit per-token router**, meaning tokens that are settled after fewer loops, and can adaptive exit exploit it?

## Legs

| Leg | What | Gate |
|---|---|---|
| 0 | Setup, pinning, smoke test at loops 1 to 4 x 2 KV modes | Coherent output in all 8 settings |
| 1 | Reproduce card IFBench and GPQA at loops 1/2/4 | Within ~2 pts of the card or CI overlaps |
| 2 | Loop sweep: depth vs length vs width, KV modes, NVFP4 | Slim pass stable across seeds |
| 3 | Convergence probe, adaptive exit, learned exit, self-speculation | Pareto plots with CIs |
| 4 | Minimal agent harness, synthetic SWE-style task bank, dev baseline | Bank frozen, tool-call parse failures under 3% |
| 5 | Claude improves Dory's harness on the bank, one-shot test on sealed real SWE-bench tasks | Holdout recorded verbatim |
| 6 | Final report with novelty assessment | Report pushed |

Details: `EXPERIMENTS.md`. Agent rules: `CLAUDE.md`. Verified model facts: `MODEL_FACTS.md`. Holdout rules: `HOLDOUT_PROTOCOL.md`. Task bank spec: `tasks/README.md`.

## How to read `runs/`

- `runs/legN/PREREG.md`: what was planned, committed **before** any result. Compare it with the report.
- `runs/legN/REPORT.md`: what happened, gate outcome, deviations from PREREG.
- `runs/legN/<YYYYMMDD-HHMM>_<name>/`: one run. `config.yaml` (settings), `env.json` (exact versions), `results.jsonl` (per item), `summary.md` (headline numbers with 95% CIs).
- `runs/legN/BLOCKED.md`: the agent stopped and is waiting for a human.
- `CLAIMS.md`: every claim, its run IDs, effect size with CI, and status.
- `runs/FINAL_REPORT.md`: the write-up.

This repo is public on purpose: the plan and every PREREG are timestamped before results exist. Benchmark questions and contamination-sensitive model outputs are never committed (CLAUDE.md, fence 9).

Results live on the **`runs`** branch. `main` holds only the plan. Large files (weights, raw generations, hidden states) stay on the GB10 in `../artifacts/` and are never committed.

"Not distinguished" means the 95% CI of the difference includes zero. It is not a weaker form of "better".

## Following along and steering

- **Live status:** `runs/STATUS.md` on the `runs` branch (pushed at least every 2 hours) and comments on the issue "dory-loops status" (leg starts, gates, problems, a daily digest).
- **Answering the agent:** reply on its `blocked` issue or on the status issue. Only comments from the logins in `control.json` count.
- **Changing the plan:** push to `main` and tell the agent on an issue. It merges `main` into `runs` at each leg start.
- **Stopping it:** open an issue titled `STOP`.

## Who verifies what

| Who | Verifies |
|---|---|
| Executing agent | Pins, gates, CIs, disk. Writes PREREG before results and REPORT after. Builds the synthetic task bank. Never touches the real holdout before Leg 5. |
| Fresh review subagent | Leg 5 only: reads the frozen harness and holdout results without having seen development, and recommends promote or reject. |
| Collin | Owns the GB10. Starts the session and decides how long it runs. |
| Daniel | Answers blocking issues, updates the plan, checks the "verify first" list in the final report. |

## Budgets

No fixed GPU-hour cap: it runs while Collin is away (a few days) and longer if he chooses. Disk: 100 GB total, including Docker images and caches. Both are logged in `runs/BUDGET.md`.
