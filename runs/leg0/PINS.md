# Leg 0 pins (exploratory, unregistered)

Date: 2026-11-03. Host: DGX Spark (GB10, aarch64, Ubuntu 24.04). Driver 580.178.04, CUDA 13.0.

| Component | Pin |
|---|---|
| vLLM | 0.33.0 (PyPI, contains merge commit 75fc05a53a366068f534a61ab3ee6b50485419f2 of PR #60149) |
| torch | 2.14.0 |
| triton | 3.8.0 |
| transformers | 5.20.2 (installed, not used for serving) |
| tokenizers | 0.23.3 |
| Python | 3.12 (system, with python3.12-dev installed by another session) |
| Checkpoint | nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16 @ f6c832e6963ddb74f62c75813a3e8c74b1af67b1 (7.95 GB) |
| Extra build tool | ninja (pip, into venv) |

Serve command (per setting): vllm serve <checkpoint> --revision <rev> --port 8001 --max-model-len 16384 --gpu-memory-utilization 0.6 --hf-overrides '{"n_recurrent_loops": N, "recurrent_kv_cache_mode": "per_loop" or "last_loop"}' --reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice

Not pinned: container digests (no containers used). The llama.cpp build was used only for the earlier unregistered check.
