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

## Leg 3 base decision

**Chosen: option (a), `transformers` from PR huggingface/transformers#50099 pinned to SHA `fcc6924dfbac964f00787859b568c867ef5ad4cb`, BF16 checkpoint.** Installed in a separate venv (`venv_tf`, torch 2.14.0+cu130, transformers 5.23.0.dev0).

Evidence, on the GB10:

| Criterion (from EXPERIMENTS.md Leg 0 step 6) | Result |
|---|---|
| Loads the real checkpoint | PASS. Config model_type `dory`, 507 weights loaded, 56 s. |
| Per-loop hidden states without invasive patches | PASS, with a caveat. No patch needed. The returned `hidden_states` tuple has 97 entries at 4 loops (37 at 1 loop, 57 at the default 2). The 20 recurrent-layer outputs repeat once per loop, so h_k can be read by index. This is read-only, but it relies on the tuple's layout, not a documented per-loop output. |
| Runs 4 loops on a 4K-token sequence | PASS. Forward of 4096 tokens at 4 loops: 4.25 s on the first call (includes warmup), 14.4 GB peak GPU memory, logits finite. |
| Numerical parity with vLLM (Leg 3 gate, checked early) | Close. Next-token top-5 logprobs at 4 loops, prompt "What is 17 * 23? Answer with just the number.": vLLM `</think>` −0.483, transformers −0.477; the other four tokens agree within 0.05 nats. One prompt, one position: this is a smoke check, not the Leg 3 gate. |

**Option (b), a standalone PyTorch port of vLLM's `dory.py`: not built or tested.** The port is roughly 300 lines plus weight mapping and parity work. I chose (a) because it passes the criteria and is already close to vLLM on parity. If the hidden-state index mapping proves fragile, (b) is the fallback.

**Efficiency comparison:** not run against (b), since (b) was not built. Among the (a) numbers, the 4K forward is 4.25 s at 4 loops including warmup, and I did not measure a steady-state time.

**Risks of (a):**
- PR #50099 is open and unmerged. The SHA pin keeps it reproducible, but the PR may change or be rejected upstream.
- The PR's recurrence (`norm(h) + input`) differs in form from vLLM's (`justnorm(state + input_h)`). The top-5 check is close but covers one prompt and one position. The Leg 3 parity gate needs to test it across many positions and loops.
- The hidden-state index mapping depends on the tuple layout.

Scripts: `scripts/leg0/leg0_base_tf.py` (load, 4K forward, hidden-state count) and `scripts/leg0/parity_check.py` (top-5 logprob comparison against a vLLM endpoint).
