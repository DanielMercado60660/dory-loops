# Model facts (verified 2026-11-02)

Checked against the live Hugging Face card, `config.json`, `chat_template.jinja`, the HF API and GitHub on 2026-11-02. Re-verify anything marked **re-check** at Leg 0 and record the result in `runs/leg0/PINS.md`. If the live state differs from this file, trust the live state, note the difference in the Leg 0 report, and stop and ask if it changes a leg's design.

## Model

| Fact | Value | Source |
|---|---|---|
| Name | NVIDIA-Nemotron-Labs-Dory1.0-4B | card |
| Architecture | Looped (latent-recurrent) normalized-GPT (nGPT), interleaved sliding-window (SWA) + full attention | card |
| Layer stack (card wording) | Input 8 layers, shared Recurrent 20 layers (applied N times, input re-injected every loop), Output 8 layers | card |
| Layer stack (config wording) | `n_input_layers: 16`, `n_recurrent_layers: 40`, `n_output_layers: 16`, `num_hidden_layers: 72` | config.json |
| Context | Up to 256K (`max_position_embeddings: 262144`), `sliding_window: 1024` | card, config |
| Language, license | English. OpenMDW-1.1 | card |
| Config defaults | `n_recurrent_loops: 2`, `recurrent_kv_cache_mode: "per_loop"` | config.json |
| Other dims | hidden 2560, 16 heads, 4 KV heads, head_dim 256, vocab 131072, untied embeddings | config.json |

**Layer counting, read carefully.** The config counts attention and MLP as separate sublayers (`layer_types` alternates `*_attention`, `mlp`). The card counts one attention+MLP pair as one layer. So card 8/20/8 blocks = config 16/40/16 sublayers. In this repo, **"layer" and "layer-pass" mean a card-style block** unless stated otherwise:

- layer-passes per generated token = 16 + 20 x loops (loops 1/2/3/4 = 36/56/76/96).
- Attention pattern: every 4th block is full attention, the rest SWA. Per block group: Input 6 SWA + 2 full, Recurrent 15 SWA + 5 full, Output 6 SWA + 2 full. Derived from `layer_types`, so check it against the code you run.

**Always pass `n_recurrent_loops` and `recurrent_kv_cache_mode` explicitly.** The default is 2 loops, not 1.

## Checkpoints (revision SHAs as of 2026-11-02, re-check)

| Repo | Revision | Weights size | Notes |
|---|---|---|---|
| nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16 | f6c832e6963ddb74f62c75813a3e8c74b1af67b1 | 7.95 GB | W16A16 |
| nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-MXFP8 | acb538da38032a1daba9c411d2380d3812eab0a2 | 4.75 GB | W8A16 (weight-only) |
| nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-NVFP4 | 64b4039a3468bef85c6744c1e24d5a80801fe965 | 3.20 GB | W4A16 (weight-only, modelopt `W4A16_NVFP4`, group 16, embeddings and lm_head excluded) |
| nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-GGUF | df53755cb8741843af8e019e088819fbef17e29b | 3.67 GB | Q5_K_M, file `NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf` |

None of the HF repos ship modeling code. There is **no `trust_remote_code` path**.

The quantized checkpoints are weight-only. The BF16 vs NVFP4 comparison measures the effect of 4-bit weights plus memory-bandwidth savings. It does not test FP4 tensor-core compute. Word claims accordingly.

## Serving (vLLM)

- Dory support PR vllm-project/vllm#60149 was **merged** on 2026-10-25 (merge commit `75fc05a53a366068f534a61ab3ee6b50485419f2`). The card still says "under review". That note is out of date.
- **vLLM 0.33.0** (PyPI, 2026-11-02) contains that merge commit and ships a `manylinux_2_28_aarch64` wheel. Re-check that the wheel's CUDA build runs on GB10.
- Card install command (now a fallback only): `VLLM_USE_PRECOMPILED=1 pip install "git+https://github.com/vllm-project/vllm.git@refs/pull/60149/head"`
- Loop count and KV mode: `--hf-overrides '{"n_recurrent_loops": N, "recurrent_kv_cache_mode": "per_loop"|"last_loop"}'`
- Serve flags: `--reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice`. The card also uses `--enable-prefix-caching --async-scheduling --max-num-seqs 128 --max-model-len 262144`.
- Coding agents: pass `extra_body={"chat_template_kwargs": {"force_nonempty_content": True}}`.
- Sampling: temperature 1.0, top_p 0.95 (`generation_config.json` also sets top_k 0).
- The card says reasoning is always on in vLLM. **However**, `chat_template.jinja` has the switches `enable_thinking` (default True), `medium_effort` (default False, appends `{reasoning effort: efficient}` to the last user turn) and `truncate_history_thinking`. Reasoning is wrapped in `<think> ... </think>`. Whether vLLM honors these via `chat_template_kwargs` is **unverified**. Test it at Leg 0.

## KV cache modes

- `per_loop`: a separate KV cache per recurrent loop, so KV memory grows with the loop count.
- `last_loop`: one cache per recurrent attention layer, overwritten each loop, so it holds only the final loop's K/V. KV memory equals the 1-loop size at any loop count. The card says accuracy "stays close" to per_loop with nearly unchanged output lengths (no numbers given).
- Rough full-attention KV size in BF16 (derived, verify): 4 KV heads x 256 dim x 2 (K,V) x 2 bytes = 4 KiB per token per full-attention layer. per_loop at loops L has 4 + 5L full-attention layers (24 at L=4, about 12.9 GB at 128K tokens). SWA layers are capped at a 1024-token window.

## llama.cpp

- PR ggml-org/llama.cpp#30306 is still **open**. The card pins `98a74c97ea09ac72f6ceda1559808fc0a2f447ce` from `github.com/brianchmielNV/llama.cpp`. The card's build instructions are macOS-only.
- Loop override: `--override-kv "dory.num_loops=int:N,dory.recurrent_kv_cache_mode=str:per_loop|last_loop"`, with N in 1..4.
- Not needed for any leg. Use it only if vLLM fails entirely, and stop and ask first.

## transformers

- No Dory support in any released `transformers` (latest v5.22.1 on 2026-10-30). Support is in open PR huggingface/transformers#50099, head `fcc6924dfbac964f00787859b568c867ef5ad4cb` as of 2026-11-02 (**re-check**, it moves).
- This matters for Leg 3. See the Leg 0 "Leg 3 base decision" step in EXPERIMENTS.md.

## Card benchmarks (column mapping confirmed: 1 loop / 2 loops / 4 loops)

| Task | 1 | 2 | 4 |
|---|---|---|---|
| IFBench | 74.29 | 77.94 | 79 |
| GPQA Diamond (no tools) | 69.19 | 72.41 | 72.16 |
| AA-LCR | 63 | 71 | 73 |
| SciCode | 27.3 | 34.94 | 35.11 |
| SWE-bench Verified | 50.3 | 59.5 | 61.8 |
| Terminal-Bench 2.1 | 12.5 | 18.1 | 22.2 |
| HLE (text, no tools) | 8.25 | 10.89 | 10.43 |
| AA-Omniscience (acc) | 10.03 | 10.08 | 10.03 |

- Harness: NeMo Gym / NeMo Evaluator SDK. Terminal-Bench 2.1 used the Terminus-2 harness.
- **Not stated on the card:** which KV mode the benchmarks used (assume per_loop, matching the card's serve command, and record this as an assumption), max tokens, and repeat counts for IFBench and GPQA. The card's repeats footnote lists other benchmarks (and mentions "Terminal-Bench 4.0" while the table says 2.1, an inconsistency in the card itself).
- AA-Omniscience is flat across loops on the card. This supports H2.1 (the knowledge control stays flat).

## Hardware

- The card lists DGX Spark as tested hardware, plus H100, B200 and B300.
- DGX Spark speedups vs BF16 (from the card):

| ISL | OSL | Batch | MXFP8 | NVFP4 |
|---|---|---|---|---|
| 2560 | 300 | 1 | 1.69x | 2.17x |
| 128 | 1024 | 1 | 1.84x | 2.44x |

- GB10: aarch64 Grace CPU, Blackwell GPU, 128 GB unified memory (CPU and GPU share it, so host RAM use counts against GPU headroom).
