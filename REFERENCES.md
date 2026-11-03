# References

All links checked on 2026-11-02.

| Reference | Link | Informs |
|---|---|---|
| Dory1.0-4B model card (NVIDIA, 2026) | https://huggingface.co/nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16 | All legs. Architecture, serving flags, card baselines (Leg 1). See MODEL_FACTS.md |
| Geiping et al. 2025, *Scaling up Test-Time Compute with Latent Reasoning: A Recurrent Depth Approach* | https://arxiv.org/abs/2502.05171 | Leg 3b: KL-based zero-training exit, per-token adaptive compute, KV sharing under exit |
| Bae et al. 2025, *Mixture-of-Recursions* | https://arxiv.org/abs/2507.10524 | Leg 3a/3c: learned token routing; recursion-wise KV caching vs recursive KV sharing (compare with per_loop / last_loop) |
| Saunshi et al. 2025, *Reasoning with Latent Thoughts: On the Power of Looped Transformers* | https://arxiv.org/abs/2502.17416 | Leg 2: which task types should benefit from depth (reasoning vs memorization) |
| Loshchilov et al. 2024, *nGPT: Normalized Transformer* | https://arxiv.org/abs/2410.01131 | Leg 3a: hidden states on the hypersphere; use cosine as well as L2 change |
| Zhu et al. 2025, *Scaling Latent Reasoning via Looped Language Models* (Ouro) | https://arxiv.org/abs/2510.25741 | Closest competitor. Legs 2, 3, 6: loop scaling, learned early exit, knowledge vs manipulation findings |
| Schuster et al. 2022, *Confident Adaptive Language Modeling* (CALM) | https://arxiv.org/abs/2207.07061 | Leg 3b/3c: confidence-based early exit, KV propagation for exited tokens, calibration |
| Elhoushi et al. 2024, *LayerSkip* | https://arxiv.org/abs/2404.16710 | Leg 3d: self-speculative decoding with early-exit drafts and shared compute |
| Graves 2016, *Adaptive Computation Time* | https://arxiv.org/abs/1603.08983 | Leg 3: halting framing, ponder cost |
| Dehghani et al. 2018, *Universal Transformers* | https://arxiv.org/abs/1807.03819 | Leg 3: weight-shared depth with per-position ACT halting |
| NeMo Evaluator | https://github.com/NVIDIA-NeMo/Evaluator | Leg 1 harness (preferred) |
| NeMo Skills | https://github.com/NVIDIA-NeMo/Skills | Leg 1 fallback harness, Leg 2 tasks |
| NVIDIA 2025, *Nemotron 3 Nano* technical report | https://arxiv.org/abs/2512.20848 | Leg 1: eval methodology and configs to mirror |
| mini-SWE-agent | https://github.com/SWE-agent/mini-swe-agent | Leg 4 reference baseline |
| Leviathan et al. 2023, *Fast Inference from Transformers via Speculative Decoding* | https://arxiv.org/abs/2211.17192 | Leg 3d: speedup formula |

## Before Leg 3: literature check (required)

Before writing the Leg 3 PREREG, look at papers that cite **Geiping et al. 2025** and **Mixture-of-Recursions**. Use the Semantic Scholar API (`api.semanticscholar.org/graph/v1/paper/arXiv:2502.05171/citations` and the same for `2507.10524`) and arXiv, both read-only. Record in `runs/leg3/LIT_CHECK.md`:

- Known pitfalls with KL-based or confidence-based exit: miscalibration, KV mismatch for exited tokens, latency gains that vanish under batching.
- Whether anyone has already studied implicit routing or early exit on Dory, Ouro, or other looped models trained at a fixed depth.
- The closest prior result to each Leg 3 hypothesis. This feeds the novelty assessment in Leg 6.

Budget: about 1 hour of agent time, no GPU. If you find a paper that already does a Leg 3 experiment, say so in LIT_CHECK.md and adjust the PREREG (that is the time to change it, before results exist).
