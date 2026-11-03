# Leg 0 REPORT: pilot (unregistered) and status

**Status: pilot only. The registered Leg 0 run has not started, and this report does not pass the Leg 0 gate.**

## What the pilot is

The pilot is the unregistered setup run that ran before `runs/leg0/PREREG.md` was pushed (commit 17cbb5f, 2026-11-03 05:54Z). The PREREG says the pilot is not used for the gate and must be listed under "Deviations from PREREG". It is listed below.

## What ran

- Stack: vLLM 0.33.0, torch 2.14.0, Triton 3.8.0, on the GB10. Pins are in `runs/leg0/PINS.md`.
- Model: `nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` at revision `f6c832e6963ddb74f62c75813a3e8c74b1af67b1`.
- Settings: 4 loop counts × 2 KV modes = 8. Each setting ran the same 5 prompts through the OpenAI-compatible endpoint.
- Sampling per request: temperature 1.0, top_p 0.95, seed 0, max_tokens 4096. `top_k` was not set explicitly (server default).
- Throughput: single stream only. Each figure is total completion tokens divided by total request latency over the 5 prompts.

Raw results are committed in `runs/leg0/pilot/smoke_loops{1..4}_{per_loop,last_loop}.json` (one object per prompt: prompt, content, reasoning, finish reason, completion tokens, latency).

## Results (pilot)

| Loops | KV mode | Completion tokens per prompt (5 prompts) | Total tokens | Single-stream tok/s | Finish reasons |
|---|---|---|---|---|---|
| 1 | per_loop | 249, 2532, 391, 112, 279 | 3563 | 24.26 | stop ×5 |
| 1 | last_loop | 249, 2532, 391, 112, 279 | 3563 | 24.19 | stop ×5 |
| 2 | per_loop | 257, 1177, 347, 169, 337 | 2287 | 16.14 | stop ×5 |
| 2 | last_loop | 257, 1682, 427, 207, 527 | 3100 | 16.03 | stop ×5 |
| 3 | per_loop | 257, 1615, 454, 169, 299 | 2794 | 11.99 | stop ×5 |
| 3 | last_loop | 249, 2639, 409, 161, 538 | 3996 | 11.92 | stop ×5 |
| 4 | per_loop | 257, 1287, 490, 161, 386 | 2581 | 9.59 | stop ×5 |
| 4 | last_loop | 272, 1431, 698, 209, 399 | 3009 | 9.60 | stop ×5 |

What these show:
- Every setting finished with `stop` on all 5 prompts. No truncation at 4096.
- Loop 1 is identical in both KV modes, as expected, because the KV mode only changes behavior when loops > 1.
- Single-stream throughput falls from about 24 tok/s at loop 1 to about 9.6 tok/s at loop 4, a ratio of about 2.5×. The layer-pass ratio is 96/36 ≈ 2.7×. This is consistent with E0.3, but it is one run per setting.
- Token counts differ between loop settings. With 5 prompts, these differences are not meaningful. This pilot makes no claim about reasoning length.

## Not done in the pilot (still open for the registered run)

- **Coherence judgment.** The outputs are committed but have not been judged. The PREREG gate requires coherence in all 8 settings, with one output pasted here.
- **Batched throughput** (batch 32 and 64). Not run.
- **Peak memory** (`nvidia-smi`, `free -m`) and mean power. Not recorded.
- **`enable_thinking` and `medium_effort` template switches.** Not tested.
- **Leg 3 base decision.** Not made.
- **Server logs** (`vllm_loops*.log`) are not committed. They contain home-directory paths on the host, which the CLAUDE.md machine-details rule forbids in the repo. They can be scrubbed and added on request.

## Deviations from PREREG

1. **Pilot ran before registration.** The 8 settings above ran before the PREREG commit. Results are pilot only and are not used for the gate.
2. **Batched throughput and memory were not captured** in the pilot. The registered run has to measure them.
3. **`top_k` was not set explicitly.** The PREREG asks for `top_k 0`. The pilot used the server default, which may differ. The registered run must set it explicitly.
4. **Stack setup needed fixes.** `vllm==0.33.0` needed Python development headers (installed by another session) and `ninja` (pip, into the venv) before it would build. This does not change the pinned versions.
5. **Another large model server on the same machine was stopped** before these runs to free memory. Its absence is why the pilot had room to run, and it is not a change to the protocol.
6. **A llama.cpp GGUF check (Q5_K_M) also ran** before the vLLM pilot, as an unregistered smoke test on a different quantization. Its results are not in this repo, and they are not comparable to the vLLM BF16 numbers above. They are not used anywhere in this report.

## Next

1. Judge coherence on all 40 pilot outputs and paste one per setting here.
2. Write `runs/leg0/PINS.md` against the registered run's stack, record batched throughput and memory, and test the template switches.
3. Start the registered Leg 0 run only after a PREREG change or a confirmation from Daniel that the pilot setup is acceptable. The current PREREG is not edited.
