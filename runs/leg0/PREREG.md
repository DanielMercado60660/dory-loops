# Leg 0 PREREG: setup and smoke test

Registered by Daniel on 2026-11-02 (see this file's commit on `runs` for the exact time). Source: `EXPERIMENTS.md`, Leg 0.

## Pilot before registration

An unregistered smoke test already ran on the GB10 before this file existed, because the agent had no push access at the time. It counts as a **pilot**:
- Not used for the gate.
- Mentioned in `REPORT.md` under "Deviations from PREREG", with what was run and any problems it found.

The registered Leg 0 run is the first run started after this commit. Reusing the pilot's environment and prompts is fine, as long as the prompts are committed before the registered run starts.

## Hypotheses

None confirmatory. Leg 0 checks the setup. Expectations, to be reported either way:
- E0.1: output is coherent in all 8 settings.
- E0.2: peak memory grows with loops under per_loop and stays roughly flat under last_loop. At short context the difference may be too small to see; report it as such.
- E0.3: single-stream decode throughput falls roughly in proportion to layer-passes per token (36 / 56 / 76 / 96 at loops 1 / 2 / 3 / 4).

## Matrix

- Model: `nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` at revision `f6c832e6963ddb74f62c75813a3e8c74b1af67b1` (re-check, record in PINS.md).
- Prompts: 5 fixed prompts in `src/smoke_prompts.json` (arithmetic, a short code task, instruction following with a format constraint, a factual question, a 2-turn chat).
- Settings: loops {1, 2, 3, 4} x KV {per_loop, last_loop} = 8. Always passed explicitly via `--hf-overrides`.
- Sampling: temperature 1.0, top_p 0.95, top_k 0, seed 0, max_tokens 4096.
- Throughput: single stream, plus batched at batch 32 and 64 (the same prompts repeated).
- Inference stack: the first working option in the EXPERIMENTS.md Leg 0 order (vLLM 0.33.0 first). If the pilot already found a working stack, use it and record why any earlier options were skipped.

Also part of Leg 0 (from EXPERIMENTS.md steps 5 to 7):
- Test whether the `enable_thinking` and `medium_effort` template switches are honored.
- Make the Leg 3 base decision.
- Write `runs/leg0/PINS.md`.

## Metrics

Per setting:
- coherence (the agent's judgment, with one output pasted into REPORT.md)
- output and reasoning tokens
- single-stream tokens/s and batched tokens/s
- peak memory (`nvidia-smi` and `free -m`)
- mean power

## Analysis plan

Descriptive only. With 5 prompts there are no headline claims, so no CIs. Report the median and range across prompts for each setting, and the throughput ratio against loop 1 next to the layer-pass ratio.

## Gate

Coherent output in all 8 settings, throughput and memory logged, Leg 3 base chosen.

## Projection

About 3 hours. Disk about 25 GB (8 GB checkpoint, about 10 GB inference environment, caches).
