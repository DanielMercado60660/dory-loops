# Leg 0 REPORT

Registered run, PREREG at `runs/leg0/PREREG.md` (commit 17cbb5f). Runner and prompts committed before the run at d60451f. The unregistered pilot is in `runs/leg0/pilot/` and is not used here.

## Gate

**Coherent output in all 8 settings, throughput and memory logged, Leg 3 base chosen.**

- Coherence: PASS. All 40 single-stream outputs (8 settings × 5 prompts) finished with `stop` and are correct: 17×23 gives 391, the Fibonacci code is a valid function, the three fruits are listed one per line, Canberra, and Sam.
- Throughput and memory: logged (below).
- Leg 3 base: **not chosen here.** That is a decision for Daniel, see open items.

Overall: gate met on coherence and logging, with the base decision left open.

## Results

Source: `results/results_loops{L}_{kv}.jsonl`. Single-stream tok/s = total completion tokens / total latency over the 5 prompts. Batch tok/s = aggregate tokens / wall time for 32 or 64 concurrent requests cycling the 5 prompts.

| Loops | KV | Single tok/s | Batch 32 tok/s | Batch 64 tok/s | Peak used RAM (MB) |
|---|---|---|---|---|---|
| 1 | per_loop | 24.15 | 212.94 | 392.08 | 85,798 |
| 1 | last_loop | 23.80 | 207.23 | 370.88 | 85,543 |
| 2 | per_loop | 16.02 | 212.93 | 347.20 | 85,820 |
| 2 | last_loop | 15.97 | 136.64 | 392.91 | 86,257 |
| 3 | per_loop | 11.95 | 110.15 | 177.83 | 86,565 |
| 3 | last_loop | 11.88 | 120.06 | 217.14 | 86,294 |
| 4 | per_loop | 9.56 | 74.99 | 147.69 | 86,071 |
| 4 | last_loop | 9.54 | 87.20 | 198.97 | 86,650 |

Completion tokens per single-stream prompt are the same across the two KV modes at loop 1 (249, 2532, 391, 112, 279) and differ at loops 2–4, as expected.

## What the numbers say

- **E0.3 (single-stream decode falls with layer-passes): consistent.** Single-stream throughput goes from about 24 tok/s at loop 1 to about 9.6 tok/s at loop 4, a ratio of about 2.5×. The layer-pass ratio is 96/36 ≈ 2.7×. One run per setting, so this is descriptive only.
- **Batched throughput is noisy and I do not use it for claims.** Several settings differ by 30–60% from the matching setting with the other KV mode (for example batch 32 at loop 2: 212.93 per_loop vs 136.64 last_loop). With one run each, I cannot tell scheduling noise from a real effect.
- **E0.2 (memory grows with loops under per_loop, flat under last_loop): not clearly visible.** Peak used RAM is 85.5–86.7 GB across all eight settings, and the machine's 124 GB includes other processes. The sampler reads system-wide `free -m`, so it cannot isolate the server's allocation. Report as inconclusive; the short context in this pilot is likely too small to show the difference, as the PREREG warned.
- **Power:** not captured. `nvidia-smi` reports N/A for memory and power on this platform.

## Template switches (loop 1, per_loop, Fibonacci prompt)

- `enable_thinking: false`: the reasoning field is null and the answer is code only, 42 tokens. The switch is honored.
- `medium_effort: true`: the reasoning field is populated and the answer is code. The switch is accepted and changes output, but the exact effect on reasoning length is not measured here.

I did not compare reasoning length between the default and `medium_effort`, so I make no claim about it.

## Deviations from PREREG

1. **Power not measured.** The PREREG lists mean power. `nvidia-smi` returns N/A on this platform. Not recorded.
2. **Peak memory is system-wide.** The PREREG asks for `nvidia-smi` and `free -m`. `nvidia-smi` memory is N/A here, so only `free -m` was used. It is not server-specific.
3. **`medium_effort` reasoning length not compared.** The probe checked the switch is honored, not its effect on length.
4. **Batched throughput has one run per setting.** The PREREG does not say how many repeats; the noise above is why it cannot support claims.
5. **Server logs are not committed.** They contain host paths, which the machine-details rule forbids in the repo.

## Open items

- **Leg 3 base decision.** Needs Daniel's sign-off on the choice. My suggestion would be the BF16 checkpoint with vLLM 0.33.0 at loop 1 as the base, since it is the only stack that has run cleanly here. This is a suggestion, not a registered decision.
- **Repeat the batched passes** if Daniel wants batched throughput as a result, with at least three repeats per setting.
- **Judge the pilot outputs** (`runs/leg0/pilot/`) for the record, since they were not judged in the previous report. They are not used for the gate.
