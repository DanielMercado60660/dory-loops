# runs/

Everything the executing agent produces that belongs in git. Lives on the `runs` branch.

```
runs/
  STATUS.md                         live status, pushed at least every 2 hours
  BUDGET.md                         GPU-hour and disk ledger, updated after every run
  FINAL_REPORT.md                   Leg 6
  leg0/
    PREREG.md                       committed before any Leg 0 result
    PINS.md                         every external dependency pinned to a SHA or digest
    REPORT.md                       outcome, gate, deviations from PREREG
    BLOCKED.md                      only while waiting for a human
    20261103-0915_smoke/            one directory per run
      config.yaml                   all settings needed to rerun
      env.json                      repo/vLLM/llama.cpp SHAs, pip freeze, nvidia-smi, CUDA, checkpoint revisions
      results.jsonl                 one line per item per sample
      summary.md                    headline numbers with 95% CIs
  leg1/ ... leg5/                   same layout. leg3/ also has LIT_CHECK.md. leg4/ has BANK_FREEZE.md. leg5/ has FREEZE.md and REVIEW.md
```

Run directory names: `<YYYYMMDD-HHMM>_<short-name>`, local time on the GB10, created by `scripts/new_run.py`.

`results.jsonl` minimum fields: `id`, `settings`, `seed`, `prediction`, `score`, `output_tokens`, `reasoning_tokens`, `latency_s`, `layer_passes`, `truncated`.

Not here: weights, raw generations, hidden-state dumps, logs over 5 MB. Those are in `../artifacts/<run-id>/` on the GB10 and are referenced from `summary.md`.
